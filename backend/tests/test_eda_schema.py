from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
import subprocess
import sys
from typing import Any, LiteralString, cast
from uuid import UUID

import psycopg
from psycopg import sql
import pytest

from anomaly_backend.config import Settings


EDA_TABLES = {
    "eda_jobs",
    "eda_raw_readings",
    "eda_result_sections",
    "eda_runs",
    "eda_source_snapshots",
}
SOURCE_SHA = "a" * 64
MANIFEST_SHA = "b" * 64
CONFIG_HASH = "c" * 64
PAYLOAD_SHA = "d" * 64


def _run_alembic(*arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=Path(__file__).parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def _connect() -> psycopg.Connection[tuple[Any, ...]]:
    settings = Settings.from_environ()
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        autocommit=True,
    )


def _public_tables(
    connection: psycopg.Connection[tuple[Any, ...]],
) -> set[str]:
    rows = connection.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _insert_snapshot(
    connection: psycopg.Connection[tuple[Any, ...]],
) -> UUID:
    row = connection.execute(
        """
        INSERT INTO eda_source_snapshots (
            dataset_id, source_sha256, manifest_sha256, config_hash,
            source_from_ts, source_to_ts, expected_row_count,
            expected_channel_count, importer_version, status,
            completed_at, manifest
        ) VALUES (
            'b02-v1', %s, %s, %s,
            '2025-01-01 00:00:00', '2025-12-31 23:59:59',
            2, 2, 'test-importer-v1', 'complete', now(),
            '{"source":"test"}'::jsonb
        )
        RETURNING id
        """,
        (SOURCE_SHA, MANIFEST_SHA, CONFIG_HASH),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_job(
    connection: psycopg.Connection[tuple[Any, ...]],
    snapshot_id: UUID,
    logical_key: str,
    *,
    from_ts: datetime = datetime(2025, 1, 1),
    to_ts: datetime = datetime(2025, 1, 2),
) -> UUID:
    row = connection.execute(
        """
        INSERT INTO eda_jobs (
            logical_key, snapshot_id, source_sha256, from_ts, to_ts,
            period_kind, algorithm_version, config_hash, trigger_kind
        ) VALUES (%s, %s, %s, %s, %s, 'custom', 'eda-v3-test', %s, 'api')
        RETURNING id
        """,
        (
            logical_key,
            snapshot_id,
            SOURCE_SHA,
            from_ts,
            to_ts,
            CONFIG_HASH,
        ),
    ).fetchone()
    assert row is not None
    return row[0]


def _insert_run(
    connection: psycopg.Connection[tuple[Any, ...]],
    snapshot_id: UUID,
    logical_key: str,
) -> UUID:
    row = connection.execute(
        """
        INSERT INTO eda_runs (
            logical_key, snapshot_id, source_sha256, from_ts, to_ts,
            period_kind, algorithm_version, config_hash, provenance,
            canonical_release, completed_at
        ) VALUES (
            %s, %s, %s, '2025-01-01 00:00:00', '2025-01-02 00:00:00',
            'daily', 'eda-v3-test', %s,
            '{"kind":"algorithm_equivalent_range"}'::jsonb, FALSE, now()
        )
        RETURNING id
        """,
        (logical_key, snapshot_id, SOURCE_SHA, CONFIG_HASH),
    ).fetchone()
    assert row is not None
    return row[0]


@pytest.fixture(scope="module", autouse=True)
def eda_schema_head() -> Iterator[None]:
    _run_alembic("upgrade", "head")
    yield
    _run_alembic("upgrade", "head")


@pytest.fixture(autouse=True)
def clean_eda_tables(eda_schema_head: None) -> Iterator[None]:
    del eda_schema_head
    with _connect() as connection:
        connection.execute(
            "TRUNCATE eda_result_sections, eda_runs, eda_jobs, "
            "eda_raw_readings, eda_source_snapshots"
        )
    yield
    with _connect() as connection:
        if connection.execute(
            "SELECT to_regclass('public.eda_source_snapshots')"
        ).fetchone() == ("eda_source_snapshots",):
            connection.execute(
                "TRUNCATE eda_result_sections, eda_runs, eda_jobs, "
                "eda_raw_readings, eda_source_snapshots"
            )


def test_schema_is_current_and_raw_readings_are_timescale_float64() -> None:
    with _connect() as connection:
        revision = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone()
        assert revision == ("20260803_0014",)
        assert EDA_TABLES <= _public_tables(connection)

        dimension = connection.execute(
            """
            SELECT column_name
            FROM timescaledb_information.dimensions
            WHERE hypertable_schema = 'public'
              AND hypertable_name = 'eda_raw_readings'
            """
        ).fetchone()
        assert dimension == ("ts",)

        column_types = dict(
            connection.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = 'eda_raw_readings'
                  AND column_name IN ('value', 'ts')
                """
            ).fetchall()
        )
        assert column_types == {
            "ts": "timestamp without time zone",
            "value": "double precision",
        }

        index_definition = connection.execute(
            """
            SELECT indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = 'uq_eda_jobs_active_logical_key'
            """
        ).fetchone()
        assert index_definition is not None
        assert "UNIQUE INDEX" in index_definition[0]
        assert "WHERE (status = ANY" in index_definition[0]
        assert "'queued'::text" in index_definition[0]
        assert "'running'::text" in index_definition[0]


def test_duplicate_raw_evidence_is_preserved_by_source_row_number() -> None:
    with _connect() as connection:
        snapshot_id = _insert_snapshot(connection)
        with connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO eda_raw_readings (
                    snapshot_id, source_row_number, device_id, data_index,
                    value, ts, is_connected
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                [
                    (
                        snapshot_id,
                        1,
                        "b02f3872-39a2-4b6f-a4ec-045a287fde4b",
                        0,
                        25.0,
                        datetime(2025, 1, 1),
                        True,
                    ),
                    (
                        snapshot_id,
                        2,
                        "b02f3872-39a2-4b6f-a4ec-045a287fde4b",
                        0,
                        25.0,
                        datetime(2025, 1, 1),
                        True,
                    ),
                ],
            )
        rows = connection.execute(
            """
            SELECT source_row_number, value
            FROM eda_raw_readings
            WHERE snapshot_id = %s
            ORDER BY source_row_number
            """,
            (snapshot_id,),
        ).fetchall()
        assert rows == [(1, 25.0), (2, 25.0)]


def test_active_job_logical_key_coalesces_until_terminal_failure() -> None:
    with _connect() as connection:
        snapshot_id = _insert_snapshot(connection)
        logical_key = "1" * 64
        first_id = _insert_job(connection, snapshot_id, logical_key)

        with pytest.raises(psycopg.errors.UniqueViolation) as duplicate:
            _insert_job(connection, snapshot_id, logical_key)
        assert duplicate.value.diag.constraint_name == (
            "uq_eda_jobs_active_logical_key"
        )

        connection.execute(
            """
            UPDATE eda_jobs
            SET status = 'failed', terminal = TRUE, completed_at = now()
            WHERE id = %s
            """,
            (first_id,),
        )
        second_id = _insert_job(connection, snapshot_id, logical_key)
        assert second_id != first_id


def test_run_identity_and_sections_are_unique() -> None:
    with _connect() as connection:
        snapshot_id = _insert_snapshot(connection)
        logical_key = "2" * 64
        run_id = _insert_run(connection, snapshot_id, logical_key)

        with pytest.raises(psycopg.errors.UniqueViolation) as duplicate_run:
            _insert_run(connection, snapshot_id, logical_key)
        assert duplicate_run.value.diag.constraint_name == "uq_eda_runs_logical_key"

        connection.execute(
            """
            INSERT INTO eda_result_sections (
                run_id, section, status, payload, payload_sha256
            ) VALUES (%s, 'quality_overview', 'complete', '{}'::jsonb, %s)
            """,
            (run_id, PAYLOAD_SHA),
        )
        connection.execute(
            """
            INSERT INTO eda_result_sections (
                run_id, section, status, reason_code, reason_detail
            ) VALUES (
                %s, 'relationships', 'not_eligible',
                'insufficient_pairs', 'Pasangan data belum cukup'
            )
            """,
            (run_id,),
        )
        connection.execute(
            """
            INSERT INTO eda_result_sections (
                run_id, section, status, reason_code, reason_detail
            ) VALUES (
                %s, 'stationarity', 'failed',
                'method_failed', 'Metode statistik gagal'
            )
            """,
            (run_id,),
        )

        with pytest.raises(psycopg.errors.UniqueViolation) as duplicate_section:
            connection.execute(
                """
                INSERT INTO eda_result_sections (
                    run_id, section, status, payload, payload_sha256
                ) VALUES (%s, 'quality_overview', 'complete', '{}'::jsonb, %s)
                """,
                (run_id, PAYLOAD_SHA),
            )
        assert duplicate_section.value.diag.constraint_name == (
            "uq_eda_result_sections_run_section"
        )


def test_invalid_writes_fail_without_partial_rows() -> None:
    with _connect() as connection:
        with pytest.raises(psycopg.errors.CheckViolation) as malformed_sha:
            connection.execute(
                """
                INSERT INTO eda_source_snapshots (
                    dataset_id, source_sha256, manifest_sha256, config_hash,
                    source_from_ts, source_to_ts, expected_row_count,
                    expected_channel_count, importer_version, status,
                    completed_at, manifest
                ) VALUES (
                    'bad-source', 'not-a-sha', %s, %s,
                    '2025-01-01', '2025-01-02', 1, 2,
                    'test-importer-v1', 'complete', now(), '{}'::jsonb
                )
                """,
                (MANIFEST_SHA, CONFIG_HASH),
            )
        assert malformed_sha.value.diag.constraint_name == (
            "ck_eda_source_snapshots_source_sha256"
        )
        assert connection.execute(
            "SELECT count(*) FROM eda_source_snapshots"
        ).fetchone() == (0,)

        snapshot_id = _insert_snapshot(connection)
        with pytest.raises(psycopg.errors.CheckViolation) as invalid_channel:
            connection.execute(
                """
                INSERT INTO eda_raw_readings (
                    snapshot_id, source_row_number, device_id, data_index,
                    value, ts, is_connected
                ) VALUES (%s, 1, 'device', 2, 1.0, '2025-01-01', TRUE)
                """,
                (snapshot_id,),
            )
        assert invalid_channel.value.diag.constraint_name == (
            "ck_eda_raw_readings_data_index"
        )
        assert connection.execute(
            "SELECT count(*) FROM eda_raw_readings"
        ).fetchone() == (0,)

        with pytest.raises(psycopg.errors.CheckViolation) as invalid_range:
            _insert_job(
                connection,
                snapshot_id,
                "3" * 64,
                from_ts=datetime(2025, 1, 2),
                to_ts=datetime(2025, 1, 2),
            )
        assert invalid_range.value.diag.constraint_name == "ck_eda_jobs_range"
        assert connection.execute("SELECT count(*) FROM eda_jobs").fetchone() == (0,)


def test_published_source_rows_runs_and_sections_are_immutable() -> None:
    with _connect() as connection:
        snapshot_id = _insert_snapshot(connection)
        connection.execute(
            """
            INSERT INTO eda_raw_readings (
                snapshot_id, source_row_number, device_id, data_index,
                value, ts, is_connected
            ) VALUES (%s, 1, 'device', 0, 1.0, '2025-01-01', TRUE)
            """,
            (snapshot_id,),
        )
        run_id = _insert_run(connection, snapshot_id, "4" * 64)
        connection.execute(
            """
            INSERT INTO eda_result_sections (
                run_id, section, status, payload, payload_sha256
            ) VALUES (%s, 'audit_metadata', 'complete', '{}'::jsonb, %s)
            """,
            (run_id, PAYLOAD_SHA),
        )

        immutable_writes = (
            (
                "UPDATE eda_source_snapshots SET manifest = '{}'::jsonb WHERE id = %s",
                (snapshot_id,),
            ),
            (
                "UPDATE eda_raw_readings SET value = 2.0 WHERE snapshot_id = %s",
                (snapshot_id,),
            ),
            (
                "DELETE FROM eda_raw_readings WHERE snapshot_id = %s",
                (snapshot_id,),
            ),
            (
                "UPDATE eda_runs SET canonical_release = TRUE WHERE id = %s",
                (run_id,),
            ),
            (
                "DELETE FROM eda_result_sections "
                "WHERE run_id = %s AND section = 'audit_metadata'",
                (run_id,),
            ),
        )
        for statement, parameters in immutable_writes:
            with pytest.raises(psycopg.Error) as immutable:
                connection.execute(sql.SQL(cast(LiteralString, statement)), parameters)
            assert immutable.value.sqlstate == "55000"


def test_staged_raw_rows_can_be_removed_before_failed_import_audit() -> None:
    with _connect() as connection:
        snapshot = connection.execute(
            """
            INSERT INTO eda_source_snapshots (
                dataset_id, source_sha256, manifest_sha256, config_hash,
                source_from_ts, source_to_ts, expected_row_count,
                expected_channel_count, importer_version, status, manifest
            ) VALUES (
                'staged-b02-v1', %s, %s, %s,
                '2025-01-01', '2025-01-02', 1, 2,
                'test-importer-v1', 'staging', '{}'::jsonb
            )
            RETURNING id
            """,
            (SOURCE_SHA, MANIFEST_SHA, CONFIG_HASH),
        ).fetchone()
        assert snapshot is not None
        snapshot_id = snapshot[0]
        connection.execute(
            """
            INSERT INTO eda_raw_readings (
                snapshot_id, source_row_number, device_id, data_index,
                value, ts, is_connected
            ) VALUES (%s, 1, 'device', 0, 1.0, '2025-01-01', TRUE)
            """,
            (snapshot_id,),
        )

        deleted = connection.execute(
            "DELETE FROM eda_raw_readings WHERE snapshot_id = %s",
            (snapshot_id,),
        )
        assert deleted.rowcount == 1
        connection.execute(
            """
            UPDATE eda_source_snapshots
            SET status = 'failed', completed_at = now()
            WHERE id = %s
            """,
            (snapshot_id,),
        )
        assert connection.execute(
            "SELECT status FROM eda_source_snapshots WHERE id = %s",
            (snapshot_id,),
        ).fetchone() == ("failed",)


def test_downgrade_is_blocked_without_mutating_eda_objects() -> None:
    with _connect() as connection:
        before = _public_tables(connection)
        assert EDA_TABLES <= before

    with pytest.raises(subprocess.CalledProcessError):
        _run_alembic("downgrade", "20260724_0002")

    with _connect() as connection:
        assert connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchone() == ("20260803_0014",)
        assert _public_tables(connection) == before
        assert connection.execute(
            """
            SELECT column_name
            FROM timescaledb_information.dimensions
            WHERE hypertable_schema = 'public'
              AND hypertable_name = 'eda_raw_readings'
            """
        ).fetchone() == ("ts",)
