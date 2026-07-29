from datetime import datetime
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import Bucket, CorpusDeviceId, SensorId


_LATEST = text(
    """
    WITH observation AS (
        SELECT max(ts) AS observation_reference
        FROM telemetry
        JOIN devices USING (device_id)
        WHERE devices.is_active
          AND devices.telemetry_kind = 'historical_replay'
    ), ranked AS (
        SELECT
            device_id,
            ts,
            temperature_c,
            relative_humidity_pct,
            row_number() OVER (PARTITION BY device_id ORDER BY ts DESC) AS position
        FROM telemetry
        JOIN devices USING (device_id)
        WHERE devices.is_active
          AND devices.telemetry_kind = 'historical_replay'
          AND (
            CAST(:device_id AS text) IS NULL
            OR device_id = CAST(:device_id AS text)
        )
    )
    SELECT
        ranked.device_id,
        ranked.ts,
        ranked.temperature_c,
        ranked.relative_humidity_pct,
        observation.observation_reference
    FROM observation
    LEFT JOIN ranked ON ranked.position = 1
    ORDER BY ranked.device_id ASC NULLS LAST
    """
)

_RAW_HISTORY = text(
    """
    WITH source_ordered AS (
        SELECT
            ts,
            temperature_c,
            relative_humidity_pct,
            source_index,
            lag(ts) OVER (ORDER BY ts ASC) AS previous_ts,
            lag(source_index) OVER (ORDER BY ts ASC) AS previous_source_index
        FROM telemetry
        WHERE device_id = :device_id
    )
    SELECT
        ts,
        temperature_c,
        relative_humidity_pct,
        1 AS sample_count,
        previous_ts IS NOT NULL
            AND source_index = previous_source_index + 1
            AND extract(epoch FROM ts - previous_ts) > 600 AS gap_before
    FROM source_ordered
    WHERE ts >= :from_ts AND ts < :to_ts
    ORDER BY ts ASC
    LIMIT :fetch_limit OFFSET :offset
    """
)

_BUCKETED_HISTORY = text(
    """
    WITH bucketed AS (
        SELECT
            time_bucket(CAST(:bucket_interval AS interval), ts) AS ts,
            avg(temperature_c) AS temperature_c,
            avg(relative_humidity_pct) AS relative_humidity_pct,
            count(*) AS sample_count
        FROM telemetry
        WHERE device_id = :device_id
          AND ts >= :from_ts
          AND ts < :to_ts
        GROUP BY 1
    ), ordered AS (
        SELECT
            ts,
            temperature_c,
            relative_humidity_pct,
            sample_count,
            lag(ts) OVER (ORDER BY ts ASC) AS previous_ts
        FROM bucketed
    )
    SELECT
        ts,
        temperature_c,
        relative_humidity_pct,
        sample_count,
        previous_ts IS NOT NULL
            AND extract(epoch FROM ts - previous_ts) > :bucket_seconds AS gap_before
    FROM ordered
    ORDER BY ts ASC
    LIMIT :fetch_limit OFFSET :offset
    """
)

_BUCKETS: dict[str, tuple[str, int]] = {
    "1m": ("1 minute", 60),
    "5m": ("5 minutes", 300),
    "15m": ("15 minutes", 900),
    "1h": ("1 hour", 3_600),
    "1d": ("1 day", 86_400),
}


async def latest_rows(
    connection: AsyncConnection,
    device_id: SensorId | None,
) -> tuple[datetime | None, list[RowMapping]]:
    result = await connection.execute(_LATEST, {"device_id": device_id})
    rows = list(result.mappings())
    reference = cast(datetime | None, rows[0]["observation_reference"])
    return reference, [row for row in rows if row["device_id"] is not None]


async def history_rows(
    connection: AsyncConnection,
    *,
    device_id: CorpusDeviceId,
    from_ts: datetime,
    to_ts: datetime,
    bucket: Bucket,
    limit: int,
    offset: int,
) -> list[RowMapping]:
    parameters: dict[str, object] = {
        "device_id": device_id,
        "from_ts": from_ts,
        "to_ts": to_ts,
        "fetch_limit": limit + 1,
        "offset": offset,
    }
    statement = _RAW_HISTORY
    if bucket != "raw":
        interval, seconds = _BUCKETS[bucket]
        parameters.update(bucket_interval=interval, bucket_seconds=seconds)
        statement = _BUCKETED_HISTORY
    result = await connection.execute(statement, parameters)
    return list(result.mappings())
