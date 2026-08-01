from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import cast
from uuid import uuid4

from sqlalchemy import and_, func, insert, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.problems import Conflict, InvalidQuery, NotFound
from anomaly_backend.replay_contract import acquire_shared_replay_contract_lock


PUBLIC_DEVICE_ID = "b02f3872-ruang-produksi"
PUBLIC_TIME_ZONE = "Asia/Jakarta"
PUBLIC_CHANNELS = ("temperature_c", "relative_humidity_pct")
PREVIEW_ACTOR = "preview-session"


def _hash_payload(payload: dict[str, object]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def active_device_rows(connection: AsyncConnection) -> list[RowMapping]:
    statement = (
        select(
            tables.devices.c.device_id,
            tables.devices.c.display_name,
            tables.devices.c.time_zone,
            tables.corpora.c.status.label("corpus_status"),
            tables.corpora.c.interval_start,
            tables.corpora.c.interval_end,
        )
        .select_from(
            tables.devices.outerjoin(
                tables.published_corpora,
                tables.published_corpora.c.device_id
                == tables.devices.c.device_id,
            ).outerjoin(
                tables.corpora,
                tables.corpora.c.corpus_id
                == tables.published_corpora.c.corpus_id,
            )
        )
        .where(tables.devices.c.is_active)
        .order_by(tables.devices.c.device_id)
    )
    return list((await connection.execute(statement)).mappings())


async def public_model_rows(
    connection: AsyncConnection, device_id: str
) -> tuple[RowMapping, list[RowMapping]]:
    selection = (
        await connection.execute(
            select(
                tables.active_model_selections.c.activation_id,
                tables.active_model_selections.c.model_version,
            ).where(tables.active_model_selections.c.device_id == device_id)
        )
    ).mappings().one_or_none()
    if selection is None:
        raise NotFound("Active model selection was not found")

    ready_artifacts = (
        select(
            tables.model_versions.c.model_key,
            func.bool_or(
                and_(
                    tables.model_versions.c.runtime_kind == "artifact",
                    tables.model_versions.c.is_selectable,
                )
            ).label("artifact_ready"),
        )
        .group_by(tables.model_versions.c.model_key)
        .subquery()
    )
    statement = (
        select(
            tables.model_families.c.model_key,
            tables.model_families.c.display_name,
            tables.model_versions.c.version,
            tables.model_versions.c.runtime_kind,
            tables.model_versions.c.is_selectable,
            tables.model_versions.c.schema_version,
            tables.model_versions.c.channels,
            tables.model_versions.c.window_size,
            tables.model_versions.c.stride,
            func.coalesce(ready_artifacts.c.artifact_ready, False).label(
                "artifact_ready"
            ),
        )
        .join(
            tables.model_versions,
            tables.model_versions.c.model_key
            == tables.model_families.c.model_key,
        )
        .outerjoin(
            ready_artifacts,
            ready_artifacts.c.model_key == tables.model_families.c.model_key,
        )
        .where(
            tables.model_families.c.is_public,
            tables.model_versions.c.runtime_kind.in_(
                ("preview_simulator", "artifact")
            ),
        )
        .order_by(
            tables.model_families.c.model_key,
            tables.model_versions.c.created_at,
            tables.model_versions.c.version,
        )
    )
    return selection, list((await connection.execute(statement)).mappings())


async def activate_model(
    connection: AsyncConnection,
    *,
    command_id: str,
    device_id: str,
    model_version: str,
) -> tuple[RowMapping, str, bool]:
    payload_hash = _hash_payload(
        {
            "device_id": device_id,
            "model_version": model_version,
        }
    )
    async with connection.begin():
        await acquire_shared_replay_contract_lock(connection)
        selection = (
            await connection.execute(
                select(tables.active_model_selections)
                .where(
                    tables.active_model_selections.c.device_id == device_id
                )
                .with_for_update()
            )
        ).mappings().one_or_none()
        if selection is None:
            raise NotFound("Active model selection was not found")

        existing = (
            await connection.execute(
                select(tables.model_activations).where(
                    tables.model_activations.c.command_id == command_id
                )
            )
        ).mappings().one_or_none()
        if existing is not None:
            if (
                existing["payload_hash"] != payload_hash
                or existing["device_id"] != device_id
                or existing["model_version"] != model_version
            ):
                raise Conflict(
                    "The activation command_id was already used for a "
                    "different payload"
                )
            return (
                existing,
                cast(str, selection["model_version"]),
                True,
            )

        candidate = (
            await connection.execute(
                select(
                    tables.model_versions.c.version,
                    tables.model_versions.c.runtime_kind,
                    tables.model_versions.c.is_selectable,
                    tables.model_versions.c.schema_version,
                    tables.model_versions.c.channels,
                    tables.model_versions.c.window_size,
                    tables.model_versions.c.stride,
                    tables.model_versions.c.contract_status,
                    tables.model_families.c.is_public,
                )
                .join(
                    tables.model_families,
                    tables.model_families.c.model_key
                    == tables.model_versions.c.model_key,
                )
                .where(tables.model_versions.c.version == model_version)
            )
        ).mappings().one_or_none()
        if candidate is None:
            raise NotFound("The model version was not found")
        if (
            not candidate["is_public"]
            or not candidate["is_selectable"]
            or candidate["runtime_kind"] != "preview_simulator"
            or candidate["schema_version"] != "b02f3872_preview_v1"
            or tuple(candidate["channels"]) != PUBLIC_CHANNELS
            or candidate["window_size"] != 10
            or candidate["stride"] != 1
            or candidate["contract_status"] != "live_10"
        ):
            raise InvalidQuery(
                "The model version is not compatible with this device"
            )

        prior = cast(str, selection["model_version"])
        activation_id = f"activation_{uuid4().hex}"
        changed = prior != model_version
        activated_at = _utc_now()
        activation_values = {
            "activation_id": activation_id,
            "command_id": command_id,
            "payload_hash": payload_hash,
            "device_id": device_id,
            "prior_model_version": prior,
            "model_version": model_version,
            "changed": changed,
            "activated_at": activated_at,
            "actor": PREVIEW_ACTOR,
        }
        activation = (
            await connection.execute(
                insert(tables.model_activations)
                .values(**activation_values)
                .returning(*tables.model_activations.c)
            )
        ).mappings().one()
        await connection.execute(
            update(tables.active_model_selections)
            .where(
                tables.active_model_selections.c.device_id == device_id
            )
            .values(
                activation_id=activation_id,
                model_version=model_version,
            )
        )
        return activation, model_version, False


async def _job_by_logical_hash(
    connection: AsyncConnection, logical_hash: str
) -> RowMapping | None:
    return (
        await connection.execute(
            select(tables.replay_jobs).where(
                tables.replay_jobs.c.logical_job_hash == logical_hash,
                tables.replay_jobs.c.status != "failed",
            )
        )
    ).mappings().one_or_none()


async def submit_replay_job(
    connection: AsyncConnection,
    *,
    command_id: str,
    device_id: str,
    from_ts: datetime,
    to_ts: datetime,
) -> tuple[RowMapping, bool]:
    command_payload_hash = _hash_payload(
        {
            "device_id": device_id,
            "from": from_ts.isoformat(timespec="seconds"),
            "to": to_ts.isoformat(timespec="seconds"),
        }
    )
    async with connection.begin():
        await acquire_shared_replay_contract_lock(connection)
        selection = (
            await connection.execute(
                select(tables.active_model_selections)
                .where(
                    tables.active_model_selections.c.device_id == device_id
                )
                .with_for_update()
            )
        ).mappings().one_or_none()
        if selection is None:
            raise NotFound("Active model selection was not found")

        existing_command = (
            await connection.execute(
                select(
                    tables.replay_commands.c.payload_hash,
                    tables.replay_commands.c.job_id,
                ).where(tables.replay_commands.c.command_id == command_id)
            )
        ).mappings().one_or_none()
        if existing_command is not None:
            if existing_command["payload_hash"] != command_payload_hash:
                raise Conflict(
                    "The replay command_id was already used for a "
                    "different payload"
                )
            job = (
                await connection.execute(
                    select(tables.replay_jobs).where(
                        tables.replay_jobs.c.job_id
                        == existing_command["job_id"]
                    )
                )
            ).mappings().one()
            return job, True

        corpus = (
            await connection.execute(
                select(tables.corpora)
                .join(
                    tables.published_corpora,
                    tables.published_corpora.c.corpus_id
                    == tables.corpora.c.corpus_id,
                )
                .where(
                    tables.published_corpora.c.device_id == device_id,
                    tables.corpora.c.status == "published",
                )
            )
        ).mappings().one_or_none()
        if corpus is None:
            raise Conflict("Telemetry import is not ready for replay")
        interval_start = cast(datetime | None, corpus["interval_start"])
        interval_end = cast(datetime | None, corpus["interval_end"])
        if (
            interval_start is None
            or interval_end is None
            or from_ts < interval_start
            or to_ts > interval_end
        ):
            raise InvalidQuery(
                "Replay interval must be contained by the published corpus"
            )

        version = (
            await connection.execute(
                select(tables.model_versions).where(
                    tables.model_versions.c.version
                    == selection["model_version"]
                )
            )
        ).mappings().one()
        if (
            not version["is_selectable"]
            or version["schema_version"] != "b02f3872_preview_v1"
            or tuple(version["channels"]) != PUBLIC_CHANNELS
            or version["window_size"] != 10
            or version["stride"] != 1
            or version["contract_status"] != "live_10"
        ):
            raise Conflict(
                "The selected model is not compatible with live replay"
            )
        runtime_kind = cast(str, version["runtime_kind"])
        if runtime_kind == "preview_simulator":
            provenance = "simulated_preview"
        elif runtime_kind == "artifact":
            provenance = "artifact_backed"
        else:
            raise Conflict(
                "The selected model has no supported replay adapter"
            )
        logical_hash = _hash_payload(
            {
                "device_id": device_id,
                "corpus_id": corpus["corpus_id"],
                "archive_sha256": corpus["archive_sha256"],
                "preprocessing_contract_version": corpus[
                    "preprocessing_contract_version"
                ],
                "model_version": selection["model_version"],
                "score_provenance": provenance,
                "from": from_ts.isoformat(timespec="seconds"),
                "to": to_ts.isoformat(timespec="seconds"),
            }
        )
        existing_job = await _job_by_logical_hash(connection, logical_hash)
        accepted_at = _utc_now()
        if existing_job is not None:
            await connection.execute(
                insert(tables.replay_commands).values(
                    command_id=command_id,
                    payload_hash=command_payload_hash,
                    job_id=existing_job["job_id"],
                    accepted_at=accepted_at,
                )
            )
            return existing_job, True

        first_index = await connection.scalar(
            select(func.min(tables.telemetry.c.corpus_index)).where(
                tables.telemetry.c.corpus_id == corpus["corpus_id"],
                tables.telemetry.c.ts >= from_ts,
                tables.telemetry.c.ts < to_ts,
            )
        )
        if first_index is None:
            raise InvalidQuery("Replay interval contains no telemetry")

        job_id = f"job_{uuid4().hex}"
        values = {
            "job_id": job_id,
            "logical_job_hash": logical_hash,
            "device_id": device_id,
            "corpus_id": corpus["corpus_id"],
            "archive_sha256": corpus["archive_sha256"],
            "preprocessing_contract_version": corpus[
                "preprocessing_contract_version"
            ],
            "activation_id": selection["activation_id"],
            "model_version": selection["model_version"],
            "score_provenance": provenance,
            "from_ts": from_ts,
            "to_ts": to_ts,
            "status": "queued",
            "lease_owner": None,
            "lease_expires_at": None,
            "heartbeat_at": None,
            "attempt_count": 0,
            "max_attempts": 3,
            "next_corpus_index": int(first_index),
            "processed_count": 0,
            "result_count": 0,
            "episode_count": 0,
            "submitted_at": accepted_at,
            "started_at": None,
            "completed_at": None,
            "error_code": None,
            "error_detail": None,
        }
        try:
            async with connection.begin_nested():
                job = (
                    await connection.execute(
                        insert(tables.replay_jobs)
                        .values(**values)
                        .returning(*tables.replay_jobs.c)
                    )
                ).mappings().one()
        except IntegrityError as error:
            constraint_name = getattr(
                getattr(error.orig, "diag", None), "constraint_name", None
            )
            if constraint_name == "uq_replay_jobs_logical_nonfailed":
                existing_job = await _job_by_logical_hash(
                    connection, logical_hash
                )
                if existing_job is None:
                    raise
                job = existing_job
            elif constraint_name == "ex_replay_jobs_nonoverlap":
                overlap = (
                    await connection.execute(
                        select(tables.replay_jobs.c.job_id).where(
                            tables.replay_jobs.c.device_id == device_id,
                            tables.replay_jobs.c.model_version
                            == selection["model_version"],
                            tables.replay_jobs.c.score_provenance
                            == provenance,
                            tables.replay_jobs.c.status.in_(
                                ("queued", "running", "succeeded")
                            ),
                            text(
                                "replay_range && "
                                "tsrange(:from_ts, :to_ts, '[)')"
                            ),
                        ),
                        {"from_ts": from_ts, "to_ts": to_ts},
                    )
                ).mappings().one_or_none()
                existing_job_id = (
                    cast(str, overlap["job_id"])
                    if overlap is not None
                    else "unknown"
                )
                raise Conflict(
                    "Replay interval overlaps existing job "
                    f"{existing_job_id}"
                ) from error
            else:
                raise

        await connection.execute(
            insert(tables.replay_commands).values(
                command_id=command_id,
                payload_hash=command_payload_hash,
                job_id=job["job_id"],
                accepted_at=accepted_at,
            )
        )
        return job, False


async def replay_job_row(
    connection: AsyncConnection, job_id: str
) -> RowMapping | None:
    return (
        await connection.execute(
            select(tables.replay_jobs)
            .join(
                tables.devices,
                tables.devices.c.device_id == tables.replay_jobs.c.device_id,
            )
            .where(
                tables.replay_jobs.c.job_id == job_id,
                tables.devices.c.is_active,
            )
        )
    ).mappings().one_or_none()


async def estimated_replay_results(
    connection: AsyncConnection, row: RowMapping
) -> int:
    temporal_semantics = cast(
        str,
        await connection.scalar(
            select(tables.model_versions.c.temporal_semantics).where(
                tables.model_versions.c.version == row["model_version"]
            )
        ),
    )
    required_preceding = (
        30 if temporal_semantics == "next_target" else 29
    )
    segment_starts = (
        select(
            tables.telemetry.c.segment_id,
            func.min(tables.telemetry.c.corpus_index).label("start_index"),
        )
        .where(tables.telemetry.c.corpus_id == row["corpus_id"])
        .group_by(tables.telemetry.c.segment_id)
        .subquery()
    )
    estimate = await connection.scalar(
        select(func.count())
        .select_from(
            tables.telemetry.join(
                segment_starts,
                segment_starts.c.segment_id == tables.telemetry.c.segment_id,
            )
        )
        .where(
            tables.telemetry.c.corpus_id == row["corpus_id"],
            tables.telemetry.c.ts >= row["from_ts"],
            tables.telemetry.c.ts < row["to_ts"],
            tables.telemetry.c.corpus_index
            - segment_starts.c.start_index
            >= required_preceding,
        )
    )
    return int(estimate or 0)
