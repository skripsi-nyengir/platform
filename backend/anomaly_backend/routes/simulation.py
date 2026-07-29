from typing import Annotated, cast

from fastapi import APIRouter, Depends
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    CorpusDeviceId,
    SetSimActiveModelRequest,
    SetSimActiveModelResponse,
    SimModel,
    SimModelsResponse,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import NotFound, new_request_id
from anomaly_backend.sql import set_sim_active_model, sim_model_rows


router = APIRouter()

_SIM_DEVICE_ID: CorpusDeviceId = "b02f3872-simulasi-injeksi"


@router.get("/api/simulation/models", response_model=SimModelsResponse)
async def simulation_models(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> SimModelsResponse:
    rows = await sim_model_rows(connection, _SIM_DEVICE_ID)
    return SimModelsResponse(
        request_id=new_request_id(),
        device_id=_SIM_DEVICE_ID,
        models=[_model(row) for row in rows],
    )


@router.post("/api/simulation/active-model", response_model=SetSimActiveModelResponse)
async def set_active_model(
    request: SetSimActiveModelRequest,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> SetSimActiveModelResponse:
    active = await set_sim_active_model(
        connection, device_id=_SIM_DEVICE_ID, model_version=request.model_version
    )
    if active is None:
        raise NotFound("The artifact model was not found for the simulation device")
    return SetSimActiveModelResponse(
        request_id=new_request_id(),
        device_id=_SIM_DEVICE_ID,
        active_model_version=active,
    )


def _model(row: RowMapping) -> SimModel:
    return SimModel(
        version=cast(str, row["version"]),
        model_key=cast(str, row["model_key"]),
        display_name=cast(str, row["display_name"]),
        score_key=cast(str, row["score_key"]),
        threshold=cast(float, row["threshold"]),
        manifest_sha256=cast(str, row["manifest_sha256"]),
        is_active=bool(row["is_active"]),
    )
