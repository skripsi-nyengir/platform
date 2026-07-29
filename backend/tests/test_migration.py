import asyncio
from datetime import datetime
from pathlib import Path
import subprocess
import sys

from sqlalchemy import text

from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine, current_migration_revision
from anomaly_backend.seed import seed_database


M1_MODEL_VERSION = "conv1d-arm-b-talpha-1-validation-fixture"
M1_EVENT_TIME = datetime(2025, 12, 12, 0, 2, 57)


def _run_alembic(*arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=Path(__file__).parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


async def _drop_public_schema() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("DROP EXTENSION IF EXISTS timescaledb CASCADE")
            )
            await connection.execute(text("DROP SCHEMA public CASCADE"))
            await connection.execute(text("CREATE SCHEMA public"))
            await connection.execute(
                text("GRANT ALL ON SCHEMA public TO PUBLIC")
            )
            await connection.execute(text("CREATE EXTENSION timescaledb"))
    finally:
        await engine.dispose()


async def _insert_m1_lineage_fixture() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO telemetry VALUES (
                        'talpha-1', '2025-12-11 23:50:35',
                        24.5, 55.0, 'm1-payload', 0
                    )
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO inference_results VALUES (
                        'talpha-1',
                        '2025-12-11 23:50:35',
                        '2025-12-12 00:02:57',
                        :model_version,
                        0.028,
                        0.02707822278141974,
                        TRUE,
                        'deterministic_threshold_fixture',
                        0, 29, 30, 1
                    )
                    """
                ),
                {"model_version": M1_MODEL_VERSION},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO alerts VALUES (
                        'm1-alert', 'talpha-1', :event_time,
                        0.028, 0.02707822278141974, :model_version,
                        '2025-12-11 23:50:35',
                        '2025-12-12 00:02:57',
                        'threshold_model_fixture'
                    )
                    """
                ),
                {
                    "event_time": M1_EVENT_TIME,
                    "model_version": M1_MODEL_VERSION,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO alert_events VALUES (
                        'm1-detected', 'm1-alert', :event_time, 'detected',
                        'talpha-1', 'threshold-model-fixture', NULL,
                        '2025-12-11 23:50:35',
                        '2025-12-12 00:02:57',
                        :model_version,
                        'threshold_model_fixture'
                    )
                    """
                ),
                {
                    "event_time": M1_EVENT_TIME,
                    "model_version": M1_MODEL_VERSION,
                },
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO alert_commands VALUES (
                        'm1-command', 'm1-alert', 'acknowledged',
                        :event_time, 'legacy note', 'm1-detected'
                    )
                    """
                ),
                {"event_time": M1_EVENT_TIME},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO model_evaluations VALUES (
                        :model_version, 'conv1d_autoencoder', 'arm_b_talpha1',
                        'M1 fixture', 'global_mae', 'legacy score',
                        '2025-12-11 – 2025-12-18', TRUE, FALSE, 1,
                        0.02707822278141974, '{"comparison": ">"}',
                        FALSE, '["threshold"]', 'M1 summary',
                        NULL, NULL, NULL, '{"threshold": 0.02707822278141974}',
                        'legacy notes'
                    )
                    """
                ),
                {"model_version": M1_MODEL_VERSION},
            )
    finally:
        await engine.dispose()


async def _restore_clean_head() -> None:
    await _drop_public_schema()
    _run_alembic("upgrade", "head")
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            await seed_database(connection)
    finally:
        await engine.dispose()


def test_fresh_database_reaches_current_head_with_score_timestamp_hypertable() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "head")

        async def verify() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.connect() as connection:
                    assert (
                        await current_migration_revision(connection)
                        == "20260729_0004"
                    )
                    dimension = await connection.scalar(
                        text(
                            """
                            SELECT column_name
                            FROM timescaledb_information.dimensions
                            WHERE hypertable_name = 'inference_results'
                            """
                        )
                    )
                    assert dimension == "score_ts"
            finally:
                await engine.dispose()

        asyncio.run(verify())
    finally:
        asyncio.run(_restore_clean_head())


def test_upgrade_preserves_m1_lineage_and_archives_legacy_devices() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "20260721_0001")
        asyncio.run(_insert_m1_lineage_fixture())
        _run_alembic("upgrade", "head")

        async def verify() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.connect() as connection:
                    devices = (
                        await connection.execute(
                            text(
                                """
                                SELECT device_id, is_active, archived_at
                                FROM devices ORDER BY device_id
                                """
                            )
                        )
                    ).mappings().all()
                    assert [row["device_id"] for row in devices] == [
                        "b02f3872-ruang-produksi",
                        "talpha-1",
                        "talpha-2",
                    ]
                    assert [row["is_active"] for row in devices] == [
                        True,
                        False,
                        False,
                    ]
                    assert devices[1]["archived_at"] is not None
                    assert devices[2]["archived_at"] is not None

                    inference = (
                        await connection.execute(
                            text(
                                """
                                SELECT window_end_ts, score_ts, model_version,
                                       score_provenance, replay_job_id
                                FROM inference_results
                                WHERE device_id = 'talpha-1'
                                """
                            )
                        )
                    ).mappings().one()
                    assert inference["score_ts"] == inference["window_end_ts"]
                    assert inference["model_version"] == M1_MODEL_VERSION
                    assert (
                        inference["score_provenance"]
                        == "deterministic_threshold_fixture"
                    )
                    assert inference["replay_job_id"] is None

                    lifecycle = (
                        await connection.execute(
                            text(
                                """
                                SELECT e.event_ts, e.event_at,
                                       e.time_domain,
                                       c.event_ts AS command_event_ts,
                                       c.accepted_at, c.time_domain AS command_domain
                                FROM alert_events e
                                JOIN alert_commands c
                                  ON c.accepted_event_id = e.event_id
                                WHERE e.event_id = 'm1-detected'
                                """
                            )
                        )
                    ).mappings().one()
                    assert lifecycle["event_ts"] == M1_EVENT_TIME
                    assert lifecycle["event_at"] is None
                    assert lifecycle["time_domain"] == "legacy_naive"
                    assert lifecycle["command_event_ts"] == M1_EVENT_TIME
                    assert lifecycle["accepted_at"] is None
                    assert lifecycle["command_domain"] == "legacy_naive"

                    alert = (
                        await connection.execute(
                            text(
                                """
                                SELECT detected_at, episode_start_ts,
                                       episode_end_ts, created_at,
                                       closure_reason
                                FROM alerts WHERE alert_id = 'm1-alert'
                                """
                            )
                        )
                    ).mappings().one()
                    assert alert["detected_at"] == M1_EVENT_TIME
                    assert alert["episode_start_ts"] == datetime(
                        2025, 12, 11, 23, 50, 35
                    )
                    assert alert["episode_end_ts"] == M1_EVENT_TIME
                    assert alert["created_at"] is None
                    assert alert["closure_reason"] == "legacy_m1_fixture"

                    evaluation = (
                        await connection.execute(
                            text(
                                """
                                SELECT version, report_source, is_public,
                                       metrics, notes
                                FROM model_evaluations
                                WHERE version = :version
                                """
                            ),
                            {"version": M1_MODEL_VERSION},
                        )
                    ).mappings().one()
                    assert evaluation["version"] == M1_MODEL_VERSION
                    assert evaluation["report_source"] == "legacy_m1_fixture"
                    assert evaluation["is_public"] is False
                    assert evaluation["metrics"] == {
                        "threshold": 0.02707822278141974
                    }
                    assert evaluation["notes"] == "legacy notes"

                    legacy_version = (
                        await connection.execute(
                            text(
                                """
                                SELECT runtime_kind, is_selectable, is_public
                                FROM model_versions
                                JOIN model_families USING (model_key)
                                WHERE version = :version
                                """
                            ),
                            {"version": M1_MODEL_VERSION},
                        )
                    ).mappings().one()
                    assert legacy_version == {
                        "runtime_kind": "legacy_fixture",
                        "is_selectable": False,
                        "is_public": False,
                    }
            finally:
                await engine.dispose()

        asyncio.run(verify())
    finally:
        asyncio.run(_restore_clean_head())
