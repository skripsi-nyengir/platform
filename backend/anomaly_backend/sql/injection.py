from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import CorpusDeviceId


_INJECTION_EVENTS = text(
    """
    SELECT
        event_id,
        family,
        severity,
        channel,
        channel_index,
        start_ts,
        end_ts,
        start_idx,
        end_idx_exclusive,
        segment_index
    FROM injection_events
    WHERE device_id = CAST(:device_id AS text)
    ORDER BY start_ts, event_id
    """
)


async def injection_event_rows(
    connection: AsyncConnection,
    device_id: CorpusDeviceId,
) -> list[RowMapping]:
    result = await connection.execute(_INJECTION_EVENTS, {"device_id": device_id})
    return cast(list[RowMapping], list(result.mappings()))
