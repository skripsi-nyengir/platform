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
    WHERE sel.device_id = CAST(:device_id AS text)
      AND ma.device_id = CAST(:device_id AS text)
      AND ma.model_version = CAST(:model_version AS text)
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
