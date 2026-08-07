"""Outbox queries for Slack alert delivery.

The outbox is filled from stored episode state rather than from events, so the live
ingest path never has to know a notifier exists. Every statement here is safe to run
repeatedly: the unique (live_episode_id, kind) turns re-enqueueing into a no-op.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, case, exists, func, literal, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.elements import ColumnElement

from anomaly_backend import tables


NotificationKind = Literal["opened", "escalated", "closed"]
KINDS: tuple[NotificationKind, ...] = ("opened", "escalated", "closed")


@dataclass(frozen=True, slots=True)
class PendingNotification:
    notification_id: UUID
    live_episode_id: UUID
    kind: NotificationKind
    attempts: int


@dataclass(frozen=True, slots=True)
class EpisodeContext:
    live_episode_id: UUID
    device_id: str
    model_version: str
    status: str
    close_reason: str | None
    started_score_ts: datetime
    ended_score_ts: datetime | None
    peak_score: float
    latest_score: float
    threshold: float
    anomalous_window_count: int
    max_severity: str


@dataclass(frozen=True, slots=True)
class ScorePoint:
    score_ts: datetime
    score: float
    threshold: float


@dataclass(frozen=True, slots=True)
class TelemetryPoint:
    received_ts: datetime
    temperature_c: float
    relative_humidity_pct: float


def _naive_utc_now():
    # The live tables store score timestamps as naive UTC, so the cutoff has to be
    # computed in the same domain rather than against an aware value.
    return func.timezone(literal("UTC"), func.clock_timestamp())


def _critical_point_exists():
    points = tables.live_alert_episode_points
    inference = tables.live_inference
    return exists(
        select(literal(1))
        .select_from(
            points.join(
                inference,
                and_(
                    inference.c.score_ts == points.c.score_ts,
                    inference.c.inference_id == points.c.inference_id,
                ),
            )
        )
        .where(
            points.c.live_episode_id == tables.live_alert_episodes.c.live_episode_id,
            inference.c.severity_at_score == "critical",
        )
    )


async def enqueue_missing(
    connection: AsyncConnection, *, max_episode_age_minutes: int
) -> int:
    """Queue any notification the stored episode state implies but has not produced.

    The age cutoff is what keeps a first start, or a restart after downtime, from
    flooding the channel with every episode the platform has ever recorded.
    """
    episodes = tables.live_alert_episodes
    cutoff = _naive_utc_now() - func.make_interval(0, 0, 0, 0, 0, max_episode_age_minutes)
    recent = episodes.c.started_score_ts > cutoff
    conditions: dict[NotificationKind, ColumnElement[bool]] = {
        "opened": recent,
        "closed": and_(recent, episodes.c.status == "closed"),
        "escalated": and_(recent, _critical_point_exists()),
    }

    queued = 0
    for kind, condition in conditions.items():
        source = select(
            episodes.c.live_episode_id,
            literal(kind),
            literal("pending"),
            func.now(),
        ).where(condition)
        statement = (
            insert(tables.alert_notifications)
            .from_select(
                ["live_episode_id", "kind", "status", "created_at"],
                source,
            )
            .on_conflict_do_nothing(constraint="uq_alert_notifications_episode_kind")
        )
        result = await connection.execute(statement)
        queued += result.rowcount if result.rowcount and result.rowcount > 0 else 0
    await connection.commit()
    return queued


async def claim_pending(
    connection: AsyncConnection, *, lease_seconds: int, limit: int
) -> list[PendingNotification]:
    """Take ownership of pending rows whose lease has lapsed.

    ``attempts`` increments on claim rather than on failure, so a worker that dies
    mid-send still burns an attempt and a poisoned row cannot retry forever.
    """
    notifications = tables.alert_notifications
    lease = func.make_interval(0, 0, 0, 0, 0, 0, lease_seconds)
    claimable = (
        select(notifications.c.notification_id)
        .where(
            notifications.c.status == "pending",
            (notifications.c.lease_expires_at.is_(None))
            | (notifications.c.lease_expires_at < func.now()),
        )
        .order_by(notifications.c.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    statement = (
        update(notifications)
        .where(notifications.c.notification_id.in_(claimable))
        .values(
            lease_expires_at=func.now() + lease,
            attempts=notifications.c.attempts + 1,
        )
        .returning(
            notifications.c.notification_id,
            notifications.c.live_episode_id,
            notifications.c.kind,
            notifications.c.attempts,
        )
    )
    rows = (await connection.execute(statement)).mappings().all()
    await connection.commit()
    return [
        PendingNotification(
            notification_id=row["notification_id"],
            live_episode_id=row["live_episode_id"],
            kind=cast(NotificationKind, row["kind"]),
            attempts=row["attempts"],
        )
        for row in rows
    ]


async def mark_sent(connection: AsyncConnection, notification_id: UUID) -> None:
    _ = await connection.execute(
        update(tables.alert_notifications)
        .where(tables.alert_notifications.c.notification_id == notification_id)
        .values(
            status="sent",
            sent_at=func.now(),
            lease_expires_at=None,
            last_error=None,
        )
    )
    await connection.commit()


async def mark_failed(
    connection: AsyncConnection,
    notification_id: UUID,
    *,
    error: str,
    max_attempts: int,
) -> None:
    """Release the row for another attempt, or retire it once the budget is spent."""
    notifications = tables.alert_notifications
    _ = await connection.execute(
        update(notifications)
        .where(notifications.c.notification_id == notification_id)
        .values(
            status=case(
                (notifications.c.attempts >= max_attempts, "failed"),
                else_="pending",
            ),
            lease_expires_at=None,
            last_error=error[:1000],
        )
    )
    await connection.commit()


async def episode_context(
    connection: AsyncConnection, live_episode_id: UUID
) -> EpisodeContext | None:
    episodes = tables.live_alert_episodes
    alerts = tables.alerts
    points = tables.live_alert_episode_points
    inference = tables.live_inference
    severity_rank = func.max(
        case(
            (inference.c.severity_at_score == "critical", 2),
            (inference.c.severity_at_score == "warning", 1),
            else_=0,
        )
    )
    row = (
        (
            await connection.execute(
                select(
                    episodes.c.live_episode_id,
                    episodes.c.device_id,
                    episodes.c.model_version,
                    episodes.c.status,
                    episodes.c.close_reason,
                    episodes.c.started_score_ts,
                    episodes.c.ended_score_ts,
                    alerts.c.peak_score,
                    alerts.c.latest_score,
                    alerts.c.threshold,
                    alerts.c.anomalous_window_count,
                    severity_rank.label("severity_rank"),
                )
                .select_from(
                    episodes.join(alerts, alerts.c.alert_id == episodes.c.alert_id)
                    .outerjoin(
                        points, points.c.live_episode_id == episodes.c.live_episode_id
                    )
                    .outerjoin(
                        inference,
                        and_(
                            inference.c.score_ts == points.c.score_ts,
                            inference.c.inference_id == points.c.inference_id,
                        ),
                    )
                )
                .where(episodes.c.live_episode_id == live_episode_id)
                .group_by(
                    episodes.c.live_episode_id,
                    episodes.c.device_id,
                    episodes.c.model_version,
                    episodes.c.status,
                    episodes.c.close_reason,
                    episodes.c.started_score_ts,
                    episodes.c.ended_score_ts,
                    alerts.c.peak_score,
                    alerts.c.latest_score,
                    alerts.c.threshold,
                    alerts.c.anomalous_window_count,
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    ranks = {2: "critical", 1: "warning", 0: "info"}
    return EpisodeContext(
        live_episode_id=row["live_episode_id"],
        device_id=row["device_id"],
        model_version=row["model_version"],
        status=row["status"],
        close_reason=row["close_reason"],
        started_score_ts=row["started_score_ts"],
        ended_score_ts=row["ended_score_ts"],
        peak_score=row["peak_score"],
        latest_score=row["latest_score"],
        threshold=row["threshold"],
        anomalous_window_count=row["anomalous_window_count"],
        max_severity=ranks.get(row["severity_rank"] or 0, "info"),
    )


async def score_points(
    connection: AsyncConnection,
    *,
    device_id: str,
    window_start: datetime,
    window_end: datetime,
) -> list[ScorePoint]:
    inference = tables.live_inference
    rows = (
        (
            await connection.execute(
                select(
                    inference.c.score_ts,
                    inference.c.score,
                    inference.c.threshold,
                )
                .where(
                    inference.c.device_id == device_id,
                    inference.c.score_ts >= window_start,
                    inference.c.score_ts <= window_end,
                )
                .order_by(inference.c.score_ts)
            )
        )
        .mappings()
        .all()
    )
    return [
        ScorePoint(
            score_ts=row["score_ts"],
            score=row["score"],
            threshold=row["threshold"],
        )
        for row in rows
    ]


async def telemetry_points(
    connection: AsyncConnection,
    *,
    device_id: str,
    window_start: datetime,
    window_end: datetime,
) -> list[TelemetryPoint]:
    telemetry = tables.live_telemetry
    rows = (
        (
            await connection.execute(
                select(
                    telemetry.c.received_ts,
                    telemetry.c.temperature_c,
                    telemetry.c.relative_humidity_pct,
                )
                .where(
                    telemetry.c.device_id == device_id,
                    telemetry.c.received_ts >= window_start,
                    telemetry.c.received_ts <= window_end,
                )
                .order_by(telemetry.c.received_ts)
            )
        )
        .mappings()
        .all()
    )
    return [
        TelemetryPoint(
            received_ts=row["received_ts"],
            temperature_c=row["temperature_c"],
            relative_humidity_pct=row["relative_humidity_pct"],
        )
        for row in rows
    ]
