from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.contracts import (
    LivenessResponse,
    ReadinessDependency,
    ReadinessResponse,
    SystemServiceStatus,
    SystemStatusResponse,
    SystemTelemetryStatus,
    current_operational_instant,
    format_historical_datetime,
)
from anomaly_backend.db import (
    current_migration_revision,
    database_is_healthy,
    get_connection,
)
from anomaly_backend.problems import DependencyFailure, new_request_id
from anomaly_backend.sql.system import telemetry_observation


_EXPECTED_REVISION = "20260726_0003"

router = APIRouter()


@router.get("/health", response_model=LivenessResponse)
async def health() -> LivenessResponse:
    return LivenessResponse(
        status="alive",
        request_id=new_request_id(),
        checked_at=current_operational_instant(),
    )


@router.get("/ready", response_model=ReadinessResponse)
async def ready(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> ReadinessResponse:
    if not await database_is_healthy(connection):
        raise DependencyFailure("Database connectivity check failed")
    revision = await current_migration_revision(connection)
    if revision != _EXPECTED_REVISION:
        raise DependencyFailure("Database migration revision is not current")
    return ReadinessResponse(
        status="ready",
        request_id=new_request_id(),
        checked_at=current_operational_instant(),
        dependencies=[
            ReadinessDependency(
                name="database",
                status="ready",
                detail="Database connectivity verified",
            ),
            ReadinessDependency(
                name="migration",
                status="ready",
                detail=f"Database revision {_EXPECTED_REVISION} is current",
            ),
        ],
    )


@router.get("/api/system/status", response_model=SystemStatusResponse)
async def system_status(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> SystemStatusResponse:
    checked_at = current_operational_instant()
    database_healthy = await database_is_healthy(connection)
    revision = await current_migration_revision(connection)
    latest_ts, fresh_count, stale_count, offline_count = (
        await telemetry_observation(connection)
    )
    database_ready = database_healthy and revision == _EXPECTED_REVISION
    published_count = int(
        await connection.scalar(
            select(func.count()).select_from(tables.published_corpora)
        )
        or 0
    )
    import_status = await connection.scalar(
        select(tables.corpora.c.status)
        .join(
            tables.published_corpora,
            tables.published_corpora.c.corpus_id
            == tables.corpora.c.corpus_id,
        )
        .where(
            tables.published_corpora.c.device_id
            == "b02f3872-ruang-produksi"
        )
    )
    worker_heartbeat = await connection.scalar(
        select(func.max(tables.worker_heartbeats.c.heartbeat_at))
    )
    active_version = await connection.scalar(
        select(tables.active_model_selections.c.model_version).where(
            tables.active_model_selections.c.device_id
            == "b02f3872-ruang-produksi"
        )
    )
    ready_artifacts = int(
        await connection.scalar(
            select(func.count()).select_from(tables.model_versions).where(
                tables.model_versions.c.runtime_kind == "artifact",
                tables.model_versions.c.is_selectable,
            )
        )
        or 0
    )
    return SystemStatusResponse(
        request_id=new_request_id(),
        checked_at=checked_at,
        overall_observation=(
            "API/DB siap; telemetri, worker preview, pilihan model, dan "
            "artifact dilaporkan sebagai status terpisah."
        ),
        services=[
            SystemServiceStatus(
                name="api",
                liveness="alive",
                readiness="ready",
                checked_at=checked_at,
                detail="API request handling observed",
            ),
            SystemServiceStatus(
                name="database",
                liveness="alive" if database_healthy else "not_alive",
                readiness="ready" if database_ready else "not_ready",
                checked_at=checked_at,
                detail=(
                    f"Database connectivity and revision {_EXPECTED_REVISION} observed"
                    if database_ready
                    else "Database connectivity or current revision was not observed"
                ),
            ),
            SystemServiceStatus(
                name="telemetry-import",
                liveness="alive" if published_count else "unknown",
                readiness="ready" if import_status == "published" else "not_ready",
                checked_at=checked_at,
                detail=(
                    "Corpus telemetri nyata telah dipublikasikan"
                    if import_status == "published"
                    else "Import telemetri nyata belum siap"
                ),
            ),
            SystemServiceStatus(
                name="preview-worker",
                liveness="alive" if worker_heartbeat is not None else "unknown",
                readiness="ready" if worker_heartbeat is not None else "not_ready",
                checked_at=checked_at,
                detail=(
                    "Heartbeat worker preview teramati"
                    if worker_heartbeat is not None
                    else "Worker preview belum mengirim heartbeat"
                ),
            ),
            SystemServiceStatus(
                name="active-selection",
                liveness="alive",
                readiness="ready" if active_version is not None else "not_ready",
                checked_at=checked_at,
                detail=(
                    f"{active_version} dipilih untuk replay berikutnya"
                    if active_version is not None
                    else "Belum ada model yang dipilih untuk replay"
                ),
            ),
            SystemServiceStatus(
                name="artifact-readiness",
                liveness="unknown",
                readiness="ready" if ready_artifacts == 7 else "not_ready",
                checked_at=checked_at,
                detail=(
                    f"{ready_artifacts}/7 artifact asli siap; "
                    "skor preview tetap berlabel simulasi"
                ),
            ),
        ],
        telemetry=SystemTelemetryStatus(
            latest_ts=(
                format_historical_datetime(latest_ts)
                if latest_ts is not None
                else None
            ),
            age_seconds=0.0 if latest_ts is not None else None,
            fresh_sensor_count=fresh_count,
            stale_sensor_count=stale_count,
            offline_sensor_count=offline_count,
        ),
        diagnostics={
            "preview_score_provenance": "simulated_preview",
            "published_corpus_count": published_count,
            "selected_model_version": active_version,
            "ready_artifact_family_count": ready_artifacts,
        },
    )
