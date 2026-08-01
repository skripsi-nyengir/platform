from datetime import datetime
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import Bucket, CorpusDeviceId, SensorId


_NORMALIZED_SOURCE = """
    SELECT
        telemetry.device_id,
        telemetry.ts,
        telemetry.temperature_c,
        telemetry.relative_humidity_pct,
        telemetry.ts AT TIME ZONE 'Asia/Jakarta' AS received_at_utc,
        'historical:' || telemetry.corpus_id || ':' || telemetry.corpus_index::text
            AS row_id
    FROM telemetry
    JOIN devices USING (device_id)
    WHERE devices.is_active
    UNION ALL
    SELECT
        live.device_id,
        live.received_ts AS ts,
        live.temperature_c,
        live.relative_humidity_pct,
        live.received_at_utc,
        'live:' || live.telemetry_id::text AS row_id
    FROM live_telemetry AS live
    JOIN devices ON devices.device_id = live.device_id
    WHERE devices.is_active
"""

_LATEST = text(
    f"""
    WITH normalized AS ({_NORMALIZED_SOURCE}), ranked AS (
        SELECT
            normalized.*,
            row_number() OVER (
                PARTITION BY device_id
                ORDER BY received_at_utc DESC, ts DESC, row_id DESC
            ) AS position
        FROM normalized
        WHERE CAST(:device_id AS text) IS NULL
           OR device_id = CAST(:device_id AS text)
    )
    SELECT
        device_id,
        ts,
        temperature_c,
        relative_humidity_pct,
        clock_timestamp() AT TIME ZONE 'Asia/Jakarta' AS observation_reference
    FROM ranked
    WHERE position = 1
    ORDER BY device_id
    """
)

_RAW_HISTORY = text(
    f"""
    WITH normalized AS ({_NORMALIZED_SOURCE}), ordered AS (
        SELECT
            normalized.*,
            lag(ts) OVER (ORDER BY ts, row_id) AS previous_ts
        FROM normalized
        WHERE device_id = :device_id
    )
    SELECT
        ts AS cursor_ts,
        row_id,
        ts,
        temperature_c,
        relative_humidity_pct,
        temperature_c AS temperature_c_min,
        temperature_c AS temperature_c_max,
        relative_humidity_pct AS relative_humidity_pct_min,
        relative_humidity_pct AS relative_humidity_pct_max,
        1 AS sample_count,
        previous_ts IS NOT NULL
            AND extract(epoch FROM ts - previous_ts) > 600 AS gap_before
    FROM ordered
    WHERE ts >= :from_ts AND ts < :to_ts
      AND (
        CAST(:after_ts AS timestamp) IS NULL
        OR ROW(ts, row_id) > ROW(CAST(:after_ts AS timestamp), :after_id)
      )
    ORDER BY ts, row_id
    LIMIT :fetch_limit
    """
)

_BUCKETED_HISTORY = text(
    f"""
    WITH normalized AS ({_NORMALIZED_SOURCE}), bucketed AS (
        SELECT
            date_bin(
                make_interval(secs => :bucket_seconds),
                ts,
                TIMESTAMP '1970-01-01 00:00:00'
            ) AS ts,
            avg(temperature_c) AS temperature_c,
            avg(relative_humidity_pct) AS relative_humidity_pct,
            min(temperature_c) AS temperature_c_min,
            max(temperature_c) AS temperature_c_max,
            min(relative_humidity_pct) AS relative_humidity_pct_min,
            max(relative_humidity_pct) AS relative_humidity_pct_max,
            count(*)::integer AS sample_count
        FROM normalized
        WHERE device_id = :device_id
          AND ts >= :from_ts
          AND ts < :to_ts
        GROUP BY 1
    ), ordered AS (
        SELECT
            bucketed.*,
            'bucket:' || extract(epoch FROM ts)::bigint::text AS row_id,
            lag(ts) OVER (ORDER BY ts) AS previous_ts
        FROM bucketed
    )
    SELECT
        ts AS cursor_ts,
        row_id,
        ts,
        temperature_c,
        relative_humidity_pct,
        temperature_c_min,
        temperature_c_max,
        relative_humidity_pct_min,
        relative_humidity_pct_max,
        sample_count,
        previous_ts IS NOT NULL
            AND extract(epoch FROM ts - previous_ts) > :bucket_seconds AS gap_before
    FROM ordered
    WHERE (
        CAST(:after_ts AS timestamp) IS NULL
        OR ROW(ts, row_id) > ROW(CAST(:after_ts AS timestamp), :after_id)
    )
    ORDER BY ts, row_id
    LIMIT :fetch_limit
    """
)


async def latest_rows(
    connection: AsyncConnection,
    device_id: SensorId | None,
) -> tuple[datetime | None, list[RowMapping]]:
    rows = list((await connection.execute(_LATEST, {"device_id": device_id})).mappings())
    reference = (
        cast(datetime, rows[0]["observation_reference"]) if rows else None
    )
    return reference, rows


async def history_rows(
    connection: AsyncConnection,
    *,
    device_id: CorpusDeviceId,
    from_ts: datetime,
    to_ts: datetime,
    bucket: Bucket,
    bucket_seconds: int | None,
    limit: int,
    after_ts: datetime | None,
    after_id: str | None,
) -> list[RowMapping]:
    parameters: dict[str, object] = {
        "device_id": device_id,
        "from_ts": from_ts,
        "to_ts": to_ts,
        "fetch_limit": limit + 1,
        "after_ts": after_ts,
        "after_id": after_id,
    }
    statement = _RAW_HISTORY
    if bucket != "raw":
        if bucket_seconds is None:
            raise ValueError("bucketed telemetry requires an effective width")
        parameters["bucket_seconds"] = bucket_seconds
        statement = _BUCKETED_HISTORY
    return list((await connection.execute(statement, parameters)).mappings())
