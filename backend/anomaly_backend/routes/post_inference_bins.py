from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    CorpusDeviceId,
    HistoricalDateTime,
    PostInferenceBin,
    PostInferenceBinSource,
    PostInferenceBinsQuery,
    PostInferenceBinsResponse,
    format_historical_datetime,
    make_keyset_cursor,
    parse_keyset_cursor,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import InvalidQuery, new_request_id
from anomaly_backend.sql import (
    live_post_inference_bin_rows,
    post_inference_bin_rows,
)

router = APIRouter()


def _datetime(row: RowMapping, field: str) -> datetime:
    return cast(datetime, row[field])


def _optional_historical(row: RowMapping, field: str) -> HistoricalDateTime | None:
    value = row[field]
    if value is None:
        return None
    return format_historical_datetime(cast(datetime, value))


@router.get("/api/post-inference-bins", response_model=PostInferenceBinsResponse)
async def post_inference_bins(
    device_id: Annotated[CorpusDeviceId, Query()],
    from_ts: Annotated[HistoricalDateTime, Query(alias="from")],
    to_ts: Annotated[HistoricalDateTime, Query(alias="to")],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    limit: Annotated[int, Query(ge=1, le=5_000)] = 500,
    cursor: Annotated[str | None, Query()] = None,
    model_version: Annotated[str | None, Query()] = None,
    source: Annotated[PostInferenceBinSource, Query()] = "replay",
) -> PostInferenceBinsResponse:
    query_fields: dict[str, object] = {
        "device_id": device_id,
        "from": from_ts,
        "to": to_ts,
        "source": source,
        "limit": limit,
    }
    if cursor is not None:
        query_fields["cursor"] = cursor
    if model_version is not None:
        query_fields["model_version"] = model_version
    try:
        query = PostInferenceBinsQuery.model_validate(query_fields, strict=True)
    except ValidationError as error:
        raise InvalidQuery("Query parameters failed validation") from error
    filters: dict[str, object] = {
        "device_id": query.device_id,
        "from": query.from_ts,
        "source": query.source,
        "model_version": query.model_version,
    }
    try:
        after = (
            parse_keyset_cursor(
                query.cursor,
                "post_inference_bins",
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
    fetch_rows = (
        live_post_inference_bin_rows
        if query.source == "live"
        else post_inference_bin_rows
    )
    canonical_version, rows = await fetch_rows(
        connection,
        device_id=query.device_id,
        from_ts=datetime.fromisoformat(query.from_ts),
        to_ts=datetime.fromisoformat(query.to_ts),
        model_version=query.model_version,
        limit=query.limit,
        after_ts=datetime.fromisoformat(after[0]) if after else None,
        after_id=after[1] if after else None,
    )
    has_more = len(rows) > query.limit
    bins = [
        PostInferenceBin(
            segment_id=cast(int, row["segment_id"]),
            bin_ordinal=cast(int, row["bin_ordinal"]),
            start_score_ts=format_historical_datetime(_datetime(row, "start_score_ts")),
            end_score_ts=format_historical_datetime(_datetime(row, "end_score_ts")),
            scored_timestamp_count=cast(int, row["scored_timestamp_count"]),
            is_alert=cast(bool, row["is_alert"]),
            candidate_alert_count=cast(int, row["candidate_alert_count"]),
            first_alert_ts=_optional_historical(row, "first_alert_ts"),
            last_alert_ts=_optional_historical(row, "last_alert_ts"),
            peak_score=cast(float, row["peak_score"]),
            latest_score=cast(float, row["latest_score"]),
            threshold=cast(float, row["threshold"]),
            schema_version=cast(str, row["schema_version"]),
        )
        for row in rows[: query.limit]
    ]
    return PostInferenceBinsResponse.model_validate(
        {
            "request_id": new_request_id(),
            "device_id": query.device_id,
            "from": query.from_ts,
            "to": query.to_ts,
            "time_zone": "Asia/Jakarta",
            "source": query.source,
            "model_version": canonical_version,
            "bins": bins,
            "next_cursor": (
                make_keyset_cursor(
                    "post_inference_bins",
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
            "returned_count": len(bins),
        },
        strict=True,
    )
