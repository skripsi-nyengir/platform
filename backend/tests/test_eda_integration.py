from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from typing import cast
from uuid import UUID, uuid4

import psycopg
from psycopg import sql
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.eda_contracts import (
    EDA_ALGORITHM_VERSION,
    EDA_CONFIG_HASH,
    EDA_DATASET_ID,
    EDA_SECTION_NAMES,
    EDA_SOURCE_FROM,
    EDA_SOURCE_SHA256,
    EDA_SOURCE_TO,
)
from anomaly_backend.eda_importer import (
    CANONICAL_MANIFEST_SHA256,
    import_eda_source,
)
from anomaly_backend.routes.eda import router
from anomaly_backend.sql.eda_runs import (
    enqueue_job,
    get_job,
    get_run,
    get_sections,
)
from anomaly_eda.config import MAXIMUM_PEAK_RSS_BYTES
from anomaly_worker.eda_service import run_once
from conftest import ClientFactory  # pyright: ignore[reportImplicitRelativeImport]


EXPECTED_COUNTS = {
    "raw_rows": 6_931_792,
    "exact_pairs": 3_460_865,
    "screened_pairs": 3_405_332,
    "excluded_pairs": 55_533,
}


def _run_migrations() -> None:
    _ = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=Path(__file__).parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def _admin_connection(
    settings: Settings,
) -> psycopg.Connection[tuple[object, ...]]:
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname="postgres",
        user=settings.postgres_user,
        password=settings.postgres_password,
        autocommit=True,
    )


def _create_database(settings: Settings, database_name: str) -> None:
    with _admin_connection(settings) as connection:
        _ = connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )


def _drop_database(settings: Settings, database_name: str) -> None:
    with _admin_connection(settings) as connection:
        _ = connection.execute(
            sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                sql.Identifier(database_name)
            )
        )


async def _table_counts(engine: AsyncEngine) -> dict[str, int]:
    targets = {
        "snapshots": tables.eda_source_snapshots,
        "raw_readings": tables.eda_raw_readings,
        "jobs": tables.eda_jobs,
        "runs": tables.eda_runs,
        "sections": tables.eda_result_sections,
    }
    async with engine.connect() as connection:
        return {
            name: int(
                cast(
                    int,
                    await connection.scalar(select(func.count()).select_from(table)),
                )
            )
            for name, table in targets.items()
        }


def _parity_report() -> dict[str, object]:
    value = os.environ.get("EDA_CANONICAL_PARITY_REPORT")
    assert value, "canonical authority parity must execute before integration"
    report = cast(object, json.loads(value))
    assert isinstance(report, dict)
    return cast(dict[str, object], report)


@pytest.mark.canonical
@pytest.mark.anyio
async def test_canonical_import_full_range_publication_and_api(
    monkeypatch: pytest.MonkeyPatch,
    client_factory: ClientFactory,
) -> None:
    raw_path_value = os.environ.get("EDA_CANONICAL_RAW_CSV")
    if not raw_path_value:
        pytest.skip("EDA_CANONICAL_RAW_CSV is required for canonical integration")
    raw_path = Path(raw_path_value)
    manifest_path = (
        raw_path.parents[3]
        / "docs/artifacts/manifests/bivariate_b02f3872_source_v1.json"
    )
    parity = _parity_report()
    assert parity["parity_status"] == "pass"
    assert parity["counts"] == EXPECTED_COUNTS

    admin_settings = Settings.from_environ()
    database_name = f"task21_{os.getpid()}_{uuid4().hex[:8]}"
    _create_database(admin_settings, database_name)
    engine: AsyncEngine | None = None
    try:
        monkeypatch.setenv("POSTGRES_DB", database_name)
        _run_migrations()
        settings = Settings.from_environ()

        imported = import_eda_source(
            raw_path,
            manifest_path,
            expected_manifest_sha256=CANONICAL_MANIFEST_SHA256,
        )
        assert imported == {
            "snapshot_id": imported["snapshot_id"],
            "dataset_id": EDA_DATASET_ID,
            "source_sha256": EDA_SOURCE_SHA256,
            "status": "complete",
            "row_count": EXPECTED_COUNTS["raw_rows"],
            "idempotent_noop": False,
        }

        snapshot_id = UUID(cast(str, imported["snapshot_id"]))
        engine = create_database_engine(settings)
        time_from = datetime.fromisoformat(EDA_SOURCE_FROM)
        time_to = datetime.fromisoformat(EDA_SOURCE_TO)
        async with engine.connect() as connection:
            snapshot = (
                await connection.execute(
                    select(tables.eda_source_snapshots).where(
                        tables.eda_source_snapshots.c.id == snapshot_id
                    )
                )
            ).mappings().one()
        async with engine.connect() as connection:
            disposition, queued = await enqueue_job(
                connection,
                snapshot_id=snapshot_id,
                source_sha256=EDA_SOURCE_SHA256,
                from_ts=time_from,
                to_ts=time_to,
                period_kind="full_range",
                algorithm_version=EDA_ALGORITHM_VERSION,
                config_hash=EDA_CONFIG_HASH,
                trigger_kind="backfill",
            )
        assert snapshot["config_hash"] == EDA_CONFIG_HASH
        assert snapshot["source_sha256"] == EDA_SOURCE_SHA256
        assert snapshot["manifest_sha256"] == CANONICAL_MANIFEST_SHA256
        assert disposition == "enqueued"

        job_id = cast(UUID, queued["id"])
        compute_started = time.monotonic()
        assert await run_once(
            engine,
            settings,
            worker_id=f"task21-canonical-{os.getpid()}",
        )
        compute_runtime_seconds = time.monotonic() - compute_started

        async with engine.connect() as connection:
            job = await get_job(connection, job_id=job_id)
            assert job is not None and job["status"] == "succeeded", job
            run_id = cast(UUID, job["run_id"])
            run = await get_run(connection, run_id=run_id)
            sections = await get_sections(connection, run_id=run_id)
        assert run is not None
        assert run["logical_key"] == parity["logical_key"]
        assert run["period_kind"] == "full_range"
        assert run["from_ts"] == time_from
        assert run["to_ts"] == time_to
        assert run["canonical_release"] is True
        provenance = cast(dict[str, object], run["provenance"])
        assert provenance["label"] == "published v3 release"
        assert provenance["source_manifest_sha256"] == CANONICAL_MANIFEST_SHA256
        assert provenance["algorithm_version"] == EDA_ALGORITHM_VERSION
        assert provenance["config_hash"] == EDA_CONFIG_HASH
        peak_rss_bytes = cast(int, provenance["peak_rss_bytes"])
        assert peak_rss_bytes < MAXIMUM_PEAK_RSS_BYTES

        assert [row["section"] for row in sections] == list(EDA_SECTION_NAMES)
        assert {row["status"] for row in sections} == {"complete"}
        section_hashes = {
            str(row["section"]): str(row["payload_sha256"]) for row in sections
        }
        assert section_hashes == parity["section_hashes"]

        async with client_factory(router) as (_, client):
            run_response = await client.get(f"/api/eda/runs/{run_id}")
            assert run_response.status_code == 200
            run_payload = cast(dict[str, object], run_response.json())
            api_run = cast(dict[str, object], run_payload["run"])
            assert api_run["run_id"] == str(run_id)
            assert api_run["canonical_release"] is True

            for section, expected_hash in section_hashes.items():
                response = await client.get(
                    f"/api/eda/runs/{run_id}/sections/{section}"
                )
                assert response.status_code == 200
                payload = cast(dict[str, object], response.json())
                assert payload["payload_sha256"] == expected_hash
                if section == "quality_overview":
                    counts = cast(dict[str, int], payload["sample_counts"])
                    assert counts == {
                        "raw_rows": EXPECTED_COUNTS["raw_rows"],
                        "exact_pairs": EXPECTED_COUNTS["exact_pairs"],
                        "screened_pairs": EXPECTED_COUNTS["screened_pairs"],
                        "active_pairs": EXPECTED_COUNTS["screened_pairs"],
                    }
                    assert counts["exact_pairs"] - counts["screened_pairs"] == (
                        EXPECTED_COUNTS["excluded_pairs"]
                    )

        before_reimport = await _table_counts(engine)
        repeated = import_eda_source(
            raw_path,
            manifest_path,
            expected_manifest_sha256=CANONICAL_MANIFEST_SHA256,
        )
        after_reimport = await _table_counts(engine)
        assert repeated == {**imported, "idempotent_noop": True}
        assert before_reimport == after_reimport
        assert after_reimport == {
            "snapshots": 1,
            "raw_readings": EXPECTED_COUNTS["raw_rows"],
            "jobs": 1,
            "runs": 1,
            "sections": len(EDA_SECTION_NAMES),
        }

        report = {
            "status": "pass",
            "parity_status": parity["parity_status"],
            "parity_runtime_seconds": parity["runtime_seconds"],
            "full_range_runtime_seconds": compute_runtime_seconds,
            "peak_rss_bytes": peak_rss_bytes,
            "counts": EXPECTED_COUNTS,
            "source_sha256": EDA_SOURCE_SHA256,
            "manifest_sha256": CANONICAL_MANIFEST_SHA256,
            "config_hash": snapshot["config_hash"],
            "logical_key": run["logical_key"],
            "section_hashes": section_hashes,
            "canonical_release": run["canonical_release"],
            "period_kind": run["period_kind"],
            "import_idempotent_noop": repeated["idempotent_noop"],
        }
        os.environ["EDA_CANONICAL_INTEGRATION_REPORT"] = json.dumps(
            report, sort_keys=True, separators=(",", ":")
        )
        print(f"task21 canonical integration report {os.environ['EDA_CANONICAL_INTEGRATION_REPORT']}")
    finally:
        if engine is not None:
            await engine.dispose()
        _drop_database(admin_settings, database_name)
