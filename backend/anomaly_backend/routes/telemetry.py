from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    Bucket,
    CorpusDeviceId,
    HistoricalDateTime,
    LatestTelemetryResponse,
    LatestTelemetrySensor,
    SensorId,
    TelemetryHistoryQuery,
    TelemetryHistoryResponse,
    TelemetryPoint,
    effective_bucket_seconds,
    format_historical_datetime,
    current_operational_instant,
    make_keyset_cursor,
    parse_keyset_cursor,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import InvalidQuery, new_request_id
from anomaly_backend.sql import history_rows, latest_rows


router = APIRouter()


def _datetime(row: RowMapping, field: str) -> datetime:
    return cast(datetime, row[field])


@router.get("/api/telemetry/latest", response_model=LatestTelemetryResponse)
async def latest_telemetry(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    device_id: Annotated[SensorId | None, Query()] = None,
) -> LatestTelemetryResponse:
    reference, rows = await latest_rows(connection, device_id)
    if reference is None:
        return LatestTelemetryResponse(
            request_id=new_request_id(),
            generated_at=current_operational_instant(),
            time_zone="Asia/Jakarta",
            sensors=[
                LatestTelemetrySensor(
                    device_id=device_id or "b02f3872-ruang-produksi",
                    ts=None,
                    temperature_c=None,
                    relative_humidity_pct=None,
                    freshness="unknown",
                    age_seconds=None,
                    availability="offline",
                )
            ],
        )
    sensors: list[LatestTelemetrySensor] = []
    for row in rows:
        timestamp = _datetime(row, "ts")
        age_seconds = (
            max(0.0, (reference - timestamp).total_seconds())
            if reference is not None
            else 0.0
        )
        sensors.append(
            LatestTelemetrySensor(
                device_id=cast(SensorId, row["device_id"]),
                ts=format_historical_datetime(timestamp),
                temperature_c=cast(float | None, row["temperature_c"]),
                relative_humidity_pct=cast(float | None, row["relative_humidity_pct"]),
                freshness="fresh" if age_seconds <= 600 else "stale",
                age_seconds=age_seconds,
                availability="online",
            )
        )
    return LatestTelemetryResponse(
        request_id=new_request_id(),
        generated_at=current_operational_instant(),
        time_zone="Asia/Jakarta",
        sensors=sensors,
    )


@router.get("/api/telemetry/history", response_model=TelemetryHistoryResponse)
async def telemetry_history(
    device_id: Annotated[CorpusDeviceId, Query()],
    from_ts: Annotated[HistoricalDateTime, Query(alias="from")],
    to_ts: Annotated[HistoricalDateTime, Query(alias="to")],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    bucket: Annotated[Bucket, Query()] = "raw",
    limit: Annotated[int, Query(ge=1, le=5_000)] = 500,
    cursor: Annotated[str | None, Query()] = None,
) -> TelemetryHistoryResponse:
    try:
        bucket_seconds = effective_bucket_seconds(bucket, from_ts, to_ts)
    except ValueError as error:
        raise InvalidQuery(
            "Query parameters failed validation",
            {"from": [str(error)]},
        ) from error
    if bucket != "raw" and limit > 2_000:
        raise InvalidQuery(
            "Query parameters failed validation",
            {"limit": ["Bucketed limit must be at most 2000"]},
        )
    query_fields: dict[str, object] = {
        "device_id": device_id,
        "from": from_ts,
        "to": to_ts,
        "bucket": bucket,
        "limit": limit,
    }
    if cursor is not None:
        query_fields["cursor"] = cursor
    query = TelemetryHistoryQuery.model_validate(query_fields, strict=True)
    filters: dict[str, object] = {
        "device_id": query.device_id,
        "from": query.from_ts,
        "bucket": query.bucket,
        "bucket_seconds": bucket_seconds,
    }
    try:
        after = (
            parse_keyset_cursor(
                query.cursor,
                "telemetry",
                snapshot_to=query.to_ts,
                filters=filters,
            )
            if query.cursor
            else None
        )
    except ValueError as error:
        raise InvalidQuery(
            "Query parameters failed validation",
            {"cursor": ["Invalid cursor"]},
        ) from error
    rows = await history_rows(
        connection,
        device_id=query.device_id,
        from_ts=datetime.fromisoformat(query.from_ts),
        to_ts=datetime.fromisoformat(query.to_ts),
        bucket=query.bucket,
        bucket_seconds=bucket_seconds,
        limit=query.limit,
        after_ts=datetime.fromisoformat(after[0]) if after else None,
        after_id=after[1] if after else None,
    )
    has_more = len(rows) > query.limit
    points = [
        TelemetryPoint(
            ts=format_historical_datetime(_datetime(row, "ts")),
            temperature_c=cast(float | None, row["temperature_c"]),
            relative_humidity_pct=cast(float | None, row["relative_humidity_pct"]),
            temperature_c_min=cast(float | None, row["temperature_c_min"]),
            temperature_c_max=cast(float | None, row["temperature_c_max"]),
            relative_humidity_pct_min=cast(
                float | None, row["relative_humidity_pct_min"]
            ),
            relative_humidity_pct_max=cast(
                float | None, row["relative_humidity_pct_max"]
            ),
            sample_count=cast(int, row["sample_count"]),
            gap_before=cast(bool, row["gap_before"]),
        )
        for row in rows[: query.limit]
    ]
    return TelemetryHistoryResponse.model_validate(
        {
            "request_id": new_request_id(),
            "device_id": query.device_id,
            "from": query.from_ts,
            "to": query.to_ts,
            "bucket": query.bucket,
            "bucket_seconds": bucket_seconds,
            "time_zone": "Asia/Jakarta",
            "points": points,
            "next_cursor": (
                make_keyset_cursor(
                    "telemetry",
                    timestamp=format_historical_datetime(
                        _datetime(rows[query.limit - 1], "cursor_ts")
                    ),
                    row_id=cast(str, rows[query.limit - 1]["row_id"]),
                    snapshot_to=query.to_ts,
                    filters=filters,
                )
                if has_more
                else None
            ),
            "returned_count": len(points),
        },
        strict=True,
    )
