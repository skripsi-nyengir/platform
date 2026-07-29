from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    CorpusDeviceId,
    InjectionEventsResponse,
    InjectionFamily,
    InjectionSeverity,
    SimInjectionEvent,
    format_historical_datetime,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import new_request_id
from anomaly_backend.sql import injection_event_rows


router = APIRouter()

_SIM_DEVICE_ID: CorpusDeviceId = "b02f3872-simulasi-injeksi"


@router.get("/api/injection-events", response_model=InjectionEventsResponse)
async def injection_events(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    device_id: Annotated[CorpusDeviceId, Query()] = _SIM_DEVICE_ID,
) -> InjectionEventsResponse:
    rows = await injection_event_rows(connection, device_id)
    events = [_event(row) for row in rows]
    return InjectionEventsResponse(
        request_id=new_request_id(),
        device_id=device_id,
        time_zone="Asia/Jakarta",
        events=events,
        returned_count=len(events),
    )


def _event(row: RowMapping) -> SimInjectionEvent:
    return SimInjectionEvent(
        event_id=cast(str, row["event_id"]),
        family=cast(InjectionFamily, row["family"]),
        severity=cast(InjectionSeverity, row["severity"]),
        channel=cast(str, row["channel"]),
        channel_index=cast(int, row["channel_index"]),
        start_ts=format_historical_datetime(cast(datetime, row["start_ts"])),
        end_ts=format_historical_datetime(cast(datetime, row["end_ts"])),
        start_idx=cast(int, row["start_idx"]),
        end_idx_exclusive=cast(int, row["end_idx_exclusive"]),
        segment_index=cast(int, row["segment_index"]),
    )
