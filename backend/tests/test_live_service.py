from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock
from typing import cast
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import event, func, insert, select, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.sql.live import (
    LIVE_DEVICE_ID,
    BoundaryReason,
    live_activation_row,
    request_live_activation,
)
from anomaly_worker import live_service as live_service_module
from anomaly_worker.live_engine import Episode, EpisodeState
from anomaly_worker.live_model import LiveModelIdentity
from anomaly_worker.live_service import LiveService
from anomaly_worker.live_subscriber import AcceptedReading
from anomaly_worker.scorer import ScoreBatch, ScoreBatchResult, ScorePoint


@dataclass(frozen=True, slots=True)
class _Lineage:
    first_pair_id: UUID
    first_activation_id: int
    first_model_version: str
    first_corpus_id: str
    second_pair_id: UUID
    second_model_version: str
    second_corpus_id: str


@dataclass(frozen=True, slots=True)
class _Database:
    settings: Settings
    lineage: _Lineage


class _Scorer:
    def __init__(
        self,
        outcomes: list[float | BaseException] | None = None,
        *,
        default: float = 0.5,
        entered: Event | None = None,
        release: Event | None = None,
    ) -> None:
        self._outcomes = deque(outcomes or ())
        self._default = default
        self._entered = entered
        self._release = release
        self._lock = Lock()
        self.batches: list[ScoreBatch] = []

    def score(self, batch: ScoreBatch) -> ScoreBatchResult:
        if self._entered is not None:
            self._entered.set()
        if self._release is not None and not self._release.wait(timeout=5):
            raise RuntimeError("test scorer timed out")
        with self._lock:
            self.batches.append(batch)
            outcome = self._outcomes.popleft() if self._outcomes else self._default
        if isinstance(outcome, BaseException):
            raise outcome
        return ScoreBatchResult(
            points=(ScorePoint(score_ts=batch.target_ts[0], score=outcome),)
        )


@dataclass(frozen=True, slots=True)
class _Model:
    identity: LiveModelIdentity
    model_version: str
    threshold: float
    scorer: _Scorer

    def scale_pair(self, value: tuple[float, float]) -> tuple[float, float]:
        return value[0] / 100.0, value[1] / 100.0


class _Loader:
    def __init__(self, scorers: dict[str, _Scorer]) -> None:
        self._scorers = scorers

    async def __call__(
        self,
        connection: AsyncConnection,
        *,
        device_id: str,
        activation_id: int | None = None,
        previous_identity: LiveModelIdentity | None = None,
    ) -> _Model:
        del previous_identity
        assert activation_id is not None
        row = await live_activation_row(
            connection,
            device_id=device_id,
            activation_id=activation_id,
        )
        assert row is not None
        model_version = cast(str, row["model_version"])
        return _Model(
            identity=LiveModelIdentity(
                model_pair_id=cast(UUID, row["model_pair_id"]),
                activation_id=activation_id,
                snapshot_corpus_id=cast(str, row["scaler_snapshot_corpus_id"]),
            ),
            model_version=model_version,
            threshold=float(row["threshold"]),
            scorer=self._scorers[model_version],
        )


def _create_pair_values(suffix: str, ordinal: int) -> tuple[dict[str, object], ...]:
    corpus_id = f"task7-corpus-{ordinal}-{suffix}"
    model_key = f"task7-model-{ordinal}-{suffix}"
    model_version = f"{model_key}-v1"
    now = datetime.now(timezone.utc)
    corpus: dict[str, object] = {
        "corpus_id": corpus_id,
        "device_id": LIVE_DEVICE_ID,
        "status": "published",
        "archive_sha256": f"{ordinal}" * 64,
        "member_sha256": None,
        "preprocessing_contract_version": "live-v1",
        "source_device_uuid": None,
        "time_zone": "Asia/Jakarta",
        "interval_start": datetime(2035, 1, 1),
        "interval_end": datetime(2036, 1, 1),
        "filter_config": {"artifact_owned": True},
        "started_at": now,
        "completed_at": now,
        "accepted_count": 0,
        "ignored_index_count": 0,
        "rejection_counts": {},
    }
    snapshot: dict[str, object] = {
        "corpus_id": corpus_id,
        "channels": ["temperature_c", "relative_humidity_pct"],
        "window_size": 10,
        "stride": 1,
        "contract_status": "live_10",
        "segment_metadata": [],
        "split_boundaries": {},
        "split_counts": {},
        "scaler": {},
    }
    family: dict[str, object] = {
        "model_key": model_key,
        "display_name": f"Task 7 model {ordinal}",
        "is_public": False,
    }
    version: dict[str, object] = {
        "version": model_version,
        "model_key": model_key,
        "runtime_kind": "artifact",
        "is_selectable": True,
        "adapter_key": "task7-test",
        "schema_version": "b02-live-v1",
        "channels": ["temperature_c", "relative_humidity_pct"],
        "window_size": 10,
        "stride": 1,
        "contract_status": "live_10",
        "score_key": "score",
        "score_semantics": "higher-is-more-anomalous",
        "threshold": 1.0,
        "threshold_policy": {
            "comparison": ">",
            "fit_split": "validation",
            "name": "task7",
        },
        "temporal_semantics": "context_end",
        "source_commit": None,
        "source_config": None,
        "manifest_sha256": "a" * 64,
        "model_manifest_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "scaler_manifest_sha256": "c" * 64,
        "scaler_sha256": "d" * 64,
        "created_at": now,
    }
    pair: dict[str, object] = {
        "model_version": model_version,
        "checkpoint_identity": f"checkpoint-{ordinal}-{suffix}",
        "scaler_snapshot_corpus_id": corpus_id,
        "model_manifest_sha256": "a" * 64,
        "checkpoint_sha256": "b" * 64,
        "scaler_manifest_sha256": "c" * 64,
        "scaler_sha256": "d" * 64,
        "threshold": 1.0,
        "contract_status": "live_10",
    }
    return corpus, snapshot, family, version, pair


@pytest.fixture(scope="module")
def task7_database() -> Iterator[_Database]:
    base = Settings.from_environ()
    database_name = f"anomaly_detection_task7_{uuid4().hex[:12]}"
    with psycopg.connect(
        host=base.postgres_host,
        port=base.postgres_port,
        dbname="postgres",
        user=base.postgres_user,
        password=base.postgres_password,
        autocommit=True,
    ) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )
    environment = os.environ.copy()
    environment["POSTGRES_DB"] = database_name
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=Path(__file__).parents[1],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    settings = replace(base, postgres_db=database_name)

    async def prepare() -> _Lineage:
        engine = create_database_engine(settings)
        suffix = uuid4().hex
        pairs: list[tuple[UUID, str, str]] = []
        try:
            async with engine.begin() as connection:
                assert (
                    await connection.scalar(
                        select(tables.devices.c.device_id).where(
                            tables.devices.c.device_id == LIVE_DEVICE_ID
                        )
                    )
                    == LIVE_DEVICE_ID
                )
                for ordinal in (1, 2):
                    corpus, snapshot, family, version, pair = _create_pair_values(
                        suffix, ordinal
                    )
                    await connection.execute(insert(tables.corpora).values(**corpus))
                    await connection.execute(
                        insert(tables.preprocessing_snapshots).values(**snapshot)
                    )
                    await connection.execute(
                        insert(tables.model_families).values(**family)
                    )
                    await connection.execute(
                        insert(tables.model_versions).values(**version)
                    )
                    pair_id = cast(
                        UUID,
                        await connection.scalar(
                            insert(tables.live_model_pairs)
                            .values(**pair)
                            .returning(tables.live_model_pairs.c.model_pair_id)
                        ),
                    )
                    pairs.append(
                        (
                            pair_id,
                            cast(str, version["version"]),
                            cast(str, corpus["corpus_id"]),
                        )
                    )

                request_id = cast(
                    UUID,
                    await connection.scalar(
                        insert(tables.live_model_activation_requests)
                        .values(
                            device_id=LIVE_DEVICE_ID,
                            model_pair_id=pairs[0][0],
                            request_hash=f"task7-bootstrap-{suffix}",
                            requested_by="test",
                        )
                        .returning(tables.live_model_activation_requests.c.request_id)
                    ),
                )
                activation = (
                    (
                        await connection.execute(
                            insert(tables.live_model_activations)
                            .values(
                                device_id=LIVE_DEVICE_ID,
                                request_id=request_id,
                                model_pair_id=pairs[0][0],
                                fencing_token=1,
                            )
                            .returning(*tables.live_model_activations.c)
                        )
                    )
                    .mappings()
                    .one()
                )
                await connection.execute(
                    insert(tables.live_model_selections).values(
                        device_id=LIVE_DEVICE_ID,
                        activation_event_id=activation["activation_event_id"],
                        model_pair_id=pairs[0][0],
                        activation_id=activation["activation_id"],
                    )
                )
            return _Lineage(
                first_pair_id=pairs[0][0],
                first_activation_id=cast(int, activation["activation_id"]),
                first_model_version=pairs[0][1],
                first_corpus_id=pairs[0][2],
                second_pair_id=pairs[1][0],
                second_model_version=pairs[1][1],
                second_corpus_id=pairs[1][2],
            )
        finally:
            await engine.dispose()

    lineage = asyncio.run(prepare())
    try:
        yield _Database(settings=settings, lineage=lineage)
    finally:
        with psycopg.connect(
            host=base.postgres_host,
            port=base.postgres_port,
            dbname="postgres",
            user=base.postgres_user,
            password=base.postgres_password,
            autocommit=True,
        ) as connection:
            connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (database_name,),
            )
            connection.execute(
                sql.SQL("DROP DATABASE {}").format(sql.Identifier(database_name))
            )


def _engine(database: _Database) -> AsyncEngine:
    return create_database_engine(database.settings)


def _reading(at: datetime, value: float = 25.0) -> AcceptedReading:
    return AcceptedReading(
        device_id=LIVE_DEVICE_ID,
        received_ts=at.replace(tzinfo=None, microsecond=0),
        received_at_utc=at,
        temperature_c=value,
        relative_humidity_pct=60.0 + value / 100,
    )


async def _start_service(
    database: _Database,
    first_scorer: _Scorer,
    *,
    second_scorer: _Scorer | None = None,
    page_size: int = 17,
    lease_seconds: int = 30,
) -> tuple[AsyncEngine, LiveService]:
    engine = _engine(database)
    await _expire_lease(engine)
    loader = _Loader(
        {
            database.lineage.first_model_version: first_scorer,
            database.lineage.second_model_version: second_scorer or _Scorer(),
        }
    )
    service = LiveService(
        engine,
        lease_owner=f"task7-{uuid4().hex}",
        model_loader=loader,
        page_size=page_size,
        lease_seconds=lease_seconds,
    )
    await service.start()
    return engine, service


async def _persist_series(
    service: LiveService,
    start: datetime,
    count: int,
    *,
    process: bool,
) -> list[RowMapping]:
    rows: list[RowMapping] = []
    for index in range(count):
        rows.append(
            await service.persist_reading(
                _reading(start + timedelta(seconds=index * 6), 25.0 + index)
            )
        )
        if process:
            await service.process_pending()
    return rows


async def _expire_lease(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE live_writer_leases "
                "SET lease_expires_at_utc = clock_timestamp() - interval '1 second' "
                "WHERE device_id = :device_id"
            ),
            {"device_id": LIVE_DEVICE_ID},
        )


@pytest.mark.anyio
async def test_telemetry_commits_before_warmup_then_stride_one_publishes(
    task7_database: _Database,
) -> None:
    scorer = _Scorer()
    engine, service = await _start_service(task7_database, scorer)
    start = datetime(2045, 1, 1, tzinfo=timezone.utc)
    try:
        rows = await _persist_series(service, start, 9, process=True)
        pending = await service.persist_reading(
            _reading(start + timedelta(seconds=54), 34.0)
        )
        epoch = cast(int, pending["continuity_epoch"])
        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    select(tables.live_telemetry.c.processing_status).where(
                        tables.live_telemetry.c.telemetry_id == pending["telemetry_id"]
                    )
                )
                == "pending"
            )
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_inference)
                    .where(tables.live_inference.c.continuity_epoch == epoch)
                )
                == 0
            )
        assert len(scorer.batches) == 0

        assert await service.process_pending() == 1
        await _persist_series(
            service,
            start + timedelta(seconds=60),
            2,
            process=True,
        )
        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_inference)
                    .where(tables.live_inference.c.continuity_epoch == epoch)
                )
                == 3
            )
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_inference_sources)
                    .join(
                        tables.live_inference,
                        tables.live_inference.c.inference_id
                        == tables.live_inference_sources.c.inference_id,
                    )
                    .where(tables.live_inference.c.continuity_epoch == epoch)
                )
                == 30
            )
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_telemetry)
                    .where(
                        tables.live_telemetry.c.telemetry_id.in_(
                            [row["telemetry_id"] for row in rows]
                        ),
                        tables.live_telemetry.c.processing_status == "processed",
                    )
                )
                == 9
            )
    finally:
        await service.stop()
        await engine.dispose()


@pytest.mark.anyio
async def test_equal_second_sources_follow_uuid_total_order(
    task7_database: _Database,
) -> None:
    scorer = _Scorer()
    engine, service = await _start_service(task7_database, scorer)
    start = datetime(2045, 2, 1, tzinfo=timezone.utc)
    try:
        ids = [UUID(int=index + 1) for index in range(10)]
        row: RowMapping | None = None
        for index, telemetry_id in enumerate(ids):
            row = await service.persist_reading(
                _reading(start + timedelta(microseconds=index), 25.0 + index),
                telemetry_id=telemetry_id,
            )
        assert row is not None
        epoch = cast(int, row["continuity_epoch"])
        assert await service.process_pending() == 10
        async with engine.connect() as connection:
            source_ids = list(
                await connection.scalars(
                    select(tables.live_inference_sources.c.telemetry_id)
                    .join(
                        tables.live_inference,
                        tables.live_inference.c.inference_id
                        == tables.live_inference_sources.c.inference_id,
                    )
                    .where(tables.live_inference.c.continuity_epoch == epoch)
                    .order_by(tables.live_inference_sources.c.ordinal)
                )
            )
        assert source_ids == ids
    finally:
        await service.stop()
        await engine.dispose()


@pytest.mark.parametrize(
    "failing_statement",
    ["INSERT INTO live_inference_sources", "UPDATE live_cursors"],
    ids=("source-links", "cursor"),
)
@pytest.mark.anyio
async def test_persistence_crash_rolls_back_publication_and_retries_once(
    task7_database: _Database,
    failing_statement: str,
) -> None:
    scorer = _Scorer(default=2.5)
    engine, service = await _start_service(task7_database, scorer)
    start = datetime(
        2045,
        3,
        2 if failing_statement == "UPDATE live_cursors" else 1,
        tzinfo=timezone.utc,
    )
    try:
        await _persist_series(service, start, 9, process=True)
        target = await service.persist_reading(
            _reading(start + timedelta(seconds=54), 34.0)
        )
        epoch = cast(int, target["continuity_epoch"])

        def fail_statement(*args: object) -> None:
            if failing_statement in cast(str, args[2]):
                raise RuntimeError("injected persistence crash")

        event.listen(engine.sync_engine, "before_cursor_execute", fail_statement)
        try:
            with pytest.raises(RuntimeError, match="injected persistence crash"):
                await service.process_pending()
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", fail_statement)

        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_inference)
                    .where(tables.live_inference.c.continuity_epoch == epoch)
                )
                == 0
            )
            assert (
                await connection.scalar(
                    select(tables.live_telemetry.c.processing_status).where(
                        tables.live_telemetry.c.telemetry_id == target["telemetry_id"]
                    )
                )
                == "pending"
            )

        assert await service.process_pending() == 1
        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_inference)
                    .where(tables.live_inference.c.continuity_epoch == epoch)
                )
                == 1
            )
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_alert_episodes)
                    .where(tables.live_alert_episodes.c.continuity_epoch == epoch)
                )
                == 1
            )
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.alerts)
                    .where(
                        tables.alerts.c.live_episode_id.is_not(None),
                        tables.alerts.c.episode_start_ts == target["received_ts"],
                    )
                )
                == 1
            )
    finally:
        await service.stop()
        await engine.dispose()


@pytest.mark.anyio
async def test_inference_failure_leaves_blocking_row_pending_for_retry(
    task7_database: _Database,
) -> None:
    scorer = _Scorer([RuntimeError("temporary scorer failure"), 0.5])
    engine, service = await _start_service(task7_database, scorer)
    start = datetime(2045, 4, 1, tzinfo=timezone.utc)
    try:
        rows = await _persist_series(service, start, 10, process=False)
        assert await service.process_pending() == 9
        assert service.health_detail_code == "inference_retry"
        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    select(tables.live_telemetry.c.processing_status).where(
                        tables.live_telemetry.c.telemetry_id == rows[-1]["telemetry_id"]
                    )
                )
                == "pending"
            )
            assert (
                await connection.scalar(
                    select(tables.live_health.c.detail_code).where(
                        tables.live_health.c.device_id == LIVE_DEVICE_ID
                    )
                )
                == "inference_retry"
            )

        assert await service.process_pending() == 1
        assert service.health_detail_code is None
    finally:
        await service.stop()
        await engine.dispose()


@pytest.mark.anyio
async def test_restart_reconstructs_only_the_last_continuous_processed_tail(
    task7_database: _Database,
) -> None:
    first_engine, first = await _start_service(task7_database, _Scorer())
    start = datetime(2045, 5, 1, tzinfo=timezone.utc)
    try:
        await _persist_series(first, start, 9, process=True)
        target = await first.persist_reading(
            _reading(start + timedelta(seconds=54), 34.0)
        )
        epoch = cast(int, target["continuity_epoch"])
        await first.stop(release_lease=False)
        await _expire_lease(first_engine)

        second_engine, second = await _start_service(task7_database, _Scorer())
        try:
            assert await second.process_pending() == 1
            async with second_engine.connect() as connection:
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_inference)
                        .where(tables.live_inference.c.continuity_epoch == epoch)
                    )
                    == 1
                )
        finally:
            await second.stop()
            await second_engine.dispose()
    finally:
        await first.stop(release_lease=False)
        await first_engine.dispose()


@pytest.mark.anyio
async def test_gap_boundary_terminates_reconstructed_tail_without_fake_recovery(
    task7_database: _Database,
) -> None:
    first_engine, first = await _start_service(task7_database, _Scorer(default=2.5))
    start = datetime(2045, 6, 1, tzinfo=timezone.utc)
    try:
        await _persist_series(first, start, 10, process=True)
        episode_id = first.episode_id
        assert episode_id is not None
        gap_row = await first.persist_reading(
            _reading(start + timedelta(seconds=100), 40.0)
        )
        gap_epoch = cast(int, gap_row["continuity_epoch"])
        await first.stop(release_lease=False)
        await _expire_lease(first_engine)

        second_engine, second = await _start_service(task7_database, _Scorer())
        try:
            assert await second.process_pending() == 1
            async with second_engine.connect() as connection:
                episode = (
                    (
                        await connection.execute(
                            select(tables.live_alert_episodes).where(
                                tables.live_alert_episodes.c.live_episode_id
                                == episode_id
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                assert episode["status"] == "resolved"
                assert episode["close_reason"] == "data_gap"
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_alert_episode_points)
                        .where(
                            tables.live_alert_episode_points.c.live_episode_id
                            == episode_id
                        )
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_inference)
                        .where(tables.live_inference.c.continuity_epoch == gap_epoch)
                    )
                    == 0
                )
        finally:
            await second.stop()
            await second_engine.dispose()
    finally:
        await first.stop(release_lease=False)
        await first_engine.dispose()


@pytest.mark.anyio
async def test_commit_then_process_crash_is_idempotent_after_takeover(
    task7_database: _Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from anomaly_backend.sql.live import publish_live_inference as durable_publish
    from anomaly_worker import live_service

    first_engine, first = await _start_service(task7_database, _Scorer(default=2.5))
    start = datetime(2045, 7, 1, tzinfo=timezone.utc)
    crashed = False
    typed_publish = cast(Callable[..., Awaitable[object]], durable_publish)

    async def publish_then_crash(*args: object, **kwargs: object) -> object:
        nonlocal crashed
        result = await typed_publish(*args, **kwargs)
        if not crashed:
            crashed = True
            raise RuntimeError("crash after durable commit")
        return result

    try:
        await _persist_series(first, start, 9, process=True)
        target = await first.persist_reading(
            _reading(start + timedelta(seconds=54), 34.0)
        )
        epoch = cast(int, target["continuity_epoch"])
        monkeypatch.setattr(live_service, "publish_live_inference", publish_then_crash)
        with pytest.raises(RuntimeError, match="crash after durable commit"):
            await first.process_pending()
        monkeypatch.setattr(live_service, "publish_live_inference", durable_publish)
        await first.stop(release_lease=False)
        await _expire_lease(first_engine)

        second_engine, second = await _start_service(task7_database, _Scorer())
        try:
            await second.process_pending()
            async with second_engine.connect() as connection:
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_inference)
                        .where(tables.live_inference.c.continuity_epoch == epoch)
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.live_alert_episodes)
                        .where(tables.live_alert_episodes.c.continuity_epoch == epoch)
                    )
                    == 1
                )
                assert (
                    await connection.scalar(
                        select(func.count())
                        .select_from(tables.alerts)
                        .where(
                            tables.alerts.c.episode_start_ts == target["received_ts"]
                        )
                    )
                    == 1
                )
        finally:
            await second.stop()
            await second_engine.dispose()
    finally:
        await first.stop(release_lease=False)
        await first_engine.dispose()


@pytest.mark.anyio
async def test_episode_context_closes_on_three_normals_and_never_reopens(
    task7_database: _Database,
) -> None:
    scorer = _Scorer([1.5, 2.5, 0.5, 0.5, 0.5, 1.5])
    engine, service = await _start_service(task7_database, scorer)
    start = datetime(2045, 8, 1, tzinfo=timezone.utc)
    try:
        rows = await _persist_series(service, start, 15, process=True)
        async with engine.connect() as connection:
            episodes = list(
                (
                    await connection.execute(
                        select(tables.live_alert_episodes).order_by(
                            tables.live_alert_episodes.c.started_score_ts
                        )
                    )
                ).mappings()
            )[-2:]
            assert len(episodes) == 2
            first, second = episodes
            assert first["live_episode_id"] != second["live_episode_id"]
            assert first["status"] == "resolved"
            assert first["close_reason"] == "normal_recovery"
            assert second["status"] == "open"
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_alert_episode_points)
                    .where(
                        tables.live_alert_episode_points.c.live_episode_id
                        == first["live_episode_id"]
                    )
                )
                == 5
            )
            assert (
                await connection.scalar(
                    select(
                        func.count(
                            func.distinct(tables.live_inference_sources.c.telemetry_id)
                        )
                    )
                    .select_from(tables.live_alert_episode_points)
                    .join(
                        tables.live_inference_sources,
                        tables.live_inference_sources.c.inference_id
                        == tables.live_alert_episode_points.c.inference_id,
                    )
                    .where(
                        tables.live_alert_episode_points.c.live_episode_id
                        == first["live_episode_id"]
                    )
                )
                == 14
            )
            first_sources = list(
                await connection.scalars(
                    select(tables.live_inference_sources.c.telemetry_id)
                    .join(
                        tables.live_alert_episode_points,
                        tables.live_alert_episode_points.c.inference_id
                        == tables.live_inference_sources.c.inference_id,
                    )
                    .where(
                        tables.live_alert_episode_points.c.live_episode_id
                        == first["live_episode_id"],
                        tables.live_alert_episode_points.c.ordinal == 0,
                    )
                    .order_by(tables.live_inference_sources.c.ordinal)
                )
            )
            assert first_sources == [row["telemetry_id"] for row in rows[:10]]
    finally:
        await service.stop()
        await engine.dispose()


@pytest.mark.anyio
async def test_watchdog_waits_for_out_of_order_ingress_with_newer_receipt_time(
    task7_database: _Database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, service = await _start_service(task7_database, _Scorer(default=2.5))
    start = datetime(2045, 8, 31, tzinfo=timezone.utc)
    insert_started = asyncio.Event()
    allow_insert = asyncio.Event()
    original_insert = live_service_module.insert_live_telemetry

    async def delayed_insert(
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
        insert_started.set()
        await allow_insert.wait()
        return await original_insert(
            connection,
            telemetry_id=telemetry_id,
            device_id=device_id,
            received_ts=received_ts,
            received_at_utc=received_at_utc,
            temperature_c=temperature_c,
            relative_humidity_pct=relative_humidity_pct,
            ingress_generation=ingress_generation,
            activation_id=activation_id,
            continuity_epoch=continuity_epoch,
            segment_start_reason=segment_start_reason,
            fencing_token=fencing_token,
        )

    try:
        await service.persist_reading(_reading(start))
        episode_id = uuid4()
        setattr(
            service,
            "_episode_state",
            EpisodeState(
                Episode(
                    live_episode_id=episode_id,
                    status="open",
                    severity="warning",
                )
            ),
        )
        monkeypatch.setattr(live_service_module, "insert_live_telemetry", delayed_insert)
        monkeypatch.setattr(
            live_service_module,
            "resolve_live_episode",
            AsyncMock(return_value=True),
        )
        reading = AcceptedReading(
            device_id=LIVE_DEVICE_ID,
            received_ts=(start - timedelta(seconds=6)).replace(tzinfo=None),
            received_at_utc=start + timedelta(seconds=11),
            temperature_c=30.0,
            relative_humidity_pct=61.0,
        )
        persistence = asyncio.create_task(service.persist_reading(reading))
        await asyncio.wait_for(insert_started.wait(), timeout=1)
        watchdog = asyncio.create_task(
            service.watchdog_once(now=start + timedelta(seconds=12, microseconds=1))
        )
        try:
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(asyncio.shield(watchdog), timeout=0.1)
            allow_insert.set()
            await asyncio.wait_for(persistence, timeout=1)
            assert not await asyncio.wait_for(watchdog, timeout=1)
            assert service.episode_id == episode_id
            setattr(service, "_episode_state", EpisodeState())
            assert await service.process_pending() == 2
        finally:
            allow_insert.set()
            await asyncio.gather(persistence, watchdog, return_exceptions=True)
    finally:
        await service.stop()
        await engine.dispose()


@pytest.mark.anyio
async def test_watchdog_closes_once_without_inventing_recovery_points(
    task7_database: _Database,
) -> None:
    engine, service = await _start_service(task7_database, _Scorer(default=2.5))
    start = datetime(2045, 9, 1, tzinfo=timezone.utc)
    try:
        await _persist_series(service, start, 10, process=True)
        episode_id = service.episode_id
        assert episode_id is not None
        assert await service.watchdog_once(
            now=start + timedelta(seconds=66, microseconds=1)
        )
        assert not await service.watchdog_once(now=start + timedelta(seconds=90))
        async with engine.connect() as connection:
            episode = (
                (
                    await connection.execute(
                        select(tables.live_alert_episodes).where(
                            tables.live_alert_episodes.c.live_episode_id == episode_id
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert episode["status"] == "resolved"
            assert episode["close_reason"] == "data_gap"
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_alert_episode_points)
                    .where(
                        tables.live_alert_episode_points.c.live_episode_id == episode_id
                    )
                )
                == 1
            )
    finally:
        await service.stop()
        await engine.dispose()


@pytest.mark.anyio
async def test_slow_scorer_renews_lease_and_drains_more_than_ingress_capacity(
    task7_database: _Database,
) -> None:
    entered = Event()
    release = Event()
    scorer = _Scorer(entered=entered, release=release)
    engine, service = await _start_service(
        task7_database,
        scorer,
        page_size=13,
        lease_seconds=1,
    )
    start = datetime(2045, 10, 1, tzinfo=timezone.utc)
    try:
        rows = await _persist_series(service, start, 110, process=False)
        task = asyncio.create_task(service.process_pending())
        assert await asyncio.to_thread(entered.wait, 2)
        await asyncio.sleep(1.2)
        release.set()
        assert await asyncio.wait_for(task, timeout=10) == 110
        epoch = cast(int, rows[-1]["continuity_epoch"])
        async with engine.connect() as connection:
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_telemetry)
                    .where(
                        tables.live_telemetry.c.continuity_epoch == epoch,
                        tables.live_telemetry.c.processing_status == "processed",
                    )
                )
                == 110
            )
            assert (
                await connection.scalar(
                    select(func.count())
                    .select_from(tables.live_inference)
                    .where(tables.live_inference.c.continuity_epoch == epoch)
                )
                == 101
            )
    finally:
        release.set()
        await service.stop()
        await engine.dispose()


@pytest.mark.anyio
async def test_activation_during_score_preserves_old_binding_and_closes_boundary(
    task7_database: _Database,
) -> None:
    entered = Event()
    release = Event()
    first_scorer = _Scorer(default=2.5, entered=entered, release=release)
    second_scorer = _Scorer()
    engine, service = await _start_service(
        task7_database,
        first_scorer,
        second_scorer=second_scorer,
    )
    start = datetime(2045, 11, 1, tzinfo=timezone.utc)
    try:
        rows = await _persist_series(service, start, 10, process=False)
        old_binding = service.binding
        processing = asyncio.create_task(service.process_pending())
        assert await asyncio.to_thread(entered.wait, 2)
        async with engine.connect() as connection:
            async with connection.begin():
                request, _ = await request_live_activation(
                    connection,
                    device_id=LIVE_DEVICE_ID,
                    model_pair_id=task7_database.lineage.second_pair_id,
                    requested_by="test",
                    idempotency_key=uuid4().hex,
                )
        await service.activate(
            request_id=cast(UUID, request["request_id"]),
            model_pair_id=task7_database.lineage.second_pair_id,
        )
        assert (
            service.binding.identity.model_pair_id
            == task7_database.lineage.second_pair_id
        )
        assert service.binding != old_binding
        new_row = await service.persist_reading(
            _reading(start + timedelta(seconds=60), 40.0)
        )
        release.set()
        await asyncio.wait_for(processing, timeout=5)
        await service.process_pending()

        async with engine.connect() as connection:
            old_result = (
                (
                    await connection.execute(
                        select(tables.live_inference).where(
                            tables.live_inference.c.continuity_epoch
                            == rows[-1]["continuity_epoch"]
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert old_result["activation_id"] == old_binding.identity.activation_id
            assert new_row["activation_id"] == service.binding.identity.activation_id
            old_episode = (
                (
                    await connection.execute(
                        select(tables.live_alert_episodes).where(
                            tables.live_alert_episodes.c.continuity_epoch
                            == rows[-1]["continuity_epoch"]
                        )
                    )
                )
                .mappings()
                .one()
            )
            assert old_episode["status"] == "resolved"
            assert old_episode["close_reason"] == "model_change"
    finally:
        release.set()
        await service.stop()
        await engine.dispose()
