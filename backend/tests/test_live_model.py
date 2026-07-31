from __future__ import annotations

import asyncio
from collections.abc import MutableMapping
from datetime import datetime, timezone
import os
from pathlib import Path
from threading import Lock
from typing import cast
from uuid import UUID
from uuid import uuid4

import pytest
from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.live_model_bootstrap import (
    LiveModelBootstrapResult,
    bootstrap_live_model,
)
from anomaly_backend.sql.live import (
    LIVE_DEVICE_ID,
    acquire_writer_lease,
    apply_live_activation,
    commit_boundary_effect,
    prepare_live_activation,
    release_writer_lease,
    request_live_activation,
)
from anomaly_worker import artifact_scorer
from anomaly_worker.live_model import (
    LiveActivationControl,
    LiveModelIdentity,
    LiveModelUnavailable,
    load_live_model,
)
from tests.live_bundle_fixture import rewrite_json, write_bundle


def _engine() -> AsyncEngine:
    return create_database_engine(Settings.from_environ())


def _configure(monkeypatch: pytest.MonkeyPatch, root: Path, bundle_id: str) -> None:
    monkeypatch.setenv("MODEL_ARTIFACTS_PATH", str(root))
    monkeypatch.setenv("LIVE_MODEL_BUNDLE_ID", bundle_id)
    monkeypatch.setattr(artifact_scorer.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(
        artifact_scorer,
        "_cuda_device",
        lambda: artifact_scorer.torch.device("cpu"),
        raising=False,
    )


async def _activate_pending(
    connection: AsyncConnection,
    registered: LiveModelBootstrapResult,
) -> None:
    if registered.activated:
        return
    async with connection.begin():
        await connection.execute(
            text(
                "UPDATE live_writer_leases "
                "SET lease_expires_at_utc = clock_timestamp() - interval '1 second' "
                "WHERE device_id = :device_id"
            ),
            {"device_id": LIVE_DEVICE_ID},
        )
    owner = f"task5-{uuid4().hex}"
    lease = await acquire_writer_lease(
        connection,
        device_id=LIVE_DEVICE_ID,
        lease_owner=owner,
        lease_seconds=60,
    )
    assert lease is not None
    async with connection.begin():
        await apply_live_activation(
            connection,
            request_id=registered.request_id,
            device_id=LIVE_DEVICE_ID,
            model_pair_id=registered.model_pair_id,
            fencing_token=int(lease["fencing_token"]),
        )
    assert await release_writer_lease(
        connection,
        device_id=LIVE_DEVICE_ID,
        lease_owner=owner,
        fencing_token=int(lease["fencing_token"]),
    )


def test_load_has_retryable_no_selection_error() -> None:
    async def run() -> None:
        engine = _engine()
        try:
            async with engine.connect() as connection:
                with pytest.raises(LiveModelUnavailable) as failure:
                    await load_live_model(
                        connection, device_id=f"missing-{uuid4().hex}"
                    )
                assert failure.value.retryable
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_activation_control_preserves_in_flight_and_queued_bindings() -> None:
    first = LiveModelIdentity(UUID(int=1), 10, "first-snapshot")
    second = LiveModelIdentity(UUID(int=2), 11, "second-snapshot")
    control = LiveActivationControl(
        first,
        ingress_generation=4,
        continuity_epoch=7,
    )
    in_flight = control.capture()
    queued = control.capture()

    with Lock():
        marker = control.activate(
            second,
            request_id=UUID(int=3),
            after_ingress_sequence=19,
        )
    later = control.capture()

    assert in_flight.identity == queued.identity == first
    assert later.identity == second
    assert (later.ingress_generation, later.continuity_epoch) == (5, 8)
    assert marker.after_ingress_sequence == 19
    assert marker.binding == later


def test_prepared_activation_stalls_consumer_not_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_root = tmp_path / "first"
    first_bundle, _ = write_bundle(first_root)
    _configure(monkeypatch, first_root, first_bundle)

    async def run() -> None:
        engine = _engine()
        blocker: AsyncConnection | None = None
        waiter: AsyncConnection | None = None
        try:
            async with engine.connect() as connection:
                first_registration = await bootstrap_live_model(connection)
                await _activate_pending(connection, first_registration)
                first = await load_live_model(connection)

            second_root = tmp_path / "second"
            second_bundle, _ = write_bundle(second_root)
            _configure(monkeypatch, second_root, second_bundle)
            async with engine.connect() as connection:
                pending = await bootstrap_live_model(connection)
                assert not pending.activated

            owner = f"task5-stall-{uuid4().hex}"
            async with engine.connect() as connection:
                lease = await acquire_writer_lease(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    lease_owner=owner,
                    lease_seconds=60,
                )
                assert lease is not None
                token = int(lease["fencing_token"])
                async with connection.begin():
                    activation, duplicate = await prepare_live_activation(
                        connection,
                        request_id=pending.request_id,
                        device_id=LIVE_DEVICE_ID,
                        model_pair_id=pending.model_pair_id,
                        fencing_token=token,
                    )
                assert not duplicate
                prepared = await load_live_model(
                    connection,
                    activation_id=int(activation["activation_id"]),
                )
                assert prepared.identity.model_pair_id == pending.model_pair_id

            async with engine.connect() as connection:
                assert (
                    await connection.scalar(
                        select(tables.live_model_selections.c.model_pair_id).where(
                            tables.live_model_selections.c.device_id == LIVE_DEVICE_ID
                        )
                    )
                    == first.identity.model_pair_id
                )

            async with engine.connect() as connection:
                maximum_epoch = await connection.scalar(
                    select(
                        func.coalesce(
                            func.max(
                                tables.live_processing_boundaries.c.continuity_epoch
                            ),
                            0,
                        )
                    )
                )
                assert maximum_epoch is not None
                next_epoch = int(maximum_epoch) + 1

            control = LiveActivationControl(
                first.identity,
                ingress_generation=next_epoch - 1,
                continuity_epoch=next_epoch - 1,
            )
            marker = control.activate(
                prepared.identity,
                request_id=pending.request_id,
                after_ingress_sequence=19,
            )

            async with engine.connect() as connection:
                cursor = (
                    (
                        await connection.execute(
                            select(
                                tables.live_cursors.c.received_ts,
                                tables.live_cursors.c.telemetry_id,
                            ).where(tables.live_cursors.c.device_id == LIVE_DEVICE_ID)
                        )
                    )
                    .mappings()
                    .one_or_none()
                )
                boundary_after_key = (
                    None
                    if cursor is None or cursor["received_ts"] is None
                    else (
                        cast(datetime, cursor["received_ts"]),
                        cast(UUID, cursor["telemetry_id"]),
                    )
                )

            blocker = await engine.connect()
            waiter = await engine.connect()
            blocker_transaction = await blocker.begin()
            await blocker.execute(
                select(tables.live_model_activation_requests)
                .where(
                    tables.live_model_activation_requests.c.request_id
                    == pending.request_id
                )
                .with_for_update()
            )

            async def apply() -> tuple[object, bool]:
                current_waiter = waiter
                assert current_waiter is not None
                async with current_waiter.begin():
                    return await apply_live_activation(
                        current_waiter,
                        request_id=pending.request_id,
                        device_id=LIVE_DEVICE_ID,
                        model_pair_id=pending.model_pair_id,
                        fencing_token=token,
                        boundary_after_key=boundary_after_key,
                        boundary_ingress_generation=marker.binding.ingress_generation,
                        boundary_continuity_epoch=marker.binding.continuity_epoch,
                    )

            task = asyncio.create_task(apply())
            await asyncio.sleep(0.05)
            assert not task.done()
            assert control.capture() == marker.binding

            await blocker_transaction.rollback()
            _, duplicate = await asyncio.wait_for(task, timeout=2)
            assert duplicate

            async with engine.connect() as connection:
                assert (
                    await connection.scalar(
                        select(tables.live_model_selections.c.model_pair_id).where(
                            tables.live_model_selections.c.device_id == LIVE_DEVICE_ID
                        )
                    )
                    == pending.model_pair_id
                )
                boundary = (
                    (
                        await connection.execute(
                            select(tables.live_processing_boundaries).where(
                                tables.live_processing_boundaries.c.device_id
                                == LIVE_DEVICE_ID,
                                tables.live_processing_boundaries.c.boundary_reason
                                == "model_change",
                                tables.live_processing_boundaries.c.continuity_epoch
                                == marker.binding.continuity_epoch,
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                assert (
                    boundary["ingress_generation"] == marker.binding.ingress_generation
                )
                await connection.rollback()
                await commit_boundary_effect(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    boundary_id=int(boundary["boundary_id"]),
                    fencing_token=token,
                )

            async with engine.connect() as connection:
                assert await release_writer_lease(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    lease_owner=owner,
                    fencing_token=token,
                )
        finally:
            if blocker is not None:
                await blocker.close()
            if waiter is not None:
                await waiter.close()
            await engine.dispose()

    asyncio.run(run())


def test_load_retries_after_manifest_repair_without_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_id, files = write_bundle(tmp_path)
    _configure(monkeypatch, tmp_path, bundle_id)

    async def run() -> None:
        engine = _engine()
        try:
            async with engine.connect() as connection:
                registered = await bootstrap_live_model(connection)
                await _activate_pending(connection, registered)
                loaded = await load_live_model(connection)
                assert loaded.identity.model_pair_id == registered.model_pair_id
                assert not loaded.reset_required
                assert loaded.scale_pair((20.0, 90.0)) == (0.0, 1.0)
                assert not isinstance(loaded.threshold_policy, MutableMapping)

                monkeypatch.setattr(
                    artifact_scorer.torch.cuda, "is_available", lambda: False
                )
                with pytest.raises(LiveModelUnavailable, match="CUDA") as cuda_failure:
                    await load_live_model(
                        connection, previous_identity=loaded.identity
                    )
                assert cuda_failure.value.retryable
                _configure(monkeypatch, tmp_path, bundle_id)

                original = files["model_manifest"].read_bytes()
                model = dict(files["model"])
                model["threshold"] = 0.5
                rewrite_json(files["model_manifest"], model)
                with pytest.raises(
                    LiveModelUnavailable, match="model manifest SHA-256"
                ) as failure:
                    await load_live_model(connection, previous_identity=loaded.identity)
                assert failure.value.retryable
                files["model_manifest"].write_bytes(original)

                repaired = await load_live_model(
                    connection, previous_identity=loaded.identity
                )
                assert repaired.identity == loaded.identity
                assert not repaired.reset_required
                assert type(repaired.scorer).__name__ == "ArtifactScorer"
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_load_retries_after_checkpoint_disappears_post_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_id, files = write_bundle(tmp_path)
    _configure(monkeypatch, tmp_path, bundle_id)

    async def run() -> None:
        engine = _engine()
        try:
            async with engine.connect() as connection:
                registered = await bootstrap_live_model(connection)
                await _activate_pending(connection, registered)

                checkpoint_bytes = files["checkpoint"].read_bytes()
                original_sha256 = artifact_scorer._sha256
                removed_after_validation = False

                def remove_after_validation(path: Path) -> str:
                    nonlocal removed_after_validation
                    digest = original_sha256(path)
                    if path == files["checkpoint"] and not removed_after_validation:
                        removed_after_validation = True
                        path.unlink()
                    return digest

                monkeypatch.setattr(
                    artifact_scorer,
                    "_sha256",
                    remove_after_validation,
                )
                with pytest.raises(LiveModelUnavailable) as failure:
                    await load_live_model(connection)
                assert failure.value.retryable
                assert removed_after_validation

                files["checkpoint"].write_bytes(checkpoint_bytes)
                monkeypatch.setattr(artifact_scorer, "_sha256", original_sha256)
                repaired = await load_live_model(connection)
                assert repaired.identity.model_pair_id == registered.model_pair_id
                assert type(repaired.scorer).__name__ == "ArtifactScorer"
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_preview_selection_change_does_not_change_live_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle_id, _ = write_bundle(tmp_path)
    _configure(monkeypatch, tmp_path, bundle_id)

    async def run() -> None:
        engine = _engine()
        preview_activation_id = f"task5-preview-{uuid4().hex}"
        try:
            async with engine.connect() as connection:
                registered = await bootstrap_live_model(connection)
                await _activate_pending(connection, registered)
                live_before = await load_live_model(connection)
                assert (
                    await connection.scalar(
                        select(tables.active_model_selections.c.model_version).where(
                            tables.active_model_selections.c.device_id == LIVE_DEVICE_ID
                        )
                    )
                    is None
                )

            other_root = tmp_path / "other"
            other_bundle, _ = write_bundle(other_root)
            _configure(monkeypatch, other_root, other_bundle)
            async with engine.connect() as connection:
                other = await bootstrap_live_model(connection)
                assert not other.activated

            _configure(monkeypatch, tmp_path, bundle_id)
            async with engine.connect() as connection:
                async with connection.begin():
                    await connection.execute(
                        insert(tables.model_activations).values(
                            activation_id=preview_activation_id,
                            command_id=preview_activation_id,
                            payload_hash=preview_activation_id,
                            device_id=LIVE_DEVICE_ID,
                            prior_model_version=None,
                            model_version=other.model_version,
                            changed=True,
                            activated_at=datetime.now(timezone.utc),
                            actor="test",
                        )
                    )
                    await connection.execute(
                        insert(tables.active_model_selections).values(
                            device_id=LIVE_DEVICE_ID,
                            activation_id=preview_activation_id,
                            model_version=other.model_version,
                        )
                    )
                live_after = await load_live_model(connection)
                assert live_after.identity == live_before.identity
        finally:
            async with engine.connect() as connection:
                async with connection.begin():
                    await connection.execute(
                        tables.active_model_selections.delete().where(
                            tables.active_model_selections.c.activation_id
                            == preview_activation_id
                        )
                    )
                    await connection.execute(
                        tables.model_activations.delete().where(
                            tables.model_activations.c.activation_id
                            == preview_activation_id
                        )
                    )
            await engine.dispose()

    asyncio.run(run())


def test_pair_identity_change_requests_reset_only_after_fenced_activation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_bundle, _ = write_bundle(tmp_path / "first")
    _configure(monkeypatch, tmp_path / "first", first_bundle)

    async def run() -> None:
        engine = _engine()
        try:
            async with engine.connect() as connection:
                registered = await bootstrap_live_model(connection)
                await _activate_pending(connection, registered)
                first = await load_live_model(connection)

            second_root = tmp_path / "second"
            second_bundle, _ = write_bundle(second_root)
            _configure(monkeypatch, second_root, second_bundle)
            async with engine.connect() as connection:
                pending = await bootstrap_live_model(connection)
                selected_pair = await connection.scalar(
                    select(tables.live_model_selections.c.model_pair_id).where(
                        tables.live_model_selections.c.device_id == LIVE_DEVICE_ID
                    )
                )
                assert selected_pair == first.identity.model_pair_id
                assert not pending.activated

            owner = f"task5-{uuid4().hex}"
            async with engine.connect() as connection:
                lease = await acquire_writer_lease(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    lease_owner=owner,
                    lease_seconds=60,
                )
                assert lease is not None
                async with connection.begin():
                    activation, duplicate = await apply_live_activation(
                        connection,
                        request_id=pending.request_id,
                        device_id=LIVE_DEVICE_ID,
                        model_pair_id=pending.model_pair_id,
                        fencing_token=int(lease["fencing_token"]),
                    )
                assert not duplicate
                assert activation["model_pair_id"] == pending.model_pair_id

            async with engine.connect() as connection:
                second = await load_live_model(
                    connection, previous_identity=first.identity
                )
                assert second.identity.model_pair_id != first.identity.model_pair_id
                assert second.identity.activation_id > first.identity.activation_id
                assert second.reset_required
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_load_uses_bundle_persisted_with_each_activation_under_fixed_worker_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_bundle, _ = write_bundle(tmp_path, bundle_id="activation-a")
    second_bundle, _ = write_bundle(tmp_path, bundle_id="activation-b")

    async def run() -> None:
        engine = _engine()
        try:
            _configure(monkeypatch, tmp_path, first_bundle)
            async with engine.connect() as connection:
                first_registration = await bootstrap_live_model(connection)
                await _activate_pending(connection, first_registration)
                first = await load_live_model(connection)

            _configure(monkeypatch, tmp_path, second_bundle)
            async with engine.connect() as connection:
                second_registration = await bootstrap_live_model(connection)
                await _activate_pending(connection, second_registration)

                active = await load_live_model(connection)
                older = await load_live_model(
                    connection,
                    activation_id=first.identity.activation_id,
                )

                assert os.environ["LIVE_MODEL_BUNDLE_ID"] == second_bundle
                assert active.model_version == second_registration.model_version
                assert older.model_version == first_registration.model_version
                assert older.identity == first.identity
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_runtime_request_can_reactivate_a_previously_used_pair_idempotently(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first_root = tmp_path / "first"
    first_bundle, _ = write_bundle(first_root)
    second_root = tmp_path / "second"
    second_bundle, _ = write_bundle(second_root)

    async def run() -> None:
        engine = _engine()
        try:
            _configure(monkeypatch, first_root, first_bundle)
            async with engine.connect() as connection:
                first_registration = await bootstrap_live_model(connection)
                await _activate_pending(connection, first_registration)
                first = await load_live_model(connection)

            _configure(monkeypatch, second_root, second_bundle)
            async with engine.connect() as connection:
                second_registration = await bootstrap_live_model(connection)
                await _activate_pending(connection, second_registration)
                second = await load_live_model(
                    connection, previous_identity=first.identity
                )
                assert second.reset_required

            owner = f"task5-reactivate-{uuid4().hex}"
            async with engine.connect() as connection:
                lease = await acquire_writer_lease(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    lease_owner=owner,
                    lease_seconds=60,
                )
                assert lease is not None
                token = int(lease["fencing_token"])
                async with connection.begin():
                    request, duplicate = await request_live_activation(
                        connection,
                        device_id=LIVE_DEVICE_ID,
                        model_pair_id=first.identity.model_pair_id,
                        requested_by="test",
                        idempotency_key="return-to-first",
                    )
                    repeated, repeated_duplicate = await request_live_activation(
                        connection,
                        device_id=LIVE_DEVICE_ID,
                        model_pair_id=first.identity.model_pair_id,
                        requested_by="test",
                        idempotency_key="return-to-first",
                    )
                    assert not duplicate
                    assert repeated_duplicate
                    assert repeated["request_id"] == request["request_id"]
                    activation, activation_duplicate = await apply_live_activation(
                        connection,
                        request_id=cast(UUID, request["request_id"]),
                        device_id=LIVE_DEVICE_ID,
                        model_pair_id=first.identity.model_pair_id,
                        fencing_token=token,
                    )
                    assert not activation_duplicate
                    assert int(activation["activation_id"]) > second.identity.activation_id
                assert await release_writer_lease(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    lease_owner=owner,
                    fencing_token=token,
                )

            _configure(monkeypatch, first_root, first_bundle)
            async with engine.connect() as connection:
                reactivated = await load_live_model(
                    connection, previous_identity=second.identity
                )
                assert reactivated.identity.model_pair_id == first.identity.model_pair_id
                assert reactivated.reset_required
        finally:
            await engine.dispose()

    asyncio.run(run())
