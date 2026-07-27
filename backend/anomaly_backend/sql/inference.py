from datetime import datetime
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import SensorId


_CANONICAL_MODEL = text(
    """
    SELECT model_version
    FROM active_model_selections
    WHERE device_id = :device_id
    """
)

_INFERENCE_RESULTS = text(
    """
    SELECT
        window_start_ts,
        window_end_ts,
        score_ts,
        score,
        threshold,
        is_anomaly,
        model_version,
        score_provenance
    FROM inference_results
    WHERE device_id = :device_id
      AND score_ts >= :from_ts
      AND score_ts < :to_ts
      AND model_version = :model_version
    ORDER BY score_ts ASC, model_version ASC
    LIMIT :fetch_limit OFFSET :offset
    """
)


async def inference_rows(
    connection: AsyncConnection,
    *,
    device_id: SensorId,
    from_ts: datetime,
    to_ts: datetime,
    model_version: str | None,
    limit: int,
    offset: int,
) -> tuple[str, list[RowMapping]]:
    canonical = cast(
        str | None,
        await connection.scalar(
            _CANONICAL_MODEL,
            {"device_id": device_id},
        ),
    )
    canonical_version = (
        model_version
        if model_version is not None
        else str(canonical)
        if canonical is not None
        else ""
    )
    result = await connection.execute(
        _INFERENCE_RESULTS,
        {
            "device_id": device_id,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "model_version": canonical_version,
            "fetch_limit": limit + 1,
            "offset": offset,
        },
    )
    return canonical_version, list(result.mappings())
