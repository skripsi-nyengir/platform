"""Slack alert notifier.

Runs beside the live pipeline and never inside it. The ingest path holds a fencing
token and a writer lease; a slow outbound request there would stall telemetry. This
service therefore reads only what the pipeline has already committed, which costs at
most one poll interval of delay and cannot hold anything up.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import logging
import signal
from types import FrameType

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.slack import Attachment, SlackClient, SlackError
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
from anomaly_backend.sql.slack_settings import read_slack_settings
from anomaly_worker.notifier_charts import (
    EmptyChartError,
    chart_window,
    score_chart,
    telemetry_chart,
)


logger = logging.getLogger("anomaly_worker.notifier")

_HEADLINE = {
    "opened": ":rotating_light: Anomaly episode opened",
    "escalated": ":bangbang: Anomaly episode escalated to critical",
    "closed": ":white_check_mark: Anomaly episode closed",
}


@dataclass(frozen=True, slots=True)
class RenderedNotification:
    comment: str
    attachments: list[Attachment]


def _format_span(context: EpisodeContext) -> str:
    started = context.started_score_ts.strftime("%Y-%m-%d %H:%M:%S")
    if context.ended_score_ts is None:
        return f"{started} UTC, still open"
    duration = context.ended_score_ts - context.started_score_ts
    ended = context.ended_score_ts.strftime("%H:%M:%S")
    return f"{started} to {ended} UTC ({int(duration.total_seconds())} s)"


def compose_comment(kind: str, context: EpisodeContext) -> str:
    """The message body. Values only, so it never reads as a physical diagnosis."""
    lines = [
        f"*{_HEADLINE.get(kind, 'Anomaly episode update')}*",
        f"• Device: `{context.device_id}`",
        f"• Model: `{context.model_version}`",
        f"• Window: {_format_span(context)}",
        f"• Peak score: {context.peak_score:.6e} (threshold {context.threshold:.6e})",
        f"• Anomalous windows: {context.anomalous_window_count}",
        f"• Highest severity: {context.max_severity}",
    ]
    if kind == "closed" and context.close_reason is not None:
        lines.append(f"• Close reason: `{context.close_reason}`")
    return "\n".join(lines)


async def render(
    engine: AsyncEngine,
    notification: PendingNotification,
    *,
    settings: Settings,
) -> RenderedNotification | None:
    """Build the message and both charts, or None when the episode has vanished."""
    async with engine.connect() as connection:
        context = await episode_context(connection, notification.live_episode_id)
        if context is None:
            return None
        fallback_end = datetime.now(timezone.utc).replace(tzinfo=None)
        window_start, window_end = chart_window(
            context.started_score_ts,
            context.ended_score_ts,
            margin_minutes=settings.notifier_chart_margin_minutes,
            fallback_end=fallback_end,
        )
        scores = await score_points(
            connection,
            device_id=context.device_id,
            window_start=window_start,
            window_end=window_end,
        )
        telemetry = await telemetry_points(
            connection,
            device_id=context.device_id,
            window_start=window_start,
            window_end=window_end,
        )

    attachments = [
        Attachment(
            filename="reconstruction-error.png",
            title="Reconstruction error against threshold",
            content=score_chart(
                scores,
                started_score_ts=context.started_score_ts,
                ended_score_ts=context.ended_score_ts,
                window_end=window_end,
            ),
        ),
        Attachment(
            filename="telemetry.png",
            title="Temperature and relative humidity",
            content=telemetry_chart(
                telemetry,
                started_score_ts=context.started_score_ts,
                ended_score_ts=context.ended_score_ts,
                window_end=window_end,
            ),
        ),
    ]
    return RenderedNotification(
        comment=compose_comment(notification.kind, context),
        attachments=attachments,
    )


async def deliver_once(engine: AsyncEngine, settings: Settings) -> int:
    """One cycle: top up the outbox, then send whatever is claimable."""
    async with engine.connect() as connection:
        slack_settings = await read_slack_settings(connection)
        if not slack_settings.enabled:
            return 0
        _ = await enqueue_missing(
            connection,
            max_episode_age_minutes=settings.notifier_max_episode_age_minutes,
        )
        claimed = await claim_pending(
            connection,
            lease_seconds=settings.notifier_lease_seconds,
            limit=5,
        )
    if not claimed:
        return 0

    sent = 0
    # The database constraint makes these non-null whenever enabled. Keeping the
    # assertion next to use makes that invariant visible to the type checker too.
    assert slack_settings.bot_token is not None
    assert slack_settings.channel_id is not None
    async with SlackClient(slack_settings.bot_token) as slack:
        for notification in claimed:
            try:
                rendered = await render(engine, notification, settings=settings)
                if rendered is None:
                    raise SlackError("episode no longer exists")
                await slack.post_charts(
                    channel_id=slack_settings.channel_id,
                    initial_comment=rendered.comment,
                    attachments=rendered.attachments,
                )
            except (SlackError, EmptyChartError, SQLAlchemyError, OSError) as error:
                logger.warning(
                    "notification %s (%s) failed: %s",
                    notification.notification_id,
                    notification.kind,
                    error,
                )
                async with engine.connect() as connection:
                    await mark_failed(
                        connection,
                        notification.notification_id,
                        error=f"{type(error).__name__}: {error}",
                        max_attempts=settings.notifier_max_attempts,
                    )
                continue
            async with engine.connect() as connection:
                await mark_sent(connection, notification.notification_id)
            sent += 1
    return sent


async def run(settings: Settings, *, stop: asyncio.Event) -> None:
    engine = create_database_engine(settings)
    try:
        while not stop.is_set():
            try:
                sent = await deliver_once(engine, settings)
                if sent:
                    logger.info("delivered %s notification(s)", sent)
            except SQLAlchemyError as error:
                # The database is the notifier's only hard dependency; keep the loop
                # alive so it recovers on its own once the database returns.
                logger.warning("notifier cycle failed: %s", error)
            try:
                await asyncio.wait_for(
                    stop.wait(), timeout=settings.notifier_poll_seconds
                )
            except TimeoutError:
                continue
    finally:
        await engine.dispose()


def main() -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s"
    )
    settings = Settings.from_environ()

    stop = asyncio.Event()

    def request_stop(signal_number: int, frame: FrameType | None) -> None:
        _ = signal_number, frame
        stop.set()

    for received in (signal.SIGTERM, signal.SIGINT):
        _ = signal.signal(received, request_stop)

    asyncio.run(run(settings, stop=stop))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
