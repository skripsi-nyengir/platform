from datetime import datetime
import re
from typing import Annotated, cast

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
    format_operational_instant,
)
from anomaly_backend.db import (
    current_migration_revision,
    database_is_healthy,
    get_connection,
)
from anomaly_backend.problems import DependencyFailure, new_request_id
from anomaly_backend.sql.system import telemetry_observation


_MINIMUM_REVISION = "20260807_0016"
_REVISION_PATTERN = re.compile(r"^\d{8}_(\d{4})$")
_STALL_BACKLOG_THRESHOLD = 100

router = APIRouter()


def _revision_ordinal(revision: str | None) -> int | None:
    if revision is None or (match := _REVISION_PATTERN.fullmatch(revision)) is None:
        return None
    return int(match.group(1))


def _revision_is_compatible(
    actual_revision: str | None,
    minimum_revision: str = _MINIMUM_REVISION,
) -> bool:
    actual = _revision_ordinal(actual_revision)
    minimum = _revision_ordinal(minimum_revision)
    return actual is not None and minimum is not None and actual >= minimum


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
    if not _revision_is_compatible(revision):
        raise DependencyFailure(
            "Database migration revision is malformed, branched, or older than required"
        )
    assert revision is not None
    return ReadinessResponse(
        status="ready",
        request_id=new_request_id(),
        checked_at=current_operational_instant(),
        database_revision=revision,
        minimum_database_revision=_MINIMUM_REVISION,
        dependencies=[
            ReadinessDependency(
                name="database",
                status="ready",
                detail="Database connectivity verified",
            ),
            ReadinessDependency(
                name="migration",
                status="ready",
                detail=(
                    f"Database revision {revision} satisfies minimum "
                    f"{_MINIMUM_REVISION}"
                ),
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
    observation = await telemetry_observation(connection)
    database_ready = database_healthy and _revision_is_compatible(revision)
    worker_heartbeat = await connection.scalar(
        select(func.max(tables.worker_heartbeats.c.heartbeat_at))
    )
    active_version = observation["active_model_version"]
    latest_ts = cast(datetime | None, observation["latest_ts"])
    age_seconds = cast(float | None, observation["age_seconds"])
    configuration_valid = cast(bool, observation["configuration_valid"])
    lease_active = cast(bool, observation["lease_active"])
    health_status = cast(str | None, observation["health_status"])
    health_detail = cast(str | None, observation["health_detail"])
    fresh = age_seconds is not None and age_seconds <= 600
    durable_backlog = cast(int, observation["durable_backlog_count"])
    scoring_stalled = fresh and durable_backlog > _STALL_BACKLOG_THRESHOLD
    reasons: list[str] = []
    if not configuration_valid:
        reasons.append("Activate a verified live model and scaler bundle.")
    if not lease_active:
        reasons.append("Start the live subscriber or restore its database lease.")
    if age_seconds is None:
        reasons.append("No valid telemetry reading has been persisted.")
    elif not fresh:
        reasons.append("Check broker delivery because the latest valid reading is stale.")
    if scoring_stalled:
        reasons.append(
            f"Live scoring is stalled: {durable_backlog} readings are persisted but unscored."
        )
    detail_reasons = {
        "persistence_retry": "Restore database writes; live persistence is retrying.",
        "inference_retry": "Restore the active model runtime; inference is retrying.",
        "watchdog_retry": "Restore the live watchdog dependency; it is retrying.",
    }
    if health_detail in detail_reasons:
        reasons.append(detail_reasons[health_detail])
    if health_status == "unhealthy":
        classification = "failed"
    elif (
        configuration_valid
        and lease_active
        and fresh
        and health_status == "healthy"
        and not scoring_stalled
    ):
        classification = "healthy"
    else:
        classification = "degraded"
    connection_state = (
        "subscribed"
        if lease_active and health_status == "healthy"
        else "connected"
        if lease_active
        else "disconnected"
    )
    subscriber_ready = (
        configuration_valid
        and lease_active
        and health_status == "healthy"
        and not scoring_stalled
    )
    subscriber_detail = (
        "Live subscriber lease, broker connection, and model are ready"
        if subscriber_ready
        else "Activate a verified live model and scaler bundle."
        if not configuration_valid
        else "Start the live subscriber or restore its database lease."
        if not lease_active
        else "Restore the live subscriber health dependency."
        if health_status != "healthy"
        else f"Live scoring is stalled with {durable_backlog} queued readings."
    )
    return SystemStatusResponse(
        request_id=new_request_id(),
        checked_at=checked_at,
        overall_observation=(
            "Live telemetry is healthy."
            if not reasons
            else " ".join(reasons)
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
                    f"Database connectivity and compatible revision {revision} observed"
                    if database_ready
                    else (
                        "Database connectivity or minimum revision "
                        f"{_MINIMUM_REVISION} was not observed"
                    )
                ),
            ),
            SystemServiceStatus(
                name="live-subscriber",
                liveness="alive" if lease_active else "not_alive",
                readiness="ready" if subscriber_ready else "not_ready",
                checked_at=checked_at,
                detail=subscriber_detail,
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
        ],
        telemetry=SystemTelemetryStatus(
            classification=classification,
            reasons=reasons,
            configuration_valid=configuration_valid,
            lease_active=lease_active,
            fencing_token=cast(int | None, observation["fencing_token"]),
            database_heartbeat=(
                format_operational_instant(value)
                if (value := cast(datetime | None, observation["database_heartbeat"]))
                else None
            ),
            connection_state=connection_state,
            connack_received=connection_state in ("connected", "subscribed"),
            suback_received=connection_state == "subscribed",
            latest_ts=format_historical_datetime(latest_ts) if latest_ts else None,
            last_valid_reading_ts=(
                format_historical_datetime(latest_ts) if latest_ts else None
            ),
            last_valid_reading_at=(
                format_operational_instant(value)
                if (value := cast(datetime | None, observation["last_valid_at"]))
                else None
            ),
            age_seconds=age_seconds,
            last_gap_at=(
                format_operational_instant(value)
                if (value := cast(datetime | None, observation["last_gap_at"]))
                else None
            ),
            invalid_message_count=None,
            retained_message_count=None,
            last_persistence_failure_at=(
                format_operational_instant(value)
                if (
                    value := cast(
                        datetime | None,
                        observation["last_persistence_failure_at"],
                    )
                )
                else None
            ),
            ingress_queue_depth=None,
            dropped_newest_count=None,
            pending_boundary_count=cast(
                int, observation["pending_boundary_count"]
            ),
            durable_backlog_count=cast(int, observation["durable_backlog_count"]),
            cursor_ts=(
                format_historical_datetime(value)
                if (value := cast(datetime | None, observation["cursor_ts"]))
                else None
            ),
            cursor_id=cast(str | None, observation["cursor_id"]),
            recovery_ready=configuration_valid and lease_active,
            active_model_version=cast(
                str | None, observation["active_model_version"]
            ),
            active_scaler_corpus_id=cast(
                str | None, observation["active_scaler_corpus_id"]
            ),
            artifact_hashes=cast(dict[str, str], observation["artifact_hashes"]),
            retry_state=(
                "retrying"
                if health_detail is not None and health_detail.endswith("_retry")
                else "idle"
                if health_status is not None
                else "unknown"
            ),
            fresh_sensor_count=1 if fresh else 0,
            stale_sensor_count=1 if age_seconds is not None and not fresh else 0,
            offline_sensor_count=1 if age_seconds is None else 0,
        ),
        diagnostics={
            "preview_score_provenance": "simulated_preview",
            "selected_model_version": active_version,
            "live_health_status": health_status,
        },
    )
