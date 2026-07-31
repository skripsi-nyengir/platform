from datetime import datetime
from typing import cast

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import CorpusDeviceId


_SIM_MODELS = text(
    """
    SELECT
        mv.version,
        mv.model_key,
        mf.display_name,
        mv.score_key,
        mv.threshold,
        mv.manifest_sha256,
        (sel.model_version = mv.version) AS is_active
    FROM model_versions mv
    JOIN model_families mf ON mf.model_key = mv.model_key
    LEFT JOIN active_model_selections sel ON sel.device_id = :device_id
    WHERE mv.runtime_kind = 'artifact'
    ORDER BY mv.version
    """
)

_SET_SIM_ACTIVE = text(
    """
    UPDATE active_model_selections AS sel
    SET activation_id = ma.activation_id,
        model_version = ma.model_version
    FROM model_activations AS ma
    JOIN model_versions AS mv ON mv.version = ma.model_version
    WHERE sel.device_id = CAST(:device_id AS text)
      AND ma.device_id = CAST(:device_id AS text)
      AND ma.model_version = CAST(:model_version AS text)
      AND mv.runtime_kind = 'artifact'
      AND mv.is_selectable
      AND mv.schema_version = 'b02f3872_preview_v1'
      AND mv.channels = '["temperature_c", "relative_humidity_pct"]'::jsonb
      AND mv.window_size = 10
      AND mv.stride = 1
      AND mv.manifest_sha256 IS NOT NULL
    RETURNING sel.model_version
    """
)


async def sim_model_rows(
    connection: AsyncConnection,
    device_id: CorpusDeviceId,
) -> list[RowMapping]:
    result = await connection.execute(_SIM_MODELS, {"device_id": device_id})
    return cast(list[RowMapping], list(result.mappings()))


async def set_sim_active_model(
    connection: AsyncConnection,
    *,
    device_id: CorpusDeviceId,
    model_version: str,
) -> str | None:
    async with connection.begin():
        result = await connection.execute(
            _SET_SIM_ACTIVE,
            {"device_id": device_id, "model_version": model_version},
        )
        row = result.mappings().one_or_none()
    return cast(str, row["model_version"]) if row is not None else None


_SIM_MODEL_META = text(
    """
    SELECT version, window_size, threshold
    FROM model_versions
    WHERE version = :model_version AND runtime_kind = 'artifact'
    """
)

_SIM_WINDOW_SCORES = text(
    """
    SELECT source_start_index, source_end_index, score
    FROM inference_results
    WHERE device_id = :device_id AND model_version = :model_version
    ORDER BY source_start_index
    """
)

_SIM_EVENTS = text(
    """
    SELECT start_idx, end_idx_exclusive
    FROM injection_events
    WHERE device_id = :device_id
    ORDER BY start_idx
    """
)

_SIM_SEGMENTS = text(
    """
    SELECT min(corpus_index) AS seg_start, max(corpus_index) + 1 AS seg_end
    FROM telemetry
    WHERE device_id = :device_id
    GROUP BY segment_id
    ORDER BY seg_start
    """
)

_SIM_CORPUS_RANGE = text(
    """
    SELECT
        coalesce(max(corpus_index) + 1, 0) AS frame_count,
        min(ts) AS corpus_from,
        max(ts) AS corpus_to
    FROM telemetry
    WHERE device_id = :device_id
    """
)

_SIM_EVENT_TIMESTAMPS = text(
    """
    SELECT corpus_index, ts
    FROM telemetry
    WHERE device_id = :device_id AND corpus_index = ANY(:indices)
    """
)


async def sim_metrics_source(
    connection: AsyncConnection,
    *,
    device_id: CorpusDeviceId,
    model_version: str,
) -> dict[str, object] | None:
    meta = (
        await connection.execute(_SIM_MODEL_META, {"model_version": model_version})
    ).mappings().one_or_none()
    if meta is None:
        return None
    params = {"device_id": device_id, "model_version": model_version}
    windows = (await connection.execute(_SIM_WINDOW_SCORES, params)).all()
    events = (await connection.execute(_SIM_EVENTS, {"device_id": device_id})).all()
    segments = (await connection.execute(_SIM_SEGMENTS, {"device_id": device_id})).all()
    corpus = (
        await connection.execute(_SIM_CORPUS_RANGE, {"device_id": device_id})
    ).mappings().one()
    return {
        "window_size": int(meta["window_size"]),
        "threshold": float(meta["threshold"]),
        "frame_count": int(corpus["frame_count"]),
        "corpus_from": corpus["corpus_from"],
        "corpus_to": corpus["corpus_to"],
        "window_rows": [(r[0], r[1], r[2]) for r in windows],
        "event_rows": [(r[0], r[1]) for r in events],
        "segment_rows": [(r[0], r[1]) for r in segments],
    }


async def sim_event_start_timestamps(
    connection: AsyncConnection,
    *,
    device_id: CorpusDeviceId,
    indices: list[int],
) -> dict[int, datetime]:
    if not indices:
        return {}
    rows = (
        await connection.execute(
            _SIM_EVENT_TIMESTAMPS, {"device_id": device_id, "indices": indices}
        )
    ).all()
    return {int(r[0]): cast(datetime, r[1]) for r in rows}
