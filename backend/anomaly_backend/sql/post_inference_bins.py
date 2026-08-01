from datetime import datetime
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import CorpusDeviceId

_MODEL_IN_RANGE = text(
    """
    SELECT model_version
    FROM post_inference_bins
    WHERE device_id = :device_id
      AND start_score_ts >= :from_ts AND start_score_ts < :to_ts
    ORDER BY start_score_ts DESC, replay_job_id DESC
    LIMIT 1
    """
)

_FALLBACK_MODEL = text(
    """
    SELECT model_version
    FROM post_inference_bins
    WHERE device_id = :device_id
    ORDER BY start_score_ts DESC
    LIMIT 1
    """
)

_ROW_ID = (
    "replay_job_id || ':' || segment_id::text || ':' || bin_ordinal::text"
)

_BIN_ROWS = text(
    f"""
    SELECT
        start_score_ts AS cursor_ts,
        {_ROW_ID} AS row_id,
        segment_id,
        bin_ordinal,
        start_score_ts,
        end_score_ts,
        scored_timestamp_count,
        is_alert,
        candidate_alert_count,
        first_alert_ts,
        last_alert_ts,
        peak_score,
        latest_score,
        threshold,
        schema_version
    FROM post_inference_bins
    WHERE device_id = :device_id
      AND model_version = :model_version
      AND start_score_ts >= :from_ts AND start_score_ts < :to_ts
      AND (
        CAST(:after_ts AS timestamp) IS NULL
        OR ROW(start_score_ts, {_ROW_ID})
           > ROW(CAST(:after_ts AS timestamp), :after_id)
      )
    ORDER BY start_score_ts, row_id
    LIMIT :fetch_limit
    """
)


async def post_inference_bin_rows(
    connection: AsyncConnection,
    *,
    device_id: CorpusDeviceId,
    from_ts: datetime,
    to_ts: datetime,
    model_version: str | None,
    limit: int,
    after_ts: datetime | None,
    after_id: str | None,
) -> tuple[str, list[RowMapping]]:
    canonical_version = model_version or cast(
        str | None,
        await connection.scalar(
            _MODEL_IN_RANGE,
            {"device_id": device_id, "from_ts": from_ts, "to_ts": to_ts},
        ),
    )
    if canonical_version is None:
        canonical_version = cast(
            str | None,
            await connection.scalar(_FALLBACK_MODEL, {"device_id": device_id}),
        )
    canonical_version = canonical_version or ""
    rows = list(
        (
            await connection.execute(
                _BIN_ROWS,
                {
                    "device_id": device_id,
                    "from_ts": from_ts,
                    "to_ts": to_ts,
                    "model_version": canonical_version,
                    "fetch_limit": limit + 1,
                    "after_ts": after_ts,
                    "after_id": after_id,
                },
            )
        ).mappings()
    )
    return canonical_version, rows
