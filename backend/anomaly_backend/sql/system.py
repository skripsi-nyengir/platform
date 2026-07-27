from datetime import datetime
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.contracts import SensorId


TALPHA_DEVICE_IDS: tuple[SensorId] = ("b02f3872-ruang-produksi",)


async def telemetry_observation(
    connection: AsyncConnection,
) -> tuple[datetime | None, int, int, int]:
    result = await connection.execute(
        select(
            tables.telemetry.c.device_id,
            func.max(tables.telemetry.c.ts).label("latest_ts"),
        )
        .where(tables.telemetry.c.device_id.in_(TALPHA_DEVICE_IDS))
        .group_by(tables.telemetry.c.device_id)
    )
    timestamps = {
        cast(str, row["device_id"]): cast(datetime, row["latest_ts"])
        for row in result.mappings()
    }
    latest_ts = max(timestamps.values(), default=None)
    fresh_count = sum(timestamp == latest_ts for timestamp in timestamps.values())
    stale_count = len(timestamps) - fresh_count
    offline_count = len(TALPHA_DEVICE_IDS) - len(timestamps)
    return latest_ts, fresh_count, stale_count, offline_count
