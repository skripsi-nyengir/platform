from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    Bucket,
    CorpusDeviceId,
    HistoricalDateTime,
    InferencePoint,
    InferenceQuery,
    InferenceResponse,
    ScoreProvenance,
    Severity,
    effective_bucket_seconds,
    format_historical_datetime,
    make_keyset_cursor,
    parse_keyset_cursor,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import InvalidQuery, new_request_id
from anomaly_backend.sql import inference_rows


router = APIRouter()


def _datetime(row: RowMapping, field: str) -> datetime:
    return cast(datetime, row[field])


@router.get("/api/inference-results", response_model=InferenceResponse)
async def inference_results(
    device_id: Annotated[CorpusDeviceId, Query()],
    from_ts: Annotated[HistoricalDateTime, Query(alias="from")],
    to_ts: Annotated[HistoricalDateTime, Query(alias="to")],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    bucket: Annotated[Bucket, Query()] = "raw",
    limit: Annotated[int, Query(ge=1, le=5_000)] = 500,
    cursor: Annotated[str | None, Query()] = None,
    model_version: Annotated[str | None, Query()] = None,
) -> InferenceResponse:
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
            {"limit": ["bucketed limit must be at most 2000"]},
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
    if model_version is not None:
        query_fields["model_version"] = model_version
    query = InferenceQuery.model_validate(query_fields, strict=True)
    filters: dict[str, object] = {
        "device_id": query.device_id,
        "from": query.from_ts,
        "bucket": query.bucket,
        "bucket_seconds": bucket_seconds,
        "model_version": query.model_version,
    }
    try:
        after = (
            parse_keyset_cursor(
                query.cursor,
                "inference",
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
    model_version, rows = await inference_rows(
        connection,
        device_id=query.device_id,
        from_ts=datetime.fromisoformat(query.from_ts),
        to_ts=datetime.fromisoformat(query.to_ts),
        model_version=query.model_version,
        bucket=query.bucket,
        bucket_seconds=bucket_seconds,
        limit=query.limit,
        after_ts=datetime.fromisoformat(after[0]) if after else None,
        after_id=after[1] if after else None,
    )
    has_more = len(rows) > query.limit
    points = [
        InferencePoint(
            window_start_ts=format_historical_datetime(
                _datetime(row, "window_start_ts")
            ),
            window_end_ts=format_historical_datetime(_datetime(row, "window_end_ts")),
            score_ts=format_historical_datetime(_datetime(row, "score_ts")),
            score=cast(float, row["score"]),
            threshold=cast(float, row["threshold"]),
            is_anomaly=cast(bool, row["is_anomaly"]),
            model_version=cast(str, row["model_version"]),
            score_provenance=cast(ScoreProvenance, row["score_provenance"]),
            severity=cast(Severity, row["severity"]),
            latest_score=cast(float, row["latest_score"]),
            sample_count=cast(int, row["sample_count"]),
            recon_temperature_c=cast(float | None, row["recon_temperature_c"]),
            recon_relative_humidity_pct=cast(
                float | None, row["recon_relative_humidity_pct"]
            ),
            band_half_temperature_c=cast(
                float | None, row["band_half_temperature_c"]
            ),
            band_half_relative_humidity_pct=cast(
                float | None, row["band_half_relative_humidity_pct"]
            ),
        )
        for row in rows[: query.limit]
    ]
    return InferenceResponse.model_validate(
        {
            "request_id": new_request_id(),
            "device_id": query.device_id,
            "from": query.from_ts,
            "to": query.to_ts,
            "bucket": query.bucket,
            "bucket_seconds": bucket_seconds,
            "time_zone": "Asia/Jakarta",
            "model_version": model_version,
            "points": points,
            "next_cursor": (
                make_keyset_cursor(
                    "inference",
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
