from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
from typing import cast
from uuid import UUID

import psycopg
import pytest
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.eda_cli import COUNTER_NAMES, backfill, enumerate_periods, main
from anomaly_backend.eda_contracts import EDA_SOURCE_FROM, EDA_SOURCE_TO
from anomaly_backend.eda_importer import (
    CANONICAL_MANIFEST_SHA256,
    CANONICAL_SOURCE_SHA256,
    CONFIG_HASH as IMPORT_CONFIG_HASH,
    DATASET_ID,
    IMPORTER_VERSION,
)


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


async def _insert_canonical_snapshot(engine: AsyncEngine) -> UUID:
    source_to_inclusive = datetime.fromisoformat(EDA_SOURCE_TO) - timedelta(seconds=1)
    async with engine.begin() as connection:
        return cast(
            UUID,
            (
                await connection.execute(
                    insert(tables.eda_source_snapshots)
                    .values(
                        dataset_id=DATASET_ID,
                        source_sha256=CANONICAL_SOURCE_SHA256,
                        manifest_sha256=CANONICAL_MANIFEST_SHA256,
                        config_hash=IMPORT_CONFIG_HASH,
                        source_from_ts=datetime.fromisoformat(EDA_SOURCE_FROM),
                        source_to_ts=source_to_inclusive,
                        expected_row_count=6_931_792,
                        expected_channel_count=2,
                        importer_version=IMPORTER_VERSION,
                        status="complete",
                        completed_at=datetime.now(timezone.utc),
                        manifest={"source": "canonical-test"},
                    )
                    .returning(tables.eda_source_snapshots.c.id)
                )
            ).scalar_one(),
        )


async def _with_engine(
    *,
    kind: str = "daily",
    from_ts: str = "2026-01-01T00:00:00",
    to_ts: str = "2026-01-03T00:00:00",
) -> dict[str, int]:
    engine = create_database_engine(Settings.from_environ())
    try:
        _ = await _insert_canonical_snapshot(engine)
        return await backfill(
            engine,
            kind=kind,
            from_ts=datetime.fromisoformat(from_ts),
            to_ts=datetime.fromisoformat(to_ts),
        )
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ("kind", "from_ts", "to_ts", "expected"),
    [
        (
            "daily",
            "2024-02-28T00:00:00",
            "2024-03-01T00:00:00",
            [
                (datetime(2024, 2, 28), datetime(2024, 2, 29), "daily"),
                (datetime(2024, 2, 29), datetime(2024, 3, 1), "daily"),
            ],
        ),
        (
            "weekly",
            "2025-12-31T00:00:00",
            "2026-01-02T00:00:00",
            [(datetime(2025, 12, 29), datetime(2026, 1, 5), "weekly")],
        ),
        (
            "monthly",
            "2024-02-10T00:00:00",
            "2024-03-10T00:00:00",
            [
                (datetime(2024, 2, 1), datetime(2024, 3, 1), "monthly"),
                (datetime(2024, 3, 1), datetime(2024, 4, 1), "monthly"),
            ],
        ),
    ],
)
def test_period_enumeration_handles_leap_month_and_iso_week_boundaries(
    kind: str,
    from_ts: str,
    to_ts: str,
    expected: list[tuple[datetime, datetime, str]],
) -> None:
    actual = list(
        enumerate_periods(
            kind, datetime.fromisoformat(from_ts), datetime.fromisoformat(to_ts)
        )
    )
    assert actual == expected


def test_backfill_skips_open_and_outside_source_periods() -> None:
    counters = asyncio.run(
        _with_engine(
            kind="daily",
            from_ts="2025-06-22T00:00:00",
            to_ts="2025-06-25T12:00:00",
        )
    )

    assert counters == {
        "cache_hits": 0,
        "active_jobs": 0,
        "enqueued": 2,
        "skipped_open": 1,
        "skipped_outside_source": 1,
        "errors": 0,
    }
    with _sync_connection() as connection:
        rows = connection.execute(
            "SELECT from_ts, to_ts FROM eda_jobs ORDER BY from_ts"
        ).fetchall()
    assert rows == [
        (datetime(2025, 6, 23), datetime(2025, 6, 24)),
        (datetime(2025, 6, 24), datetime(2025, 6, 25)),
    ]


def test_monthly_source_edges_enqueue_no_partial_period() -> None:
    counters = asyncio.run(
        _with_engine(
            kind="monthly",
            from_ts=EDA_SOURCE_FROM,
            to_ts="2025-07-02T00:00:00",
        )
    )

    assert counters["enqueued"] == 0
    assert counters["skipped_outside_source"] == 1
    assert counters["skipped_open"] == 1


def test_identical_backfill_coalesces_without_a_running_worker() -> None:
    async def scenario() -> tuple[dict[str, int], dict[str, int], int, list[str]]:
        engine = create_database_engine(Settings.from_environ())
        try:
            _ = await _insert_canonical_snapshot(engine)
            first = await backfill(
                engine,
                kind="daily",
                from_ts=datetime(2026, 1, 1),
                to_ts=datetime(2026, 1, 3),
            )
            second = await backfill(
                engine,
                kind="daily",
                from_ts=datetime(2026, 1, 1),
                to_ts=datetime(2026, 1, 3),
            )
            async with engine.connect() as connection:
                count = cast(
                    int, await connection.scalar(select(func.count()).select_from(tables.eda_jobs))
                )
                statuses = list(
                    (
                        await connection.execute(
                            select(tables.eda_jobs.c.status).order_by(
                                tables.eda_jobs.c.from_ts
                            )
                        )
                    ).scalars()
                )
            return first, second, count, statuses
        finally:
            await engine.dispose()

    first, second, count, statuses = asyncio.run(scenario())
    assert first["enqueued"] == 2
    assert second["enqueued"] == 0
    assert second["active_jobs"] == 2
    assert count == 2
    assert statuses == ["queued", "queued"]


def test_all_kind_json_output_is_machine_readable(capsys: pytest.CaptureFixture[str]) -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        _ = asyncio.run(_insert_canonical_snapshot(engine))
    finally:
        asyncio.run(engine.dispose())

    exit_code = main(
        [
            "backfill",
            "--kind",
            "all",
            "--from",
            "2026-01-01T00:00:00",
            "--to",
            "2026-01-02T00:00:00",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    payload = cast(dict[str, int], json.loads(captured.out))
    assert exit_code == 0
    assert captured.err == ""
    assert tuple(payload) == COUNTER_NAMES
    assert payload["enqueued"] == 1
    assert payload["skipped_open"] == 2


def test_missing_snapshot_exits_without_creating_jobs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "backfill",
            "--kind",
            "daily",
            "--from",
            "2026-01-01T00:00:00",
            "--to",
            "2026-01-02T00:00:00",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "complete canonical EDA source snapshot" in captured.err


def test_invalid_range_exits_nonzero_before_database_access(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            "backfill",
            "--kind",
            "daily",
            "--from",
            "2026-01-02T00:00:00",
            "--to",
            "2026-01-02T00:00:00",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "--from must be earlier than --to" in captured.err
