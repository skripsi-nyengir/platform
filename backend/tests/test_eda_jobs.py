from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import subprocess
import sys
from typing import cast
from uuid import UUID

import psycopg
import pytest
from sqlalchemy import func, insert, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.eda_contracts import EDA_SECTION_NAMES, EdaPeriodKind
from anomaly_backend.sql.eda_runs import (
    EnqueueDisposition,
    build_logical_key,
    cache_lookup,
    claim_job,
    complete_job,
    enqueue_job,
    fail_job,
    get_job,
    get_run,
    get_sections,
    list_periods,
    release_job,
    renew_lease,
)


SOURCE_SHA = "a" * 64
OTHER_SOURCE_SHA = "b" * 64
MANIFEST_SHA = "c" * 64
CONFIG_HASH = "d" * 64
OTHER_CONFIG_HASH = "e" * 64
ALGORITHM_VERSION = "eda-v3-test"
FROM_TS = datetime(2025, 1, 1)
TO_TS = datetime(2025, 1, 2)


def _run_alembic(*arguments: str) -> None:
    _ = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=Path(__file__).parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def _sync_connection() -> psycopg.Connection[tuple[object, ...]]:
    settings = Settings.from_environ()
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        autocommit=True,
    )


@pytest.fixture(scope="module", autouse=True)
def eda_schema_head() -> Iterator[None]:
    _run_alembic("upgrade", "head")
    yield


@pytest.fixture(autouse=True)
def clean_eda_tables(eda_schema_head: None) -> Iterator[None]:
    del eda_schema_head
    with _sync_connection() as connection:
        _ = connection.execute(
            "TRUNCATE eda_result_sections, eda_runs, eda_jobs, eda_raw_readings, eda_source_snapshots"
        )
    yield
    with _sync_connection() as connection:
        _ = connection.execute(
            "TRUNCATE eda_result_sections, eda_runs, eda_jobs, eda_raw_readings, eda_source_snapshots"
        )


async def _insert_snapshot(
    engine: AsyncEngine,
    *,
    source_sha256: str = SOURCE_SHA,
    config_hash: str = CONFIG_HASH,
    dataset_id: str = "b02-v1",
) -> UUID:
    async with engine.begin() as connection:
        return cast(
            UUID,
            (
                await connection.execute(
                insert(tables.eda_source_snapshots)
                .values(
                    dataset_id=dataset_id,
                    source_sha256=source_sha256,
                    manifest_sha256=MANIFEST_SHA,
                    config_hash=config_hash,
                    source_from_ts=datetime(2024, 1, 1),
                    source_to_ts=datetime(2026, 1, 1),
                    expected_row_count=2,
                    expected_channel_count=2,
                    importer_version="test-importer-v1",
                    status="complete",
                    completed_at=datetime.now(timezone.utc),
                    manifest={"source": "test"},
                )
                .returning(tables.eda_source_snapshots.c.id)
                )
            ).scalar_one(),
        )


def _sections(*, include_not_eligible: bool = False) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name in EDA_SECTION_NAMES:
        if include_not_eligible and name == "relationships":
            rows.append(
                {
                    "section": name,
                    "status": "not_eligible",
                    "reason_code": "insufficient_nonconstant_pairs",
                    "detail": "Pasangan data tidak cukup bervariasi",
                }
            )
        else:
            rows.append(
                {
                    "section": name,
                    "status": "complete",
                    "payload": {},
                    "payload_sha256": hashlib.sha256(name.encode()).hexdigest(),
                }
            )
    return rows


async def _enqueue(
    engine: AsyncEngine,
    *,
    snapshot_id: UUID,
    source_sha256: str = SOURCE_SHA,
    from_ts: datetime = FROM_TS,
    to_ts: datetime = TO_TS,
    period_kind: EdaPeriodKind = "custom",
    algorithm_version: str = ALGORITHM_VERSION,
    config_hash: str = CONFIG_HASH,
    max_attempts: int = 3,
) -> tuple[EnqueueDisposition, RowMapping]:
    async with engine.connect() as connection:
        disposition, row = await enqueue_job(
            connection,
            snapshot_id=snapshot_id,
            source_sha256=source_sha256,
            from_ts=from_ts,
            to_ts=to_ts,
            period_kind=period_kind,
            algorithm_version=algorithm_version,
            config_hash=config_hash,
            trigger_kind="api",
            max_attempts=max_attempts,
        )
        return disposition, row


async def _publish(
    engine: AsyncEngine,
    *,
    snapshot_id: UUID,
    source_sha256: str,
    from_ts: datetime,
    algorithm_version: str = ALGORITHM_VERSION,
    config_hash: str = CONFIG_HASH,
) -> UUID:
    disposition, queued = await _enqueue(
        engine,
        snapshot_id=snapshot_id,
        source_sha256=source_sha256,
        from_ts=from_ts,
        to_ts=from_ts + timedelta(days=1),
        period_kind="daily",
        algorithm_version=algorithm_version,
        config_hash=config_hash,
    )
    assert disposition == "enqueued"
    job_id = cast(UUID, queued["id"])
    async with engine.connect() as connection:
        claimed = await claim_job(
            connection, lease_owner=f"worker-{job_id}", lease_seconds=60
        )
    assert claimed is not None and claimed["id"] == job_id
    async with engine.connect() as connection:
        completed = await complete_job(
            connection,
            job_id=job_id,
            lease_owner=f"worker-{job_id}",
            attempt_count=cast(int, claimed["attempt_count"]),
            provenance={"kind": "algorithm-equivalent range computation"},
            canonical_release=False,
            sections=_sections(),
        )
    assert completed is not None
    return cast(UUID, completed[0]["id"])


def test_logical_key_is_canonical_and_sensitive_to_every_component() -> None:
    base = {
        "source_sha256": SOURCE_SHA,
        "from_ts": FROM_TS,
        "to_ts": TO_TS,
        "period_kind": "custom",
        "algorithm_version": ALGORITHM_VERSION,
        "config_hash": CONFIG_HASH,
    }
    expected = build_logical_key(**base)  # pyright: ignore[reportArgumentType]
    assert build_logical_key(**base) == expected  # pyright: ignore[reportArgumentType]

    variants = (
        {**base, "source_sha256": OTHER_SOURCE_SHA},
        {**base, "from_ts": FROM_TS + timedelta(seconds=1)},
        {**base, "to_ts": TO_TS + timedelta(seconds=1)},
        {**base, "period_kind": "daily"},
        {**base, "algorithm_version": "eda-v3-test-next"},
        {**base, "config_hash": OTHER_CONFIG_HASH},
    )
    keys = {expected}
    keys.update(
        build_logical_key(**variant)  # pyright: ignore[reportArgumentType]
        for variant in variants
    )
    assert len(keys) == 7


@pytest.mark.anyio
async def test_concurrent_enqueue_coalesces_then_completed_run_cache_hits() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        snapshot_id = await _insert_snapshot(engine)
        first_wave = await asyncio.gather(
            *(_enqueue(engine, snapshot_id=snapshot_id) for _ in range(20))
        )
        job_ids = {cast(UUID, row["id"]) for _, row in first_wave}
        assert len(job_ids) == 1
        assert [state for state, _ in first_wave].count("enqueued") == 1
        assert [state for state, _ in first_wave].count("active_job") == 19

        job_id = job_ids.pop()
        async with engine.connect() as connection:
            claimed = await claim_job(
                connection, lease_owner="worker-success", lease_seconds=60
            )
        assert claimed is not None and claimed["id"] == job_id
        async with engine.connect() as connection:
            completed = await complete_job(
                connection,
                job_id=job_id,
                lease_owner="worker-success",
                attempt_count=cast(int, claimed["attempt_count"]),
                provenance={"kind": "algorithm-equivalent range computation"},
                canonical_release=False,
                sections=_sections(include_not_eligible=True),
            )
        assert completed is not None
        run_id = cast(UUID, completed[0]["id"])

        second_wave = await asyncio.gather(
            *(_enqueue(engine, snapshot_id=snapshot_id) for _ in range(20))
        )
        assert {state for state, _ in second_wave} == {"cache_hit"}
        assert {cast(UUID, row["id"]) for _, row in second_wave} == {run_id}

        async with engine.connect() as connection:
            job = await get_job(connection, job_id=job_id)
            sections = await get_sections(connection, run_id=run_id)
            relationship = await get_sections(
                connection, run_id=run_id, section="relationships"
            )
        assert job is not None and job["status"] == "succeeded"
        assert job["run_id"] == run_id
        assert len(sections) == 11
        assert relationship[0]["status"] == "not_eligible"
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_lease_transitions_terminal_failure_and_failed_reenqueue() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        snapshot_id = await _insert_snapshot(engine)
        disposition, queued = await _enqueue(engine, snapshot_id=snapshot_id)
        assert disposition == "enqueued"
        job_id = cast(UUID, queued["id"])

        async with engine.connect() as connection:
            first = await claim_job(
                connection, lease_owner="worker-a", lease_seconds=30
            )
        assert first is not None and first["status"] == "running"
        async with engine.connect() as connection:
            renewed = await renew_lease(
                connection,
                job_id=job_id,
                lease_owner="worker-a",
                attempt_count=cast(int, first["attempt_count"]),
                lease_seconds=60,
            )
        assert renewed is not None and renewed["lease_until"] > first["lease_until"]
        async with engine.connect() as connection:
            released = await release_job(
                connection,
                job_id=job_id,
                lease_owner="worker-a",
                attempt_count=cast(int, first["attempt_count"]),
            )
        assert released is not None and released["status"] == "queued"

        async with engine.connect() as connection:
            second = await claim_job(
                connection, lease_owner="worker-b", lease_seconds=60
            )
        assert second is not None and second["attempt_count"] == 2
        async with engine.connect() as connection:
            failed = await fail_job(
                connection,
                job_id=job_id,
                lease_owner="worker-b",
                attempt_count=cast(int, second["attempt_count"]),
                error_code="source_invalid",
                error_detail="Source validation failed",
            )
        assert failed is not None and failed["status"] == "failed"
        assert failed["terminal"] is True

        disposition, retry = await _enqueue(engine, snapshot_id=snapshot_id)
        assert disposition == "enqueued"
        retry_id = cast(UUID, retry["id"])
        assert retry_id != job_id
        async with engine.connect() as connection:
            retry_claim = await claim_job(
                connection, lease_owner="worker-retry", lease_seconds=60
            )
        assert retry_claim is not None and retry_claim["id"] == retry_id
        async with engine.connect() as connection:
            retry_completion = await complete_job(
                connection,
                job_id=retry_id,
                lease_owner="worker-retry",
                attempt_count=cast(int, retry_claim["attempt_count"]),
                provenance={"kind": "retry"},
                canonical_release=False,
                sections=_sections(),
            )
        assert retry_completion is not None
        async with engine.connect() as connection:
            rows = list(
                (
                    await connection.execute(
                        select(tables.eda_jobs.c.id, tables.eda_jobs.c.status)
                        .where(
                            tables.eda_jobs.c.logical_key
                            == cast(str, failed["logical_key"])
                        )
                        .order_by(tables.eda_jobs.c.created_at)
                    )
                ).mappings()
            )
            failed_history = await get_job(connection, job_id=job_id)
            successful_retry = await get_job(connection, job_id=retry_id)
        assert [row["status"] for row in rows] == ["failed", "succeeded"]
        assert failed_history is not None and failed_history["run_id"] is None
        assert successful_retry is not None
        assert successful_retry["run_id"] == retry_completion[0]["id"]
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_expired_final_attempt_becomes_terminal_failure() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        snapshot_id = await _insert_snapshot(engine)
        _, queued = await _enqueue(
            engine, snapshot_id=snapshot_id, max_attempts=1
        )
        job_id = cast(UUID, queued["id"])
        async with engine.connect() as connection:
            claimed = await claim_job(
                connection, lease_owner="worker-final", lease_seconds=60
            )
        assert claimed is not None and claimed["attempt_count"] == 1
        async with engine.begin() as connection:
            _ = await connection.execute(
                update(tables.eda_jobs)
                .where(tables.eda_jobs.c.id == job_id)
                .values(
                    lease_until=datetime.now(timezone.utc) - timedelta(seconds=1)
                )
            )
        async with engine.connect() as connection:
            assert await claim_job(
                connection, lease_owner="worker-next", lease_seconds=60
            ) is None
        async with engine.connect() as connection:
            exhausted = await get_job(connection, job_id=job_id)
        assert exhausted is not None
        assert exhausted["status"] == "failed"
        assert exhausted["terminal"] is True
        assert exhausted["error_code"] == "max_attempts_exhausted"
        assert exhausted["run_id"] is None
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_period_pagination_filters_active_identity_but_history_is_fetchable() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        active_snapshot = await _insert_snapshot(engine)
        historical_snapshot = await _insert_snapshot(
            engine,
            source_sha256=OTHER_SOURCE_SHA,
            config_hash=OTHER_CONFIG_HASH,
            dataset_id="b02-v0",
        )
        active_ids = [
            await _publish(
                engine,
                snapshot_id=active_snapshot,
                source_sha256=SOURCE_SHA,
                from_ts=datetime(2025, 1, day),
            )
            for day in (1, 2, 3)
        ]
        historical_id = await _publish(
            engine,
            snapshot_id=historical_snapshot,
            source_sha256=OTHER_SOURCE_SHA,
            from_ts=datetime(2025, 1, 4),
            config_hash=OTHER_CONFIG_HASH,
        )
        _ = await _publish(
            engine,
            snapshot_id=active_snapshot,
            source_sha256=SOURCE_SHA,
            from_ts=datetime(2025, 1, 5),
            algorithm_version="eda-v2-history",
        )
        _ = await _publish(
            engine,
            snapshot_id=active_snapshot,
            source_sha256=SOURCE_SHA,
            from_ts=datetime(2025, 1, 6),
            config_hash=OTHER_CONFIG_HASH,
        )

        async with engine.connect() as connection:
            first, cursor = await list_periods(
                connection,
                period_kind="daily",
                source_sha256=SOURCE_SHA,
                algorithm_version=ALGORITHM_VERSION,
                config_hash=CONFIG_HASH,
                limit=2,
            )
            second, final_cursor = await list_periods(
                connection,
                period_kind="daily",
                source_sha256=SOURCE_SHA,
                algorithm_version=ALGORITHM_VERSION,
                config_hash=CONFIG_HASH,
                limit=2,
                cursor=cursor,
            )
            historical = await get_run(connection, run_id=historical_id)
        assert [row["id"] for row in first] == active_ids[::-1][:2]
        assert cursor == "eda-periods:2"
        assert [row["id"] for row in second] == active_ids[::-1][2:]
        assert final_cursor is None
        assert historical is not None and historical["id"] == historical_id
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_stale_lease_is_fenced_and_publication_is_atomically_visible() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        snapshot_id = await _insert_snapshot(engine)
        _, queued = await _enqueue(engine, snapshot_id=snapshot_id)
        job_id = cast(UUID, queued["id"])
        async with engine.connect() as connection:
            stale = await claim_job(
                connection, lease_owner="worker-stale", lease_seconds=60
            )
        assert stale is not None
        async with engine.begin() as connection:
            _ = await connection.execute(
                update(tables.eda_jobs)
                .where(tables.eda_jobs.c.id == job_id)
                .values(lease_until=datetime.now(timezone.utc) - timedelta(seconds=1))
            )
        async with engine.connect() as connection:
            current = await claim_job(
                connection, lease_owner="worker-current", lease_seconds=60
            )
        assert current is not None and current["attempt_count"] == 2

        async with engine.connect() as connection:
            stale_result = await complete_job(
                connection,
                job_id=job_id,
                lease_owner="worker-stale",
                attempt_count=cast(int, stale["attempt_count"]),
                provenance={"kind": "stale"},
                canonical_release=False,
                sections=_sections(),
            )
            stale_renewal = await renew_lease(
                connection,
                job_id=job_id,
                lease_owner="worker-stale",
                attempt_count=cast(int, stale["attempt_count"]),
                lease_seconds=60,
            )
        assert stale_result is None
        assert stale_renewal is None
        async with engine.connect() as connection:
            assert await connection.scalar(
                select(func.count()).select_from(tables.eda_runs)
            ) == 0

        async with engine.connect() as connection:
            completed = await complete_job(
                connection,
                job_id=job_id,
                lease_owner="worker-current",
                attempt_count=cast(int, current["attempt_count"]),
                provenance={"kind": "current"},
                canonical_release=False,
                sections=_sections(),
            )
        assert completed is not None

        logical_key = build_logical_key(
            source_sha256=SOURCE_SHA,
            from_ts=datetime(2025, 2, 1),
            to_ts=datetime(2025, 2, 2),
            period_kind="daily",
            algorithm_version=ALGORITHM_VERSION,
            config_hash=CONFIG_HASH,
        )
        publisher = await engine.connect()
        transaction = await publisher.begin()
        try:
            run_id = cast(
                UUID,
                (
                    await publisher.execute(
                    insert(tables.eda_runs)
                    .values(
                        logical_key=logical_key,
                        snapshot_id=snapshot_id,
                        source_sha256=SOURCE_SHA,
                        from_ts=datetime(2025, 2, 1),
                        to_ts=datetime(2025, 2, 2),
                        period_kind="daily",
                        algorithm_version=ALGORITHM_VERSION,
                        config_hash=CONFIG_HASH,
                        provenance={"kind": "atomic"},
                        canonical_release=False,
                        completed_at=datetime.now(timezone.utc),
                    )
                    .returning(tables.eda_runs.c.id)
                    )
                ).scalar_one(),
            )
            _ = await publisher.execute(
                insert(tables.eda_result_sections),
                [
                    {
                        "run_id": run_id,
                        "section": row["section"],
                        "status": row["status"],
                        "payload": row.get("payload"),
                        "payload_sha256": row.get("payload_sha256"),
                    }
                    for row in _sections()
                ],
            )
            async with engine.connect() as reader:
                assert await cache_lookup(reader, logical_key=logical_key) is None
                assert await get_sections(reader, run_id=run_id) == []
            await transaction.commit()
        finally:
            if transaction.is_active:
                await transaction.rollback()
            await publisher.close()

        async with engine.connect() as reader:
            assert await cache_lookup(reader, logical_key=logical_key) is not None
            assert len(await get_sections(reader, run_id=run_id)) == 11
    finally:
        await engine.dispose()
