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
    format_historical_datetime,
    make_cursor,
    parse_cursor,
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
    if from_ts >= to_ts:
        raise InvalidQuery(
            "Query parameters failed validation",
            {"from": ["from must be earlier than to"]},
        )
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
    try:
        offset = parse_cursor(query.cursor, "inference") if query.cursor else 0
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
        limit=query.limit,
        offset=offset,
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
        )
        for row in rows[: query.limit]
    ]
    return InferenceResponse(
        request_id=new_request_id(),
        device_id=query.device_id,
        time_zone="Asia/Jakarta",
        model_version=model_version,
        points=points,
        next_cursor=make_cursor("inference", offset + query.limit) if has_more else None,
        returned_count=len(points),
    )
