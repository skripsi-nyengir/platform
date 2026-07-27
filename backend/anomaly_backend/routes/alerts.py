from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    AcknowledgeAlertResponse,
    AlertCommandRequest,
    AlertEvent,
    AlertEventsQuery,
    AlertEventsResponse,
    AlertStatus,
    CurrentAlert,
    CurrentAlertsQuery,
    CurrentAlertsResponse,
    DetectionBasis,
    HistoricalDateTime,
    OperationalInstant,
    ResolveAlertResponse,
    SensorId,
    current_operational_instant,
    format_historical_datetime,
    format_operational_instant,
    make_cursor,
    parse_cursor,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import InvalidQuery, new_request_id
from anomaly_backend.sql.alerts import (
    AlertAction,
    alert_event_rows,
    apply_alert_command,
    current_alert_rows,
)


router = APIRouter()
_LIFECYCLE_ACTOR = "preview-session"


def _datetime(row: RowMapping, field: str) -> HistoricalDateTime:
    return format_historical_datetime(cast(datetime, row[field]))


def _operational_datetime(row: RowMapping, field: str) -> OperationalInstant:
    return format_operational_instant(cast(datetime, row[field]))


def _optional_operational_datetime(
    row: RowMapping, field: str
) -> OperationalInstant | None:
    value = cast(datetime | None, row[field])
    return format_operational_instant(value) if value is not None else None


def _alert_event(row: RowMapping) -> AlertEvent:
    return AlertEvent(
        event_id=cast(str, row["event_id"]),
        alert_id=cast(str, row["alert_id"]),
        event_at=_operational_datetime(row, "event_at"),
        event_type=cast(AlertStatus, row["event_type"]),
        device_id=cast(SensorId, row["device_id"]),
        actor=cast(str, row["actor"]),
        note=cast(str | None, row["note"]),
        accepted_at=_optional_operational_datetime(row, "accepted_at"),
        inference_model_version=cast(str | None, row["inference_model_version"]),
        detection_basis=cast(DetectionBasis, row["detection_basis"]),
    )


async def _apply_command(
    connection: AsyncConnection,
    *,
    alert_id: str,
    action: AlertAction,
    command: AlertCommandRequest,
) -> tuple[AlertEvent, bool]:
    row, replay = await apply_alert_command(
        connection,
        command_id=command.command_id,
        alert_id=alert_id,
        action=action,
        actor=_LIFECYCLE_ACTOR,
        note=command.note,
    )
    return _alert_event(row), replay


@router.get("/api/alert-events", response_model=AlertEventsResponse)
async def alert_events(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    alert_id: Annotated[str | None, Query(min_length=1)] = None,
    device_id: Annotated[SensorId | None, Query()] = None,
    from_ts: Annotated[OperationalInstant | None, Query(alias="from")] = None,
    to_ts: Annotated[OperationalInstant | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 200,
    cursor: Annotated[str | None, Query()] = None,
) -> AlertEventsResponse:
    if from_ts is not None and to_ts is not None and from_ts >= to_ts:
        raise InvalidQuery(
            "Query parameters failed validation",
            {"from": ["from must be earlier than to"]},
        )
    query_fields: dict[str, object] = {"limit": limit}
    for name, value in (
        ("alert_id", alert_id),
        ("device_id", device_id),
        ("from", from_ts),
        ("to", to_ts),
        ("cursor", cursor),
    ):
        if value is not None:
            query_fields[name] = value
    query = AlertEventsQuery.model_validate(query_fields, strict=True)
    try:
        offset = parse_cursor(query.cursor, "alert-events") if query.cursor else 0
    except ValueError as error:
        raise InvalidQuery(
            "Query parameters failed validation",
            {"cursor": ["Invalid cursor"]},
        ) from error
    rows = await alert_event_rows(
        connection,
        alert_id=query.alert_id,
        device_id=query.device_id,
        from_ts=(
            datetime.fromisoformat(query.from_ts.replace("Z", "+00:00"))
            if query.from_ts
            else None
        ),
        to_ts=(
            datetime.fromisoformat(query.to_ts.replace("Z", "+00:00"))
            if query.to_ts
            else None
        ),
        limit=query.limit,
        offset=offset,
    )
    has_more = len(rows) > query.limit
    events = [_alert_event(row) for row in rows[: query.limit]]
    return AlertEventsResponse(
        request_id=new_request_id(),
        time_zone="Asia/Jakarta",
        events=events,
        next_cursor=(
            make_cursor("alert-events", offset + query.limit) if has_more else None
        ),
        returned_count=len(events),
    )


@router.get("/api/alerts/current", response_model=CurrentAlertsResponse)
async def current_alerts(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    device_id: Annotated[SensorId | None, Query()] = None,
    status: Annotated[AlertStatus | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 25,
) -> CurrentAlertsResponse:
    query_fields: dict[str, object] = {"page": page, "page_size": page_size}
    if device_id is not None:
        query_fields["device_id"] = device_id
    if status is not None:
        query_fields["status"] = status
    query = CurrentAlertsQuery.model_validate(query_fields, strict=True)
    total, rows = await current_alert_rows(
        connection,
        device_id=query.device_id,
        status=query.status,
        page=query.page,
        page_size=query.page_size,
    )
    items: list[CurrentAlert] = []
    for row in rows:
        projected_status = cast(AlertStatus, row["status"])
        items.append(
            CurrentAlert(
                alert_id=cast(str, row["alert_id"]),
                device_id=cast(SensorId, row["device_id"]),
                status=projected_status,
                episode_start_ts=_datetime(row, "episode_start_ts"),
                episode_end_ts=_datetime(row, "episode_end_ts"),
                last_score_ts=_datetime(row, "last_score_ts"),
                created_at=_operational_datetime(row, "created_at"),
                latest_event_at=_operational_datetime(row, "latest_event_at"),
                latest_event_id=cast(str, row["latest_event_id"]),
                peak_score=cast(float, row["peak_score"]),
                latest_score=cast(float, row["latest_score"]),
                anomalous_window_count=cast(int, row["anomalous_window_count"]),
                replay_job_id=cast(str, row["replay_job_id"]),
                threshold=cast(float, row["threshold"]),
                model_version=cast(str, row["model_version"]),
                detection_basis=cast(DetectionBasis, row["detection_basis"]),
                can_acknowledge=projected_status == "detected",
                can_resolve=projected_status == "acknowledged",
            )
        )
    return CurrentAlertsResponse(
        request_id=new_request_id(),
        time_zone="Asia/Jakarta",
        generated_at=current_operational_instant(),
        items=items,
        page=query.page,
        page_size=query.page_size,
        total=total,
    )


@router.post(
    "/api/alerts/{alert_id}/acknowledge",
    response_model=AcknowledgeAlertResponse,
)
async def acknowledge_alert(
    alert_id: str,
    command: AlertCommandRequest,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> AcknowledgeAlertResponse:
    accepted_event, replay = await _apply_command(
        connection,
        alert_id=alert_id,
        action="acknowledged",
        command=command,
    )
    return AcknowledgeAlertResponse(
        request_id=new_request_id(),
        alert_id=alert_id,
        status="acknowledged",
        event=accepted_event,
        idempotent_replay=replay,
    )


@router.post(
    "/api/alerts/{alert_id}/resolve",
    response_model=ResolveAlertResponse,
)
async def resolve_alert(
    alert_id: str,
    command: AlertCommandRequest,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> ResolveAlertResponse:
    accepted_event, replay = await _apply_command(
        connection,
        alert_id=alert_id,
        action="resolved",
        command=command,
    )
    return ResolveAlertResponse(
        request_id=new_request_id(),
        alert_id=alert_id,
        status="resolved",
        event=accepted_event,
        idempotent_replay=replay,
    )
