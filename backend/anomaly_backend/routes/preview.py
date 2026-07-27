from __future__ import annotations

from datetime import datetime
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.contracts import (
    DeviceItem,
    DevicesResponse,
    ModelActivation,
    ModelActivationRequest,
    ModelActivationResponse,
    ModelsResponse,
    PublicModelFamily,
    PublicModelVersion,
    ReplayJobItem,
    ReplayJobRequest,
    ReplayJobResponse,
    ReplayJobStatusResponse,
    SensorId,
    format_historical_datetime,
    format_operational_instant,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import InvalidQuery, NotFound, new_request_id
from anomaly_backend.sql.preview import (
    PUBLIC_CHANNELS,
    PUBLIC_TIME_ZONE,
    activate_model,
    active_device_rows,
    estimated_replay_results,
    public_model_rows,
    replay_job_row,
    submit_replay_job,
)


router = APIRouter()
_MODEL_ORDER = {
    model_key: position
    for position, model_key in enumerate(
        (
            "ewma",
            "pca",
            "wsn-dense-ae",
            "lstm-ae",
            "usad",
            "cfc-autoencoder",
            "mtad-gat",
        )
    )
}


def _operational(row: RowMapping, field: str) -> str | None:
    value = cast(datetime | None, row[field])
    return format_operational_instant(value) if value is not None else None


async def _replay_item(
    connection: AsyncConnection, row: RowMapping
) -> ReplayJobItem:
    estimated = await estimated_replay_results(connection, row)
    result_count = int(row["result_count"])
    status = cast(str, row["status"])
    if status == "succeeded":
        progress = 1.0
    elif estimated <= 0:
        progress = 0.0
    else:
        progress = min(
            0.999 if status == "running" else 1.0,
            result_count / estimated,
        )
    return ReplayJobItem.model_validate(
        {
            "job_id": row["job_id"],
            "device_id": row["device_id"],
            "from": format_historical_datetime(
                cast(datetime, row["from_ts"])
            ),
            "to": format_historical_datetime(cast(datetime, row["to_ts"])),
            "time_zone": PUBLIC_TIME_ZONE,
            "model_version": row["model_version"],
            "activation_id": row["activation_id"],
            "score_provenance": row["score_provenance"],
            "status": status,
            "progress": progress,
            "processed_count": int(row["processed_count"]),
            "result_count": result_count,
            "episode_count": int(row["episode_count"]),
            "submitted_at": _operational(row, "submitted_at"),
            "started_at": _operational(row, "started_at"),
            "completed_at": _operational(row, "completed_at"),
            "error_code": row["error_code"],
            "error_detail": row["error_detail"],
        },
        strict=True,
    )


@router.get("/api/devices", response_model=DevicesResponse)
async def devices(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> DevicesResponse:
    rows = await active_device_rows(connection)
    items: list[DeviceItem] = []
    for row in rows:
        status = cast(str | None, row["corpus_status"])
        readiness = {
            None: "pending",
            "staging": "importing",
            "published": "ready",
            "failed": "failed",
        }[status]
        interval_start = cast(datetime | None, row["interval_start"])
        interval_end = cast(datetime | None, row["interval_end"])
        items.append(
            DeviceItem.model_validate(
                {
                    "device_id": row["device_id"],
                    "display_name": "TALPHA Ruang Produksi",
                    "time_zone": "Asia/Jakarta",
                    "channels": PUBLIC_CHANNELS,
                    "corpus_from": (
                    format_historical_datetime(interval_start)
                    if interval_start is not None
                    else None
                ),
                    "corpus_to": (
                    format_historical_datetime(interval_end)
                    if interval_end is not None
                    else None
                ),
                    "import_readiness": readiness,
                },
                strict=True,
            )
        )
    return DevicesResponse(request_id=new_request_id(), items=items)


@router.get("/api/models", response_model=ModelsResponse)
async def models(
    device_id: Annotated[SensorId, Query()],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> ModelsResponse:
    selection, rows = await public_model_rows(connection, device_id)
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        model_key = cast(str, row["model_key"])
        family = grouped.setdefault(
            model_key,
            {
                "model_key": model_key,
                "display_name": row["display_name"],
                "artifact_status": (
                    "ready" if row["artifact_ready"] else "pending"
                ),
                "versions": [],
            },
        )
        runtime_kind = cast(str, row["runtime_kind"])
        compatible = (
            row["schema_version"] == "b02f3872_preview_v1"
            and tuple(row["channels"]) == PUBLIC_CHANNELS
            and row["window_size"] == 30
            and row["stride"] == 1
        )
        versions = cast(list[PublicModelVersion], family["versions"])
        versions.append(
            PublicModelVersion.model_validate(
                {
                    "version": row["version"],
                    "runtime_kind": runtime_kind,
                    "selectable": (
                        row["is_selectable"]
                        and runtime_kind == "preview_simulator"
                    ),
                    "compatible": compatible,
                    "artifact_status": (
                    "ready" if row["artifact_ready"] else "pending"
                ),
                    "score_provenance": (
                    "artifact_backed"
                    if runtime_kind == "artifact"
                    else "simulated_preview"
                ),
                },
                strict=True,
            )
        )
    families = [
        PublicModelFamily.model_validate(value, strict=True)
        for _, value in sorted(
            grouped.items(),
            key=lambda item: _MODEL_ORDER[item[0]],
        )
    ]
    return ModelsResponse(
        request_id=new_request_id(),
        device_id=device_id,
        active_activation_id=cast(str, selection["activation_id"]),
        active_model_version=cast(str, selection["model_version"]),
        families=families,
    )


@router.post(
    "/api/model-activations", response_model=ModelActivationResponse
)
async def model_activation(
    request: ModelActivationRequest,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> ModelActivationResponse:
    row, active_version, idempotent = await activate_model(
        connection,
        command_id=request.command_id,
        device_id=request.device_id,
        model_version=request.model_version,
    )
    activation = ModelActivation(
        activation_id=cast(str, row["activation_id"]),
        command_id=cast(str, row["command_id"]),
        device_id=cast(SensorId, row["device_id"]),
        prior_model_version=cast(str | None, row["prior_model_version"]),
        model_version=cast(str, row["model_version"]),
        changed=cast(bool, row["changed"]),
        activated_at=format_operational_instant(
            cast(datetime, row["activated_at"])
        ),
        actor=cast(str, row["actor"]),
    )
    return ModelActivationResponse(
        request_id=new_request_id(),
        activation=activation,
        active_model_version=active_version,
        idempotent_request_replay=idempotent,
    )


@router.post("/api/replay-jobs", response_model=ReplayJobResponse)
async def create_replay_job(
    request: ReplayJobRequest,
    response: Response,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> ReplayJobResponse:
    from_ts = datetime.fromisoformat(request.from_ts)
    to_ts = datetime.fromisoformat(request.to_ts)
    if from_ts >= to_ts:
        raise InvalidQuery(
            "Replay from must be earlier than to",
            errors={"from": ["Must be earlier than to"]},
        )
    if (to_ts - from_ts).total_seconds() > 31 * 86_400:
        raise InvalidQuery(
            "Replay interval must not exceed 31 days",
            errors={"to": ["Must be at most 31 days after from"]},
        )
    row, idempotent = await submit_replay_job(
        connection,
        command_id=request.command_id,
        device_id=request.device_id,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    response.status_code = 200 if idempotent else 202
    return ReplayJobResponse(
        request_id=new_request_id(),
        job=await _replay_item(connection, row),
        idempotent_request_replay=idempotent,
    )


@router.get(
    "/api/replay-jobs/{job_id}", response_model=ReplayJobStatusResponse
)
async def replay_job(
    job_id: str,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> ReplayJobStatusResponse:
    row = await replay_job_row(connection, job_id)
    if row is None:
        raise NotFound("The replay job was not found")
    return ReplayJobStatusResponse(
        request_id=new_request_id(),
        job=await _replay_item(connection, row),
    )
