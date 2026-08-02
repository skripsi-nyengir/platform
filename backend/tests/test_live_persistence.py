from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone
from typing import cast
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import event, func, insert, select, text, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.sql.live import (
    LIVE_DEVICE_ID,
    LiveLeaseLost,
    acquire_writer_lease,
    commit_boundary_effect,
    insert_live_telemetry,
    live_activation_row,
    live_selection_row,
    mark_telemetry_processed,
    publish_live_inference,
    publish_processing_boundary,
    read_live_cursor,
    read_live_health,
    release_writer_lease,
    renew_writer_lease,
    resolve_live_episode,
    unprocessed_live_tail,
    write_live_health,
)


def _engine() -> AsyncEngine:
    return create_database_engine(Settings.from_environ())


async def _next_received_ts(engine: AsyncEngine) -> datetime:
    async with engine.connect() as connection:
        latest = cast(
            datetime | None,
            await connection.scalar(select(func.max(tables.live_telemetry.c.received_ts))),
        )
    return (latest or datetime(2040, 1, 1)) + timedelta(seconds=1)


async def _next_epoch(engine: AsyncEngine) -> int:
    async with engine.connect() as connection:
        telemetry_epoch = cast(
            int,
            await connection.scalar(
                select(func.coalesce(func.max(tables.live_telemetry.c.continuity_epoch), 0))
            ),
        )
        boundary_epoch = cast(
            int,
            await connection.scalar(
                select(
                    func.coalesce(
                        func.max(tables.live_processing_boundaries.c.continuity_epoch),
                        0,
                    )
                )
            ),
        )
        cursor_epoch = cast(
            int,
            await connection.scalar(
                select(func.coalesce(func.max(tables.live_cursors.c.continuity_epoch), 0))
            ),
        )
    return max(telemetry_epoch, boundary_epoch, cursor_epoch) + 1


async def _committed_cursor_key(engine: AsyncEngine) -> tuple[datetime, UUID] | None:
    async with engine.connect() as connection:
        cursor = await read_live_cursor(connection, device_id=LIVE_DEVICE_ID)
    if cursor is None or cursor["received_ts"] is None:
        return None
    return cast(datetime, cursor["received_ts"]), cast(UUID, cursor["telemetry_id"])


@pytest.fixture(scope="module")
def live_lineage() -> dict[str, object]:
    async def create() -> dict[str, object]:
        suffix = uuid4().hex
        corpus_id = f"live-persistence-corpus-{suffix}"
        model_key = f"live-persistence-model-{suffix}"
        model_version = f"{model_key}-v1"
        core_activation_id = f"live-persistence-activation-{suffix}"
        replay_job_id = f"live-persistence-replay-{suffix}"
        archive_sha256 = suffix * 2
        engine = _engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    insert(tables.corpora).values(
                        corpus_id=corpus_id,
                        device_id=LIVE_DEVICE_ID,
                        status="published",
                        archive_sha256=archive_sha256,
                        member_sha256=None,
                        preprocessing_contract_version="live-v1",
                        source_device_uuid=None,
                        time_zone="Asia/Jakarta",
                        interval_start=datetime(2035, 1, 1),
                        interval_end=datetime(2036, 1, 1),
                        filter_config={},
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        accepted_count=10,
                        ignored_index_count=0,
                        rejection_counts={},
                    )
                )
                await connection.execute(
                    insert(tables.preprocessing_snapshots).values(
                        corpus_id=corpus_id,
                        channels=["temperature_c", "relative_humidity_pct"],
                        window_size=10,
                        stride=1,
                        contract_status="live_10",
                        segment_metadata=[],
                        split_boundaries={},
                        split_counts={},
                        scaler={},
                    )
                )
                await connection.execute(
                    insert(tables.model_families).values(
                        model_key=model_key,
                        display_name="Live persistence test model",
                        is_public=False,
                    )
                )
                await connection.execute(
                    insert(tables.model_versions).values(
                        version=model_version,
                        model_key=model_key,
                        runtime_kind="artifact",
                        is_selectable=True,
                        adapter_key="live-persistence-test",
                        schema_version="live-v1",
                        channels=["temperature_c", "relative_humidity_pct"],
                        window_size=10,
                        stride=1,
                        contract_status="live_10",
                        score_key="score",
                        score_semantics="higher-is-more-anomalous",
                        threshold=1.0,
                        threshold_policy={},
                        temporal_semantics="context_end",
                        source_commit=None,
                        source_config=None,
                        manifest_sha256=None,
                        model_manifest_sha256="a" * 64,
                        checkpoint_sha256="b" * 64,
                        scaler_manifest_sha256="c" * 64,
                        scaler_sha256="d" * 64,
                        created_at=datetime.now(timezone.utc),
                    )
                )
                model_pair_id = cast(
                    UUID,
                    await connection.scalar(
                        text(
                            """
                            INSERT INTO live_model_pairs (
                                model_version, checkpoint_identity,
                                scaler_snapshot_corpus_id,
                                model_manifest_sha256, checkpoint_sha256,
                                scaler_manifest_sha256, scaler_sha256,
                                threshold, contract_status
                            ) VALUES (
                                :model_version, :checkpoint_identity, :corpus_id,
                                repeat('a', 64), repeat('b', 64),
                                repeat('c', 64), repeat('d', 64),
                                1.0, 'live_10'
                            ) RETURNING model_pair_id
                            """
                        ),
                        {
                            "model_version": model_version,
                            "checkpoint_identity": f"checkpoint-{suffix}",
                            "corpus_id": corpus_id,
                        },
                    ),
                )
                request_id = cast(
                    UUID,
                    await connection.scalar(
                        text(
                            """
                            INSERT INTO live_model_activation_requests (
                                device_id, model_pair_id, request_hash, requested_by
                            ) VALUES (
                                :device_id, :model_pair_id, :request_hash, 'test'
                            ) RETURNING request_id
                            """
                        ),
                        {
                            "device_id": LIVE_DEVICE_ID,
                            "model_pair_id": model_pair_id,
                            "request_hash": f"request-{suffix}",
                        },
                    ),
                )
                activation = (
                    await connection.execute(
                        text(
                            """
                            INSERT INTO live_model_activations (
                                device_id, request_id, model_pair_id, fencing_token
                            ) VALUES (
                                :device_id, :request_id, :model_pair_id, 1
                            ) RETURNING activation_event_id, activation_id
                            """
                        ),
                        {
                            "device_id": LIVE_DEVICE_ID,
                            "request_id": request_id,
                            "model_pair_id": model_pair_id,
                        },
                    )
                ).mappings().one()
                await connection.execute(
                    text(
                        """
                        INSERT INTO live_model_selections (
                            device_id, activation_event_id, model_pair_id,
                            activation_id
                        ) VALUES (
                            :device_id, :activation_event_id, :model_pair_id,
                            :activation_id
                        ) ON CONFLICT (device_id) DO UPDATE SET
                            activation_event_id = EXCLUDED.activation_event_id,
                            model_pair_id = EXCLUDED.model_pair_id,
                            activation_id = EXCLUDED.activation_id,
                            selected_at_utc = now()
                        WHERE live_model_selections.activation_id
                            < EXCLUDED.activation_id
                        """
                    ),
                    {
                        "device_id": LIVE_DEVICE_ID,
                        "activation_event_id": activation["activation_event_id"],
                        "model_pair_id": model_pair_id,
                        "activation_id": activation["activation_id"],
                    },
                )
                await connection.execute(
                    insert(tables.model_activations).values(
                        activation_id=core_activation_id,
                        command_id=f"live-persistence-command-{suffix}",
                        payload_hash=f"live-persistence-payload-{suffix}",
                        device_id=LIVE_DEVICE_ID,
                        prior_model_version=None,
                        model_version=model_version,
                        changed=True,
                        activated_at=datetime.now(timezone.utc),
                        actor="test",
                    )
                )
                await connection.execute(
                    insert(tables.replay_jobs).values(
                        job_id=replay_job_id,
                        logical_job_hash=f"live-persistence-job-{suffix}",
                        device_id=LIVE_DEVICE_ID,
                        corpus_id=corpus_id,
                        archive_sha256=archive_sha256,
                        preprocessing_contract_version="live-v1",
                        activation_id=core_activation_id,
                        model_version=model_version,
                        score_provenance="artifact_backed",
                        from_ts=datetime(2035, 1, 1),
                        to_ts=datetime(2035, 1, 2),
                        status="succeeded",
                        lease_owner=None,
                        lease_expires_at=None,
                        heartbeat_at=None,
                        attempt_count=1,
                        max_attempts=3,
                        next_corpus_index=0,
                        processed_count=0,
                        result_count=0,
                        episode_count=0,
                        submitted_at=datetime.now(timezone.utc),
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        error_code=None,
                        error_detail=None,
                    )
                )
            return {
                "activation_id": cast(int, activation["activation_id"]),
                "corpus_id": corpus_id,
                "model_pair_id": model_pair_id,
                "model_version": model_version,
                "replay_job_id": replay_job_id,
            }
        finally:
            await engine.dispose()

    return asyncio.run(create())


async def _leased_engine(owner: str) -> AsyncIterator[tuple[AsyncEngine, RowMapping]]:
    engine = _engine()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                """
                UPDATE live_writer_leases
                SET lease_expires_at_utc = clock_timestamp() - interval '1 second'
                WHERE device_id = :device_id
                """
            ),
            {"device_id": LIVE_DEVICE_ID},
        )
    async with engine.connect() as connection:
        lease = await acquire_writer_lease(
            connection,
            device_id=LIVE_DEVICE_ID,
            lease_owner=owner,
            lease_seconds=60,
        )
    assert lease is not None
    try:
        yield engine, lease
    finally:
        await engine.dispose()


async def _insert_series(
    engine: AsyncEngine,
    *,
    lease: RowMapping,
    activation_id: int,
    continuity_epoch: int,
    start: datetime,
    count: int,
) -> list[tuple[datetime, UUID]]:
    cursor_key = await _committed_cursor_key(engine)
    async with engine.connect() as connection:
        boundary, duplicate = await publish_processing_boundary(
            connection,
            device_id=LIVE_DEVICE_ID,
            boundary_reason="startup",
            ingress_generation=continuity_epoch,
            continuity_epoch=continuity_epoch,
            fencing_token=cast(int, lease["fencing_token"]),
            after_key=cursor_key,
        )
        await commit_boundary_effect(
            connection,
            device_id=LIVE_DEVICE_ID,
            boundary_id=cast(int, boundary["boundary_id"]),
            fencing_token=cast(int, lease["fencing_token"]),
        )
    assert not duplicate
    keys: list[tuple[datetime, UUID]] = []
    for index in range(count):
        key = (start + timedelta(seconds=index * 6), uuid4())
        async with engine.connect() as connection:
            row = await insert_live_telemetry(
                connection,
                telemetry_id=key[1],
                device_id=LIVE_DEVICE_ID,
                received_ts=key[0],
                received_at_utc=key[0].replace(tzinfo=timezone.utc),
                temperature_c=25.0 + index,
                relative_humidity_pct=60.0 + index,
                ingress_generation=continuity_epoch,
                activation_id=activation_id,
                continuity_epoch=continuity_epoch,
                segment_start_reason="startup" if index == 0 else None,
                fencing_token=cast(int, lease["fencing_token"]),
            )
        assert row["processing_status"] == "pending"
        keys.append(key)
    return keys


def _alert_values(
    *,
    alert_id: str,
    live_episode_id: UUID,
    score_ts: datetime,
    model_version: str,
    corpus_id: str,
    replay_job_id: str | None,
) -> dict[str, object]:
    return {
        "alert_id": alert_id,
        "device_id": LIVE_DEVICE_ID,
        "detected_at": None,
        "score": 2.5,
        "threshold": 1.0,
        "model_version": model_version,
        "inference_result_window_start_ts": score_ts - timedelta(seconds=54),
        "inference_result_window_end_ts": score_ts,
        "detection_basis": "artifact_backed",
        "corpus_id": corpus_id,
        "episode_start_ts": score_ts,
        "episode_end_ts": score_ts,
        "last_score_ts": score_ts,
        "created_at": datetime.now(timezone.utc),
        "peak_score": 2.5,
        "latest_score": 2.5,
        "anomalous_window_count": 1,
        "replay_job_id": replay_job_id,
        "segment_id": 1,
        "closure_reason": "normal",
        "live_episode_id": live_episode_id,
    }


@pytest.mark.anyio
async def test_telemetry_commits_before_inference_and_identity_is_immutable(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"durable-{uuid4().hex}"):
        activation_id = cast(int, live_lineage["activation_id"])
        epoch = await _next_epoch(engine)
        received_ts = await _next_received_ts(engine)
        async with engine.connect() as connection:
            boundary, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="startup",
                ingress_generation=epoch,
                continuity_epoch=epoch,
                fencing_token=cast(int, lease["fencing_token"]),
                after_key=await _committed_cursor_key(engine),
            )
            telemetry = await insert_live_telemetry(
                connection,
                telemetry_id=uuid4(),
                device_id=LIVE_DEVICE_ID,
                received_ts=received_ts,
                received_at_utc=received_ts.replace(tzinfo=timezone.utc),
                temperature_c=25.0,
                relative_humidity_pct=60.0,
                ingress_generation=epoch,
                activation_id=activation_id,
                continuity_epoch=epoch,
                segment_start_reason="startup",
                fencing_token=cast(int, lease["fencing_token"]),
            )

        async with engine.connect() as reader:
            assert await reader.scalar(
                select(func.count()).select_from(tables.live_telemetry).where(
                    tables.live_telemetry.c.telemetry_id
                    == telemetry["telemetry_id"]
                )
            ) == 1
            assert await reader.scalar(
                select(func.count()).select_from(tables.live_inference).where(
                    tables.live_inference.c.continuity_epoch == epoch
                )
            ) == 0

        async with engine.connect() as connection:
            with pytest.raises(DBAPIError, match="identity is immutable"):
                async with connection.begin():
                    await connection.execute(
                        update(tables.live_telemetry)
                        .where(
                            tables.live_telemetry.c.received_ts == received_ts,
                            tables.live_telemetry.c.telemetry_id
                            == telemetry["telemetry_id"],
                        )
                        .values(ingress_generation=epoch + 1)
                    )

        async with engine.connect() as connection:
            with pytest.raises(DBAPIError, match="identity is immutable"):
                async with connection.begin():
                    await connection.execute(
                        update(tables.live_telemetry)
                        .where(
                            tables.live_telemetry.c.received_ts == received_ts,
                            tables.live_telemetry.c.telemetry_id
                            == telemetry["telemetry_id"],
                        )
                        .values(activation_id=activation_id + 1)
                    )

        async with engine.connect() as connection:
            with pytest.raises(DBAPIError):
                await insert_live_telemetry(
                    connection,
                    telemetry_id=uuid4(),
                    device_id=LIVE_DEVICE_ID,
                    received_ts=received_ts + timedelta(seconds=1),
                    received_at_utc=(received_ts + timedelta(seconds=1)).replace(
                        tzinfo=timezone.utc
                    ),
                    temperature_c=float("inf"),
                    relative_humidity_pct=60.0,
                    ingress_generation=epoch,
                    activation_id=activation_id,
                    continuity_epoch=epoch,
                    segment_start_reason=None,
                    fencing_token=cast(int, lease["fencing_token"]),
                )
        async with engine.connect() as reader:
            assert await reader.scalar(
                select(func.count()).select_from(tables.live_inference).where(
                    tables.live_inference.c.continuity_epoch == epoch
                )
            ) == 0
            assert await reader.scalar(
                select(func.count()).select_from(tables.live_alert_episodes).where(
                    tables.live_alert_episodes.c.continuity_epoch == epoch
                )
            ) == 0
        async with engine.connect() as connection:
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, boundary["boundary_id"]),
                fencing_token=cast(int, lease["fencing_token"]),
            )
            assert await mark_telemetry_processed(
                connection,
                device_id=LIVE_DEVICE_ID,
                telemetry_key=(received_ts, cast(UUID, telemetry["telemetry_id"])),
                continuity_epoch=epoch,
                fencing_token=cast(int, lease["fencing_token"]),
            )


@pytest.mark.anyio
async def test_equal_second_keyset_tail_orders_anchored_boundaries(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"tail-{uuid4().hex}"):
        activation_id = cast(int, live_lineage["activation_id"])
        first_epoch = await _next_epoch(engine)
        second_epoch = first_epoch + 1
        received_ts = await _next_received_ts(engine)
        telemetry_ids = sorted((uuid4(), uuid4(), uuid4()))
        token = cast(int, lease["fencing_token"])
        async with engine.connect() as connection:
            startup, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="startup",
                ingress_generation=first_epoch,
                continuity_epoch=first_epoch,
                fencing_token=token,
                after_key=await _committed_cursor_key(engine),
            )
            for index in range(2):
                await insert_live_telemetry(
                    connection,
                    telemetry_id=telemetry_ids[index],
                    device_id=LIVE_DEVICE_ID,
                    received_ts=received_ts,
                    received_at_utc=received_ts.replace(tzinfo=timezone.utc),
                    temperature_c=25.0 + index,
                    relative_humidity_pct=60.0 + index,
                    ingress_generation=first_epoch,
                    activation_id=activation_id,
                    continuity_epoch=first_epoch,
                    segment_start_reason="startup" if index == 0 else None,
                    fencing_token=token,
                )
            overload, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="overload",
                ingress_generation=second_epoch,
                continuity_epoch=second_epoch,
                fencing_token=token,
                after_key=(received_ts, telemetry_ids[1]),
            )
            await insert_live_telemetry(
                connection,
                telemetry_id=telemetry_ids[2],
                device_id=LIVE_DEVICE_ID,
                received_ts=received_ts,
                received_at_utc=received_ts.replace(tzinfo=timezone.utc),
                temperature_c=27.0,
                relative_humidity_pct=62.0,
                ingress_generation=second_epoch,
                activation_id=activation_id,
                continuity_epoch=second_epoch,
                segment_start_reason="overload",
                fencing_token=token,
            )
            whole_tail = await unprocessed_live_tail(
                connection,
                device_id=LIVE_DEVICE_ID,
                after_key=(
                    received_ts - timedelta(seconds=1),
                    UUID(int=(1 << 128) - 1),
                ),
                last_boundary_id=cast(int, startup["boundary_id"]) - 1,
                limit=10,
            )
            keyset_tail = await unprocessed_live_tail(
                connection,
                device_id=LIVE_DEVICE_ID,
                after_key=(received_ts, telemetry_ids[0]),
                last_boundary_id=cast(int, startup["boundary_id"]),
                limit=10,
            )

        assert [item["kind"] for item in whole_tail] == [
            "boundary",
            "telemetry",
            "telemetry",
            "boundary",
            "telemetry",
        ]
        assert [item["kind"] for item in keyset_tail] == [
            "telemetry",
            "boundary",
            "telemetry",
        ]
        assert keyset_tail[0]["telemetry_id"] == telemetry_ids[1]
        assert keyset_tail[0]["received_ts"] == received_ts
        assert keyset_tail[0]["received_at_utc"] == received_ts.replace(
            tzinfo=timezone.utc
        )
        assert keyset_tail[1]["boundary_id"] == overload["boundary_id"]
        assert keyset_tail[1]["after_received_ts"] == received_ts
        assert keyset_tail[1]["after_telemetry_id"] == telemetry_ids[1]
        assert isinstance(keyset_tail[1]["recorded_at_utc"], datetime)
        assert keyset_tail[2]["telemetry_id"] == telemetry_ids[2]
        async with engine.connect() as connection:
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, startup["boundary_id"]),
                fencing_token=token,
            )
            for telemetry_id in telemetry_ids[:2]:
                assert await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=(received_ts, telemetry_id),
                    continuity_epoch=first_epoch,
                    fencing_token=token,
                )
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, overload["boundary_id"]),
                fencing_token=token,
            )
            assert await mark_telemetry_processed(
                connection,
                device_id=LIVE_DEVICE_ID,
                telemetry_key=(received_ts, telemetry_ids[2]),
                continuity_epoch=second_epoch,
                fencing_token=token,
            )


@pytest.mark.anyio
async def test_late_same_second_smaller_uuid_row_is_not_stranded(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"late-arrival-{uuid4().hex}"):
        activation_id = cast(int, live_lineage["activation_id"])
        token = cast(int, lease["fencing_token"])
        epoch = await _next_epoch(engine)
        received_ts = await _next_received_ts(engine)
        # Same whole-second received_ts; the later arrival (low_id) sorts BEFORE
        # the earlier one by UUID, so telemetry_id ordering would strand it.
        high_id, low_id = sorted((uuid4(), uuid4()), reverse=True)
        async with engine.connect() as connection:
            startup, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="startup",
                ingress_generation=epoch,
                continuity_epoch=epoch,
                fencing_token=token,
                after_key=await _committed_cursor_key(engine),
            )
            await insert_live_telemetry(
                connection,
                telemetry_id=high_id,
                device_id=LIVE_DEVICE_ID,
                received_ts=received_ts,
                received_at_utc=received_ts.replace(tzinfo=timezone.utc),
                temperature_c=25.0,
                relative_humidity_pct=60.0,
                ingress_generation=epoch,
                activation_id=activation_id,
                continuity_epoch=epoch,
                segment_start_reason="startup",
                fencing_token=token,
            )
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, startup["boundary_id"]),
                fencing_token=token,
            )
            assert await mark_telemetry_processed(
                connection,
                device_id=LIVE_DEVICE_ID,
                telemetry_key=(received_ts, high_id),
                continuity_epoch=epoch,
                fencing_token=token,
            )
            await insert_live_telemetry(
                connection,
                telemetry_id=low_id,
                device_id=LIVE_DEVICE_ID,
                received_ts=received_ts,
                received_at_utc=received_ts.replace(tzinfo=timezone.utc),
                temperature_c=26.0,
                relative_humidity_pct=61.0,
                ingress_generation=epoch,
                activation_id=activation_id,
                continuity_epoch=epoch,
                segment_start_reason=None,
                fencing_token=token,
            )
            tail = await unprocessed_live_tail(
                connection,
                device_id=LIVE_DEVICE_ID,
                after_key=(received_ts, high_id),
                last_boundary_id=cast(int, startup["boundary_id"]),
                limit=10,
            )
            assert [item["telemetry_id"] for item in tail] == [low_id]
            await connection.rollback()
            assert await mark_telemetry_processed(
                connection,
                device_id=LIVE_DEVICE_ID,
                telemetry_key=(received_ts, low_id),
                continuity_epoch=epoch,
                fencing_token=token,
            )
            cursor = await read_live_cursor(connection, device_id=LIVE_DEVICE_ID)
            assert cursor is not None
            assert cursor["telemetry_id"] == low_id


@pytest.mark.anyio
async def test_same_second_window_scores_in_ingress_order(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"same-second-score-{uuid4().hex}"):
        epoch = await _next_epoch(engine)
        token = cast(int, lease["fencing_token"])
        activation_id = cast(int, live_lineage["activation_id"])
        start = await _next_received_ts(engine)
        # Rows 8 and 9 share a whole-second received_ts; the later arrival (row 9)
        # sorts BEFORE row 8 by UUID, so telemetry_id ordering would mis-order the window.
        high_id, low_id = sorted((uuid4(), uuid4()), reverse=True)
        same_second = start + timedelta(seconds=8 * 6)
        specs = [
            (start + timedelta(seconds=index * 6), uuid4()) for index in range(8)
        ]
        specs.append((same_second, high_id))
        specs.append((same_second, low_id))
        async with engine.connect() as connection:
            boundary, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="startup",
                ingress_generation=epoch,
                continuity_epoch=epoch,
                fencing_token=token,
                after_key=await _committed_cursor_key(engine),
            )
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, boundary["boundary_id"]),
                fencing_token=token,
            )
            for index, (received_ts, telemetry_id) in enumerate(specs):
                await insert_live_telemetry(
                    connection,
                    telemetry_id=telemetry_id,
                    device_id=LIVE_DEVICE_ID,
                    received_ts=received_ts,
                    received_at_utc=received_ts.replace(tzinfo=timezone.utc),
                    temperature_c=25.0 + index,
                    relative_humidity_pct=60.0 + index,
                    ingress_generation=epoch,
                    activation_id=activation_id,
                    continuity_epoch=epoch,
                    segment_start_reason="startup" if index == 0 else None,
                    fencing_token=token,
                )
            for key in specs[:9]:
                assert await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=key,
                    continuity_epoch=epoch,
                    fencing_token=token,
                )
            result, duplicate = await publish_live_inference(
                connection,
                device_id=LIVE_DEVICE_ID,
                source_keys=specs,
                score=1.0,
                is_anomaly=False,
                severity_at_score="info",
                fencing_token=token,
            )
            assert not duplicate
            source_rows = (
                await connection.execute(
                    select(
                        tables.live_inference_sources.c.ordinal,
                        tables.live_inference_sources.c.received_ts,
                        tables.live_inference_sources.c.telemetry_id,
                    )
                    .where(
                        tables.live_inference_sources.c.score_ts == specs[-1][0],
                        tables.live_inference_sources.c.inference_id
                        == result["inference_id"],
                    )
                    .order_by(tables.live_inference_sources.c.ordinal)
                )
            ).all()
            assert source_rows == [
                (ordinal, received_ts, telemetry_id)
                for ordinal, (received_ts, telemetry_id) in enumerate(specs)
            ]


@pytest.mark.anyio
async def test_row_effects_wait_for_boundary_and_prior_telemetry(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"effects-{uuid4().hex}"):
        epoch = await _next_epoch(engine)
        token = cast(int, lease["fencing_token"])
        received_ts = await _next_received_ts(engine)
        telemetry_ids = (uuid4(), uuid4())
        async with engine.connect() as connection:
            boundary, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="startup",
                ingress_generation=epoch,
                continuity_epoch=epoch,
                fencing_token=token,
                after_key=await _committed_cursor_key(engine),
            )
            for index, telemetry_id in enumerate(telemetry_ids):
                await insert_live_telemetry(
                    connection,
                    telemetry_id=telemetry_id,
                    device_id=LIVE_DEVICE_ID,
                    received_ts=received_ts + timedelta(seconds=index),
                    received_at_utc=(received_ts + timedelta(seconds=index)).replace(
                        tzinfo=timezone.utc
                    ),
                    temperature_c=25.0,
                    relative_humidity_pct=60.0,
                    ingress_generation=epoch,
                    activation_id=cast(int, live_lineage["activation_id"]),
                    continuity_epoch=epoch,
                    segment_start_reason="startup" if index == 0 else None,
                    fencing_token=token,
                )
            cursor_before = await read_live_cursor(
                connection, device_id=LIVE_DEVICE_ID
            )
            cursor_before_values = (
                dict(cursor_before) if cursor_before is not None else None
            )
            await connection.rollback()

            with pytest.raises(ValueError, match="processing boundary"):
                await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=(received_ts, telemetry_ids[0]),
                    continuity_epoch=epoch,
                    fencing_token=token,
                )
            cursor_after = await read_live_cursor(
                connection, device_id=LIVE_DEVICE_ID
            )
            assert (
                dict(cursor_after) if cursor_after is not None else None
            ) == cursor_before_values
            await connection.rollback()

            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, boundary["boundary_id"]),
                fencing_token=token,
            )
            with pytest.raises(ValueError, match="global earliest pending"):
                await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=(
                        received_ts + timedelta(seconds=1),
                        telemetry_ids[1],
                    ),
                    continuity_epoch=epoch,
                    fencing_token=token,
                )
            for index, telemetry_id in enumerate(telemetry_ids):
                assert await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=(
                        received_ts + timedelta(seconds=index),
                        telemetry_id,
                    ),
                    continuity_epoch=epoch,
                    fencing_token=token,
                )


@pytest.mark.anyio
async def test_inference_requires_committed_warmup_effects(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"warmup-{uuid4().hex}"):
        epoch = await _next_epoch(engine)
        token = cast(int, lease["fencing_token"])
        keys = await _insert_series(
            engine,
            lease=lease,
            activation_id=cast(int, live_lineage["activation_id"]),
            continuity_epoch=epoch,
            start=await _next_received_ts(engine),
            count=10,
        )
        async with engine.connect() as connection:
            with pytest.raises(ValueError, match="warm-up"):
                await publish_live_inference(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    source_keys=keys,
                    score=2.5,
                    is_anomaly=True,
                    severity_at_score="critical",
                    fencing_token=token,
                )
            assert await connection.scalar(
                select(func.count()).select_from(tables.live_inference).where(
                    tables.live_inference.c.continuity_epoch == epoch
                )
            ) == 0
            assert await connection.scalar(
                select(func.count()).select_from(tables.live_telemetry).where(
                    tables.live_telemetry.c.continuity_epoch == epoch,
                    tables.live_telemetry.c.processing_status == "pending",
                )
            ) == 10
            await connection.rollback()
            for key in keys:
                assert await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=key,
                    continuity_epoch=epoch,
                    fencing_token=token,
                )


@pytest.mark.anyio
async def test_inference_retry_is_noop_and_failed_alert_rolls_back_cursor(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"result-{uuid4().hex}"):
        epoch = await _next_epoch(engine)
        token = cast(int, lease["fencing_token"])
        keys = await _insert_series(
            engine,
            lease=lease,
            activation_id=cast(int, live_lineage["activation_id"]),
            continuity_epoch=epoch,
            start=await _next_received_ts(engine),
            count=11,
        )
        async with engine.connect() as connection:
            for key in keys[:9]:
                assert await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=key,
                    continuity_epoch=epoch,
                    fencing_token=token,
                )
            result, duplicate = await publish_live_inference(
                connection,
                device_id=LIVE_DEVICE_ID,
                source_keys=keys[:10],
                score=2.5,
                is_anomaly=True,
                severity_at_score="critical",
                fencing_token=token,
            )
            retried, retried_duplicate = await publish_live_inference(
                connection,
                device_id=LIVE_DEVICE_ID,
                source_keys=keys[:10],
                score=99.0,
                is_anomaly=True,
                severity_at_score="critical",
                fencing_token=token,
            )
            cursor_before_failure = await read_live_cursor(
                connection, device_id=LIVE_DEVICE_ID
            )

        assert not duplicate
        assert retried_duplicate
        assert retried["inference_id"] == result["inference_id"]
        assert cursor_before_failure is not None
        assert cursor_before_failure["telemetry_id"] == keys[9][1]

        invalid_episode_id = uuid4()
        with pytest.raises(IntegrityError):
            async with engine.connect() as connection:
                await publish_live_inference(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    source_keys=keys[1:11],
                    score=2.5,
                    is_anomaly=True,
                    severity_at_score="critical",
                    fencing_token=token,
                    live_episode_id=invalid_episode_id,
                    alert_values=_alert_values(
                        alert_id=f"invalid-alert-{uuid4().hex}",
                        live_episode_id=invalid_episode_id,
                        score_ts=keys[10][0],
                        model_version=cast(str, live_lineage["model_version"]),
                        corpus_id=cast(str, live_lineage["corpus_id"]),
                        replay_job_id="missing-replay-job",
                    ),
                    alert_actor="test",
                )
        async with engine.connect() as connection:
            cursor_after_failure = await read_live_cursor(
                connection, device_id=LIVE_DEVICE_ID
            )
            assert cursor_after_failure is not None
            assert cursor_after_failure["telemetry_id"] == keys[9][1]
            assert await connection.scalar(
                select(tables.live_telemetry.c.processing_status).where(
                    tables.live_telemetry.c.received_ts == keys[10][0],
                    tables.live_telemetry.c.telemetry_id == keys[10][1],
                )
            ) == "pending"
            assert await connection.scalar(
                select(func.count()).select_from(tables.live_inference).where(
                    tables.live_inference.c.continuity_epoch == epoch
                )
            ) == 1
            assert await connection.scalar(
                select(func.count())
                .select_from(tables.live_inference_sources)
                .where(
                    tables.live_inference_sources.c.inference_id
                    == result["inference_id"]
                )
            ) == 10
            source_rows = (
                await connection.execute(
                    select(
                        tables.live_inference_sources.c.ordinal,
                        tables.live_inference_sources.c.received_ts,
                        tables.live_inference_sources.c.telemetry_id,
                    )
                    .where(
                        tables.live_inference_sources.c.inference_id
                        == result["inference_id"]
                    )
                    .order_by(tables.live_inference_sources.c.ordinal)
                )
            ).all()
            assert source_rows == [
                (ordinal, received_ts, telemetry_id)
                for ordinal, (received_ts, telemetry_id) in enumerate(keys[:10])
            ]
            await connection.rollback()
            assert await mark_telemetry_processed(
                connection,
                device_id=LIVE_DEVICE_ID,
                telemetry_key=keys[10],
                continuity_epoch=epoch,
                fencing_token=token,
            )


@pytest.mark.anyio
async def test_live_episode_alert_rejects_replay_lineage(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"alert-lineage-{uuid4().hex}"):
        epoch = await _next_epoch(engine)
        token = cast(int, lease["fencing_token"])
        keys = await _insert_series(
            engine,
            lease=lease,
            activation_id=cast(int, live_lineage["activation_id"]),
            continuity_epoch=epoch,
            start=await _next_received_ts(engine),
            count=10,
        )
        episode_id = uuid4()
        async with engine.connect() as connection:
            for key in keys[:9]:
                await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=key,
                    continuity_epoch=epoch,
                    fencing_token=token,
                )
        with pytest.raises(IntegrityError):
            async with engine.connect() as connection:
                await publish_live_inference(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    source_keys=keys,
                    score=2.5,
                    is_anomaly=True,
                    severity_at_score="critical",
                    fencing_token=token,
                    live_episode_id=episode_id,
                    alert_values=_alert_values(
                        alert_id=f"invalid-live-alert-{uuid4().hex}",
                        live_episode_id=episode_id,
                        score_ts=keys[-1][0],
                        model_version=cast(str, live_lineage["model_version"]),
                        corpus_id=cast(str, live_lineage["corpus_id"]),
                        replay_job_id=cast(str, live_lineage["replay_job_id"]),
                    ),
                    alert_actor="test",
                )
        async with engine.connect() as connection:
            assert await mark_telemetry_processed(
                connection,
                device_id=LIVE_DEVICE_ID,
                telemetry_key=keys[-1],
                continuity_epoch=epoch,
                fencing_token=token,
            )


@pytest.mark.anyio
async def test_linked_episode_alert_is_atomic_and_not_duplicated(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"alert-{uuid4().hex}"):
        epoch = await _next_epoch(engine)
        token = cast(int, lease["fencing_token"])
        keys = await _insert_series(
            engine,
            lease=lease,
            activation_id=cast(int, live_lineage["activation_id"]),
            continuity_epoch=epoch,
            start=await _next_received_ts(engine),
            count=10,
        )
        episode_id = uuid4()
        alert_id = f"live-alert-{uuid4().hex}"
        alert_values = _alert_values(
            alert_id=alert_id,
            live_episode_id=episode_id,
            score_ts=keys[-1][0],
            model_version=cast(str, live_lineage["model_version"]),
            corpus_id=cast(str, live_lineage["corpus_id"]),
            replay_job_id=None,
        )
        async with engine.connect() as connection:
            for key in keys[:9]:
                await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=key,
                    continuity_epoch=epoch,
                    fencing_token=token,
                )
            result, duplicate = await publish_live_inference(
                connection,
                device_id=LIVE_DEVICE_ID,
                source_keys=keys,
                score=2.5,
                is_anomaly=True,
                severity_at_score="critical",
                fencing_token=token,
                live_episode_id=episode_id,
                alert_values=alert_values,
                alert_actor="test",
            )
            retried, retried_duplicate = await publish_live_inference(
                connection,
                device_id=LIVE_DEVICE_ID,
                source_keys=keys,
                score=2.5,
                is_anomaly=True,
                severity_at_score="critical",
                fencing_token=token,
                live_episode_id=episode_id,
                alert_values=alert_values,
                alert_actor="test",
            )

        assert not duplicate and retried_duplicate
        assert retried["inference_id"] == result["inference_id"]
        async with engine.connect() as connection:
            assert await connection.scalar(
                select(func.count()).select_from(tables.alerts).where(
                    tables.alerts.c.alert_id == alert_id
                )
            ) == 1
            assert await connection.scalar(
                select(func.count()).select_from(tables.alert_events).where(
                    tables.alert_events.c.alert_id == alert_id
                )
            ) == 1
            assert await connection.scalar(
                select(func.count()).select_from(tables.live_alert_episodes).where(
                    tables.live_alert_episodes.c.live_episode_id == episode_id
                )
            ) == 1
            assert await connection.scalar(
                select(func.count())
                .select_from(tables.live_alert_episode_points)
                .where(
                    tables.live_alert_episode_points.c.live_episode_id == episode_id
                )
            ) == 1
            await connection.rollback()
            assert await resolve_live_episode(
                connection,
                device_id=LIVE_DEVICE_ID,
                live_episode_id=episode_id,
                ended_score_ts=keys[-1][0],
                fencing_token=token,
            )
            assert await connection.scalar(
                select(tables.live_alert_episodes.c.status).where(
                    tables.live_alert_episodes.c.live_episode_id == episode_id
                )
            ) == "resolved"
            assert await connection.scalar(
                select(func.count()).select_from(tables.alert_events).where(
                    tables.alert_events.c.alert_id == alert_id
                )
            ) == 1


@pytest.mark.anyio
async def test_cursor_health_selection_and_fenced_takeover(
    live_lineage: dict[str, object],
) -> None:
    engine = _engine()
    stale_owner = f"stale-{uuid4().hex}"
    current_owner = f"current-{uuid4().hex}"
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    UPDATE live_writer_leases
                    SET lease_expires_at_utc = clock_timestamp() - interval '1 second'
                    WHERE device_id = :device_id
                    """
                ),
                {"device_id": LIVE_DEVICE_ID},
            )
        async with engine.connect() as connection:
            stale = await acquire_writer_lease(
                connection,
                device_id=LIVE_DEVICE_ID,
                lease_owner=stale_owner,
                lease_seconds=60,
            )
            assert stale is not None
            await write_live_health(
                connection,
                device_id=LIVE_DEVICE_ID,
                status="healthy",
                detail_code=None,
                fencing_token=cast(int, stale["fencing_token"]),
            )
            selection = await live_selection_row(
                connection, device_id=LIVE_DEVICE_ID
            )
            activation = await live_activation_row(
                connection,
                device_id=LIVE_DEVICE_ID,
                activation_id=cast(int, live_lineage["activation_id"]),
            )
        assert selection is not None and activation is not None
        assert selection["model_pair_id"] == live_lineage["model_pair_id"]
        assert activation["model_version"] == live_lineage["model_version"]

        async with engine.begin() as connection:
            await connection.execute(
                update(tables.live_writer_leases)
                .where(tables.live_writer_leases.c.device_id == LIVE_DEVICE_ID)
                .values(
                    lease_expires_at_utc=func.clock_timestamp()
                    - text("interval '1 second'")
                )
            )
        async with engine.connect() as connection:
            current = await acquire_writer_lease(
                connection,
                device_id=LIVE_DEVICE_ID,
                lease_owner=current_owner,
                lease_seconds=60,
            )
            assert current is not None
            assert current["fencing_token"] == stale["fencing_token"] + 1
            assert await renew_writer_lease(
                connection,
                device_id=LIVE_DEVICE_ID,
                lease_owner=stale_owner,
                fencing_token=cast(int, stale["fencing_token"]),
                lease_seconds=60,
            ) is None
            with pytest.raises(LiveLeaseLost):
                await write_live_health(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    status="degraded",
                    detail_code="stale_writer",
                    fencing_token=cast(int, stale["fencing_token"]),
                )
            with pytest.raises(LiveLeaseLost):
                await publish_processing_boundary(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    boundary_reason="lease_takeover",
                    ingress_generation=await _next_epoch(engine),
                    continuity_epoch=await _next_epoch(engine),
                    fencing_token=cast(int, stale["fencing_token"]),
                    after_key=None,
                )
            with pytest.raises(ValueError, match="detail_code"):
                await write_live_health(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    status="unhealthy",
                    detail_code="password=secret",
                    fencing_token=cast(int, current["fencing_token"]),
                )
            health = await write_live_health(
                connection,
                device_id=LIVE_DEVICE_ID,
                status="degraded",
                detail_code="recovering_backlog",
                fencing_token=cast(int, current["fencing_token"]),
            )
            observed = await read_live_health(
                connection, device_id=LIVE_DEVICE_ID
            )
            assert observed is not None and observed["detail_code"] == health["detail_code"]
            await connection.rollback()

            continuity_epoch = await _next_epoch(engine)
            boundary, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="lease_takeover",
                ingress_generation=continuity_epoch,
                continuity_epoch=continuity_epoch,
                fencing_token=cast(int, current["fencing_token"]),
                after_key=await _committed_cursor_key(engine),
            )
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, boundary["boundary_id"]),
                fencing_token=cast(int, current["fencing_token"]),
            )
            cursor = await read_live_cursor(connection, device_id=LIVE_DEVICE_ID)
            assert cursor is not None
            assert cursor["last_boundary_id"] == boundary["boundary_id"]
            await connection.rollback()
            assert await release_writer_lease(
                connection,
                device_id=LIVE_DEVICE_ID,
                lease_owner=current_owner,
                fencing_token=cast(int, current["fencing_token"]),
            )
            assert await renew_writer_lease(
                connection,
                device_id=LIVE_DEVICE_ID,
                lease_owner=current_owner,
                fencing_token=cast(int, current["fencing_token"]),
                lease_seconds=60,
            ) is None
            with pytest.raises(LiveLeaseLost):
                await write_live_health(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    status="unhealthy",
                    detail_code="lease_expired",
                    fencing_token=cast(int, current["fencing_token"]),
                )
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_boundary_effect_requires_committed_cursor_anchor(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"boundary-anchor-{uuid4().hex}"):
        token = cast(int, lease["fencing_token"])
        epoch = await _next_epoch(engine)
        key = (
            await _insert_series(
                engine,
                lease=lease,
                activation_id=cast(int, live_lineage["activation_id"]),
                continuity_epoch=epoch,
                start=await _next_received_ts(engine),
                count=1,
            )
        )[0]
        async with engine.connect() as connection:
            wrong_epoch = await _next_epoch(engine)
            boundary, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="data_gap",
                ingress_generation=wrong_epoch,
                continuity_epoch=wrong_epoch,
                fencing_token=token,
                after_key=key,
            )
            with pytest.raises(ValueError, match="cursor anchor"):
                await commit_boundary_effect(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    boundary_id=cast(int, boundary["boundary_id"]),
                    fencing_token=token,
                )
            assert await mark_telemetry_processed(
                connection,
                device_id=LIVE_DEVICE_ID,
                telemetry_key=key,
                continuity_epoch=epoch,
                fencing_token=token,
            )
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, boundary["boundary_id"]),
                fencing_token=token,
            )


@pytest.mark.anyio
async def test_boundary_effect_requires_next_uncommitted_boundary() -> None:
    async for engine, lease in _leased_engine(f"boundary-order-{uuid4().hex}"):
        token = cast(int, lease["fencing_token"])
        cursor_key = await _committed_cursor_key(engine)
        first_epoch = await _next_epoch(engine)
        async with engine.connect() as connection:
            first, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="data_gap",
                ingress_generation=first_epoch,
                continuity_epoch=first_epoch,
                fencing_token=token,
                after_key=cursor_key,
            )
            second, _ = await publish_processing_boundary(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_reason="model_change",
                ingress_generation=first_epoch + 1,
                continuity_epoch=first_epoch + 1,
                fencing_token=token,
                after_key=cursor_key,
            )
            with pytest.raises(ValueError, match="next uncommitted boundary"):
                await commit_boundary_effect(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    boundary_id=cast(int, second["boundary_id"]),
                    fencing_token=token,
                )
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, first["boundary_id"]),
                fencing_token=token,
            )
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=cast(int, second["boundary_id"]),
                fencing_token=token,
            )


@pytest.mark.anyio
async def test_later_epoch_cannot_process_before_global_earliest_pending(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"global-order-{uuid4().hex}"):
        token = cast(int, lease["fencing_token"])
        cursor_key = await _committed_cursor_key(engine)
        first_epoch = await _next_epoch(engine)
        second_epoch = first_epoch + 1
        start = await _next_received_ts(engine)
        keys = ((start, uuid4()), (start + timedelta(seconds=1), uuid4()))
        async with engine.connect() as connection:
            for epoch in (first_epoch, second_epoch):
                boundary, _ = await publish_processing_boundary(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    boundary_reason="data_gap",
                    ingress_generation=epoch,
                    continuity_epoch=epoch,
                    fencing_token=token,
                    after_key=cursor_key,
                )
                await commit_boundary_effect(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    boundary_id=cast(int, boundary["boundary_id"]),
                    fencing_token=token,
                )
            for index, (received_ts, telemetry_id) in enumerate(keys):
                await insert_live_telemetry(
                    connection,
                    telemetry_id=telemetry_id,
                    device_id=LIVE_DEVICE_ID,
                    received_ts=received_ts,
                    received_at_utc=received_ts.replace(tzinfo=timezone.utc),
                    temperature_c=25.0,
                    relative_humidity_pct=60.0,
                    ingress_generation=first_epoch + index,
                    activation_id=cast(int, live_lineage["activation_id"]),
                    continuity_epoch=first_epoch + index,
                    segment_start_reason="data_gap",
                    fencing_token=token,
                )
            with pytest.raises(ValueError, match="global earliest pending"):
                await mark_telemetry_processed(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    telemetry_key=keys[1],
                    continuity_epoch=second_epoch,
                    fencing_token=token,
                )
            await connection.execute(
                update(tables.live_telemetry)
                .where(
                    tables.live_telemetry.c.device_id == LIVE_DEVICE_ID,
                    tables.live_telemetry.c.continuity_epoch.in_(
                        (first_epoch, second_epoch)
                    ),
                    tables.live_telemetry.c.processing_status == "pending",
                )
                .values(processing_status="processed")
            )
            await connection.commit()


@pytest.mark.anyio
async def test_recovery_tail_excludes_boundary_committed_after_query_snapshot(
    live_lineage: dict[str, object],
) -> None:
    async for engine, lease in _leased_engine(f"tail-snapshot-{uuid4().hex}"):
        token = cast(int, lease["fencing_token"])
        epoch = await _next_epoch(engine)
        key = (
            await _insert_series(
                engine,
                lease=lease,
                activation_id=cast(int, live_lineage["activation_id"]),
                continuity_epoch=epoch,
                start=await _next_received_ts(engine),
                count=1,
            )
        )[0]
        concurrent_epoch = await _next_epoch(engine)
        settings = Settings.from_environ()
        inserted_boundary_id: int | None = None

        def insert_boundary_after_query(*args: object) -> None:
            nonlocal inserted_boundary_id
            statement = cast(str, args[2])
            if inserted_boundary_id is not None or "FROM live_telemetry" not in statement:
                return
            with psycopg.connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                dbname=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                autocommit=True,
            ) as concurrent:
                row = concurrent.execute(
                    """
                    INSERT INTO live_processing_boundaries (
                        device_id, boundary_reason, ingress_generation,
                        continuity_epoch, fencing_token, after_received_ts,
                        after_telemetry_id
                    ) VALUES (
                        %(device_id)s, 'data_gap', %(epoch)s, %(epoch)s,
                        %(token)s, %(received_ts)s, %(telemetry_id)s
                    ) RETURNING boundary_id
                    """,
                    {
                        "device_id": LIVE_DEVICE_ID,
                        "epoch": concurrent_epoch,
                        "token": token,
                        "received_ts": key[0],
                        "telemetry_id": key[1],
                    },
                ).fetchone()
                assert row is not None
                inserted_boundary_id = cast(int, row[0])

        async with engine.connect() as connection:
            boundary_id = cast(
                int,
                await connection.scalar(
                    select(tables.live_processing_boundaries.c.boundary_id).where(
                        tables.live_processing_boundaries.c.continuity_epoch == epoch
                    )
                ),
            )
            await connection.rollback()
            event.listen(
                connection.sync_connection,
                "after_cursor_execute",
                insert_boundary_after_query,
            )
            try:
                first_read = await unprocessed_live_tail(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    after_key=(key[0] - timedelta(seconds=1), UUID(int=(1 << 128) - 1)),
                    last_boundary_id=boundary_id,
                    limit=10,
                )
            finally:
                event.remove(
                    connection.sync_connection,
                    "after_cursor_execute",
                    insert_boundary_after_query,
                )
            await connection.rollback()
            second_read = await unprocessed_live_tail(
                connection,
                device_id=LIVE_DEVICE_ID,
                after_key=(key[0] - timedelta(seconds=1), UUID(int=(1 << 128) - 1)),
                last_boundary_id=boundary_id,
                limit=10,
            )

        assert inserted_boundary_id is not None
        assert inserted_boundary_id not in {
            item.get("boundary_id") for item in first_read
        }
        assert inserted_boundary_id in {
            item.get("boundary_id") for item in second_read
        }

        async with engine.connect() as connection:
            assert await mark_telemetry_processed(
                connection,
                device_id=LIVE_DEVICE_ID,
                telemetry_key=key,
                continuity_epoch=epoch,
                fencing_token=token,
            )
            await commit_boundary_effect(
                connection,
                device_id=LIVE_DEVICE_ID,
                boundary_id=inserted_boundary_id,
                fencing_token=token,
            )


@pytest.mark.anyio
async def test_same_owner_concurrent_acquisition_has_one_winner() -> None:
    engine = _engine()
    owner = f"same-owner-{uuid4().hex}"
    try:
        async with engine.begin() as connection:
            await connection.execute(
                update(tables.live_writer_leases)
                .where(tables.live_writer_leases.c.device_id == LIVE_DEVICE_ID)
                .values(
                    lease_expires_at_utc=func.clock_timestamp()
                    - text("interval '1 second'")
                )
            )

        async def acquire() -> RowMapping | None:
            async with engine.connect() as connection:
                return await acquire_writer_lease(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    lease_owner=owner,
                    lease_seconds=60,
                )

        results = await asyncio.gather(acquire(), acquire())
        winners = [result for result in results if result is not None]
        assert len(winners) == 1
        async with engine.connect() as connection:
            assert await renew_writer_lease(
                connection,
                device_id=LIVE_DEVICE_ID,
                lease_owner=owner,
                fencing_token=cast(int, winners[0]["fencing_token"]),
                lease_seconds=60,
            ) is not None
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("alert_values", "alert_actor"),
    (({}, None), (None, "test")),
    ids=("values-only", "actor-only"),
)
@pytest.mark.anyio
async def test_linked_alert_requires_values_and_actor_together(
    alert_values: dict[str, object] | None,
    alert_actor: str | None,
) -> None:
    async for engine, lease in _leased_engine(f"alert-args-{uuid4().hex}"):
        start = await _next_received_ts(engine)
        source_keys = [
            (start + timedelta(seconds=index), UUID(int=index + 1))
            for index in range(10)
        ]
        async with engine.connect() as connection:
            with pytest.raises(ValueError, match="alert values and actor together"):
                await publish_live_inference(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    source_keys=source_keys,
                    score=2.5,
                    is_anomaly=True,
                    severity_at_score="critical",
                    fencing_token=cast(int, lease["fencing_token"]),
                    live_episode_id=uuid4(),
                    alert_values=alert_values,
                    alert_actor=alert_actor,
                )
