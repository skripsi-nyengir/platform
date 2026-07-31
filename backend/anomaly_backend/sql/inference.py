from datetime import datetime
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import Bucket, CorpusDeviceId


_NORMALIZED_SOURCE = """
    SELECT
        results.device_id,
        results.window_start_ts,
        results.window_end_ts,
        results.score_ts,
        results.score,
        results.threshold,
        results.is_anomaly,
        CASE
            WHEN results.is_anomaly AND results.score / results.threshold > 2
                THEN 'critical'
            WHEN results.is_anomaly THEN 'warning'
            ELSE 'info'
        END AS severity,
        results.model_version,
        results.score_provenance,
        results.recon_temperature_c,
        results.recon_relative_humidity_pct,
        results.band_half_temperature_c,
        results.band_half_relative_humidity_pct,
        'historical:' || results.model_version || ':'
            || extract(epoch FROM results.score_ts)::bigint::text AS row_id
    FROM inference_results AS results
    JOIN devices ON devices.device_id = results.device_id
    WHERE devices.is_active
    UNION ALL
    SELECT
        live.device_id,
        live.window_start_ts,
        live.window_end_ts,
        live.score_ts,
        live.score,
        live.threshold,
        live.is_anomaly,
        live.severity_at_score AS severity,
        live.model_version,
        'artifact_backed'::text AS score_provenance,
        NULL::double precision AS recon_temperature_c,
        NULL::double precision AS recon_relative_humidity_pct,
        NULL::double precision AS band_half_temperature_c,
        NULL::double precision AS band_half_relative_humidity_pct,
        'live:' || live.inference_id::text AS row_id
    FROM live_inference AS live
    JOIN devices ON devices.device_id = live.device_id
    WHERE devices.is_active
"""

_MODEL_IN_RANGE = text(
    f"""
    WITH normalized AS ({_NORMALIZED_SOURCE})
    SELECT model_version
    FROM normalized
    WHERE device_id = :device_id
      AND score_ts >= :from_ts AND score_ts < :to_ts
    ORDER BY score_ts DESC, row_id DESC
    LIMIT 1
    """
)

_FALLBACK_MODEL = text(
    """
    SELECT model_version FROM (
        SELECT pair.model_version, 0 AS priority
        FROM live_model_selections AS selection
        JOIN live_model_pairs AS pair USING (model_pair_id)
        WHERE selection.device_id = :device_id
        UNION ALL
        SELECT model_version, 1 AS priority
        FROM active_model_selections
        WHERE device_id = :device_id
    ) AS choices
    ORDER BY priority
    LIMIT 1
    """
)

_RAW_RESULTS = text(
    f"""
    WITH normalized AS ({_NORMALIZED_SOURCE})
    SELECT
        score_ts AS cursor_ts,
        row_id,
        window_start_ts,
        window_end_ts,
        score_ts,
        score,
        threshold,
        is_anomaly,
        severity,
        score AS latest_score,
        1 AS sample_count,
        model_version,
        score_provenance,
        recon_temperature_c,
        recon_relative_humidity_pct,
        band_half_temperature_c,
        band_half_relative_humidity_pct
    FROM normalized
    WHERE device_id = :device_id
      AND score_ts >= :from_ts AND score_ts < :to_ts
      AND model_version = :model_version
      AND (
        CAST(:after_ts AS timestamp) IS NULL
        OR ROW(score_ts, row_id) > ROW(CAST(:after_ts AS timestamp), :after_id)
      )
    ORDER BY score_ts, row_id
    LIMIT :fetch_limit
    """
)

_BUCKETED_RESULTS = text(
    f"""
    WITH normalized AS ({_NORMALIZED_SOURCE}), scoped AS (
        SELECT
            normalized.*,
            date_bin(
                make_interval(secs => :bucket_seconds),
                score_ts,
                TIMESTAMP '1970-01-01 00:00:00'
            ) AS bucket_ts,
            CASE severity WHEN 'critical' THEN 2 WHEN 'warning' THEN 1 ELSE 0 END
                AS severity_rank
        FROM normalized
        WHERE device_id = :device_id
          AND score_ts >= :from_ts AND score_ts < :to_ts
          AND model_version = :model_version
    ), ranked AS (
        SELECT
            scoped.*,
            row_number() OVER (
                PARTITION BY bucket_ts
                ORDER BY score / threshold DESC, severity_rank DESC,
                         score_ts DESC, row_id DESC
            ) AS peak_position,
            row_number() OVER (
                PARTITION BY bucket_ts ORDER BY score_ts DESC, row_id DESC
            ) AS latest_position
        FROM scoped
    ), aggregate AS (
        SELECT
            bucket_ts,
            count(*)::integer AS sample_count,
            bool_or(is_anomaly) AS is_anomaly,
            max(severity_rank) AS severity_rank,
            max(score) FILTER (WHERE latest_position = 1) AS latest_score
        FROM ranked
        GROUP BY bucket_ts
    )
    SELECT
        aggregate.bucket_ts AS cursor_ts,
        'bucket:' || extract(epoch FROM aggregate.bucket_ts)::bigint::text AS row_id,
        peak.window_start_ts,
        peak.window_end_ts,
        peak.score_ts,
        peak.score,
        peak.threshold,
        aggregate.is_anomaly,
        CASE aggregate.severity_rank
            WHEN 2 THEN 'critical' WHEN 1 THEN 'warning' ELSE 'info'
        END AS severity,
        aggregate.latest_score,
        aggregate.sample_count,
        peak.model_version,
        peak.score_provenance,
        peak.recon_temperature_c,
        peak.recon_relative_humidity_pct,
        peak.band_half_temperature_c,
        peak.band_half_relative_humidity_pct
    FROM aggregate
    JOIN ranked AS peak
      ON peak.bucket_ts = aggregate.bucket_ts AND peak.peak_position = 1
    WHERE (
        CAST(:after_ts AS timestamp) IS NULL
        OR ROW(
            aggregate.bucket_ts,
            'bucket:' || extract(epoch FROM aggregate.bucket_ts)::bigint::text
        ) > ROW(CAST(:after_ts AS timestamp), :after_id)
    )
    ORDER BY aggregate.bucket_ts, row_id
    LIMIT :fetch_limit
    """
)


async def inference_rows(
    connection: AsyncConnection,
    *,
    device_id: CorpusDeviceId,
    from_ts: datetime,
    to_ts: datetime,
    model_version: str | None,
    bucket: Bucket,
    bucket_seconds: int | None,
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
    parameters: dict[str, object] = {
        "device_id": device_id,
        "from_ts": from_ts,
        "to_ts": to_ts,
        "model_version": canonical_version,
        "fetch_limit": limit + 1,
        "after_ts": after_ts,
        "after_id": after_id,
    }
    statement = _RAW_RESULTS
    if bucket != "raw":
        if bucket_seconds is None:
            raise ValueError("bucketed inference requires an effective width")
        parameters["bucket_seconds"] = bucket_seconds
        statement = _BUCKETED_RESULTS
    rows = list((await connection.execute(statement, parameters)).mappings())
    return canonical_version, rows
