from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    CorpusDeviceId,
    ScopeMetricsModel,
    SetSimActiveModelRequest,
    SetSimActiveModelResponse,
    SimAlertEventModel,
    SimMetricsResponse,
    SimModel,
    SimModelsResponse,
)
from anomaly_backend.db import get_connection
from anomaly_backend.evaluation import ScopeMetrics
from anomaly_backend.problems import NotFound, new_request_id
from anomaly_backend.sim_metrics import assemble_sim_metrics
from anomaly_backend.sql import set_sim_active_model, sim_metrics_source, sim_model_rows


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


@router.get("/api/simulation/metrics", response_model=SimMetricsResponse)
async def simulation_metrics(
    model_version: Annotated[str, Query(min_length=1)],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    cooldown_samples: Annotated[int, Query(ge=1)] = 10,
) -> SimMetricsResponse:
    source = await sim_metrics_source(
        connection, device_id=_SIM_DEVICE_ID, model_version=model_version
    )
    if source is None:
        raise NotFound("The artifact model was not found for the simulation device")
    if not source["window_rows"]:
        raise NotFound("No replay results exist for this model on the simulation device")
    metrics = assemble_sim_metrics(
        model_version=model_version,
        threshold=cast(float, source["threshold"]),
        window_size=cast(int, source["window_size"]),
        frame_count=cast(int, source["frame_count"]),
        window_rows=cast(list, source["window_rows"]),
        event_rows=cast(list, source["event_rows"]),
        segment_rows=cast(list, source["segment_rows"]),
        cooldown_samples=cooldown_samples,
    )
    return SimMetricsResponse(
        request_id=new_request_id(),
        device_id=_SIM_DEVICE_ID,
        model_version=metrics.model_version,
        threshold=metrics.threshold,
        window_size=metrics.window_size,
        frame_count=metrics.frame_count,
        event_count=metrics.event_count,
        scored_windows=metrics.scored_windows,
        timestamp_scope=_scope(metrics.timestamp),
        overlapping_scope=_scope(metrics.overlapping),
        bins_scope=_scope(metrics.bins),
        operational_event_count=metrics.operational_event_count,
        operational_events=[
            SimAlertEventModel(
                segment_id=event.segment_id,
                start_idx=event.start_idx,
                end_idx=event.end_idx,
                n_candidates=event.n_candidates,
                peak_score=event.peak_score,
            )
            for event in metrics.operational_events
        ],
    )


def _scope(metrics: ScopeMetrics) -> ScopeMetricsModel:
    return ScopeMetricsModel(
        scope=metrics.scope,
        precision=metrics.precision,
        recall=metrics.recall,
        f1=metrics.f1,
        accuracy=metrics.accuracy,
        tn=metrics.tn,
        fp=metrics.fp,
        fn=metrics.fn,
        tp=metrics.tp,
        n_evaluated=metrics.n_evaluated,
        n_anomalous=metrics.n_anomalous,
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
