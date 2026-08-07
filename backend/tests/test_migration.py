import asyncio
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import psycopg
from psycopg.rows import DictRow, dict_row
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine, current_migration_revision
from anomaly_backend.problems import NotFound
from anomaly_backend.seed import seed_database
from anomaly_backend.sql.preview import submit_replay_job
from anomaly_worker.service import claim_job


M1_MODEL_VERSION = "conv1d-arm-b-talpha-1-validation-fixture"
M1_EVENT_TIME = datetime(2025, 12, 12, 0, 2, 57)
LIVE_DEVICE_ID = "b02f3872-ruang-produksi"
PREVIEW_VERSIONS = (
    ("ewma", "preview-ewma-v1"),
    ("pca", "preview-pca-v1"),
    ("wsn-dense-ae", "preview-wsn-dense-ae-v1"),
    ("lstm-ae", "preview-lstm-ae-v1"),
    ("usad", "preview-usad-v1"),
    ("cfc-autoencoder", "preview-cfc-autoencoder-v1"),
    ("mtad-gat", "preview-mtad-gat-v1"),
)


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


async def _insert_live_contract_fixture() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    """
                    INSERT INTO devices (
                        device_id, display_name, source_device_uuid, time_zone,
                        telemetry_kind, is_active, archived_at
                    ) VALUES
                        ('legacy-preview-device', 'Legacy preview', NULL,
                         'Asia/Jakarta', 'historical_replay', FALSE, now())
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO corpora (
                        corpus_id, device_id, status, archive_sha256,
                        member_sha256, preprocessing_contract_version,
                        source_device_uuid, time_zone, interval_start, interval_end,
                        filter_config, started_at, completed_at, accepted_count,
                        ignored_index_count, rejection_counts
                    ) VALUES
                        ('contract-live-canonical', :live_device, 'published',
                         repeat('a', 64), NULL, 'preview-v1', NULL, 'Asia/Jakarta',
                         '2026-01-01 00:00:00', '2026-01-01 00:10:00',
                         '{}'::jsonb, now(), now(), 10, 0, '{}'::jsonb),
                        ('contract-live-alias', :live_device, 'published',
                         repeat('b', 64), NULL, 'preview-v1', NULL, 'Asia/Jakarta',
                         '2026-01-02 00:00:00', '2026-01-02 00:10:00',
                         '{}'::jsonb, now(), now(), 10, 0, '{}'::jsonb),
                        ('contract-malformed', :live_device, 'published',
                         repeat('c', 64), NULL, 'preview-v1', NULL, 'Asia/Jakarta',
                         '2026-01-03 00:00:00', '2026-01-03 00:10:00',
                         '{}'::jsonb, now(), now(), 10, 0, '{}'::jsonb),
                        ('contract-legacy', :live_device, 'published',
                         repeat('d', 64), NULL, 'preview-v1', NULL, 'Asia/Jakarta',
                         '2026-01-04 00:00:00', '2026-01-04 00:10:00',
                         '{}'::jsonb, now(), now(), 30, 0, '{}'::jsonb)
                    """
                ),
                {"live_device": LIVE_DEVICE_ID},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO published_corpora (device_id, corpus_id, published_at)
                    VALUES (:live_device, 'contract-live-canonical', now())
                    """
                ),
                {"live_device": LIVE_DEVICE_ID},
            )
            await connection.exec_driver_sql(
                """
                    INSERT INTO preprocessing_snapshots (
                        corpus_id, channels, window_size, stride,
                        segment_metadata, split_boundaries, split_counts, scaler
                    ) VALUES
                        ('contract-live-canonical',
                         '["temperature_c", "relative_humidity_pct"]'::jsonb,
                         30, 1,
                         '[{"segment_id":0,
                            "first_ts":"2026-01-01T00:00:00",
                            "last_ts":"2026-01-01T00:09:00",
                            "first_corpus_index":0,
                            "last_corpus_index":9,
                            "row_count":10}]'::jsonb,
                         '{"validation_start":"2026-01-01T00:06:00",
                           "test_start":"2026-01-01T00:08:00"}'::jsonb,
                         '{"train":6,"validation":2,"test":2}'::jsonb,
                         '{"channels":["temperature_c","relative_humidity_pct"],
                            "minimum":[20.25,40.5],"maximum":[30.75,70.125],
                            "fit_split":"train"}'::jsonb),
                        ('contract-live-alias', '["suhu", "rh"]'::jsonb,
                         30, 1,
                         '{"provenance":{"source":"alias","revision":2},
                           "source_identity":{"device":"b02f3872-ruang-produksi"},
                           "extra":["preserve",2]}'::jsonb,
                         '{"fit_split":"train","train":{"start":0,"end":89},
                           "validation":{"start":90,"end":109}}'::jsonb,
                         '{"train":90,"validation":20}'::jsonb,
                         '{"channels":["suhu","rh"],
                           "minimum":[21.25,41.5],"maximum":[31.75,71.125],
                           "fit_split":"train",
                           "provenance":{"source":"alias-scaler"}}'::jsonb),
                        ('contract-malformed',
                         '["temperature_c", "relative_humidity_pct"]'::jsonb,
                         30, 1, '{"provenance":{"source":"malformed"}}'::jsonb,
                         '{"train":{"start":0,"end":9}}'::jsonb,
                         '{"train":10}'::jsonb,
                         '{"channels":["temperature_c","relative_humidity_pct"],
                           "minimum":[20,40],"maximum":[30,70]}'::jsonb),
                        ('contract-legacy',
                         '["temperature_c", "relative_humidity_pct"]'::jsonb,
                         30, 1, '{"provenance":{"source":"legacy"}}'::jsonb,
                         '{"fit_split":"train"}'::jsonb,
                         '{"train":30}'::jsonb,
                         '{"channels":["temperature_c","relative_humidity_pct"],
                           "minimum":[20,40],"maximum":[30,70],
                           "fit_split":"train"}'::jsonb)
                """
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO model_families (model_key, display_name, is_public)
                    VALUES
                        ('contract-live', 'Contract live', TRUE),
                        ('contract-legacy', 'Contract legacy', TRUE)
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO model_versions (
                        version, model_key, runtime_kind, is_selectable, adapter_key,
                        schema_version, channels, window_size, stride, score_key,
                        score_semantics, threshold, threshold_policy,
                        temporal_semantics, source_commit, source_config,
                        manifest_sha256, created_at
                    ) VALUES
                        ('contract-ten-no-hashes', 'contract-live', 'preview_simulator',
                         TRUE, 'preview', 'b02f3872_preview_v1',
                         '["temperature_c", "relative_humidity_pct"]'::jsonb,
                         10, 1, 'mae', 'higher_is_anomalous', 0.5,
                         '{}'::jsonb, 'context_end', 'test', 'test',
                          repeat('e', 64), now()),
                        ('contract-legacy-v30', 'contract-legacy', 'preview_simulator',
                         TRUE, 'preview', 'b02f3872_preview_v1',
                         '["suhu1", "rh1"]'::jsonb, 30, 1, 'mae',
                         'higher_is_anomalous', 0.5, '{}'::jsonb, 'context_end',
                          'test', 'test', repeat('f', 64), now())
                    """
                )
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO model_activations (
                        activation_id, command_id, payload_hash, device_id,
                        prior_model_version, model_version, changed, activated_at, actor
                    ) VALUES
                        ('activation-contract-live', 'command-contract-live', 'live',
                         :live_device, NULL, 'contract-ten-no-hashes', TRUE, now(), 'test'),
                        ('activation-contract-legacy', 'command-contract-legacy',
                         'legacy', 'legacy-preview-device', NULL,
                         'contract-legacy-v30', TRUE, now(), 'test')
                    """
                ),
                {"live_device": LIVE_DEVICE_ID},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO active_model_selections (
                        device_id, activation_id, model_version
                    ) VALUES
                        (:live_device, 'activation-contract-live', 'contract-ten-no-hashes'),
                        ('legacy-preview-device', 'activation-contract-legacy',
                         'contract-legacy-v30')
                    """
                ),
                {"live_device": LIVE_DEVICE_ID},
            )
            for ordinal, status in enumerate(
                ("queued", "running", "succeeded", "failed")
            ):
                await connection.execute(
                    text(
                        """
                        INSERT INTO replay_jobs (
                            job_id, logical_job_hash, device_id, corpus_id,
                            archive_sha256, preprocessing_contract_version,
                            activation_id, model_version, score_provenance,
                            from_ts, to_ts, status, lease_owner, lease_expires_at,
                            heartbeat_at, attempt_count, max_attempts,
                            next_corpus_index, processed_count, result_count,
                            episode_count, submitted_at, started_at, completed_at,
                            error_code, error_detail
                        ) VALUES (
                            :job_id, :logical_hash, :live_device,
                            'contract-live-canonical', repeat('a', 64), 'preview-v1',
                            'activation-contract-legacy', 'contract-legacy-v30',
                            'simulated_preview',
                            :from_ts, :to_ts, :status,
                            CASE WHEN :status = 'running' THEN 'worker' END,
                            CASE WHEN :status = 'running' THEN now() + interval '1 minute' END,
                            CASE WHEN :status = 'running' THEN now() END,
                            CASE WHEN :status = 'running' THEN 1 ELSE 0 END,
                            3, 0, 0, 0, 0, now(),
                            CASE WHEN :status IN ('running', 'succeeded', 'failed') THEN now() END,
                            CASE WHEN :status IN ('succeeded', 'failed') THEN now() END,
                            NULL, NULL
                        )
                        """
                    ),
                    {
                        "job_id": f"contract-job-{status}",
                        "logical_hash": f"contract-{status}",
                        "live_device": LIVE_DEVICE_ID,
                        "from_ts": datetime(2026, 1, 1, 0, ordinal * 2),
                        "to_ts": datetime(2026, 1, 1, 0, ordinal * 2 + 1),
                        "status": status,
                    },
                )
    finally:
        await engine.dispose()


async def _insert_legacy_preview_seed_fixture() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.begin() as connection:
            for ordinal, (model_key, version) in enumerate(PREVIEW_VERSIONS, 1):
                await connection.execute(
                    text(
                        """
                        INSERT INTO model_families (
                            model_key, display_name, is_public
                        ) VALUES (:model_key, :display_name, TRUE)
                        """
                    ),
                    {"model_key": model_key, "display_name": model_key},
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO model_versions (
                            version, model_key, runtime_kind, is_selectable,
                            adapter_key, schema_version, channels, window_size,
                            stride, score_key, score_semantics, threshold,
                            threshold_policy, temporal_semantics, source_commit,
                            source_config, manifest_sha256, created_at
                        ) VALUES (
                            :version, :model_key, 'artifact', TRUE,
                            'legacy-preview-checkpoint', 'b02f3872_preview_v1',
                            '["suhu", "rh"]'::jsonb, 30, 1, 'mae',
                            'legacy checkpoint identity', 1.0,
                            '{"comparator":">"}'::jsonb, 'context_end',
                            'legacy-seed', 'legacy-seed-v1', :manifest_sha256,
                            '2026-07-24 00:00:00+00'
                        )
                        """
                    ),
                    {
                        "version": version,
                        "model_key": model_key,
                        "manifest_sha256": f"{ordinal:064x}",
                    },
                )
            await connection.execute(
                text(
                    """
                    INSERT INTO model_activations (
                        activation_id, command_id, payload_hash, device_id,
                        prior_model_version, model_version, changed,
                        activated_at, actor
                    ) VALUES (
                        'activation-preview-lstm-ae-v1',
                        'seed-preview-lstm-ae-v1', 'legacy-seed-payload',
                        :device_id, NULL, 'preview-lstm-ae-v1', TRUE,
                        '2026-07-24 00:00:00+00', 'legacy-seed'
                    )
                    """
                ),
                {"device_id": LIVE_DEVICE_ID},
            )
            await connection.execute(
                text(
                    """
                    INSERT INTO active_model_selections (
                        device_id, activation_id, model_version
                    ) VALUES (
                        :device_id, 'activation-preview-lstm-ae-v1',
                        'preview-lstm-ae-v1'
                    )
                    """
                ),
                {"device_id": LIVE_DEVICE_ID},
            )
    finally:
        await engine.dispose()


def test_fresh_database_reaches_live_telemetry_head() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "head")

        async def verify() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.connect() as connection:
                    assert (
                        await current_migration_revision(connection)
                    == "20260807_0016"
                    )
                    dimensions = (
                        text(
                            """
                            SELECT column_name
                            FROM timescaledb_information.dimensions
                            WHERE hypertable_name IN ('live_inference', 'live_telemetry')
                            ORDER BY hypertable_name
                            """
                        )
                    )
                    dimensions = (
                        await connection.execute(dimensions)
                    ).scalars().all()
                    assert dimensions == ["score_ts", "received_ts"]
                    tables = (
                        await connection.execute(
                            text(
                                """
                                SELECT table_name
                                FROM information_schema.tables
                                WHERE table_schema = 'public'
                                  AND table_name IN (
                                    'live_telemetry', 'live_inference',
                                    'live_inference_sources', 'live_model_pairs',
                                    'live_model_activation_requests',
                                    'live_model_selections', 'live_model_activations',
                                    'live_processing_boundaries', 'live_writer_leases',
                                    'live_cursors', 'live_health',
                                    'live_alert_episodes', 'live_alert_episode_points'
                                  )
                                ORDER BY table_name
                                """
                            )
                        )
                    ).scalars().all()
                    assert tables == [
                        "live_alert_episode_points",
                        "live_alert_episodes",
                        "live_cursors",
                        "live_health",
                        "live_inference",
                        "live_inference_sources",
                        "live_model_activation_requests",
                        "live_model_activations",
                        "live_model_pairs",
                        "live_model_selections",
                        "live_processing_boundaries",
                        "live_telemetry",
                        "live_writer_leases",
                    ]
                    pair_columns = set(
                        (
                            await connection.execute(
                                text(
                                    """
                                    SELECT column_name
                                    FROM information_schema.columns
                                    WHERE table_schema = 'public'
                                      AND table_name = 'live_model_pairs'
                                    """
                                )
                            )
                        ).scalars()
                    )
                    assert {
                        "model_manifest_sha256",
                        "checkpoint_sha256",
                        "scaler_manifest_sha256",
                        "scaler_sha256",
                    } <= pair_columns
                    assert "model_sha256" not in pair_columns
                    assert "contract_sha256" not in pair_columns
                    episode_columns = set(
                        (
                            await connection.execute(
                                text(
                                    """
                                    SELECT column_name
                                    FROM information_schema.columns
                                    WHERE table_schema = 'public'
                                      AND table_name = 'live_alert_episodes'
                                    """
                                )
                            )
                        ).scalars()
                    )
                    assert "close_reason" in episode_columns
                    indexes = (
                        await connection.execute(
                            text(
                                """
                                SELECT indexname
                                FROM pg_indexes
                                WHERE schemaname = 'public'
                                  AND indexname IN (
                                    'ix_live_telemetry_device_received_tail',
                                    'uq_live_inference_idempotency'
                                  )
                                ORDER BY indexname
                                """
                            )
                        )
                    ).scalars().all()
                    assert indexes == [
                        "ix_live_telemetry_device_received_tail",
                        "uq_live_inference_idempotency",
                    ]
                    constraint_names = set(
                        (
                            await connection.execute(
                                text(
                                    """
                                    SELECT conname
                                    FROM pg_constraint
                                    WHERE connamespace = 'public'::regnamespace
                                    """
                                )
                            )
                        ).scalars()
                    )
                    assert {
                        "uq_preprocessing_snapshots_live_identity",
                        "uq_model_versions_live_artifact_identity",
                        "ck_live_model_pairs_model_manifest_sha256",
                        "ck_live_model_pairs_checkpoint_sha256",
                        "ck_live_model_pairs_scaler_manifest_sha256",
                        "ck_live_model_pairs_scaler_sha256",
                        "fk_live_model_pairs_artifact_identity",
                        "fk_live_model_pairs_snapshot_contract",
                        "uq_live_model_pairs_lineage",
                        "uq_live_activation_request_lineage",
                        "fk_live_activation_request_lineage",
                        "uq_live_activation_lineage",
                        "uq_live_activation_event_lineage",
                        "fk_live_selection_activation_lineage",
                        "fk_live_telemetry_activation",
                        "uq_live_telemetry_device_anchor",
                        "fk_live_inference_activation_lineage",
                        "fk_live_inference_pair_snapshot",
                        "uq_live_inference_device_identity",
                        "fk_live_inference_source_inference",
                        "fk_live_inference_source_telemetry",
                        "uq_live_boundary_device_id",
                        "fk_live_boundary_telemetry_anchor",
                        "fk_live_cursor_telemetry_anchor",
                        "fk_live_cursor_boundary_device",
                        "fk_live_episode_activation_lineage",
                        "fk_live_episode_pair_snapshot",
                        "uq_live_episode_lineage",
                        "uq_live_episode_alert_link",
                        "fk_alerts_live_episode",
                        "fk_live_episode_point_episode_lineage",
                        "fk_live_episode_point_inference_lineage",
                        "ck_live_alert_episodes_close_reason",
                    } <= constraint_names
                    trigger_names = set(
                        (
                            await connection.execute(
                                text(
                                    """
                                    SELECT tgname
                                    FROM pg_trigger
                                    WHERE NOT tgisinternal
                                      AND tgrelid::regclass::text LIKE 'live_%'
                                    """
                                )
                            )
                        ).scalars()
                    )
                    assert {
                        "live_model_pairs_immutable",
                        "live_model_activation_requests_immutable",
                        "live_model_activations_immutable",
                        "live_processing_boundaries_immutable",
                        "live_inference_immutable",
                        "live_inference_sources_immutable",
                        "live_alert_episode_points_immutable",
                        "live_telemetry_state_guard",
                        "live_alert_episodes_state_guard",
                        "live_model_selections_state_guard",
                        "live_writer_leases_state_guard",
                        "live_cursors_state_guard",
                        "live_health_state_guard",
                    } <= trigger_names
                    index_definitions = {
                        row["indexname"]: row["indexdef"]
                        for row in (
                            await connection.execute(
                                text(
                                    """
                                    SELECT indexname, indexdef
                                    FROM pg_indexes
                                    WHERE schemaname = 'public'
                                      AND indexname IN (
                                        'ix_live_telemetry_device_received_tail',
                                        'uq_live_inference_idempotency'
                                      )
                                    """
                                )
                            )
                        ).mappings()
                    }
                    assert "(device_id, received_ts DESC, telemetry_id DESC)" in (
                        index_definitions["ix_live_telemetry_device_received_tail"]
                    )
                    assert (
                        "score_ts, device_id, model_pair_id, activation_id, "
                        "continuity_epoch, ordered_source_fingerprint"
                    ) in index_definitions["uq_live_inference_idempotency"]
            finally:
                await engine.dispose()

        asyncio.run(verify())
        try:
            _run_alembic("downgrade", "20260730_0006")
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("live telemetry downgrade must require a backup restore")

        async def verify_downgrade_did_not_mutate() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.connect() as connection:
                    assert (
                        await current_migration_revision(connection)
                    == "20260807_0016"
                    )
                    assert await connection.scalar(
                        text("SELECT to_regclass('public.live_telemetry')")
                    ) == "live_telemetry"
            finally:
                await engine.dispose()

        asyncio.run(verify_downgrade_did_not_mutate())
    finally:
        asyncio.run(_restore_clean_head())


def test_live_state_trigger_repair_is_forward_only() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "20260730_0007")

        async def reproduce_and_repair() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO live_writer_leases (
                                device_id, lease_owner, lease_expires_at_utc,
                                fencing_token
                            ) VALUES (
                                :device_id, 'migration-probe',
                                clock_timestamp() + interval '1 minute', 1
                            )
                            """
                        ),
                        {"device_id": LIVE_DEVICE_ID},
                    )
                async with engine.connect() as connection:
                    with pytest.raises(
                        DBAPIError,
                        match='record "new" has no field "activation_id"',
                    ):
                        async with connection.begin():
                            await connection.execute(
                                text(
                                    """
                                    UPDATE live_writer_leases
                                    SET lease_expires_at_utc =
                                        clock_timestamp() + interval '2 minutes'
                                    WHERE device_id = :device_id
                                    """
                                ),
                                {"device_id": LIVE_DEVICE_ID},
                            )
            finally:
                await engine.dispose()

            _run_alembic("upgrade", "head")
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.begin() as connection:
                    updated = await connection.execute(
                        text(
                            """
                            UPDATE live_writer_leases
                            SET lease_expires_at_utc =
                                clock_timestamp() + interval '3 minutes'
                            WHERE device_id = :device_id
                            """
                        ),
                        {"device_id": LIVE_DEVICE_ID},
                    )
                    assert updated.rowcount == 1
                    assert (
                        await current_migration_revision(connection)
                        == "20260807_0016"
                    )
            finally:
                await engine.dispose()

        asyncio.run(reproduce_and_repair())
        try:
            _run_alembic("downgrade", "20260730_0007")
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("live state trigger repair must be forward-only")

        async def verify_failed_downgrade_did_not_mutate() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.connect() as connection:
                    assert (
                        await current_migration_revision(connection)
                        == "20260807_0016"
                    )
            finally:
                await engine.dispose()

        asyncio.run(verify_failed_downgrade_did_not_mutate())
    finally:
        asyncio.run(_restore_clean_head())


def test_live_model_contract_downgrade_fails_before_mutation() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "20260730_0006")
        try:
            _run_alembic("downgrade", "20260730_0005")
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("model contract downgrade must require a backup restore")

        async def verify() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.connect() as connection:
                    assert (
                        await current_migration_revision(connection)
                        == "20260730_0006"
                    )
                    columns = set(
                        (
                            await connection.execute(
                                text(
                                    """
                                    SELECT column_name
                                    FROM information_schema.columns
                                    WHERE table_schema = 'public'
                                      AND table_name = 'model_versions'
                                    """
                                )
                            )
                        ).scalars()
                    )
                    assert {
                        "contract_status",
                        "model_manifest_sha256",
                        "checkpoint_sha256",
                        "scaler_manifest_sha256",
                        "scaler_sha256",
                    } <= columns
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
                                SELECT runtime_kind, is_selectable, is_public,
                                       channels, window_size, stride
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
                        "channels": ["suhu1", "rh1"],
                        "window_size": 30,
                        "stride": 1,
                    }

                    legacy_snapshot = (
                        await connection.execute(
                            text(
                                """
                                SELECT channels, window_size, stride,
                                       contract_status, segment_metadata,
                                       split_boundaries, split_counts, scaler
                                FROM preprocessing_snapshots
                                WHERE corpus_id = 'legacy-corpus-talpha-1'
                                """
                            )
                        )
                    ).mappings().one()
                    assert legacy_snapshot == {
                        "channels": [
                            "temperature_c",
                            "relative_humidity_pct",
                        ],
                        "window_size": 30,
                        "stride": 1,
                        "contract_status": "legacy_30",
                        "segment_metadata": {
                            "provenance": "legacy_m1_fixture"
                        },
                        "split_boundaries": {},
                        "split_counts": {},
                        "scaler": {},
                    }
            finally:
                await engine.dispose()

        asyncio.run(verify())
    finally:
        asyncio.run(_restore_clean_head())


def test_live_model_contract_rejects_active_replays_then_canonicalizes() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "20260730_0005")
        asyncio.run(_insert_live_contract_fixture())

        try:
            _run_alembic("upgrade", "20260730_0006")
        except subprocess.CalledProcessError:
            pass
        else:
            raise AssertionError("active replay jobs must block the contract cutover")

        async def terminalize_and_verify_precheck() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.begin() as connection:
                    precheck = (
                        await connection.execute(
                            text(
                                """
                                SELECT channels, window_size, stride,
                                       segment_metadata, split_boundaries,
                                       split_counts, scaler
                                FROM preprocessing_snapshots
                                WHERE corpus_id = 'contract-live-alias'
                                """
                            )
                        )
                    ).mappings().one()
                    assert precheck == {
                        "channels": ["suhu", "rh"],
                        "window_size": 30,
                        "stride": 1,
                        "segment_metadata": {
                            "provenance": {"source": "alias", "revision": 2},
                            "source_identity": {"device": LIVE_DEVICE_ID},
                            "extra": ["preserve", 2],
                        },
                        "split_boundaries": {
                            "fit_split": "train",
                            "train": {"start": 0, "end": 89},
                            "validation": {"start": 90, "end": 109},
                        },
                        "split_counts": {"train": 90, "validation": 20},
                        "scaler": {
                            "channels": ["suhu", "rh"],
                            "minimum": [21.25, 41.5],
                            "maximum": [31.75, 71.125],
                            "fit_split": "train",
                            "provenance": {"source": "alias-scaler"},
                        },
                    }
                    await connection.execute(
                        text(
                            """
                            UPDATE replay_jobs
                            SET status = 'failed', completed_at = now(),
                                lease_owner = NULL, lease_expires_at = NULL,
                                heartbeat_at = NULL
                            WHERE status IN ('queued', 'running')
                            """
                        )
                    )
            finally:
                await engine.dispose()

        asyncio.run(terminalize_and_verify_precheck())
        _run_alembic("upgrade", "20260730_0006")

        async def verify() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.connect() as connection:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO corpora (
                                corpus_id, device_id, status, archive_sha256,
                                preprocessing_contract_version, time_zone,
                                interval_start, interval_end, filter_config,
                                started_at, completed_at, accepted_count,
                                ignored_index_count, rejection_counts
                            ) VALUES (
                                'runtime-importer-shape', :device_id, 'published',
                                repeat('9', 64), 'b02f3872_ruang_produksi_v2',
                                'Asia/Jakarta', '2026-02-01 00:00:00',
                                '2026-02-01 00:09:00', '{}'::jsonb, now(), now(),
                                10, 0, '{}'::jsonb
                            )
                            """
                        ),
                        {"device_id": LIVE_DEVICE_ID},
                    )
                    await connection.exec_driver_sql(
                            """
                            INSERT INTO preprocessing_snapshots (
                                corpus_id, channels, window_size, stride,
                                segment_metadata, split_boundaries, split_counts,
                                scaler
                            ) VALUES (
                                'runtime-importer-shape',
                                '["temperature_c", "relative_humidity_pct"]'::jsonb,
                                10, 1,
                                '[{"segment_id":0,
                                   "first_ts":"2026-02-01T00:00:00",
                                   "last_ts":"2026-02-01T00:09:00",
                                   "first_corpus_index":0,
                                   "last_corpus_index":9,
                                   "row_count":10}]'::jsonb,
                                '{"validation_start":"2026-02-01T00:06:00",
                                  "test_start":"2026-02-01T00:08:00"}'::jsonb,
                                '{"train":6,"validation":2,"test":2}'::jsonb,
                                '{"channels":["temperature_c",
                                              "relative_humidity_pct"],
                                  "minimum":[20,40],"maximum":[30,70],
                                  "fit_split":"train"}'::jsonb
                            )
                            """
                    )
                    assert await connection.scalar(
                        text(
                            """
                            SELECT contract_status
                            FROM preprocessing_snapshots
                            WHERE corpus_id = 'runtime-importer-shape'
                            """
                        )
                    ) == "live_10"
                    snapshots = (
                        await connection.execute(
                            text(
                                """
                                SELECT corpus_id, channels, window_size, stride,
                                       contract_status, scaler, segment_metadata,
                                       split_boundaries, split_counts
                                FROM preprocessing_snapshots
                                WHERE corpus_id LIKE 'contract-%'
                                ORDER BY corpus_id
                                """
                            )
                        )
                    ).mappings().all()
                    assert snapshots == [
                        {
                            "corpus_id": "contract-legacy",
                            "channels": [
                                "temperature_c",
                                "relative_humidity_pct",
                            ],
                            "window_size": 30,
                            "stride": 1,
                            "contract_status": "legacy_30",
                            "scaler": {
                                "channels": [
                                    "temperature_c",
                                    "relative_humidity_pct",
                                ],
                                "minimum": [20, 40],
                                "maximum": [30, 70],
                                "fit_split": "train",
                            },
                            "segment_metadata": {
                                "provenance": {"source": "legacy"}
                            },
                            "split_boundaries": {"fit_split": "train"},
                            "split_counts": {"train": 30},
                        },
                        {
                            "corpus_id": "contract-live-alias",
                            "channels": [
                                "temperature_c",
                                "relative_humidity_pct",
                            ],
                            "window_size": 30,
                            "stride": 1,
                            "contract_status": "legacy_30",
                            "scaler": {
                                "channels": [
                                    "temperature_c",
                                    "relative_humidity_pct",
                                ],
                                "minimum": [21.25, 41.5],
                                "maximum": [31.75, 71.125],
                                "fit_split": "train",
                                "provenance": {"source": "alias-scaler"},
                            },
                            "segment_metadata": {
                                "provenance": {"source": "alias", "revision": 2},
                                "source_identity": {"device": LIVE_DEVICE_ID},
                                "extra": ["preserve", 2],
                            },
                            "split_boundaries": {
                                "fit_split": "train",
                                "train": {"start": 0, "end": 89},
                                "validation": {"start": 90, "end": 109},
                            },
                            "split_counts": {"train": 90, "validation": 20},
                        },
                        {
                            "corpus_id": "contract-live-canonical",
                            "channels": [
                                "temperature_c",
                                "relative_humidity_pct",
                            ],
                            "window_size": 30,
                            "stride": 1,
                            "contract_status": "legacy_30",
                            "scaler": {
                                "channels": [
                                    "temperature_c",
                                    "relative_humidity_pct",
                                ],
                                "minimum": [20.25, 40.5],
                                "maximum": [30.75, 70.125],
                                "fit_split": "train",
                            },
                            "segment_metadata": [
                                {
                                    "segment_id": 0,
                                    "first_ts": "2026-01-01T00:00:00",
                                    "last_ts": "2026-01-01T00:09:00",
                                    "first_corpus_index": 0,
                                    "last_corpus_index": 9,
                                    "row_count": 10,
                                }
                            ],
                            "split_boundaries": {
                                "validation_start": "2026-01-01T00:06:00",
                                "test_start": "2026-01-01T00:08:00",
                            },
                            "split_counts": {
                                "train": 6,
                                "validation": 2,
                                "test": 2,
                            },
                        },
                        {
                            "corpus_id": "contract-malformed",
                            "channels": [
                                "temperature_c",
                                "relative_humidity_pct",
                            ],
                            "window_size": 30,
                            "stride": 1,
                            "contract_status": "legacy_30",
                            "scaler": {
                                "channels": [
                                    "temperature_c",
                                    "relative_humidity_pct",
                                ],
                                "minimum": [20, 40],
                                "maximum": [30, 70],
                            },
                            "segment_metadata": {
                                "provenance": {"source": "malformed"}
                            },
                            "split_boundaries": {
                                "train": {"start": 0, "end": 9}
                            },
                            "split_counts": {"train": 10},
                        },
                    ]
                    models = (
                        await connection.execute(
                            text(
                                """
                                SELECT version, channels, window_size, stride,
                                       is_selectable, contract_status,
                                       manifest_sha256, model_manifest_sha256,
                                       checkpoint_sha256, scaler_manifest_sha256,
                                       scaler_sha256
                                FROM model_versions
                                WHERE version LIKE 'contract-%'
                                ORDER BY version
                                """
                            )
                        )
                    ).mappings().all()
                    assert models == [
                        {
                            "version": "contract-legacy-v30",
                            "channels": ["suhu1", "rh1"],
                            "window_size": 30,
                            "stride": 1,
                            "is_selectable": False,
                            "contract_status": "legacy_30",
                            "manifest_sha256": "f" * 64,
                            "model_manifest_sha256": None,
                            "checkpoint_sha256": None,
                            "scaler_manifest_sha256": None,
                            "scaler_sha256": None,
                        },
                        {
                            "version": "contract-ten-no-hashes",
                            "channels": [
                                "temperature_c",
                                "relative_humidity_pct",
                            ],
                            "window_size": 10,
                            "stride": 1,
                            "is_selectable": False,
                            "contract_status": "legacy_30",
                            "manifest_sha256": "e" * 64,
                            "model_manifest_sha256": None,
                            "checkpoint_sha256": None,
                            "scaler_manifest_sha256": None,
                            "scaler_sha256": None,
                        },
                    ]
                    selections = (
                        await connection.execute(
                            text(
                                """
                                SELECT device_id, model_version
                                FROM active_model_selections
                                WHERE device_id IN (:live_device, 'legacy-preview-device')
                                ORDER BY device_id
                                """
                            ),
                            {"live_device": LIVE_DEVICE_ID},
                        )
                    ).mappings().all()
                    assert selections == []
                    jobs = (
                        await connection.execute(
                            text(
                                """
                                SELECT job_id, model_version, status
                                FROM replay_jobs
                                WHERE job_id LIKE 'contract-job-%'
                                ORDER BY job_id
                                """
                            )
                        )
                    ).mappings().all()
                    assert len(jobs) == 4
                    assert {row["status"] for row in jobs} == {"failed", "succeeded"}
                    assert {row["model_version"] for row in jobs} == {
                        "contract-legacy-v30"
                    }
            finally:
                await engine.dispose()

        asyncio.run(verify())
    finally:
        asyncio.run(_restore_clean_head())


def test_real_contract_cutover_blocks_replay_submission_and_worker_claim() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "20260730_0005")
        asyncio.run(_insert_live_contract_fixture())

        async def exercise() -> None:
            settings = Settings.from_environ()
            blocker = psycopg.Connection[DictRow].connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                dbname=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                row_factory=dict_row,
                autocommit=False,
            )
            observer = psycopg.Connection[DictRow].connect(
                host=settings.postgres_host,
                port=settings.postgres_port,
                dbname=settings.postgres_db,
                user=settings.postgres_user,
                password=settings.postgres_password,
                row_factory=dict_row,
                autocommit=True,
            )
            engine = create_database_engine(settings)
            migration: subprocess.Popen[str] | None = None

            async def submit() -> str:
                async with engine.connect() as connection:
                    try:
                        await submit_replay_job(
                            connection,
                            command_id="cutover-lock-submission",
                            device_id=LIVE_DEVICE_ID,
                            from_ts=datetime(2026, 1, 1),
                            to_ts=datetime(2026, 1, 1, 0, 1),
                        )
                    except NotFound:
                        return "not_found"
                return "submitted"

            def claim() -> object:
                connection = psycopg.Connection[DictRow].connect(
                    host=settings.postgres_host,
                    port=settings.postgres_port,
                    dbname=settings.postgres_db,
                    user=settings.postgres_user,
                    password=settings.postgres_password,
                    row_factory=dict_row,
                    autocommit=True,
                )
                with connection:
                    return claim_job(connection, "cutover-lock-worker")

            try:
                blocker.execute(
                    """
                    UPDATE replay_jobs
                    SET status = 'failed', completed_at = now(),
                        lease_owner = NULL, lease_expires_at = NULL,
                        heartbeat_at = NULL
                    WHERE status IN ('queued', 'running')
                    """
                )
                blocker.commit()
                blocker.execute(
                    "LOCK TABLE preprocessing_snapshots IN ACCESS SHARE MODE"
                )
                migration = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "alembic",
                        "-c",
                        "alembic.ini",
                        "upgrade",
                        "20260730_0006",
                    ],
                    cwd=Path(__file__).parents[1],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(100):
                    owns_cutover_lock = observer.execute(
                        """
                        SELECT EXISTS (
                            SELECT 1 FROM pg_locks
                            WHERE locktype = 'advisory'
                              AND granted
                              AND objid = 731113
                        ) AS owns_lock
                        """
                    ).fetchone()
                    if owns_cutover_lock and owns_cutover_lock["owns_lock"]:
                        break
                    await asyncio.sleep(0.05)
                else:
                    raise AssertionError(
                        "migration did not acquire the exclusive cutover lock"
                    )

                submission = asyncio.create_task(submit())
                worker = asyncio.create_task(asyncio.to_thread(claim))
                await asyncio.sleep(0.1)
                assert not submission.done()
                assert not worker.done()
                blocker.commit()
                stdout, stderr = await asyncio.to_thread(
                    migration.communicate, timeout=30
                )
                assert migration.returncode == 0, stdout + stderr
                assert await submission == "not_found"
                assert await worker is None
            finally:
                blocker.rollback()
                blocker.close()
                observer.close()
                if migration is not None and migration.poll() is None:
                    migration.terminate()
                    migration.wait(timeout=5)
                await engine.dispose()

        asyncio.run(exercise())
    finally:
        asyncio.run(_restore_clean_head())


def test_populated_0005_seed_keeps_only_unselectable_legacy_identities() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "20260730_0005")
        asyncio.run(_insert_legacy_preview_seed_fixture())
        _run_alembic("upgrade", "head")

        async def reseed_and_verify() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO active_model_selections (
                                device_id, activation_id, model_version
                            ) VALUES (
                                :device_id, 'activation-preview-lstm-ae-v1',
                                'preview-lstm-ae-v1'
                            )
                            """
                        ),
                        {"device_id": LIVE_DEVICE_ID},
                    )
                async with engine.connect() as connection:
                    await seed_database(connection)
                    rows = (
                        await connection.execute(
                            text(
                                """
                                SELECT version, channels, window_size, stride,
                                       contract_status, is_selectable,
                                       manifest_sha256, model_manifest_sha256,
                                       checkpoint_sha256, scaler_manifest_sha256,
                                       scaler_sha256
                                FROM model_versions
                                WHERE version LIKE 'preview-%-v1%'
                                ORDER BY version
                                """
                            )
                        )
                    ).mappings().all()
                    assert len(rows) == 7
                    rows_by_version = {row["version"]: row for row in rows}
                    for ordinal, (_, version) in enumerate(PREVIEW_VERSIONS, 1):
                        legacy = rows_by_version[version]
                        assert legacy["channels"] == ["suhu", "rh"]
                        assert legacy["window_size"] == 30
                        assert legacy["stride"] == 1
                        assert legacy["contract_status"] == "legacy_30"
                        assert legacy["is_selectable"] is False
                        assert legacy["manifest_sha256"] == f"{ordinal:064x}"
                        assert legacy["model_manifest_sha256"] is None
                        assert legacy["checkpoint_sha256"] is None
                        assert legacy["scaler_manifest_sha256"] is None
                        assert legacy["scaler_sha256"] is None

                    selection = (
                        await connection.execute(
                            text(
                                """
                                SELECT selection.model_version,
                                       activation.model_version AS activation_model_version
                                FROM active_model_selections AS selection
                                JOIN model_activations AS activation
                                  ON activation.activation_id = selection.activation_id
                                WHERE selection.device_id = :device_id
                                """
                            ),
                            {"device_id": LIVE_DEVICE_ID},
                        )
                    ).mappings().one_or_none()
                    assert selection is None
                    activations = (
                        await connection.execute(
                            text(
                                """
                                SELECT activation_id, command_id, model_version
                                FROM model_activations
                                WHERE activation_id LIKE 'activation-preview-lstm-ae-v1%'
                                ORDER BY activation_id
                                """
                            )
                        )
                    ).mappings().all()
                    assert activations == [
                        {
                            "activation_id": "activation-preview-lstm-ae-v1",
                            "command_id": "seed-preview-lstm-ae-v1",
                            "model_version": "preview-lstm-ae-v1",
                        },
                    ]
            finally:
                await engine.dispose()

        asyncio.run(reseed_and_verify())
    finally:
        asyncio.run(_restore_clean_head())


def test_live_lineage_foreign_keys_and_immutability_reject_invalid_writes() -> None:
    try:
        asyncio.run(_drop_public_schema())
        _run_alembic("upgrade", "head")

        async def verify() -> None:
            engine = create_database_engine(Settings.from_environ())
            try:
                async with engine.begin() as connection:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO corpora (
                                corpus_id, device_id, status, archive_sha256,
                                preprocessing_contract_version, filter_config,
                                started_at, completed_at, accepted_count,
                                ignored_index_count, rejection_counts
                            ) VALUES (
                                'lineage-snapshot', :device_id, 'published',
                                repeat('1', 64), 'live-v1', '{}'::jsonb,
                                now(), now(), 10, 0, '{}'::jsonb
                            )
                            """
                        ),
                        {"device_id": LIVE_DEVICE_ID},
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO preprocessing_snapshots (
                                corpus_id, channels, window_size, stride,
                                contract_status, segment_metadata,
                                split_boundaries, split_counts, scaler
                            ) VALUES (
                                'lineage-snapshot',
                                '["temperature_c", "relative_humidity_pct"]'::jsonb,
                                10, 1, 'live_10', '[]'::jsonb, '{}'::jsonb,
                                '{}'::jsonb, '{}'::jsonb
                            )
                            """
                        )
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO model_families (
                                model_key, display_name, is_public
                            ) VALUES ('lineage-model', 'Lineage model', FALSE)
                            """
                        )
                    )
                    await connection.execute(
                        text(
                            """
                            INSERT INTO model_versions (
                                version, model_key, runtime_kind, is_selectable,
                                adapter_key, schema_version, channels, window_size,
                                stride, contract_status, score_key, score_semantics,
                                threshold, threshold_policy, temporal_semantics,
                                model_manifest_sha256, checkpoint_sha256,
                                scaler_manifest_sha256, scaler_sha256, created_at
                            ) VALUES (
                                'lineage-model-v1', 'lineage-model', 'artifact', TRUE,
                                'lineage', 'live-v1',
                                '["temperature_c", "relative_humidity_pct"]'::jsonb,
                                10, 1, 'live_10', 'score', 'higher', 1.0,
                                '{}'::jsonb, 'context_end', repeat('a', 64),
                                repeat('b', 64), repeat('c', 64), repeat('d', 64),
                                now()
                            )
                            """
                        )
                    )

                    with pytest.raises(
                        IntegrityError,
                        match="fk_live_model_pairs_snapshot_contract",
                    ):
                        async with connection.begin_nested():
                            await connection.execute(
                                text(
                                    """
                                    INSERT INTO live_model_pairs (
                                        model_version, checkpoint_identity,
                                        scaler_snapshot_corpus_id,
                                        model_manifest_sha256, checkpoint_sha256,
                                        scaler_manifest_sha256, scaler_sha256,
                                        threshold, contract_status
                                    ) VALUES (
                                        'lineage-model-v1', 'missing-snapshot',
                                        'missing-snapshot', repeat('a', 64),
                                        repeat('b', 64), repeat('c', 64),
                                        repeat('d', 64), 1.0, 'live_10'
                                    )
                                    """
                                )
                            )

                    pair_ids: list[object] = []
                    for checkpoint_identity in ("checkpoint-a", "checkpoint-b"):
                        pair_ids.append(
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
                                        'lineage-model-v1', :checkpoint_identity,
                                        'lineage-snapshot', repeat('a', 64),
                                        repeat('b', 64), repeat('c', 64),
                                        repeat('d', 64), 1.0, 'live_10'
                                    ) RETURNING model_pair_id
                                    """
                                ),
                                {"checkpoint_identity": checkpoint_identity},
                            )
                        )
                    request_id = await connection.scalar(
                        text(
                            """
                            INSERT INTO live_model_activation_requests (
                                device_id, model_pair_id, request_hash, requested_by
                            ) VALUES (:device_id, :model_pair_id, 'lineage-request', 'test')
                            RETURNING request_id
                            """
                        ),
                        {
                            "device_id": LIVE_DEVICE_ID,
                            "model_pair_id": pair_ids[0],
                        },
                    )
                    with pytest.raises(
                        IntegrityError,
                        match="fk_live_activation_request_lineage",
                    ):
                        async with connection.begin_nested():
                            await connection.execute(
                                text(
                                    """
                                    INSERT INTO live_model_activations (
                                        device_id, request_id, model_pair_id,
                                        fencing_token
                                    ) VALUES (
                                        :device_id, :request_id, :model_pair_id, 1
                                    )
                                    """
                                ),
                                {
                                    "device_id": LIVE_DEVICE_ID,
                                    "request_id": request_id,
                                    "model_pair_id": pair_ids[1],
                                },
                            )
                    with pytest.raises(DBAPIError, match="append-only"):
                        async with connection.begin_nested():
                            await connection.execute(
                                text(
                                    """
                                    UPDATE live_model_pairs
                                    SET threshold = 2.0
                                    WHERE model_pair_id = :model_pair_id
                                    """
                                ),
                                {"model_pair_id": pair_ids[0]},
                            )
            finally:
                await engine.dispose()

        asyncio.run(verify())
    finally:
        asyncio.run(_restore_clean_head())
