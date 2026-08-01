from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
import hashlib
import re
from typing import Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables


LIVE_DEVICE_ID = "b02f3872-ruang-produksi"
BoundaryReason = Literal[
    "startup", "data_gap", "model_change", "overload", "lease_takeover"
]
HealthStatus = Literal["healthy", "degraded", "unhealthy"]
Severity = Literal["info", "warning", "critical"]
EpisodeCloseReason = Literal[
    "normal_recovery",
    "startup",
    "data_gap",
    "model_change",
    "overload",
    "lease_takeover",
]
TelemetryKey = tuple[datetime, UUID]
_DETAIL_CODE = re.compile(r"[a-z0-9_]{1,64}")


class LiveLeaseLost(RuntimeError):
    pass


class LiveWindowDesyncError(ValueError):
    pass


async def _database_now(connection: AsyncConnection) -> datetime:
    return cast(datetime, await connection.scalar(select(func.clock_timestamp())))


async def _require_lease(
    connection: AsyncConnection,
    *,
    device_id: str,
    fencing_token: int,
) -> RowMapping:
    lease = (
        (
            await connection.execute(
                select(tables.live_writer_leases)
                .where(
                    tables.live_writer_leases.c.device_id == device_id,
                    tables.live_writer_leases.c.fencing_token == fencing_token,
                    tables.live_writer_leases.c.lease_expires_at_utc
                    > func.clock_timestamp(),
                )
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if lease is None:
        raise LiveLeaseLost("live writer lease is expired or fenced")
    return lease


def _validate_health(status: HealthStatus, detail_code: str | None) -> None:
    if detail_code is not None and _DETAIL_CODE.fullmatch(detail_code) is None:
        raise ValueError("detail_code must be a sanitized lowercase identifier")
    if status not in ("healthy", "degraded", "unhealthy"):
        raise ValueError("invalid live health status")


async def _write_live_health(
    connection: AsyncConnection,
    *,
    device_id: str,
    status: HealthStatus,
    detail_code: str | None,
    fencing_token: int,
) -> RowMapping:
    _validate_health(status, detail_code)
    return (
        (
            await connection.execute(
                pg_insert(tables.live_health)
                .values(
                    device_id=device_id,
                    status=status,
                    detail_code=detail_code,
                    fencing_token=fencing_token,
                    observed_at_utc=func.clock_timestamp(),
                )
                .on_conflict_do_update(
                    index_elements=["device_id"],
                    set_={
                        "status": status,
                        "detail_code": detail_code,
                        "fencing_token": fencing_token,
                        "observed_at_utc": func.clock_timestamp(),
                    },
                )
                .returning(*tables.live_health.c)
            )
        )
        .mappings()
        .one()
    )


async def _close_live_episode(
    connection: AsyncConnection,
    *,
    device_id: str,
    live_episode_id: UUID,
    close_reason: EpisodeCloseReason,
    ended_score_ts: datetime | None,
) -> bool:
    episode = (
        (
            await connection.execute(
                select(tables.live_alert_episodes)
                .where(
                    tables.live_alert_episodes.c.live_episode_id == live_episode_id,
                    tables.live_alert_episodes.c.device_id == device_id,
                )
                .with_for_update()
            )
        )
        .mappings()
        .one()
    )
    if episode["status"] == "resolved":
        return False
    effective_end = ended_score_ts or cast(
        datetime | None,
        await connection.scalar(
            select(func.max(tables.live_alert_episode_points.c.score_ts)).where(
                tables.live_alert_episode_points.c.live_episode_id == live_episode_id
            )
        ),
    )
    if effective_end is None:
        raise ValueError("live episode closure requires persisted context")
    await connection.execute(
        update(tables.live_alert_episodes)
        .where(tables.live_alert_episodes.c.live_episode_id == live_episode_id)
        .values(
            status="resolved",
            ended_score_ts=effective_end,
            close_reason=close_reason,
        )
    )
    await connection.execute(
        update(tables.alerts)
        .where(tables.alerts.c.alert_id == episode["alert_id"])
        .values(
            episode_end_ts=effective_end,
            closure_reason=("normal" if close_reason == "normal_recovery" else "gap"),
        )
    )
    return True


async def acquire_writer_lease(
    connection: AsyncConnection,
    *,
    device_id: str,
    lease_owner: str,
    lease_seconds: int,
) -> RowMapping | None:
    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")
    async with connection.begin():
        now = await _database_now(connection)
        created = (
            (
                await connection.execute(
                    pg_insert(tables.live_writer_leases)
                    .values(
                        device_id=device_id,
                        lease_owner=lease_owner,
                        lease_expires_at_utc=now + timedelta(seconds=lease_seconds),
                        fencing_token=1,
                        updated_at_utc=now,
                    )
                    .on_conflict_do_nothing(index_elements=["device_id"])
                    .returning(*tables.live_writer_leases.c)
                )
            )
            .mappings()
            .one_or_none()
        )
        if created is not None:
            return created

        current = (
            (
                await connection.execute(
                    select(tables.live_writer_leases)
                    .where(tables.live_writer_leases.c.device_id == device_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one()
        )
        active = current["lease_expires_at_utc"] > now
        if active:
            return None
        fencing_token = cast(int, current["fencing_token"]) + 1
        return (
            (
                await connection.execute(
                    update(tables.live_writer_leases)
                    .where(tables.live_writer_leases.c.device_id == device_id)
                    .values(
                        lease_owner=lease_owner,
                        lease_expires_at_utc=now + timedelta(seconds=lease_seconds),
                        fencing_token=fencing_token,
                        updated_at_utc=now,
                    )
                    .returning(*tables.live_writer_leases.c)
                )
            )
            .mappings()
            .one()
        )


async def renew_writer_lease(
    connection: AsyncConnection,
    *,
    device_id: str,
    lease_owner: str,
    fencing_token: int,
    lease_seconds: int,
) -> RowMapping | None:
    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")
    async with connection.begin():
        now = await _database_now(connection)
        return (
            (
                await connection.execute(
                    update(tables.live_writer_leases)
                    .where(
                        tables.live_writer_leases.c.device_id == device_id,
                        tables.live_writer_leases.c.lease_owner == lease_owner,
                        tables.live_writer_leases.c.fencing_token == fencing_token,
                        tables.live_writer_leases.c.lease_expires_at_utc >= now,
                    )
                    .values(
                        lease_expires_at_utc=now + timedelta(seconds=lease_seconds),
                        updated_at_utc=now,
                    )
                    .returning(*tables.live_writer_leases.c)
                )
            )
            .mappings()
            .one_or_none()
        )


async def release_writer_lease(
    connection: AsyncConnection,
    *,
    device_id: str,
    lease_owner: str,
    fencing_token: int,
) -> bool:
    async with connection.begin():
        now = await _database_now(connection)
        released = await connection.execute(
            update(tables.live_writer_leases)
            .where(
                tables.live_writer_leases.c.device_id == device_id,
                tables.live_writer_leases.c.lease_owner == lease_owner,
                tables.live_writer_leases.c.fencing_token == fencing_token,
                tables.live_writer_leases.c.lease_expires_at_utc >= now,
            )
            .values(lease_expires_at_utc=now, updated_at_utc=now)
        )
        return released.rowcount == 1


async def live_selection_row(
    connection: AsyncConnection, *, device_id: str
) -> RowMapping | None:
    return (
        (
            await connection.execute(
                select(
                    *tables.live_model_selections.c,
                    tables.live_model_pairs.c.model_version,
                    tables.live_model_pairs.c.scaler_snapshot_corpus_id,
                    tables.live_model_pairs.c.threshold,
                    tables.live_model_pairs.c.model_manifest_sha256,
                    tables.live_model_pairs.c.checkpoint_sha256,
                    tables.live_model_pairs.c.scaler_manifest_sha256,
                    tables.live_model_pairs.c.scaler_sha256,
                )
                .join(
                    tables.live_model_pairs,
                    tables.live_model_pairs.c.model_pair_id
                    == tables.live_model_selections.c.model_pair_id,
                )
                .where(tables.live_model_selections.c.device_id == device_id)
            )
        )
        .mappings()
        .one_or_none()
    )


async def live_activation_row(
    connection: AsyncConnection,
    *,
    device_id: str,
    activation_id: int,
) -> RowMapping | None:
    return (
        (
            await connection.execute(
                select(
                    *tables.live_model_activations.c,
                    tables.live_model_pairs.c.model_version,
                    tables.live_model_pairs.c.scaler_snapshot_corpus_id,
                    tables.live_model_pairs.c.threshold,
                    tables.live_model_pairs.c.model_manifest_sha256,
                    tables.live_model_pairs.c.checkpoint_sha256,
                    tables.live_model_pairs.c.scaler_manifest_sha256,
                    tables.live_model_pairs.c.scaler_sha256,
                )
                .join(
                    tables.live_model_pairs,
                    tables.live_model_pairs.c.model_pair_id
                    == tables.live_model_activations.c.model_pair_id,
                )
                .where(
                    tables.live_model_activations.c.device_id == device_id,
                    tables.live_model_activations.c.activation_id == activation_id,
                )
            )
        )
        .mappings()
        .one_or_none()
    )


def _require_registered_values(
    row: RowMapping,
    values: Mapping[str, object],
    label: str,
) -> None:
    non_identity_timestamps = {"started_at", "completed_at", "created_at"}
    if any(
        row[key] != value
        for key, value in values.items()
        if key not in non_identity_timestamps
    ):
        raise ValueError(f"{label} already exists with different artifact values")


async def register_live_artifact(
    connection: AsyncConnection,
    *,
    corpus_values: Mapping[str, object],
    snapshot_values: Mapping[str, object],
    family_values: Mapping[str, object],
    version_values: Mapping[str, object],
    pair_values: Mapping[str, object],
) -> tuple[RowMapping, bool]:
    await connection.execute(
        pg_insert(tables.model_families)
        .values(**family_values)
        .on_conflict_do_nothing(index_elements=["model_key"])
    )
    family = (
        (
            await connection.execute(
                select(tables.model_families).where(
                    tables.model_families.c.model_key == family_values["model_key"]
                )
            )
        )
        .mappings()
        .one()
    )
    _require_registered_values(family, family_values, "artifact model family")

    for table, values, key, label in (
        (tables.corpora, corpus_values, "corpus_id", "artifact corpus"),
        (
            tables.preprocessing_snapshots,
            snapshot_values,
            "corpus_id",
            "artifact preprocessing snapshot",
        ),
        (tables.model_versions, version_values, "version", "artifact model version"),
    ):
        await connection.execute(
            pg_insert(table)
            .values(**values)
            .on_conflict_do_nothing(index_elements=[key])
        )
        row = (
            (await connection.execute(select(table).where(table.c[key] == values[key])))
            .mappings()
            .one()
        )
        _require_registered_values(row, values, label)

    inserted = (
        (
            await connection.execute(
                pg_insert(tables.live_model_pairs)
                .values(**pair_values)
                .on_conflict_do_nothing(constraint="uq_live_model_pairs_identity")
                .returning(*tables.live_model_pairs.c)
            )
        )
        .mappings()
        .one_or_none()
    )
    if inserted is not None:
        return inserted, True
    pair = (
        (
            await connection.execute(
                select(tables.live_model_pairs).where(
                    tables.live_model_pairs.c.model_version
                    == pair_values["model_version"],
                    tables.live_model_pairs.c.checkpoint_identity
                    == pair_values["checkpoint_identity"],
                    tables.live_model_pairs.c.scaler_snapshot_corpus_id
                    == pair_values["scaler_snapshot_corpus_id"],
                )
            )
        )
        .mappings()
        .one()
    )
    _require_registered_values(pair, pair_values, "live model pair")
    return pair, False


async def request_live_activation(
    connection: AsyncConnection,
    *,
    device_id: str,
    model_pair_id: UUID,
    requested_by: str,
    idempotency_key: str | None = None,
) -> tuple[RowMapping, bool]:
    request_identity = f"live-activation-v1|{device_id}|{model_pair_id}"
    if idempotency_key is not None:
        if not idempotency_key or idempotency_key.strip() != idempotency_key:
            raise ValueError("activation idempotency_key must be a non-empty string")
        request_identity = f"{request_identity}|{idempotency_key}"
    request_hash = hashlib.sha256(request_identity.encode()).hexdigest()
    inserted = (
        (
            await connection.execute(
                pg_insert(tables.live_model_activation_requests)
                .values(
                    device_id=device_id,
                    model_pair_id=model_pair_id,
                    request_hash=request_hash,
                    requested_by=requested_by,
                )
                .on_conflict_do_nothing(index_elements=["request_hash"])
                .returning(*tables.live_model_activation_requests.c)
            )
        )
        .mappings()
        .one_or_none()
    )
    if inserted is not None:
        return inserted, False
    existing = (
        (
            await connection.execute(
                select(tables.live_model_activation_requests).where(
                    tables.live_model_activation_requests.c.request_hash == request_hash
                )
            )
        )
        .mappings()
        .one()
    )
    if (
        existing["device_id"] != device_id
        or existing["model_pair_id"] != model_pair_id
        or existing["requested_by"] != requested_by
    ):
        raise ValueError("activation request hash has conflicting lineage")
    return existing, True


async def prepare_live_activation(
    connection: AsyncConnection,
    *,
    request_id: UUID,
    device_id: str,
    model_pair_id: UUID,
    fencing_token: int | None,
) -> tuple[RowMapping, bool]:
    request = (
        (
            await connection.execute(
                select(tables.live_model_activation_requests)
                .where(tables.live_model_activation_requests.c.request_id == request_id)
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if request is None:
        raise ValueError("live activation request does not exist")
    if request["device_id"] != device_id or request["model_pair_id"] != model_pair_id:
        raise ValueError("live activation request lineage does not match")

    existing = (
        (
            await connection.execute(
                select(tables.live_model_activations).where(
                    tables.live_model_activations.c.request_id == request_id
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if existing is not None:
        if fencing_token is not None:
            await _require_lease(
                connection,
                device_id=device_id,
                fencing_token=fencing_token,
            )
            if existing["fencing_token"] != fencing_token:
                raise LiveLeaseLost("prepared activation belongs to a stale writer")
        return existing, True

    if fencing_token is None:
        selection = (
            (
                await connection.execute(
                    select(tables.live_model_selections)
                    .where(tables.live_model_selections.c.device_id == device_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if selection is not None:
            raise ValueError(
                "bootstrap activation is allowed only before live selection"
            )
        effective_token = 1
    else:
        await _require_lease(
            connection,
            device_id=device_id,
            fencing_token=fencing_token,
        )
        effective_token = fencing_token

    activation = (
        (
            await connection.execute(
                insert(tables.live_model_activations)
                .values(
                    device_id=device_id,
                    request_id=request_id,
                    model_pair_id=model_pair_id,
                    fencing_token=effective_token,
                )
                .returning(*tables.live_model_activations.c)
            )
        )
        .mappings()
        .one()
    )
    return activation, False


async def apply_live_activation(
    connection: AsyncConnection,
    *,
    request_id: UUID,
    device_id: str,
    model_pair_id: UUID,
    fencing_token: int | None,
    boundary_after_key: TelemetryKey | None = None,
    boundary_ingress_generation: int | None = None,
    boundary_continuity_epoch: int | None = None,
) -> tuple[RowMapping, bool]:
    if (boundary_ingress_generation is None) != (boundary_continuity_epoch is None):
        raise ValueError("model-change boundary generation and epoch must be paired")
    activation, duplicate = await prepare_live_activation(
        connection,
        request_id=request_id,
        device_id=device_id,
        model_pair_id=model_pair_id,
        fencing_token=fencing_token,
    )
    selection = (
        (
            await connection.execute(
                select(tables.live_model_selections)
                .where(tables.live_model_selections.c.device_id == device_id)
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if (
        fencing_token is None
        and selection is not None
        and selection["activation_event_id"] != activation["activation_event_id"]
    ):
        raise ValueError("bootstrap activation is allowed only before live selection")
    selection_insert = pg_insert(tables.live_model_selections).values(
        device_id=device_id,
        activation_event_id=activation["activation_event_id"],
        model_pair_id=model_pair_id,
        activation_id=activation["activation_id"],
    )
    await connection.execute(
        selection_insert.on_conflict_do_update(
            index_elements=["device_id"],
            set_={
                "activation_event_id": selection_insert.excluded.activation_event_id,
                "model_pair_id": selection_insert.excluded.model_pair_id,
                "activation_id": selection_insert.excluded.activation_id,
                "selected_at_utc": func.clock_timestamp(),
            },
            where=(
                tables.live_model_selections.c.activation_id
                < selection_insert.excluded.activation_id
            ),
        )
    )
    if (
        boundary_ingress_generation is not None
        and boundary_continuity_epoch is not None
    ):
        await _publish_processing_boundary(
            connection,
            device_id=device_id,
            boundary_reason="model_change",
            ingress_generation=boundary_ingress_generation,
            continuity_epoch=boundary_continuity_epoch,
            fencing_token=cast(int, activation["fencing_token"]),
            after_key=boundary_after_key,
        )
    return activation, duplicate


async def publish_processing_boundary(
    connection: AsyncConnection,
    *,
    device_id: str,
    boundary_reason: BoundaryReason,
    ingress_generation: int,
    continuity_epoch: int,
    fencing_token: int,
    after_key: TelemetryKey | None,
) -> tuple[RowMapping, bool]:
    async with connection.begin():
        return await _publish_processing_boundary(
            connection,
            device_id=device_id,
            boundary_reason=boundary_reason,
            ingress_generation=ingress_generation,
            continuity_epoch=continuity_epoch,
            fencing_token=fencing_token,
            after_key=after_key,
        )


async def _publish_processing_boundary(
    connection: AsyncConnection,
    *,
    device_id: str,
    boundary_reason: BoundaryReason,
    ingress_generation: int,
    continuity_epoch: int,
    fencing_token: int,
    after_key: TelemetryKey | None,
) -> tuple[RowMapping, bool]:
    values = {
        "device_id": device_id,
        "boundary_reason": boundary_reason,
        "ingress_generation": ingress_generation,
        "continuity_epoch": continuity_epoch,
        "fencing_token": fencing_token,
        "after_received_ts": after_key[0] if after_key else None,
        "after_telemetry_id": after_key[1] if after_key else None,
    }
    await _require_lease(connection, device_id=device_id, fencing_token=fencing_token)
    await connection.execute(
        select(tables.live_cursors.c.device_id)
        .where(tables.live_cursors.c.device_id == device_id)
        .with_for_update()
    )
    inserted = (
        (
            await connection.execute(
                pg_insert(tables.live_processing_boundaries)
                .values(**values)
                .on_conflict_do_nothing(
                    constraint="uq_live_processing_boundaries_epoch"
                )
                .returning(*tables.live_processing_boundaries.c)
            )
        )
        .mappings()
        .one_or_none()
    )
    if inserted is not None:
        return inserted, False
    existing = (
        (
            await connection.execute(
                select(tables.live_processing_boundaries).where(
                    tables.live_processing_boundaries.c.device_id == device_id,
                    tables.live_processing_boundaries.c.continuity_epoch
                    == continuity_epoch,
                )
            )
        )
        .mappings()
        .one()
    )
    if any(existing[key] != value for key, value in values.items()):
        raise ValueError("continuity_epoch already has a different boundary")
    return existing, True


async def insert_live_telemetry(
    connection: AsyncConnection,
    *,
    telemetry_id: UUID,
    device_id: str,
    received_ts: datetime,
    received_at_utc: datetime,
    temperature_c: float,
    relative_humidity_pct: float,
    ingress_generation: int,
    activation_id: int,
    continuity_epoch: int,
    segment_start_reason: BoundaryReason | None,
    fencing_token: int,
) -> RowMapping:
    async with connection.begin():
        await _require_lease(
            connection, device_id=device_id, fencing_token=fencing_token
        )
        first_in_epoch = not cast(
            bool,
            await connection.scalar(
                select(
                    select(tables.live_telemetry.c.telemetry_id)
                    .where(
                        tables.live_telemetry.c.device_id == device_id,
                        tables.live_telemetry.c.continuity_epoch == continuity_epoch,
                    )
                    .exists()
                )
            ),
        )
        if first_in_epoch != (segment_start_reason is not None):
            raise ValueError(
                "the first telemetry row in an epoch requires its boundary reason"
            )
        if segment_start_reason is not None:
            boundary = (
                (
                    await connection.execute(
                        select(tables.live_processing_boundaries)
                        .where(
                            tables.live_processing_boundaries.c.device_id == device_id,
                            tables.live_processing_boundaries.c.continuity_epoch
                            == continuity_epoch,
                            tables.live_processing_boundaries.c.boundary_reason
                            == segment_start_reason,
                        )
                        .with_for_update()
                    )
                )
                .mappings()
                .one_or_none()
            )
            if boundary is None:
                raise ValueError(
                    "segment start requires a persisted processing boundary"
                )
            anchor_ts = cast(datetime | None, boundary["after_received_ts"])
            anchor_id = cast(UUID | None, boundary["after_telemetry_id"])
            if anchor_ts is not None and (received_ts, telemetry_id) <= (
                anchor_ts,
                cast(UUID, anchor_id),
            ):
                raise ValueError("segment telemetry must follow its boundary anchor")
        return (
            (
                await connection.execute(
                    insert(tables.live_telemetry)
                    .values(
                        received_ts=received_ts,
                        telemetry_id=telemetry_id,
                        device_id=device_id,
                        received_at_utc=received_at_utc,
                        temperature_c=temperature_c,
                        relative_humidity_pct=relative_humidity_pct,
                        ingress_generation=ingress_generation,
                        activation_id=activation_id,
                        continuity_epoch=continuity_epoch,
                        segment_start_reason=segment_start_reason,
                        fencing_token=fencing_token,
                        processing_status="pending",
                    )
                    .returning(*tables.live_telemetry.c)
                )
            )
            .mappings()
            .one()
        )


async def unprocessed_live_tail(
    connection: AsyncConnection,
    *,
    device_id: str,
    after_key: TelemetryKey | None,
    last_boundary_id: int | None,
    limit: int,
) -> list[dict[str, object]]:
    if limit < 1:
        raise ValueError("limit must be positive")
    rows = (
        await connection.execute(
            text(
                """
                WITH recovery_items AS (
                    SELECT
                        'telemetry'::text AS kind,
                        to_jsonb(telemetry) AS payload,
                        telemetry.received_ts AS order_ts,
                        telemetry.telemetry_id AS order_id,
                        0 AS kind_order,
                        0::bigint AS boundary_order
                    FROM live_telemetry AS telemetry
                    WHERE telemetry.device_id = :device_id
                      AND telemetry.processing_status = 'pending'
                      AND (
                          CAST(:after_received_ts AS timestamp) IS NULL
                          OR ROW(telemetry.received_ts, telemetry.telemetry_id) >
                             ROW(
                                 CAST(:after_received_ts AS timestamp),
                                 CAST(:after_telemetry_id AS uuid)
                             )
                      )
                    UNION ALL
                    SELECT
                        'boundary'::text AS kind,
                        to_jsonb(boundary) AS payload,
                        boundary.after_received_ts AS order_ts,
                        boundary.after_telemetry_id AS order_id,
                        1 AS kind_order,
                        boundary.boundary_id AS boundary_order
                    FROM live_processing_boundaries AS boundary
                    WHERE boundary.device_id = :device_id
                      AND (
                          CAST(:last_boundary_id AS bigint) IS NULL
                          OR boundary.boundary_id >
                             CAST(:last_boundary_id AS bigint)
                      )
                )
                SELECT kind, payload
                FROM recovery_items
                ORDER BY order_ts ASC NULLS FIRST,
                         order_id ASC NULLS FIRST,
                         kind_order ASC,
                         boundary_order ASC
                LIMIT :limit
                """
            ),
            {
                "device_id": device_id,
                "after_received_ts": after_key[0] if after_key else None,
                "after_telemetry_id": after_key[1] if after_key else None,
                "last_boundary_id": last_boundary_id,
                "limit": limit,
            },
        )
    ).mappings()
    items: list[dict[str, object]] = []
    for row in rows:
        item = dict(cast(Mapping[str, object], row["payload"]))
        kind = cast(str, row["kind"])
        if kind == "telemetry":
            item["telemetry_id"] = UUID(cast(str, item["telemetry_id"]))
            for name in ("received_ts", "received_at_utc"):
                item[name] = datetime.fromisoformat(cast(str, item[name]))
        else:
            item["recorded_at_utc"] = datetime.fromisoformat(
                cast(str, item["recorded_at_utc"])
            )
            if item["after_received_ts"] is not None:
                item["after_received_ts"] = datetime.fromisoformat(
                    cast(str, item["after_received_ts"])
                )
                item["after_telemetry_id"] = UUID(cast(str, item["after_telemetry_id"]))
        item["kind"] = kind
        items.append(item)
    return items


async def processed_live_tail(
    connection: AsyncConnection,
    *,
    device_id: str,
    activation_id: int,
    continuity_epoch: int,
    limit: int = 9,
) -> list[RowMapping]:
    if limit < 1 or limit > 9:
        raise ValueError("processed live tail limit must be between 1 and 9")
    rows = list(
        (
            await connection.execute(
                select(tables.live_telemetry)
                .where(
                    tables.live_telemetry.c.device_id == device_id,
                    tables.live_telemetry.c.activation_id == activation_id,
                    tables.live_telemetry.c.continuity_epoch == continuity_epoch,
                    tables.live_telemetry.c.processing_status == "processed",
                )
                .order_by(
                    tables.live_telemetry.c.received_ts.desc(),
                    tables.live_telemetry.c.telemetry_id.desc(),
                )
                .limit(limit)
            )
        ).mappings()
    )
    rows.reverse()
    return rows


async def read_live_cursor(
    connection: AsyncConnection, *, device_id: str
) -> RowMapping | None:
    return (
        (
            await connection.execute(
                select(tables.live_cursors).where(
                    tables.live_cursors.c.device_id == device_id
                )
            )
        )
        .mappings()
        .one_or_none()
    )


async def _advance_cursor(
    connection: AsyncConnection,
    *,
    device_id: str,
    telemetry_key: TelemetryKey | None,
    last_boundary_id: int | None,
    continuity_epoch: int,
    fencing_token: int,
) -> RowMapping:
    cursor = (
        (
            await connection.execute(
                select(tables.live_cursors)
                .where(tables.live_cursors.c.device_id == device_id)
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if cursor is None:
        return (
            (
                await connection.execute(
                    insert(tables.live_cursors)
                    .values(
                        device_id=device_id,
                        received_ts=telemetry_key[0] if telemetry_key else None,
                        telemetry_id=telemetry_key[1] if telemetry_key else None,
                        last_boundary_id=last_boundary_id,
                        continuity_epoch=continuity_epoch,
                        fencing_token=fencing_token,
                        updated_at_utc=func.clock_timestamp(),
                    )
                    .returning(*tables.live_cursors.c)
                )
            )
            .mappings()
            .one()
        )
    current_key = (
        (cast(datetime, cursor["received_ts"]), cast(UUID, cursor["telemetry_id"]))
        if cursor["received_ts"] is not None
        else None
    )
    if (
        telemetry_key is not None
        and current_key is not None
        and telemetry_key < current_key
    ):
        raise ValueError("live cursor cannot move backwards")
    current_boundary = cast(int | None, cursor["last_boundary_id"])
    if (
        last_boundary_id is not None
        and current_boundary is not None
        and last_boundary_id < current_boundary
    ):
        raise ValueError("live boundary cursor cannot move backwards")
    return (
        (
            await connection.execute(
                update(tables.live_cursors)
                .where(tables.live_cursors.c.device_id == device_id)
                .values(
                    received_ts=(telemetry_key or current_key or (None, None))[0],
                    telemetry_id=(telemetry_key or current_key or (None, None))[1],
                    last_boundary_id=(
                        last_boundary_id
                        if last_boundary_id is not None
                        else current_boundary
                    ),
                    continuity_epoch=continuity_epoch,
                    fencing_token=fencing_token,
                    updated_at_utc=func.clock_timestamp(),
                )
                .returning(*tables.live_cursors.c)
            )
        )
        .mappings()
        .one()
    )


async def _require_global_earliest_pending(
    connection: AsyncConnection,
    *,
    device_id: str,
    telemetry_key: TelemetryKey,
) -> None:
    earliest = (
        await connection.execute(
            select(
                tables.live_telemetry.c.received_ts,
                tables.live_telemetry.c.telemetry_id,
            )
            .where(
                tables.live_telemetry.c.device_id == device_id,
                tables.live_telemetry.c.processing_status == "pending",
            )
            .order_by(
                tables.live_telemetry.c.received_ts,
                tables.live_telemetry.c.telemetry_id,
            )
            .limit(1)
            .with_for_update()
        )
    ).one_or_none()
    if earliest is None or tuple(earliest) != telemetry_key:
        raise ValueError("target telemetry is not the global earliest pending row")


async def mark_telemetry_processed(
    connection: AsyncConnection,
    *,
    device_id: str,
    telemetry_key: TelemetryKey,
    continuity_epoch: int,
    fencing_token: int,
    last_boundary_id: int | None = None,
    live_episode_id: UUID | None = None,
    episode_close_reason: EpisodeCloseReason | None = None,
    health_status: HealthStatus | None = None,
    health_detail_code: str | None = None,
) -> bool:
    if (live_episode_id is None) != (episode_close_reason is None):
        raise ValueError("episode id and close reason must be provided together")
    if health_status is None and health_detail_code is not None:
        raise ValueError("health detail requires a health status")
    async with connection.begin():
        await _require_lease(
            connection, device_id=device_id, fencing_token=fencing_token
        )
        telemetry = (
            (
                await connection.execute(
                    select(tables.live_telemetry)
                    .where(
                        tables.live_telemetry.c.device_id == device_id,
                        tables.live_telemetry.c.received_ts == telemetry_key[0],
                        tables.live_telemetry.c.telemetry_id == telemetry_key[1],
                        tables.live_telemetry.c.continuity_epoch == continuity_epoch,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one()
        )
        if telemetry["processing_status"] == "processed":
            return False
        boundary_id = cast(
            int,
            await connection.scalar(
                select(tables.live_processing_boundaries.c.boundary_id).where(
                    tables.live_processing_boundaries.c.device_id == device_id,
                    tables.live_processing_boundaries.c.continuity_epoch
                    == continuity_epoch,
                )
            ),
        )
        cursor = (
            (
                await connection.execute(
                    select(tables.live_cursors)
                    .where(tables.live_cursors.c.device_id == device_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            cursor is None
            or cursor["last_boundary_id"] is None
            or cast(int, cursor["last_boundary_id"]) < boundary_id
        ):
            raise ValueError("processing boundary effect must commit first")
        await _require_global_earliest_pending(
            connection,
            device_id=device_id,
            telemetry_key=telemetry_key,
        )
        await connection.execute(
            update(tables.live_telemetry)
            .where(
                tables.live_telemetry.c.received_ts == telemetry_key[0],
                tables.live_telemetry.c.telemetry_id == telemetry_key[1],
            )
            .values(processing_status="processed")
        )
        if live_episode_id is not None and episode_close_reason is not None:
            await _close_live_episode(
                connection,
                device_id=device_id,
                live_episode_id=live_episode_id,
                close_reason=episode_close_reason,
                ended_score_ts=None,
            )
        await _advance_cursor(
            connection,
            device_id=device_id,
            telemetry_key=telemetry_key,
            last_boundary_id=last_boundary_id,
            continuity_epoch=continuity_epoch,
            fencing_token=fencing_token,
        )
        if health_status is not None:
            await _write_live_health(
                connection,
                device_id=device_id,
                status=health_status,
                detail_code=health_detail_code,
                fencing_token=fencing_token,
            )
        return True


async def commit_boundary_effect(
    connection: AsyncConnection,
    *,
    device_id: str,
    boundary_id: int,
    fencing_token: int,
    live_episode_id: UUID | None = None,
    episode_close_reason: EpisodeCloseReason | None = None,
    health_status: HealthStatus | None = None,
    health_detail_code: str | None = None,
) -> RowMapping:
    if (live_episode_id is None) != (episode_close_reason is None):
        raise ValueError("episode id and close reason must be provided together")
    if health_status is None and health_detail_code is not None:
        raise ValueError("health detail requires a health status")
    async with connection.begin():
        await _require_lease(
            connection, device_id=device_id, fencing_token=fencing_token
        )
        boundary = (
            (
                await connection.execute(
                    select(tables.live_processing_boundaries)
                    .where(
                        tables.live_processing_boundaries.c.device_id == device_id,
                        tables.live_processing_boundaries.c.boundary_id == boundary_id,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one()
        )
        cursor = (
            (
                await connection.execute(
                    select(tables.live_cursors)
                    .where(tables.live_cursors.c.device_id == device_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        key = (
            (
                cast(datetime, cursor["received_ts"]),
                cast(UUID, cursor["telemetry_id"]),
            )
            if cursor is not None and cursor["received_ts"] is not None
            else None
        )
        boundary_key = (
            (
                cast(datetime, boundary["after_received_ts"]),
                cast(UUID, boundary["after_telemetry_id"]),
            )
            if boundary["after_received_ts"] is not None
            else None
        )
        if boundary_key != key:
            raise ValueError(
                "processing boundary cursor anchor does not match committed telemetry cursor"
            )
        current_boundary_id = (
            cast(int, cursor["last_boundary_id"])
            if cursor is not None and cursor["last_boundary_id"] is not None
            else None
        )
        if current_boundary_id == boundary_id:
            return cast(RowMapping, cursor)
        next_boundary_id = cast(
            int | None,
            await connection.scalar(
                select(func.min(tables.live_processing_boundaries.c.boundary_id)).where(
                    tables.live_processing_boundaries.c.device_id == device_id,
                    tables.live_processing_boundaries.c.boundary_id
                    > (current_boundary_id or 0),
                )
            ),
        )
        if next_boundary_id != boundary_id:
            raise ValueError("processing boundary is not the next uncommitted boundary")
        if live_episode_id is not None and episode_close_reason is not None:
            await _close_live_episode(
                connection,
                device_id=device_id,
                live_episode_id=live_episode_id,
                close_reason=episode_close_reason,
                ended_score_ts=None,
            )
        advanced = await _advance_cursor(
            connection,
            device_id=device_id,
            telemetry_key=key,
            last_boundary_id=boundary_id,
            continuity_epoch=cast(int, boundary["continuity_epoch"]),
            fencing_token=fencing_token,
        )
        if health_status is not None:
            await _write_live_health(
                connection,
                device_id=device_id,
                status=health_status,
                detail_code=health_detail_code,
                fencing_token=fencing_token,
            )
        return advanced


def _source_fingerprint(
    *,
    device_id: str,
    model_pair_id: UUID,
    activation_id: int,
    continuity_epoch: int,
    source_keys: Sequence[TelemetryKey],
) -> str:
    lines = [
        "live-window-v1",
        device_id,
        str(model_pair_id),
        str(activation_id),
        str(continuity_epoch),
        *(
            f"{ordinal}|{received_ts.isoformat(timespec='seconds')}|{telemetry_id}"
            for ordinal, (received_ts, telemetry_id) in enumerate(source_keys)
        ),
    ]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


async def publish_live_inference(
    connection: AsyncConnection,
    *,
    device_id: str,
    source_keys: Sequence[TelemetryKey],
    score: float,
    is_anomaly: bool,
    severity_at_score: Severity,
    fencing_token: int,
    live_episode_id: UUID | None = None,
    alert_values: Mapping[str, object] | None = None,
    alert_actor: str | None = None,
    episode_close_reason: EpisodeCloseReason | None = None,
    health_status: HealthStatus | None = None,
    health_detail_code: str | None = None,
    recon_temperature_c: float | None = None,
    recon_relative_humidity_pct: float | None = None,
) -> tuple[RowMapping, bool]:
    if len(source_keys) != 10 or len(set(source_keys)) != 10:
        raise ValueError("live inference requires exactly ten unique source keys")
    if list(source_keys) != sorted(source_keys):
        raise ValueError("live inference source keys must be in total order")
    if (alert_values is None) != (alert_actor is None):
        raise ValueError("linked alert requires alert values and actor together")
    if live_episode_id is None and alert_values is not None:
        raise ValueError("linked alert requires a live episode id")
    if episode_close_reason is not None and live_episode_id is None:
        raise ValueError("episode closure requires a live episode id")
    if health_status is None and health_detail_code is not None:
        raise ValueError("health detail requires a health status")

    async with connection.begin():
        await _require_lease(
            connection, device_id=device_id, fencing_token=fencing_token
        )
        sources = list(
            (
                await connection.execute(
                    select(tables.live_telemetry)
                    .where(
                        tables.live_telemetry.c.device_id == device_id,
                        tuple_(
                            tables.live_telemetry.c.received_ts,
                            tables.live_telemetry.c.telemetry_id,
                        ).in_(source_keys),
                    )
                    .order_by(
                        tables.live_telemetry.c.received_ts,
                        tables.live_telemetry.c.telemetry_id,
                    )
                    .with_for_update()
                )
            ).mappings()
        )
        actual_keys = [
            (cast(datetime, row["received_ts"]), cast(UUID, row["telemetry_id"]))
            for row in sources
        ]
        if actual_keys != list(source_keys):
            raise ValueError("live inference sources are not all durable")
        activation_ids = {cast(int, row["activation_id"]) for row in sources}
        continuity_epochs = {cast(int, row["continuity_epoch"]) for row in sources}
        if len(activation_ids) != 1 or len(continuity_epochs) != 1:
            raise ValueError(
                "live inference cannot cross activation or continuity boundaries"
            )
        activation_id = activation_ids.pop()
        continuity_epoch = continuity_epochs.pop()
        window = list(
            (
                await connection.execute(
                    select(
                        tables.live_telemetry.c.received_ts,
                        tables.live_telemetry.c.telemetry_id,
                    )
                    .where(
                        tables.live_telemetry.c.device_id == device_id,
                        tables.live_telemetry.c.activation_id == activation_id,
                        tables.live_telemetry.c.continuity_epoch == continuity_epoch,
                        tuple_(
                            tables.live_telemetry.c.received_ts,
                            tables.live_telemetry.c.telemetry_id,
                        )
                        <= source_keys[-1],
                    )
                    .order_by(
                        tables.live_telemetry.c.received_ts.desc(),
                        tables.live_telemetry.c.telemetry_id.desc(),
                    )
                    .limit(10)
                    .with_for_update()
                )
            ).all()
        )
        window.reverse()
        if window != list(source_keys):
            raise LiveWindowDesyncError(
                "live inference requires a contiguous ten-row window"
            )
        pair = (
            (
                await connection.execute(
                    select(
                        tables.live_model_activations.c.model_pair_id,
                        tables.live_model_pairs.c.model_version,
                        tables.live_model_pairs.c.scaler_snapshot_corpus_id,
                        tables.live_model_pairs.c.threshold,
                    )
                    .join(
                        tables.live_model_pairs,
                        tables.live_model_pairs.c.model_pair_id
                        == tables.live_model_activations.c.model_pair_id,
                    )
                    .where(
                        tables.live_model_activations.c.device_id == device_id,
                        tables.live_model_activations.c.activation_id == activation_id,
                    )
                )
            )
            .mappings()
            .one()
        )
        model_pair_id = cast(UUID, pair["model_pair_id"])
        score_ts = source_keys[-1][0]
        fingerprint = _source_fingerprint(
            device_id=device_id,
            model_pair_id=model_pair_id,
            activation_id=activation_id,
            continuity_epoch=continuity_epoch,
            source_keys=source_keys,
        )
        identity = {
            "score_ts": score_ts,
            "device_id": device_id,
            "model_pair_id": model_pair_id,
            "activation_id": activation_id,
            "continuity_epoch": continuity_epoch,
            "ordered_source_fingerprint": fingerprint,
        }
        result = (
            (
                await connection.execute(
                    pg_insert(tables.live_inference)
                    .values(
                        **identity,
                        window_start_ts=source_keys[0][0],
                        window_end_ts=score_ts,
                        score=score,
                        threshold=pair["threshold"],
                        is_anomaly=is_anomaly,
                        severity_at_score=severity_at_score,
                        model_version=pair["model_version"],
                        snapshot_corpus_id=pair["scaler_snapshot_corpus_id"],
                        recon_temperature_c=recon_temperature_c,
                        recon_relative_humidity_pct=recon_relative_humidity_pct,
                    )
                    .on_conflict_do_nothing(constraint="uq_live_inference_idempotency")
                    .returning(*tables.live_inference.c)
                )
            )
            .mappings()
            .one_or_none()
        )
        if result is None:
            existing = (
                (
                    await connection.execute(
                        select(tables.live_inference).where(
                            *(
                                tables.live_inference.c[key] == value
                                for key, value in identity.items()
                            )
                        )
                    )
                )
                .mappings()
                .one()
            )
            return existing, True

        if any(row["processing_status"] != "processed" for row in sources[:-1]):
            raise ValueError("live inference warm-up effects must commit first")
        if sources[-1]["processing_status"] != "pending":
            raise ValueError("live inference target telemetry must be pending")
        await _require_global_earliest_pending(
            connection,
            device_id=device_id,
            telemetry_key=source_keys[-1],
        )
        cursor = (
            (
                await connection.execute(
                    select(tables.live_cursors)
                    .where(tables.live_cursors.c.device_id == device_id)
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        expected_cursor = source_keys[-2]
        if (
            cursor is None
            or cursor["continuity_epoch"] != continuity_epoch
            or cursor["received_ts"] != expected_cursor[0]
            or cursor["telemetry_id"] != expected_cursor[1]
        ):
            raise ValueError("live inference warm-up cursor must commit first")

        await connection.execute(
            insert(tables.live_inference_sources),
            [
                {
                    "score_ts": score_ts,
                    "inference_id": result["inference_id"],
                    "ordinal": ordinal,
                    "received_ts": received_ts,
                    "telemetry_id": telemetry_id,
                    "device_id": device_id,
                }
                for ordinal, (received_ts, telemetry_id) in enumerate(source_keys)
            ],
        )

        if live_episode_id is not None:
            if alert_values is not None:
                alert = dict(alert_values)
                alert.setdefault("live_episode_id", live_episode_id)
                if (
                    alert.get("device_id") != device_id
                    or alert.get("model_version") != pair["model_version"]
                    or alert.get("corpus_id") != pair["scaler_snapshot_corpus_id"]
                    or alert.get("inference_result_window_start_ts")
                    != source_keys[0][0]
                    or alert.get("inference_result_window_end_ts") != score_ts
                    or alert.get("live_episode_id") != live_episode_id
                ):
                    raise ValueError("linked alert lineage does not match inference")
                await connection.execute(insert(tables.alerts).values(**alert))
                episode = (
                    (
                        await connection.execute(
                            insert(tables.live_alert_episodes)
                            .values(
                                live_episode_id=live_episode_id,
                                alert_id=alert["alert_id"],
                                device_id=device_id,
                                model_pair_id=model_pair_id,
                                activation_id=activation_id,
                                continuity_epoch=continuity_epoch,
                                model_version=pair["model_version"],
                                snapshot_corpus_id=pair["scaler_snapshot_corpus_id"],
                                started_score_ts=score_ts,
                                 ended_score_ts=None,
                                 status="open",
                                 close_reason=None,
                             )
                            .returning(*tables.live_alert_episodes.c)
                        )
                    )
                    .mappings()
                    .one()
                )
                await connection.execute(
                    insert(tables.alert_events).values(
                        event_id=uuid4().hex,
                        alert_id=alert["alert_id"],
                        event_ts=None,
                        event_at=func.clock_timestamp(),
                        time_domain="utc",
                        event_type="detected",
                        device_id=device_id,
                        actor=cast(str, alert_actor),
                        note=None,
                        inference_result_window_start_ts=source_keys[0][0],
                        inference_result_window_end_ts=score_ts,
                        inference_model_version=pair["model_version"],
                        detection_basis=alert["detection_basis"],
                    )
                )
                ordinal = 0
            else:
                episode = (
                    (
                        await connection.execute(
                            select(tables.live_alert_episodes)
                            .where(
                                tables.live_alert_episodes.c.live_episode_id
                                == live_episode_id,
                                tables.live_alert_episodes.c.device_id == device_id,
                                tables.live_alert_episodes.c.status == "open",
                            )
                            .with_for_update()
                        )
                    )
                    .mappings()
                    .one()
                )
                ordinal = cast(
                    int,
                    await connection.scalar(
                        select(
                            func.coalesce(
                                func.max(tables.live_alert_episode_points.c.ordinal),
                                -1,
                            )
                            + 1
                        ).where(
                            tables.live_alert_episode_points.c.live_episode_id
                            == live_episode_id
                        )
                    ),
                )
                await connection.execute(
                    update(tables.alerts)
                    .where(tables.alerts.c.alert_id == episode["alert_id"])
                    .values(
                        peak_score=func.greatest(tables.alerts.c.peak_score, score),
                        latest_score=score,
                        anomalous_window_count=tables.alerts.c.anomalous_window_count
                        + int(is_anomaly),
                        last_score_ts=score_ts,
                        episode_end_ts=score_ts,
                    )
                )
            await connection.execute(
                insert(tables.live_alert_episode_points).values(
                    live_episode_id=live_episode_id,
                    score_ts=score_ts,
                    inference_id=result["inference_id"],
                    ordinal=ordinal,
                    device_id=device_id,
                    model_pair_id=model_pair_id,
                    activation_id=activation_id,
                    continuity_epoch=continuity_epoch,
                    model_version=pair["model_version"],
                    snapshot_corpus_id=pair["scaler_snapshot_corpus_id"],
                )
            )
            if episode_close_reason is not None:
                await _close_live_episode(
                    connection,
                    device_id=device_id,
                    live_episode_id=live_episode_id,
                    close_reason=episode_close_reason,
                    ended_score_ts=score_ts,
                )

        processed = await connection.execute(
            update(tables.live_telemetry)
            .where(
                tables.live_telemetry.c.received_ts == source_keys[-1][0],
                tables.live_telemetry.c.telemetry_id == source_keys[-1][1],
                tables.live_telemetry.c.processing_status == "pending",
            )
            .values(processing_status="processed")
        )
        if processed.rowcount != 1:
            raise RuntimeError("inference target telemetry was not pending")
        await _advance_cursor(
            connection,
            device_id=device_id,
            telemetry_key=source_keys[-1],
            last_boundary_id=None,
            continuity_epoch=continuity_epoch,
            fencing_token=fencing_token,
        )
        if health_status is not None:
            await _write_live_health(
                connection,
                device_id=device_id,
                status=health_status,
                detail_code=health_detail_code,
                fencing_token=fencing_token,
            )
        return result, False


async def resolve_live_episode(
    connection: AsyncConnection,
    *,
    device_id: str,
    live_episode_id: UUID,
    ended_score_ts: datetime | None,
    fencing_token: int,
    close_reason: EpisodeCloseReason = "normal_recovery",
    health_status: HealthStatus | None = None,
    health_detail_code: str | None = None,
) -> bool:
    if health_status is None and health_detail_code is not None:
        raise ValueError("health detail requires a health status")
    async with connection.begin():
        await _require_lease(
            connection, device_id=device_id, fencing_token=fencing_token
        )
        changed = await _close_live_episode(
            connection,
            device_id=device_id,
            live_episode_id=live_episode_id,
            close_reason=close_reason,
            ended_score_ts=ended_score_ts,
        )
        if health_status is not None:
            await _write_live_health(
                connection,
                device_id=device_id,
                status=health_status,
                detail_code=health_detail_code,
                fencing_token=fencing_token,
            )
        return changed


async def read_live_health(
    connection: AsyncConnection, *, device_id: str
) -> RowMapping | None:
    return (
        (
            await connection.execute(
                select(tables.live_health).where(
                    tables.live_health.c.device_id == device_id
                )
            )
        )
        .mappings()
        .one_or_none()
    )


async def write_live_health(
    connection: AsyncConnection,
    *,
    device_id: str,
    status: HealthStatus,
    detail_code: str | None,
    fencing_token: int,
) -> RowMapping:
    _validate_health(status, detail_code)
    async with connection.begin():
        await _require_lease(
            connection, device_id=device_id, fencing_token=fencing_token
        )
        return await _write_live_health(
            connection,
            device_id=device_id,
            status=status,
            detail_code=detail_code,
            fencing_token=fencing_token,
        )
