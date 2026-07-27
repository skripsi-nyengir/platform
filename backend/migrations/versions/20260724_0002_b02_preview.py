from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260724_0002"
down_revision: str | None = "20260721_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FINITE_SCORE = (
    "score > '-Infinity'::double precision "
    "AND score < 'Infinity'::double precision"
)
FINITE_THRESHOLD = (
    "threshold > '-Infinity'::double precision "
    "AND threshold < 'Infinity'::double precision"
)
LEGACY_CORPUS_SHA = (
    "56c43dfd7aeb4f79e533a67e373174a07c45c2a4b1ba3df14352309e6670f2b1"
)
MIGRATION_INSTANT = "2026-07-24T00:00:00+00:00"


def _create_catalog_tables() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "devices",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("source_device_uuid", sa.Text(), nullable=True),
        sa.Column("time_zone", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(is_active AND archived_at IS NULL) OR "
            "(NOT is_active AND archived_at IS NOT NULL)",
            name="ck_devices_archive_state",
        ),
        sa.PrimaryKeyConstraint("device_id"),
    )
    op.create_index(
        "uq_devices_one_public_active",
        "devices",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    op.create_table(
        "corpora",
        sa.Column("corpus_id", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("archive_sha256", sa.Text(), nullable=False),
        sa.Column("member_sha256", sa.Text(), nullable=True),
        sa.Column("preprocessing_contract_version", sa.Text(), nullable=False),
        sa.Column("source_device_uuid", sa.Text(), nullable=True),
        sa.Column("time_zone", sa.Text(), nullable=True),
        sa.Column("interval_start", sa.DateTime(timezone=False), nullable=True),
        sa.Column("interval_end", sa.DateTime(timezone=False), nullable=True),
        sa.Column("filter_config", postgresql.JSONB(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_count", sa.BigInteger(), nullable=False),
        sa.Column("ignored_index_count", sa.BigInteger(), nullable=False),
        sa.Column("rejection_counts", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "status IN ('staging', 'published', 'failed')",
            name="ck_corpora_status",
        ),
        sa.CheckConstraint(
            "accepted_count >= 0 AND ignored_index_count >= 0",
            name="ck_corpora_counts",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.PrimaryKeyConstraint("corpus_id"),
        sa.UniqueConstraint(
            "device_id",
            "archive_sha256",
            "preprocessing_contract_version",
            name="uq_corpora_identity",
        ),
    )
    op.create_table(
        "published_corpora",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("corpus_id", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["corpus_id"], ["corpora.corpus_id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint("corpus_id", name="uq_published_corpora_corpus"),
    )
    op.create_table(
        "preprocessing_snapshots",
        sa.Column("corpus_id", sa.Text(), nullable=False),
        sa.Column("channels", postgresql.JSONB(), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("stride", sa.Integer(), nullable=False),
        sa.Column("segment_metadata", postgresql.JSONB(), nullable=False),
        sa.Column("split_boundaries", postgresql.JSONB(), nullable=False),
        sa.Column("split_counts", postgresql.JSONB(), nullable=False),
        sa.Column("scaler", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "window_size = 30 AND stride = 1",
            name="ck_preprocessing_window_stride",
        ),
        sa.ForeignKeyConstraint(["corpus_id"], ["corpora.corpus_id"]),
        sa.PrimaryKeyConstraint("corpus_id"),
    )

    op.create_table(
        "model_families",
        sa.Column("model_key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("model_key"),
    )
    op.create_table(
        "model_versions",
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("model_key", sa.Text(), nullable=False),
        sa.Column("runtime_kind", sa.Text(), nullable=False),
        sa.Column("is_selectable", sa.Boolean(), nullable=False),
        sa.Column("adapter_key", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("channels", postgresql.JSONB(), nullable=False),
        sa.Column("window_size", sa.Integer(), nullable=False),
        sa.Column("stride", sa.Integer(), nullable=False),
        sa.Column("score_key", sa.Text(), nullable=False),
        sa.Column("score_semantics", sa.Text(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("threshold_policy", postgresql.JSONB(), nullable=False),
        sa.Column("temporal_semantics", sa.Text(), nullable=False),
        sa.Column("source_commit", sa.Text(), nullable=True),
        sa.Column("source_config", sa.Text(), nullable=True),
        sa.Column("manifest_sha256", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "runtime_kind IN ('legacy_fixture', 'preview_simulator', 'artifact')",
            name="ck_model_versions_runtime_kind",
        ),
        sa.CheckConstraint(
            "temporal_semantics IN ('context_end', 'next_target')",
            name="ck_model_versions_temporal_semantics",
        ),
        sa.CheckConstraint(
            "window_size > 0 AND stride > 0",
            name="ck_model_versions_window_stride",
        ),
        sa.CheckConstraint(
            FINITE_THRESHOLD,
            name="ck_model_versions_threshold_finite",
        ),
        sa.ForeignKeyConstraint(["model_key"], ["model_families.model_key"]),
        sa.PrimaryKeyConstraint("version"),
    )
    op.create_table(
        "model_activations",
        sa.Column("activation_id", sa.Text(), nullable=False),
        sa.Column("command_id", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("prior_model_version", sa.Text(), nullable=True),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("changed", sa.Boolean(), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["prior_model_version"], ["model_versions.version"]
        ),
        sa.ForeignKeyConstraint(["model_version"], ["model_versions.version"]),
        sa.PrimaryKeyConstraint("activation_id"),
        sa.UniqueConstraint("command_id", name="uq_model_activations_command"),
    )
    op.create_table(
        "active_model_selections",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("activation_id", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(
            ["activation_id"], ["model_activations.activation_id"]
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(["model_version"], ["model_versions.version"]),
        sa.PrimaryKeyConstraint("device_id"),
        sa.UniqueConstraint(
            "activation_id", name="uq_active_model_selections_activation"
        ),
    )


def _seed_legacy_catalog() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO devices (
                device_id, display_name, source_device_uuid, time_zone,
                is_active, archived_at
            ) VALUES
                (
                    'talpha-1', 'TALPHA 1 (arsip M1)', NULL, NULL,
                    FALSE, CAST(:migration_instant AS timestamptz)
                ),
                (
                    'talpha-2', 'TALPHA 2 (arsip M1)', NULL, NULL,
                    FALSE, CAST(:migration_instant AS timestamptz)
                ),
                (
                    'b02f3872-ruang-produksi', 'TALPHA Ruang Produksi',
                    'b02f3872-39a2-4b6f-a4ec-045a287fde4b',
                    'Asia/Jakarta', TRUE, NULL
                )
            """
        ).bindparams(migration_instant=MIGRATION_INSTANT)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO corpora (
                corpus_id, device_id, status, archive_sha256, member_sha256,
                preprocessing_contract_version, source_device_uuid, time_zone,
                interval_start, interval_end, filter_config, started_at,
                completed_at, accepted_count, ignored_index_count,
                rejection_counts
            )
            SELECT
                'legacy-corpus-' || device_id,
                device_id,
                'published',
                :legacy_sha,
                :legacy_sha,
                'legacy_m1_fixture',
                NULL,
                NULL,
                min(ts),
                max(ts) + interval '1 second',
                '{"provenance":"legacy_m1_fixture"}'::jsonb,
                CAST(:migration_instant AS timestamptz),
                CAST(:migration_instant AS timestamptz),
                count(*),
                0,
                '{}'::jsonb
            FROM telemetry
            WHERE device_id IN ('talpha-1', 'talpha-2')
            GROUP BY device_id
            """
        ).bindparams(
            legacy_sha=LEGACY_CORPUS_SHA,
            migration_instant=MIGRATION_INSTANT,
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO corpora (
                corpus_id, device_id, status, archive_sha256, member_sha256,
                preprocessing_contract_version, source_device_uuid, time_zone,
                interval_start, interval_end, filter_config, started_at,
                completed_at, accepted_count, ignored_index_count,
                rejection_counts
            )
            SELECT
                'legacy-corpus-' || device_id,
                device_id,
                'published',
                :legacy_sha,
                :legacy_sha,
                'legacy_m1_fixture',
                NULL,
                NULL,
                NULL,
                NULL,
                '{"provenance":"legacy_m1_fixture"}'::jsonb,
                CAST(:migration_instant AS timestamptz),
                CAST(:migration_instant AS timestamptz),
                0,
                0,
                '{}'::jsonb
            FROM (VALUES ('talpha-1'), ('talpha-2')) AS legacy(device_id)
            ON CONFLICT (corpus_id) DO NOTHING
            """
        ).bindparams(
            legacy_sha=LEGACY_CORPUS_SHA,
            migration_instant=MIGRATION_INSTANT,
        )
    )
    op.execute(
        """
        INSERT INTO preprocessing_snapshots (
            corpus_id, channels, window_size, stride, segment_metadata,
            split_boundaries, split_counts, scaler
        )
        SELECT
            corpus_id,
            '["temperature_c","relative_humidity_pct"]'::jsonb,
            30,
            1,
            '{"provenance":"legacy_m1_fixture"}'::jsonb,
            '{}'::jsonb,
            '{}'::jsonb,
            '{}'::jsonb
        FROM corpora
        WHERE preprocessing_contract_version = 'legacy_m1_fixture'
        ON CONFLICT (corpus_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO model_families (model_key, display_name, is_public)
        VALUES ('legacy-threshold-fixture', 'Legacy threshold fixture', FALSE)
        """
    )
    op.execute(
        sa.text(
            """
            INSERT INTO model_versions (
                version, model_key, runtime_kind, is_selectable, adapter_key,
                schema_version, channels, window_size, stride, score_key,
                score_semantics, threshold, threshold_policy,
                temporal_semantics, source_commit, source_config,
                manifest_sha256, created_at
            ) VALUES
                (
                    'conv1d-arm-b-talpha-1-validation-fixture',
                    'legacy-threshold-fixture', 'legacy_fixture', FALSE,
                    'legacy_fixture', 'legacy_m1', '["suhu1","rh1"]'::jsonb,
                    30, 1, 'global_mse', 'legacy validation fixture',
                    0.02707822278141974, '{"comparator":">"}'::jsonb,
                    'context_end', NULL, NULL, NULL,
                    CAST(:migration_instant AS timestamptz)
                ),
                (
                    'conv1d-arm-b-talpha-2-validation-fixture',
                    'legacy-threshold-fixture', 'legacy_fixture', FALSE,
                    'legacy_fixture', 'legacy_m1', '["suhu2","rh2"]'::jsonb,
                    30, 1, 'global_mse', 'legacy validation fixture',
                    0.031537856459617604, '{"comparator":">"}'::jsonb,
                    'context_end', NULL, NULL, NULL,
                    CAST(:migration_instant AS timestamptz)
                )
            """
        ).bindparams(migration_instant=MIGRATION_INSTANT)
    )


def _upgrade_telemetry() -> None:
    op.drop_constraint(
        "ck_telemetry_device_id", "telemetry", type_="check"
    )
    op.add_column("telemetry", sa.Column("corpus_id", sa.Text(), nullable=True))
    op.add_column(
        "telemetry", sa.Column("corpus_index", sa.BigInteger(), nullable=True)
    )
    op.add_column(
        "telemetry", sa.Column("segment_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "telemetry", sa.Column("dataset_split", sa.Text(), nullable=True)
    )
    op.execute(
        """
        UPDATE telemetry
        SET
            corpus_id = 'legacy-corpus-' || device_id,
            corpus_index = source_index,
            segment_id = CASE
                WHEN source_index < 36032 THEN 0
                WHEN source_index < 65146 THEN 1
                ELSE 2
            END,
            dataset_split = 'legacy'
        """
    )
    for column in ("corpus_id", "corpus_index", "segment_id", "dataset_split"):
        op.alter_column("telemetry", column, nullable=False)
    op.create_foreign_key(
        "fk_telemetry_device",
        "telemetry",
        "devices",
        ["device_id"],
        ["device_id"],
    )
    op.create_foreign_key(
        "fk_telemetry_corpus",
        "telemetry",
        "corpora",
        ["corpus_id"],
        ["corpus_id"],
    )
    op.create_check_constraint(
        "ck_telemetry_corpus_index",
        "telemetry",
        "corpus_index >= 0 AND segment_id >= 0",
    )
    op.create_check_constraint(
        "ck_telemetry_dataset_split",
        "telemetry",
        "dataset_split IN ('legacy', 'train', 'validation', 'test')",
    )
    op.create_index(
        "ix_telemetry_corpus_index",
        "telemetry",
        ["corpus_id", "corpus_index"],
    )


def _create_replay_tables() -> None:
    op.create_table(
        "replay_jobs",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("logical_job_hash", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("corpus_id", sa.Text(), nullable=False),
        sa.Column("archive_sha256", sa.Text(), nullable=False),
        sa.Column("preprocessing_contract_version", sa.Text(), nullable=False),
        sa.Column("activation_id", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("score_provenance", sa.Text(), nullable=False),
        sa.Column("from_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("to_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column(
            "replay_range",
            postgresql.TSRANGE(),
            sa.Computed("tsrange(from_ts, to_ts, '[)')", persisted=True),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_corpus_index", sa.BigInteger(), nullable=False),
        sa.Column("processed_count", sa.BigInteger(), nullable=False),
        sa.Column("result_count", sa.BigInteger(), nullable=False),
        sa.Column("episode_count", sa.BigInteger(), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_replay_jobs_status",
        ),
        sa.CheckConstraint("from_ts < to_ts", name="ck_replay_jobs_range"),
        sa.CheckConstraint(
            "to_ts - from_ts <= interval '31 days'",
            name="ck_replay_jobs_max_range",
        ),
        sa.CheckConstraint(
            "score_provenance IN ('simulated_preview', 'artifact_backed')",
            name="ck_replay_jobs_provenance",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts > 0 "
            "AND attempt_count <= max_attempts",
            name="ck_replay_jobs_attempts",
        ),
        sa.CheckConstraint(
            "next_corpus_index >= 0 AND processed_count >= 0 "
            "AND result_count >= 0 AND episode_count >= 0",
            name="ck_replay_jobs_progress",
        ),
        sa.ForeignKeyConstraint(
            ["activation_id"], ["model_activations.activation_id"]
        ),
        sa.ForeignKeyConstraint(["corpus_id"], ["corpora.corpus_id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(["model_version"], ["model_versions.version"]),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_index(
        "uq_replay_jobs_logical_nonfailed",
        "replay_jobs",
        ["logical_job_hash"],
        unique=True,
        postgresql_where=sa.text("status <> 'failed'"),
    )
    op.execute(
        """
        ALTER TABLE replay_jobs
        ADD CONSTRAINT ex_replay_jobs_nonoverlap
        EXCLUDE USING gist (
            device_id WITH =,
            model_version WITH =,
            score_provenance WITH =,
            replay_range WITH &&
        )
        WHERE (status IN ('queued', 'running', 'succeeded'))
        """
    )
    op.create_table(
        "replay_commands",
        sa.Column("command_id", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["replay_jobs.job_id"]),
        sa.PrimaryKeyConstraint("command_id"),
    )
    op.create_index("ix_replay_commands_job", "replay_commands", ["job_id"])
    op.create_table(
        "replay_result_staging",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("score_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("window_start_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("window_end_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("score_provenance", sa.Text(), nullable=False),
        sa.Column("source_start_index", sa.BigInteger(), nullable=False),
        sa.Column("source_end_index", sa.BigInteger(), nullable=False),
        sa.Column("reading_count", sa.Integer(), nullable=False),
        sa.Column("stride", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("eligible_window_ordinal", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            FINITE_SCORE, name="ck_replay_result_staging_score_finite"
        ),
        sa.CheckConstraint(
            FINITE_THRESHOLD,
            name="ck_replay_result_staging_threshold_finite",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["replay_jobs.job_id"]),
        sa.PrimaryKeyConstraint("job_id", "score_ts"),
    )
    op.create_table(
        "replay_episode_staging",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("episode_ordinal", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("episode_start_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("episode_end_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("last_score_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("first_window_start_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("first_window_end_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("peak_score", sa.Float(), nullable=False),
        sa.Column("latest_score", sa.Float(), nullable=False),
        sa.Column("anomalous_window_count", sa.Integer(), nullable=False),
        sa.Column("closure_reason", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "closure_reason IN ('normal', 'gap', 'replay_end')",
            name="ck_replay_episode_staging_closure",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["replay_jobs.job_id"]),
        sa.PrimaryKeyConstraint("job_id", "episode_ordinal"),
    )
    op.create_table(
        "replay_episode_checkpoints",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["replay_jobs.job_id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_id", sa.Text(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("worker_id"),
    )


def _rebuild_inference_results() -> None:
    op.create_table(
        "inference_results_m2",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("corpus_id", sa.Text(), nullable=False),
        sa.Column("window_start_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("window_end_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("score_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("score_provenance", sa.Text(), nullable=False),
        sa.Column("source_start_index", sa.BigInteger(), nullable=False),
        sa.Column("source_end_index", sa.BigInteger(), nullable=False),
        sa.Column("reading_count", sa.Integer(), nullable=False),
        sa.Column("stride", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("replay_job_id", sa.Text(), nullable=True),
        sa.CheckConstraint(
            FINITE_SCORE, name="ck_inference_results_m2_score_finite"
        ),
        sa.CheckConstraint(
            FINITE_THRESHOLD,
            name="ck_inference_results_m2_threshold_finite",
        ),
        sa.CheckConstraint(
            "window_start_ts < window_end_ts",
            name="ck_inference_results_m2_window_order",
        ),
        sa.CheckConstraint(
            "score_provenance IN ("
            "'deterministic_threshold_fixture', "
            "'simulated_preview', 'artifact_backed')",
            name="ck_inference_results_m2_provenance",
        ),
        sa.CheckConstraint(
            "source_start_index >= 0 "
            "AND source_start_index <= source_end_index "
            "AND reading_count > 0 AND stride > 0 AND segment_id >= 0",
            name="ck_inference_results_m2_window_shape",
        ),
        sa.ForeignKeyConstraint(["corpus_id"], ["corpora.corpus_id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(["model_version"], ["model_versions.version"]),
        sa.ForeignKeyConstraint(["replay_job_id"], ["replay_jobs.job_id"]),
        sa.PrimaryKeyConstraint("device_id", "score_ts", "model_version"),
    )
    op.execute(
        "SELECT create_hypertable("
        "'inference_results_m2', 'score_ts', if_not_exists => TRUE)"
    )
    op.execute(
        """
        INSERT INTO inference_results_m2 (
            device_id, corpus_id, window_start_ts, window_end_ts, score_ts,
            model_version, score, threshold, is_anomaly, score_provenance,
            source_start_index, source_end_index, reading_count, stride,
            segment_id, replay_job_id
        )
        SELECT
            device_id,
            'legacy-corpus-' || device_id,
            window_start_ts,
            window_end_ts,
            window_end_ts,
            model_version,
            score,
            threshold,
            is_anomaly,
            score_provenance,
            source_start_index,
            source_end_index,
            reading_count,
            stride,
            CASE
                WHEN source_end_index < 36032 THEN 0
                WHEN source_end_index < 65146 THEN 1
                ELSE 2
            END,
            NULL
        FROM inference_results
        """
    )
    op.execute(
        """
        DO $$
        DECLARE
            legacy_count bigint;
            rebuilt_count bigint;
            score_dimension_count integer;
        BEGIN
            SELECT count(*) INTO legacy_count FROM inference_results;
            SELECT count(*) INTO rebuilt_count FROM inference_results_m2;
            IF legacy_count <> rebuilt_count THEN
                RAISE EXCEPTION
                    'inference rebuild row-count mismatch: legacy %, rebuilt %',
                    legacy_count, rebuilt_count;
            END IF;

            IF EXISTS (
                (
                    SELECT
                        device_id, window_start_ts, window_end_ts,
                        model_version, score, threshold, is_anomaly,
                        score_provenance, source_start_index, source_end_index,
                        reading_count, stride
                    FROM inference_results
                    EXCEPT
                    SELECT
                        device_id, window_start_ts, window_end_ts,
                        model_version, score, threshold, is_anomaly,
                        score_provenance, source_start_index, source_end_index,
                        reading_count, stride
                    FROM inference_results_m2
                )
                UNION ALL
                (
                    SELECT
                        device_id, window_start_ts, window_end_ts,
                        model_version, score, threshold, is_anomaly,
                        score_provenance, source_start_index, source_end_index,
                        reading_count, stride
                    FROM inference_results_m2
                    EXCEPT
                    SELECT
                        device_id, window_start_ts, window_end_ts,
                        model_version, score, threshold, is_anomaly,
                        score_provenance, source_start_index, source_end_index,
                        reading_count, stride
                    FROM inference_results
                )
            ) THEN
                RAISE EXCEPTION 'inference rebuild value mismatch';
            END IF;

            IF EXISTS (
                SELECT 1
                FROM inference_results_m2
                WHERE score_ts <> window_end_ts
            ) THEN
                RAISE EXCEPTION
                    'legacy inference score timestamp backfill mismatch';
            END IF;

            SELECT count(*) INTO score_dimension_count
            FROM timescaledb_information.dimensions
            WHERE hypertable_schema = current_schema()
              AND hypertable_name = 'inference_results_m2'
              AND column_name = 'score_ts';
            IF score_dimension_count <> 1 THEN
                RAISE EXCEPTION
                    'inference_results_m2 score_ts dimension missing';
            END IF;
        END
        $$;
        """
    )
    op.execute(
        "ALTER TABLE inference_results "
        "RENAME CONSTRAINT inference_results_pkey "
        "TO inference_results_legacy_backup_pkey"
    )
    op.rename_table(
        "inference_results", "inference_results_legacy_backup"
    )
    op.rename_table("inference_results_m2", "inference_results")
    op.execute(
        "ALTER TABLE inference_results "
        "RENAME CONSTRAINT inference_results_m2_pkey "
        "TO inference_results_pkey"
    )
    op.create_index(
        "ix_inference_results_replay",
        "inference_results",
        ["replay_job_id", "score_ts"],
    )


def _upgrade_alerts() -> None:
    op.drop_constraint("ck_alerts_device_id", "alerts", type_="check")
    op.drop_constraint(
        "ck_alerts_detection_basis", "alerts", type_="check"
    )
    op.alter_column("alerts", "detected_at", nullable=True)
    op.add_column("alerts", sa.Column("corpus_id", sa.Text(), nullable=True))
    op.add_column(
        "alerts",
        sa.Column("episode_start_ts", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("episode_end_ts", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "alerts",
        sa.Column("last_score_ts", sa.DateTime(timezone=False), nullable=True),
    )
    op.add_column(
        "alerts", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("alerts", sa.Column("peak_score", sa.Float(), nullable=True))
    op.add_column("alerts", sa.Column("latest_score", sa.Float(), nullable=True))
    op.add_column(
        "alerts", sa.Column("anomalous_window_count", sa.Integer(), nullable=True)
    )
    op.add_column("alerts", sa.Column("replay_job_id", sa.Text(), nullable=True))
    op.add_column("alerts", sa.Column("segment_id", sa.Integer(), nullable=True))
    op.add_column(
        "alerts", sa.Column("closure_reason", sa.Text(), nullable=True)
    )
    op.execute(
        """
        UPDATE alerts
        SET
            corpus_id = 'legacy-corpus-' || device_id,
            episode_start_ts = inference_result_window_start_ts,
            episode_end_ts = inference_result_window_end_ts,
            last_score_ts = inference_result_window_end_ts,
            peak_score = score,
            latest_score = score,
            anomalous_window_count = 1,
            segment_id = CASE
                WHEN device_id = 'talpha-1' THEN 0
                ELSE 0
            END,
            closure_reason = 'legacy_m1_fixture'
        """
    )
    for column in (
        "corpus_id",
        "episode_start_ts",
        "episode_end_ts",
        "last_score_ts",
        "peak_score",
        "latest_score",
        "anomalous_window_count",
        "segment_id",
        "closure_reason",
    ):
        op.alter_column("alerts", column, nullable=False)
    op.create_foreign_key(
        "fk_alerts_device", "alerts", "devices", ["device_id"], ["device_id"]
    )
    op.create_foreign_key(
        "fk_alerts_corpus", "alerts", "corpora", ["corpus_id"], ["corpus_id"]
    )
    op.create_foreign_key(
        "fk_alerts_model",
        "alerts",
        "model_versions",
        ["model_version"],
        ["version"],
    )
    op.create_foreign_key(
        "fk_alerts_replay",
        "alerts",
        "replay_jobs",
        ["replay_job_id"],
        ["job_id"],
    )
    op.create_check_constraint(
        "ck_alerts_detection_basis",
        "alerts",
        "detection_basis IN ("
        "'threshold_model_fixture', 'simulated_preview', 'artifact_backed')",
    )
    op.create_check_constraint(
        "ck_alerts_lineage_time_domain",
        "alerts",
        "("
        "detection_basis = 'threshold_model_fixture' "
        "AND detected_at IS NOT NULL AND created_at IS NULL "
        "AND replay_job_id IS NULL "
        "AND closure_reason = 'legacy_m1_fixture'"
        ") OR ("
        "detection_basis IN ('simulated_preview', 'artifact_backed') "
        "AND detected_at IS NULL AND created_at IS NOT NULL "
        "AND replay_job_id IS NOT NULL "
        "AND closure_reason IN ('normal', 'gap', 'replay_end')"
        ")",
    )
    op.create_check_constraint(
        "ck_alerts_episode_shape",
        "alerts",
        "episode_start_ts <= episode_end_ts "
        "AND episode_end_ts <= last_score_ts "
        "AND anomalous_window_count > 0 AND segment_id >= 0 "
        "AND peak_score > '-Infinity'::double precision "
        "AND peak_score < 'Infinity'::double precision "
        "AND latest_score > '-Infinity'::double precision "
        "AND latest_score < 'Infinity'::double precision",
    )
    op.create_index(
        "ix_alerts_episode_order",
        "alerts",
        [sa.text("episode_end_ts DESC"), "alert_id"],
    )

    op.drop_constraint(
        "ck_alert_events_device_id", "alert_events", type_="check"
    )
    op.drop_constraint(
        "ck_alert_events_detection_basis", "alert_events", type_="check"
    )
    op.alter_column("alert_events", "event_ts", nullable=True)
    op.add_column(
        "alert_events",
        sa.Column("event_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alert_events",
        sa.Column(
            "time_domain",
            sa.Text(),
            nullable=False,
            server_default="legacy_naive",
        ),
    )
    op.create_foreign_key(
        "fk_alert_events_device",
        "alert_events",
        "devices",
        ["device_id"],
        ["device_id"],
    )
    op.create_check_constraint(
        "ck_alert_events_detection_basis",
        "alert_events",
        "detection_basis IN ("
        "'threshold_model_fixture', 'simulated_preview', 'artifact_backed')",
    )
    op.create_check_constraint(
        "ck_alert_events_time_domain",
        "alert_events",
        "(time_domain = 'legacy_naive' "
        "AND event_ts IS NOT NULL AND event_at IS NULL) OR "
        "(time_domain = 'utc' "
        "AND event_ts IS NULL AND event_at IS NOT NULL)",
    )
    op.create_index(
        "ix_alert_events_event_at", "alert_events", ["event_at", "event_id"]
    )

    op.alter_column("alert_commands", "event_ts", nullable=True)
    op.add_column(
        "alert_commands",
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "alert_commands",
        sa.Column(
            "time_domain",
            sa.Text(),
            nullable=False,
            server_default="legacy_naive",
        ),
    )
    op.add_column(
        "alert_commands",
        sa.Column(
            "payload_hash",
            sa.Text(),
            nullable=False,
            server_default="legacy_m1_fixture",
        ),
    )
    op.create_check_constraint(
        "ck_alert_commands_time_domain",
        "alert_commands",
        "(time_domain = 'legacy_naive' "
        "AND event_ts IS NOT NULL AND accepted_at IS NULL) OR "
        "(time_domain = 'utc' "
        "AND event_ts IS NULL AND accepted_at IS NOT NULL)",
    )


def _upgrade_evaluations() -> None:
    additions = (
        sa.Column("model_key", sa.Text(), nullable=True),
        sa.Column(
            "report_source",
            sa.Text(),
            nullable=False,
            server_default="legacy_m1_fixture",
        ),
        sa.Column(
            "label_source", sa.Text(), nullable=False, server_default="none"
        ),
        sa.Column(
            "evaluation_kind",
            sa.Text(),
            nullable=False,
            server_default="validation_threshold",
        ),
        sa.Column(
            "test_observed", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "independent_final",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("source_commit", sa.Text(), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("source_sha256", sa.Text(), nullable=True),
        sa.Column(
            "is_public", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    for column in additions:
        op.add_column("model_evaluations", column)
    op.create_check_constraint(
        "ck_model_evaluations_report_source",
        "model_evaluations",
        "report_source IN ("
        "'legacy_m1_fixture', 'platform_computed', 'reported_dandy_pilot')",
    )
    op.create_check_constraint(
        "ck_model_evaluations_label_source",
        "model_evaluations",
        "label_source IN ('none', 'synthetic_injection', 'expert', 'natural')",
    )
    op.create_check_constraint(
        "ck_model_evaluations_kind",
        "model_evaluations",
        "evaluation_kind IN ("
        "'validation_threshold', 'synthetic_test', "
        "'clean_test', 'comparison_snapshot')",
    )


def upgrade() -> None:
    _create_catalog_tables()
    _seed_legacy_catalog()
    _upgrade_telemetry()
    _create_replay_tables()
    _rebuild_inference_results()
    _upgrade_alerts()
    _upgrade_evaluations()


def downgrade() -> None:
    raise NotImplementedError(
        "M2 changes temporal semantics and rebuilds a Timescale hypertable; "
        "a destructive automatic downgrade is intentionally unsupported."
    )
