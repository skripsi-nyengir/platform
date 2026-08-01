from datetime import datetime, timezone
import string
from typing import cast
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.sql.live import LIVE_DEVICE_ID


_JAKARTA = ZoneInfo("Asia/Jakarta")
_HASH_FIELDS = (
    "model_manifest_sha256",
    "checkpoint_sha256",
    "scaler_manifest_sha256",
    "scaler_sha256",
)


def _valid_hash(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in string.hexdigits.lower() for character in value)
    )


async def telemetry_observation(
    connection: AsyncConnection,
) -> dict[str, object]:
    now_utc = cast(datetime, await connection.scalar(select(func.clock_timestamp())))
    latest = (
        await connection.execute(
            select(tables.live_telemetry)
            .where(tables.live_telemetry.c.device_id == LIVE_DEVICE_ID)
            .order_by(
                tables.live_telemetry.c.received_at_utc.desc(),
                tables.live_telemetry.c.ingress_sequence.desc(),
            )
            .limit(1)
        )
    ).mappings().one_or_none()
    if latest is None:
        historical_ts = cast(
            datetime | None,
            await connection.scalar(
                select(func.max(tables.telemetry.c.ts)).where(
                    tables.telemetry.c.device_id == LIVE_DEVICE_ID
                )
            ),
        )
        latest_ts = historical_ts
        last_valid_at = (
            historical_ts.replace(tzinfo=_JAKARTA).astimezone(timezone.utc)
            if historical_ts is not None
            else None
        )
    else:
        latest_ts = cast(datetime, latest["received_ts"])
        last_valid_at = cast(datetime, latest["received_at_utc"])

    lease = (
        await connection.execute(
            select(tables.live_writer_leases).where(
                tables.live_writer_leases.c.device_id == LIVE_DEVICE_ID
            )
        )
    ).mappings().one_or_none()
    health = (
        await connection.execute(
            select(tables.live_health).where(
                tables.live_health.c.device_id == LIVE_DEVICE_ID
            )
        )
    ).mappings().one_or_none()
    selection = (
        await connection.execute(
            select(
                tables.live_model_selections.c.activation_id,
                tables.live_model_pairs.c.model_version,
                tables.live_model_pairs.c.scaler_snapshot_corpus_id,
                tables.live_model_pairs.c.contract_status,
                *(tables.live_model_pairs.c[name] for name in _HASH_FIELDS),
            )
            .join(
                tables.live_model_pairs,
                tables.live_model_pairs.c.model_pair_id
                == tables.live_model_selections.c.model_pair_id,
            )
            .where(tables.live_model_selections.c.device_id == LIVE_DEVICE_ID)
        )
    ).mappings().one_or_none()
    cursor = (
        await connection.execute(
            select(tables.live_cursors).where(
                tables.live_cursors.c.device_id == LIVE_DEVICE_ID
            )
        )
    ).mappings().one_or_none()
    cursor_boundary = (
        cast(int, cursor["last_boundary_id"])
        if cursor is not None and cursor["last_boundary_id"] is not None
        else 0
    )
    pending_boundary_count = int(
        await connection.scalar(
            select(func.count())
            .select_from(tables.live_processing_boundaries)
            .where(
                tables.live_processing_boundaries.c.device_id == LIVE_DEVICE_ID,
                tables.live_processing_boundaries.c.boundary_id > cursor_boundary,
            )
        )
        or 0
    )
    durable_backlog_count = int(
        await connection.scalar(
            select(func.count())
            .select_from(tables.live_telemetry)
            .where(
                tables.live_telemetry.c.device_id == LIVE_DEVICE_ID,
                tables.live_telemetry.c.processing_status == "pending",
            )
        )
        or 0
    )
    last_gap_at = cast(
        datetime | None,
        await connection.scalar(
            select(func.max(tables.live_processing_boundaries.c.recorded_at_utc)).where(
                tables.live_processing_boundaries.c.device_id == LIVE_DEVICE_ID,
                tables.live_processing_boundaries.c.boundary_reason == "data_gap",
            )
        ),
    )
    hashes = (
        {name: cast(str, selection[name]) for name in _HASH_FIELDS}
        if selection is not None
        else {}
    )
    configuration_valid = bool(
        selection is not None
        and selection["contract_status"] == "live_10"
        and all(_valid_hash(value) for value in hashes.values())
        and len(hashes) == len(_HASH_FIELDS)
    )
    lease_active = bool(
        lease is not None and cast(datetime, lease["lease_expires_at_utc"]) > now_utc
    )
    age_seconds = (
        max(0.0, (now_utc - last_valid_at).total_seconds())
        if last_valid_at is not None
        else None
    )
    health_detail = cast(str | None, health["detail_code"]) if health else None
    return {
        "now_utc": now_utc,
        "latest_ts": latest_ts,
        "last_valid_at": last_valid_at,
        "age_seconds": age_seconds,
        "lease_active": lease_active,
        "fencing_token": cast(int, lease["fencing_token"]) if lease else None,
        "database_heartbeat": cast(datetime, lease["updated_at_utc"]) if lease else None,
        "health_status": cast(str, health["status"]) if health else None,
        "health_detail": health_detail,
        "last_persistence_failure_at": (
            cast(datetime, health["observed_at_utc"])
            if health is not None and health_detail == "persistence_retry"
            else None
        ),
        "last_gap_at": last_gap_at,
        "pending_boundary_count": pending_boundary_count,
        "durable_backlog_count": durable_backlog_count,
        "cursor_ts": cast(datetime, cursor["received_ts"]) if cursor and cursor["received_ts"] else None,
        "cursor_id": str(cursor["telemetry_id"]) if cursor and cursor["telemetry_id"] else None,
        "configuration_valid": configuration_valid,
        "active_model_version": cast(str, selection["model_version"]) if selection else None,
        "active_scaler_corpus_id": (
            cast(str, selection["scaler_snapshot_corpus_id"]) if selection else None
        ),
        "artifact_hashes": hashes,
    }
