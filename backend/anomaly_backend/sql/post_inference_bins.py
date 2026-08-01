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


LIVE_BIN_SCHEMA_VERSION = "live-post-inference-bins-v1"

_BIN_SIZE = 51

_LIVE_MODEL_IN_RANGE = text(
    """
    SELECT model_version
    FROM live_inference
    WHERE device_id = :device_id
      AND score_ts >= :from_ts AND score_ts < :to_ts
    ORDER BY score_ts DESC
    LIMIT 1
    """
)

_LIVE_FALLBACK_MODEL = text(
    """
    SELECT model_version
    FROM live_inference
    WHERE device_id = :device_id
    ORDER BY score_ts DESC
    LIMIT 1
    """
)

_LIVE_BIN_ROWS = text(
    f"""
    WITH relevant_epochs AS (
        SELECT DISTINCT continuity_epoch
        FROM live_inference
        WHERE device_id = :device_id
          AND model_version = :model_version
          AND score_ts >= :from_ts AND score_ts < :to_ts
    ),
    scored AS (
        SELECT
            score_ts,
            score,
            threshold,
            is_anomaly,
            continuity_epoch,
            (
                row_number() OVER (
                    PARTITION BY continuity_epoch
                    ORDER BY score_ts, inference_id
                ) - 1
            ) / {_BIN_SIZE} AS bin_ordinal
        FROM live_inference
        WHERE device_id = :device_id
          AND model_version = :model_version
          AND continuity_epoch IN (SELECT continuity_epoch FROM relevant_epochs)
    ),
    grouped AS (
        SELECT
            continuity_epoch AS segment_id,
            bin_ordinal,
            min(score_ts) AS start_score_ts,
            max(score_ts) AS end_score_ts,
            count(*)::int AS scored_timestamp_count,
            bool_or(is_anomaly) AS is_alert,
            (count(*) FILTER (WHERE is_anomaly))::int AS candidate_alert_count,
            min(score_ts) FILTER (WHERE is_anomaly) AS first_alert_ts,
            max(score_ts) FILTER (WHERE is_anomaly) AS last_alert_ts,
            max(score) AS peak_score,
            (array_agg(score ORDER BY score_ts DESC))[1] AS latest_score,
            max(threshold) AS threshold
        FROM scored
        GROUP BY continuity_epoch, bin_ordinal
        HAVING count(*) = {_BIN_SIZE}
    ),
    identified AS (
        SELECT
            *,
            'live:' || segment_id::text || ':' || bin_ordinal::text AS row_id
        FROM grouped
    )
    SELECT
        start_score_ts AS cursor_ts,
        row_id,
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
        :schema_version AS schema_version
    FROM identified
    WHERE start_score_ts >= :from_ts AND start_score_ts < :to_ts
      AND (
        CAST(:after_ts AS timestamp) IS NULL
        OR ROW(start_score_ts, row_id) > ROW(CAST(:after_ts AS timestamp), :after_id)
      )
    ORDER BY start_score_ts, row_id
    LIMIT :fetch_limit
    """
)


async def live_post_inference_bin_rows(
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
            _LIVE_MODEL_IN_RANGE,
            {"device_id": device_id, "from_ts": from_ts, "to_ts": to_ts},
        ),
    )
    if canonical_version is None:
        canonical_version = cast(
            str | None,
            await connection.scalar(
                _LIVE_FALLBACK_MODEL, {"device_id": device_id}
            ),
        )
    canonical_version = canonical_version or ""
    rows = list(
        (
            await connection.execute(
                _LIVE_BIN_ROWS,
                {
                    "device_id": device_id,
                    "from_ts": from_ts,
                    "to_ts": to_ts,
                    "model_version": canonical_version,
                    "schema_version": LIVE_BIN_SCHEMA_VERSION,
                    "fetch_limit": limit + 1,
                    "after_ts": after_ts,
                    "after_id": after_id,
                },
            )
        ).mappings()
    )
    return canonical_version, rows


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
