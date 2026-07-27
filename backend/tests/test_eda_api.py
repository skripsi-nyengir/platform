from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import datetime, timedelta, timezone
import hashlib
from pathlib import Path
import subprocess
import sys
from typing import Any, cast
from uuid import UUID, uuid4

import psycopg
import pytest
from httpx import Response
from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.contracts import ProblemDetails
from anomaly_backend.db import create_database_engine
from anomaly_backend.eda_contracts import (
    EDA_ALGORITHM_VERSION,
    EDA_CONFIG_HASH,
    EDA_DATASET_ID,
    EDA_DEVICE_ID,
    EdaPeriodKind,
    EDA_SECTION_NAMES,
    EDA_SOURCE_FROM,
    EDA_SOURCE_SHA256,
    EDA_SOURCE_TO,
    EDA_TIME_ZONE,
)
from anomaly_backend.routes.eda import router
from anomaly_backend.sql.eda_runs import (
    build_logical_key,
    claim_job,
    complete_job,
    enqueue_job,
)
from conftest import ClientFactory  # pyright: ignore[reportImplicitRelativeImport]


MANIFEST_SHA256 = "1" * 64
SOURCE_FROM = datetime.fromisoformat(EDA_SOURCE_FROM)
SOURCE_TO = datetime.fromisoformat(EDA_SOURCE_TO)
CUSTOM_FROM = datetime(2025, 7, 1)
CUSTOM_TO = datetime(2025, 7, 2)


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
    statement = (
        "TRUNCATE eda_result_sections, eda_runs, eda_jobs, "
        "eda_raw_readings, eda_source_snapshots"
    )
    with _sync_connection() as connection:
        _ = connection.execute(statement)
    yield
    with _sync_connection() as connection:
        _ = connection.execute(statement)


def _body(start: datetime = CUSTOM_FROM, end: datetime = CUSTOM_TO) -> dict[str, str]:
    return {
        "device_id": EDA_DEVICE_ID,
        "time_zone": EDA_TIME_ZONE,
        "period_kind": "custom",
        "from": start.isoformat(timespec="seconds"),
        "to": end.isoformat(timespec="seconds"),
    }


def _payload(response: Response) -> dict[str, Any]:
    return cast(dict[str, Any], response.json())


def _problem(response: Response, status: int) -> ProblemDetails:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    problem = ProblemDetails.model_validate(_payload(response), strict=True)
    assert problem.status == status
    assert problem.request_id
    assert problem.instance == response.request.url.path
    return problem


async def _insert_snapshot(
    engine: AsyncEngine,
    *,
    source_sha256: str = EDA_SOURCE_SHA256,
    config_hash: str = EDA_CONFIG_HASH,
    dataset_id: str = EDA_DATASET_ID,
    status: str = "complete",
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
                        manifest_sha256=MANIFEST_SHA256,
                        config_hash=config_hash,
                        source_from_ts=SOURCE_FROM,
                        source_to_ts=SOURCE_TO - timedelta(seconds=1),
                        expected_row_count=60,
                        expected_channel_count=2,
                        importer_version="test-importer-v1",
                        status=status,
                        completed_at=datetime.now(timezone.utc),
                        manifest={"source": "test"},
                    )
                    .returning(tables.eda_source_snapshots.c.id)
                )
            ).scalar_one(),
        )


def _sections() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for section in EDA_SECTION_NAMES:
        if section == "relationships":
            rows.append(
                {
                    "section": section,
                    "status": "not_eligible",
                    "reason_code": "insufficient_nonconstant_pairs",
                    "detail": "Pasangan data tidak cukup bervariasi.",
                }
            )
        elif section == "stationarity":
            rows.append(
                {
                    "section": section,
                    "status": "failed",
                    "reason_code": "section_compute_failed",
                    "detail": "Bagian statistik gagal dihitung.",
                }
            )
        else:
            payload: dict[str, object] = {}
            if section == "quality_overview":
                payload = {
                    "source_audit": {
                        "row_count": 60,
                        "exact_pair_count": 30,
                        "rule_screened_pair_count": 30,
                    },
                    "count_conservation": {"status": "pass"},
                    "quality_metrics": {"excluded_pairs": 0},
                }
            rows.append(
                {
                    "section": section,
                    "status": "complete",
                    "payload": payload,
                    "payload_sha256": hashlib.sha256(
                        repr(payload).encode()
                    ).hexdigest(),
                }
            )
    return rows


async def _publish(
    engine: AsyncEngine,
    *,
    snapshot_id: UUID,
    from_ts: datetime,
    to_ts: datetime,
    period_kind: EdaPeriodKind,
    source_sha256: str = EDA_SOURCE_SHA256,
    algorithm_version: str = EDA_ALGORITHM_VERSION,
    config_hash: str = EDA_CONFIG_HASH,
) -> tuple[UUID, UUID]:
    async with engine.connect() as connection:
        disposition, queued = await enqueue_job(
            connection,
            snapshot_id=snapshot_id,
            source_sha256=source_sha256,
            from_ts=from_ts,
            to_ts=to_ts,
            period_kind=period_kind,
            algorithm_version=algorithm_version,
            config_hash=config_hash,
            trigger_kind="backfill" if period_kind != "custom" else "api",
        )
    assert disposition == "enqueued"
    job_id = cast(UUID, queued["id"])
    worker_id = f"worker-{job_id}"
    async with engine.connect() as connection:
        claimed = await claim_job(
            connection, lease_owner=worker_id, lease_seconds=60
        )
    assert claimed is not None and claimed["id"] == job_id
    async with engine.connect() as connection:
        completed = await complete_job(
            connection,
            job_id=job_id,
            lease_owner=worker_id,
            attempt_count=cast(int, claimed["attempt_count"]),
            provenance={"label": "algorithm-equivalent range computation"},
            canonical_release=False,
            sections=_sections(),
        )
    assert completed is not None
    return cast(UUID, completed[0]["id"]), job_id


@pytest.mark.anyio
async def test_compute_miss_coalesces_and_job_polling(
    client_factory: ClientFactory,
) -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        _ = await _insert_snapshot(engine)
        async with client_factory(router) as (_, client):
            first = await client.post("/api/eda/compute", json=_body())
            second = await client.post("/api/eda/compute", json=_body())

            assert first.status_code == second.status_code == 202
            first_job = _payload(first)["job"]
            second_job = _payload(second)["job"]
            assert isinstance(first_job, Mapping)
            assert isinstance(second_job, Mapping)
            assert first_job["job_id"] == second_job["job_id"]
            assert first_job["status"] == "queued"

            poll = await client.get(f"/api/eda/jobs/{first_job['job_id']}")
            assert poll.status_code == 200
            assert _payload(poll)["job"]["status"] == "queued"
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_cache_hit_run_and_complete_diagnostic_sections(
    client_factory: ClientFactory,
) -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        snapshot_id = await _insert_snapshot(engine)
        run_id, job_id = await _publish(
            engine,
            snapshot_id=snapshot_id,
            from_ts=CUSTOM_FROM,
            to_ts=CUSTOM_TO,
            period_kind="custom",
        )
        async with client_factory(router) as (_, client):
            hit = await client.post("/api/eda/compute", json=_body())
            assert hit.status_code == 200
            assert _payload(hit)["cache_hit"] is True
            assert _payload(hit)["run"]["run_id"] == str(run_id)

            job = await client.get(f"/api/eda/jobs/{job_id}")
            assert job.status_code == 200
            assert _payload(job)["job"]["run_id"] == str(run_id)

            run = await client.get(f"/api/eda/runs/{run_id}")
            assert run.status_code == 200
            assert len(_payload(run)["run"]["sections"]) == 11

            complete = await client.get(
                f"/api/eda/runs/{run_id}/sections/quality_overview"
            )
            not_eligible = await client.get(
                f"/api/eda/runs/{run_id}/sections/relationships"
            )
            failed = await client.get(
                f"/api/eda/runs/{run_id}/sections/stationarity"
            )

            assert complete.status_code == 200
            assert _payload(complete)["status"] == "complete"
            assert _payload(complete)["payload"]["source_audit"]["row_count"] == 60
            assert not_eligible.status_code == 200
            assert _payload(not_eligible)["status"] == "not_eligible"
            assert _payload(not_eligible)["payload"] is None
            assert failed.status_code == 200
            assert _payload(failed)["status"] == "failed"
            assert _payload(failed)["reason_code"] == "section_compute_failed"
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_period_pagination_uses_active_identity_and_history_by_id(
    client_factory: ClientFactory,
) -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        snapshot_id = await _insert_snapshot(engine)
        active_ids: list[UUID] = []
        for month in (7, 8, 9):
            run_id, _ = await _publish(
                engine,
                snapshot_id=snapshot_id,
                from_ts=datetime(2025, month, 1),
                to_ts=datetime(2025, month + 1, 1),
                period_kind="monthly",
            )
            active_ids.append(run_id)
        historical_id, _ = await _publish(
            engine,
            snapshot_id=snapshot_id,
            from_ts=datetime(2025, 10, 1),
            to_ts=datetime(2025, 11, 1),
            period_kind="monthly",
            algorithm_version="legacy-eda-model-coupled-v2",
        )

        async with client_factory(router) as (_, client):
            first = await client.get(
                "/api/eda/periods", params={"period_kind": "monthly", "limit": 2}
            )
            assert first.status_code == 200
            first_payload = _payload(first)
            assert [item["run_id"] for item in first_payload["items"]] == [
                str(active_ids[2]),
                str(active_ids[1]),
            ]
            assert first_payload["next_cursor"] == "eda-periods:2"

            second = await client.get(
                "/api/eda/periods",
                params={
                    "period_kind": "monthly",
                    "limit": 2,
                    "cursor": first_payload["next_cursor"],
                },
            )
            assert second.status_code == 200
            assert [item["run_id"] for item in _payload(second)["items"]] == [
                str(active_ids[0])
            ]
            assert _payload(second)["next_cursor"] is None

            history = await client.get(f"/api/eda/runs/{historical_id}")
            assert history.status_code == 200
            assert _payload(history)["run"]["algorithm_version"].startswith("legacy-")
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_no_source_contract_errors_unknown_and_partial_publication(
    client_factory: ClientFactory,
) -> None:
    engine = create_database_engine(Settings.from_environ())
    unknown = uuid4()
    try:
        async with client_factory(router) as (_, client):
            _problem(
                await client.get(
                    "/api/eda/periods", params={"period_kind": "daily"}
                ),
                503,
            )
            _problem(await client.post("/api/eda/compute", json=_body()), 503)

            invalid_requests = (
                {**_body(), "period_kind": "daily"},
                {**_body(), "from": "2025-07-01T00:00:00+07:00"},
                {**_body(), "from": "2025-07-01T00:00:00.000"},
                {**_body(), "from": "2025-07-02T00:00:00"},
                {**_body(), "from": "2025-06-22T23:59:59"},
            )
            for invalid in invalid_requests:
                _problem(
                    await client.post("/api/eda/compute", json=invalid), 422
                )

            _problem(await client.get(f"/api/eda/jobs/{unknown}"), 404)
            _problem(await client.get(f"/api/eda/runs/{unknown}"), 404)
            _problem(
                await client.get(
                    f"/api/eda/runs/{unknown}/sections/quality_overview"
                ),
                404,
            )

        snapshot_id = await _insert_snapshot(engine)
        logical_key = build_logical_key(
            source_sha256=EDA_SOURCE_SHA256,
            from_ts=CUSTOM_FROM,
            to_ts=CUSTOM_TO,
            period_kind="custom",
            algorithm_version=EDA_ALGORITHM_VERSION,
            config_hash=EDA_CONFIG_HASH,
        )
        async with engine.begin() as connection:
            partial_run_id = cast(
                UUID,
                (
                    await connection.execute(
                        insert(tables.eda_runs)
                        .values(
                            logical_key=logical_key,
                            snapshot_id=snapshot_id,
                            source_sha256=EDA_SOURCE_SHA256,
                            from_ts=CUSTOM_FROM,
                            to_ts=CUSTOM_TO,
                            period_kind="custom",
                            algorithm_version=EDA_ALGORITHM_VERSION,
                            config_hash=EDA_CONFIG_HASH,
                            provenance={"label": "partial"},
                            canonical_release=False,
                            completed_at=datetime.now(timezone.utc),
                        )
                        .returning(tables.eda_runs.c.id)
                    )
                ).scalar_one(),
            )
            _ = await connection.execute(
                insert(tables.eda_result_sections).values(
                    run_id=partial_run_id,
                    section="quality_overview",
                    status="complete",
                    payload={"source_audit": {}},
                    payload_sha256="2" * 64,
                )
            )
        async with client_factory(router) as (_, client):
            _problem(await client.get(f"/api/eda/runs/{partial_run_id}"), 404)
            _problem(
                await client.get(
                    f"/api/eda/runs/{partial_run_id}/sections/quality_overview"
                ),
                404,
            )
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_custom_job_cap_allows_cache_hits_and_coalescing(
    client_factory: ClientFactory,
) -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        snapshot_id = await _insert_snapshot(engine)
        cached_from = datetime(2025, 7, 3)
        cached_to = datetime(2025, 7, 4)
        cached_run_id, _ = await _publish(
            engine,
            snapshot_id=snapshot_id,
            from_ts=cached_from,
            to_ts=cached_to,
            period_kind="custom",
        )
        coalesced_from = datetime(2025, 7, 5)
        coalesced_to = coalesced_from + timedelta(seconds=1)

        async with client_factory(router) as (_, client):
            coalesced = await client.post(
                "/api/eda/compute", json=_body(coalesced_from, coalesced_to)
            )
            assert coalesced.status_code == 202
            coalesced_job_id = _payload(coalesced)["job"]["job_id"]

            for index in range(31):
                start = datetime(2025, 7, 6) + timedelta(seconds=index * 2)
                async with engine.connect() as connection:
                    disposition, _ = await enqueue_job(
                        connection,
                        snapshot_id=snapshot_id,
                        source_sha256=EDA_SOURCE_SHA256,
                        from_ts=start,
                        to_ts=start + timedelta(seconds=1),
                        period_kind="custom",
                        algorithm_version=EDA_ALGORITHM_VERSION,
                        config_hash=EDA_CONFIG_HASH,
                        trigger_kind="api",
                    )
                assert disposition == "enqueued"

            miss_from = datetime(2025, 7, 7)
            limited = await client.post(
                "/api/eda/compute",
                json=_body(miss_from, miss_from + timedelta(seconds=1)),
            )
            problem = _problem(limited, 429)
            assert "retry" in problem.detail

            same_active = await client.post(
                "/api/eda/compute", json=_body(coalesced_from, coalesced_to)
            )
            assert same_active.status_code == 202
            assert _payload(same_active)["job"]["job_id"] == coalesced_job_id

            cached = await client.post(
                "/api/eda/compute", json=_body(cached_from, cached_to)
            )
            assert cached.status_code == 200
            assert _payload(cached)["run"]["run_id"] == str(cached_run_id)
    finally:
        await engine.dispose()
