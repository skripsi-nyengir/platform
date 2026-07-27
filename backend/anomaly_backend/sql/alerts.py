from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Literal, cast
from uuid import uuid4

from sqlalchemy import func, select, true
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.contracts import AlertStatus, SensorId
from anomaly_backend.problems import Conflict, NotFound


AlertAction = Literal["acknowledged", "resolved"]


def _payload_hash(
    alert_id: str, action: AlertAction, note: str | None
) -> str:
    payload = json.dumps(
        {"alert_id": alert_id, "action": action, "note": note},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def alert_event_rows(
    connection: AsyncConnection,
    *,
    alert_id: str | None,
    device_id: SensorId | None,
    from_ts: datetime | None,
    to_ts: datetime | None,
    limit: int,
    offset: int,
) -> list[RowMapping]:
    events = tables.alert_events
    commands = tables.alert_commands
    statement = (
        select(
            *events.c,
            commands.c.accepted_at,
        )
        .join(
            tables.devices,
            tables.devices.c.device_id == events.c.device_id,
        )
        .outerjoin(
            commands,
            commands.c.accepted_event_id == events.c.event_id,
        )
        .where(
            tables.devices.c.is_active,
            events.c.time_domain == "utc",
        )
        .order_by(events.c.event_at.asc(), events.c.event_id.asc())
    )
    if alert_id is not None:
        statement = statement.where(events.c.alert_id == alert_id)
    if device_id is not None:
        statement = statement.where(events.c.device_id == device_id)
    if from_ts is not None:
        statement = statement.where(events.c.event_at >= from_ts)
    if to_ts is not None:
        statement = statement.where(events.c.event_at < to_ts)
    result = await connection.execute(statement.limit(limit + 1).offset(offset))
    return list(result.mappings())


async def current_alert_rows(
    connection: AsyncConnection,
    *,
    device_id: SensorId | None,
    status: AlertStatus | None,
    page: int,
    page_size: int,
) -> tuple[int, list[RowMapping]]:
    events = tables.alert_events
    ranked_events = (
        select(
            events.c.alert_id,
            events.c.event_at.label("latest_event_at"),
            events.c.event_id.label("latest_event_id"),
            events.c.event_type.label("status"),
            func.row_number()
            .over(
                partition_by=events.c.alert_id,
                order_by=(events.c.event_at.desc(), events.c.event_id.desc()),
            )
            .label("event_position"),
        )
        .where(events.c.time_domain == "utc")
        .cte("ranked_alert_events")
    )
    alerts = tables.alerts
    statement = (
        select(
            alerts.c.alert_id,
            alerts.c.device_id,
            alerts.c.episode_start_ts,
            alerts.c.episode_end_ts,
            alerts.c.last_score_ts,
            alerts.c.created_at,
            alerts.c.peak_score,
            alerts.c.latest_score,
            alerts.c.anomalous_window_count,
            alerts.c.replay_job_id,
            alerts.c.threshold,
            alerts.c.model_version,
            alerts.c.detection_basis,
            ranked_events.c.latest_event_at,
            ranked_events.c.latest_event_id,
            ranked_events.c.status,
        )
        .join(
            ranked_events,
            (ranked_events.c.alert_id == alerts.c.alert_id)
            & (ranked_events.c.event_position == 1),
        )
        .join(
            tables.devices,
            tables.devices.c.device_id == alerts.c.device_id,
        )
        .where(
            tables.devices.c.is_active,
            alerts.c.detection_basis.in_(
                ("simulated_preview", "artifact_backed")
            ),
        )
    )
    if device_id is not None:
        statement = statement.where(alerts.c.device_id == device_id)
    if status is not None:
        statement = statement.where(ranked_events.c.status == status)

    projection = statement.cte("current_alert_projection")
    page_rows = (
        select(*projection.c)
        .order_by(
            projection.c.episode_end_ts.desc(),
            projection.c.alert_id.asc(),
        )
        .limit(page_size)
        .offset((page - 1) * page_size)
        .cte("current_alert_page")
    )
    total_row = (
        select(func.count().label("total"))
        .select_from(projection)
        .cte("current_alert_total")
    )
    result = await connection.execute(
        select(total_row.c.total, *page_rows.c)
        .select_from(total_row.outerjoin(page_rows, true()))
        .order_by(
            page_rows.c.episode_end_ts.desc(),
            page_rows.c.alert_id.asc(),
        )
    )
    rows = list(result.mappings())
    total = int(rows[0]["total"]) if rows else 0
    return total, [row for row in rows if row["alert_id"] is not None]


async def apply_alert_command(
    connection: AsyncConnection,
    *,
    command_id: str,
    alert_id: str,
    action: AlertAction,
    actor: str,
    note: str | None,
) -> tuple[RowMapping, bool]:
    commands = tables.alert_commands
    events = tables.alert_events
    payload_hash = _payload_hash(alert_id, action, note)
    async with connection.begin():
        alert = (
            await connection.execute(
                select(
                    tables.alerts.c.alert_id,
                    tables.alerts.c.device_id,
                    tables.alerts.c.model_version,
                    tables.alerts.c.inference_result_window_start_ts,
                    tables.alerts.c.inference_result_window_end_ts,
                    tables.alerts.c.detection_basis,
                )
                .join(
                    tables.devices,
                    tables.devices.c.device_id == tables.alerts.c.device_id,
                )
                .where(
                    tables.alerts.c.alert_id == alert_id,
                    tables.devices.c.is_active,
                    tables.alerts.c.detection_basis.in_(
                        ("simulated_preview", "artifact_backed")
                    ),
                )
                .with_for_update()
            )
        ).mappings().one_or_none()
        if alert is None:
            raise NotFound("Alert not found")

        existing = (
            await connection.execute(
                select(
                    commands.c.alert_id.label("command_alert_id"),
                    commands.c.action.label("command_action"),
                    commands.c.note.label("command_note"),
                    commands.c.payload_hash.label("command_payload_hash"),
                    commands.c.accepted_at,
                    *events.c,
                )
                .join(
                    events,
                    commands.c.accepted_event_id == events.c.event_id,
                )
                .where(commands.c.command_id == command_id)
            )
        ).mappings().one_or_none()
        if existing is not None:
            if (
                existing["command_alert_id"] != alert_id
                or existing["command_action"] != action
                or existing["command_note"] != note
                or existing["command_payload_hash"] != payload_hash
                or existing["event_type"] != action
            ):
                raise Conflict("Command ID conflicts with persisted state")
            return existing, True

        latest = (
            await connection.execute(
                select(
                    events.c.event_at,
                    events.c.event_id,
                    events.c.event_type,
                )
                .where(
                    events.c.alert_id == alert_id,
                    events.c.time_domain == "utc",
                )
                .order_by(events.c.event_at.desc(), events.c.event_id.desc())
                .limit(1)
            )
        ).mappings().one_or_none()
        required_status = (
            "detected" if action == "acknowledged" else "acknowledged"
        )
        if latest is None or latest["event_type"] != required_status:
            raise Conflict(
                "Alert lifecycle transition conflicts with persisted state"
            )

        accepted_at = datetime.now(timezone.utc)
        event_id = uuid4().hex
        accepted = (
            await connection.execute(
                events.insert()
                .values(
                    event_id=event_id,
                    alert_id=alert_id,
                    event_ts=None,
                    event_at=accepted_at,
                    time_domain="utc",
                    event_type=action,
                    device_id=alert["device_id"],
                    actor=actor,
                    note=note,
                    inference_result_window_start_ts=alert[
                        "inference_result_window_start_ts"
                    ],
                    inference_result_window_end_ts=alert[
                        "inference_result_window_end_ts"
                    ],
                    inference_model_version=alert["model_version"],
                    detection_basis=alert["detection_basis"],
                )
                .returning(*events.c)
            )
        ).mappings().one()
        await connection.execute(
            commands.insert().values(
                command_id=command_id,
                alert_id=alert_id,
                action=action,
                event_ts=None,
                accepted_at=accepted_at,
                time_domain="utc",
                payload_hash=payload_hash,
                note=note,
                accepted_event_id=event_id,
            )
        )
        return cast(
            RowMapping,
            {
                **dict(accepted),
                "accepted_at": accepted_at,
            },
        ), False
