from datetime import datetime, timedelta
import os
from typing import Any, cast
from unittest.mock import patch
from uuid import UUID

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.sql.notifications import (
    EpisodeContext,
    PendingNotification,
    claim_pending,
    enqueue_missing,
    episode_context,
    mark_failed,
    mark_sent,
    score_points,
    telemetry_points,
)
from anomaly_worker.notifier_service import compose_comment, render

# The live lineage an episode needs (device, corpus, model pair, activation, alert,
# points) is already assembled by the live API fixture. Reusing it keeps this module
# about notification behaviour instead of a second copy of that setup.
from test_live_api import live_api_fixture  # noqa: F401


DATABASE_ENV = {
    "POSTGRES_HOST": "db",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "anomaly_detection",
    "POSTGRES_USER": "anomaly",
    "POSTGRES_PASSWORD": "anomaly-dev-only",
}
# Wide enough that the fixture's historical episode is always inside the window; the
# cutoff itself gets its own test.
FOREVER = 60 * 24 * 365 * 100


async def _episode_inference_ids(
    connection: AsyncConnection, episode_id: UUID
) -> list[UUID]:
    rows = await connection.scalars(
        select(tables.live_alert_episode_points.c.inference_id).where(
            tables.live_alert_episode_points.c.live_episode_id == episode_id
        )
    )
    return list(rows)


async def _severities(connection: AsyncConnection, episode_id: UUID) -> set[str]:
    """Severities recorded for an episode's points.

    live_inference is append-only, enforced by the live_reject_mutation trigger, so a
    test reads the severities the fixture produced rather than setting them.
    """
    rows = await connection.scalars(
        select(tables.live_inference.c.severity_at_score)
        .select_from(
            tables.live_alert_episode_points.join(
                tables.live_inference,
                (
                    tables.live_inference.c.score_ts
                    == tables.live_alert_episode_points.c.score_ts
                )
                & (
                    tables.live_inference.c.inference_id
                    == tables.live_alert_episode_points.c.inference_id
                ),
            )
        )
        .where(tables.live_alert_episode_points.c.live_episode_id == episode_id)
    )
    return set(rows)


async def _escalation_candidates(connection: AsyncConnection) -> int:
    """Episodes that genuinely hold a critical point, counted independently."""
    return cast(
        int,
        await connection.scalar(
            select(
                func.count(func.distinct(tables.live_alert_episode_points.c.live_episode_id))
            )
            .select_from(
                tables.live_alert_episode_points.join(
                    tables.live_inference,
                    (
                        tables.live_inference.c.score_ts
                        == tables.live_alert_episode_points.c.score_ts
                    )
                    & (
                        tables.live_inference.c.inference_id
                        == tables.live_alert_episode_points.c.inference_id
                    ),
                )
            )
            .where(tables.live_inference.c.severity_at_score == "critical")
        ),
    )


async def _kinds(connection: AsyncConnection, episode_id: UUID) -> list[str]:
    rows = await connection.scalars(
        select(tables.alert_notifications.c.kind).where(
            tables.alert_notifications.c.live_episode_id == episode_id
        )
    )
    return sorted(rows)


async def _row(
    connection: AsyncConnection, episode_id: UUID, kind: str
) -> dict[str, Any]:
    return dict(
        (
            await connection.execute(
                select(tables.alert_notifications).where(
                    tables.alert_notifications.c.live_episode_id == episode_id,
                    tables.alert_notifications.c.kind == kind,
                )
            )
        )
        .mappings()
        .one()
    )


async def _claim_for(
    connection: AsyncConnection, episode_id: UUID, kind: str
) -> PendingNotification | None:
    # Other modules' fixtures may leave episodes behind, so a claim is filtered down
    # to the row this test actually owns.
    claimed = await claim_pending(connection, lease_seconds=120, limit=50)
    for item in claimed:
        if item.live_episode_id == episode_id and item.kind == kind:
            return item
    return None


@pytest.fixture
async def episode(live_api_fixture: dict[str, object]):  # noqa: F811
    """A seeded episode with an empty outbox."""
    episode_id = cast(UUID, live_api_fixture["live_episode_id"])
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            inference_ids = await _episode_inference_ids(connection, episode_id)
            _ = await connection.execute(delete(tables.alert_notifications))
            await connection.commit()
            yield connection, episode_id, inference_ids
            _ = await connection.execute(delete(tables.alert_notifications))
            await connection.commit()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_an_open_episode_queues_exactly_one_opened_notification(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode

    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)
    first = await _kinds(connection, episode_id)
    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)
    second = await _kinds(connection, episode_id)

    assert "opened" in first
    assert len(first) == len(set(first))
    # Repeating the cycle must not duplicate anything; the unique constraint is what
    # makes the whole loop safe to run again.
    assert second == first


@pytest.mark.anyio
async def test_an_old_episode_is_never_notified(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode

    _ = await enqueue_missing(connection, max_episode_age_minutes=60)

    # Without this cutoff a first start would post every episode ever recorded.
    assert await _kinds(connection, episode_id) == []


@pytest.mark.anyio
async def test_only_closed_episodes_get_a_closed_notification(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode
    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)

    status = await connection.scalar(
        select(tables.live_alert_episodes.c.status).where(
            tables.live_alert_episodes.c.live_episode_id == episode_id
        )
    )
    closed_rows = cast(
        int,
        await connection.scalar(
            select(func.count()).where(tables.alert_notifications.c.kind == "closed")
        ),
    )
    closed_episodes = cast(
        int,
        await connection.scalar(
            select(func.count()).where(
                tables.live_alert_episodes.c.status == "closed"
            )
        ),
    )

    # Episode status is guarded by live_guard_episode_update, so rather than forcing
    # a transition this checks the predicate against the real population.
    assert status == "open"
    assert "closed" not in await _kinds(connection, episode_id)
    assert closed_rows == closed_episodes


@pytest.mark.anyio
async def test_escalation_follows_the_points_and_is_queued_once(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode
    severities = await _severities(connection, episode_id)
    # Stated rather than assumed: the assertion below only means something because
    # this episode really does hold a critical point.
    assert "critical" in severities

    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)
    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)

    # Escalation is derived from the points rather than stored on the episode, and
    # the unique constraint is what keeps it to a single message.
    assert await _kinds(connection, episode_id) == ["escalated", "opened"]


@pytest.mark.anyio
async def test_only_episodes_holding_a_critical_point_are_escalated(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, _, _ = episode
    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)

    escalated = cast(
        int,
        await connection.scalar(
            select(func.count()).where(
                tables.alert_notifications.c.kind == "escalated"
            )
        ),
    )

    # Counted independently of the enqueue statement, so the predicate cannot be
    # over- or under-inclusive without this failing.
    assert escalated == await _escalation_candidates(connection)


@pytest.mark.anyio
async def test_claiming_burns_an_attempt_and_hides_the_row_from_a_second_claim(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode
    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)

    claimed = await _claim_for(connection, episode_id, "opened")
    again = await _claim_for(connection, episode_id, "opened")

    assert claimed is not None
    assert claimed.attempts == 1
    # A worker that dies mid-send still burns the attempt, so a poisoned row cannot
    # retry forever, and a second worker cannot pick up a leased row.
    assert again is None
    assert (await _row(connection, episode_id, "opened"))["status"] == "pending"


@pytest.mark.anyio
async def test_marking_sent_records_the_time_and_clears_the_lease(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode
    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)
    claimed = await _claim_for(connection, episode_id, "opened")
    assert claimed is not None

    await mark_sent(connection, claimed.notification_id)

    row = await _row(connection, episode_id, "opened")
    assert row["status"] == "sent"
    assert row["sent_at"] is not None
    assert row["lease_expires_at"] is None

    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)
    # A sent notification is never queued or sent a second time.
    assert (await _row(connection, episode_id, "opened"))["status"] == "sent"


@pytest.mark.anyio
async def test_failures_retry_until_the_budget_runs_out(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode
    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)

    statuses: list[str] = []
    for _attempt in range(3):
        claimed = await _claim_for(connection, episode_id, "opened")
        assert claimed is not None
        await mark_failed(
            connection,
            claimed.notification_id,
            error="SlackError: channel_not_found",
            max_attempts=3,
        )
        statuses.append((await _row(connection, episode_id, "opened"))["status"])

    assert statuses == ["pending", "pending", "failed"]
    row = await _row(connection, episode_id, "opened")
    assert row["attempts"] == 3
    assert "channel_not_found" in row["last_error"]
    # A retired row stays for inspection rather than vanishing.
    assert row["sent_at"] is None


@pytest.mark.anyio
async def test_a_retired_row_is_not_queued_again(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode
    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)
    claimed = await _claim_for(connection, episode_id, "opened")
    assert claimed is not None
    await mark_failed(
        connection, claimed.notification_id, error="gone", max_attempts=1
    )

    _ = await enqueue_missing(connection, max_episode_age_minutes=FOREVER)

    assert (await _row(connection, episode_id, "opened"))["status"] == "failed"


@pytest.mark.anyio
async def test_episode_context_and_chart_data_come_back_together(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode

    context = await episode_context(connection, episode_id)
    assert context is not None
    assert context.device_id == "b02f3872-ruang-produksi"
    assert context.max_severity == "critical"
    assert context.threshold > 0
    assert context.latest_point_score_ts is not None
    assert context.latest_point_score_ts >= context.started_score_ts

    wide_start = context.started_score_ts.replace(year=2000)
    wide_end = context.started_score_ts.replace(year=2100)
    scores = await score_points(
        connection,
        device_id=context.device_id,
        window_start=wide_start,
        window_end=wide_end,
    )
    telemetry = await telemetry_points(
        connection,
        device_id=context.device_id,
        window_start=wide_start,
        window_end=wide_end,
    )
    assert scores and telemetry


@pytest.mark.anyio
async def test_open_episode_render_uses_event_time_when_host_clock_is_behind(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, episode_id, _ = episode
    context = await episode_context(connection, episode_id)
    assert context is not None
    assert context.ended_score_ts is None

    class HostClockBehindEventTime:
        @classmethod
        def now(cls, timezone_info=None):
            event_time = context.started_score_ts - timedelta(hours=7)
            return event_time.replace(tzinfo=timezone_info)

    notification = PendingNotification(
        notification_id=UUID(int=1),
        live_episode_id=episode_id,
        kind="opened",
        attempts=1,
    )
    with patch(
        "anomaly_worker.notifier_service.datetime", HostClockBehindEventTime
    ):
        rendered = await render(
            connection.engine,
            notification,
            settings=Settings.from_environ(),
        )

    assert rendered is not None
    assert [attachment.filename for attachment in rendered.attachments] == [
        "reconstruction-error.png",
        "telemetry.png",
    ]


@pytest.mark.anyio
async def test_a_missing_episode_yields_no_context(
    episode: tuple[AsyncConnection, UUID, list[UUID]],
) -> None:
    connection, _, _ = episode

    assert await episode_context(connection, UUID(int=0)) is None


def test_the_message_states_values_without_diagnosing() -> None:
    context = EpisodeContext(
        live_episode_id=UUID(int=1),
        device_id="b02f3872-ruang-produksi",
        model_version="artifact-transformer-ae-v3",
        status="closed",
        close_reason="normal",
        started_score_ts=datetime(2026, 8, 8, 1, 0, 0),
        ended_score_ts=datetime(2026, 8, 8, 1, 5, 0),
        latest_point_score_ts=datetime(2026, 8, 8, 1, 5, 0),
        peak_score=5.5e-4,
        latest_score=1.2e-4,
        threshold=2.657e-4,
        anomalous_window_count=92,
        max_severity="critical",
    )

    message = compose_comment("closed", context)

    assert "b02f3872-ruang-produksi" in message
    assert "artifact-transformer-ae-v3" in message
    assert "300 s" in message
    assert "92" in message
    assert "normal" in message
    # The platform reports measurements; it never states a physical cause.
    for forbidden in ("caused", "failure of", "broken", "diagnosis"):
        assert forbidden not in message.lower()


def test_an_open_episode_message_says_so_instead_of_inventing_an_end() -> None:
    context = EpisodeContext(
        live_episode_id=UUID(int=1),
        device_id="b02f3872-ruang-produksi",
        model_version="artifact-transformer-ae-v3",
        status="open",
        close_reason=None,
        started_score_ts=datetime(2026, 8, 8, 1, 0, 0),
        ended_score_ts=None,
        latest_point_score_ts=datetime(2026, 8, 8, 1, 4, 0),
        peak_score=5.5e-4,
        latest_score=5.5e-4,
        threshold=2.657e-4,
        anomalous_window_count=12,
        max_severity="warning",
    )

    assert "still open" in compose_comment("opened", context)


def test_notifier_tuning_defaults_are_sane() -> None:
    with patch.dict(os.environ, DATABASE_ENV, clear=True):
        settings = Settings.from_environ()

    assert settings.notifier_poll_seconds == 15
    assert settings.notifier_max_attempts == 5
    assert settings.notifier_max_episode_age_minutes == 60
    # The lease has to outlast a poll or one row could be claimed twice.
    assert settings.notifier_lease_seconds > settings.notifier_poll_seconds


def test_a_lease_shorter_than_the_poll_interval_is_refused() -> None:
    overrides = {"NOTIFIER_POLL_SECONDS": "120", "NOTIFIER_LEASE_SECONDS": "60"}
    with patch.dict(os.environ, {**DATABASE_ENV, **overrides}, clear=True):
        with pytest.raises(ValueError, match="lease"):
            _ = Settings.from_environ()


def test_the_live_ingest_path_does_not_import_the_notifier() -> None:
    """The promise that notifications cannot stall telemetry, enforced.

    Any import here would allow a Slack call from inside the fencing-token loop,
    which is exactly what this design avoids.
    """
    from pathlib import Path

    source = Path("anomaly_worker/live_service.py").read_text(encoding="utf-8")
    for forbidden in ("notifier_service", "slack_client", "notifier_charts", "httpx"):
        assert forbidden not in source
