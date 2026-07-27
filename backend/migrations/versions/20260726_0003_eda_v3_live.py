from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260726_0003"
down_revision: str | None = "20260724_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SHA256_CHECK = "{column} ~ '^[0-9a-f]{{64}}$'"
PERIOD_KIND_CHECK = (
    "period_kind IN ('daily', 'weekly', 'monthly', 'custom', 'full_range')"
)
SECTION_CHECK = (
    "section IN ("
    "'quality_overview', 'joint_density', 'univariate', "
    "'quality_excerpt', 'temporal_coverage', 'temporal_distribution', "
    "'relationships', 'stationarity', 'change_points', 'uncertainty', "
    "'audit_metadata')"
)


def _create_immutability_function() -> None:
    op.execute(
        """
        CREATE FUNCTION eda_reject_immutable_change()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION '% is immutable', TG_TABLE_NAME
                USING ERRCODE = '55000';
        END
        $$
        """
    )
    op.execute(
        """
        CREATE FUNCTION eda_guard_raw_reading_delete()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM eda_source_snapshots
                WHERE id = OLD.snapshot_id AND status = 'complete'
            ) THEN
                RAISE EXCEPTION 'eda_raw_readings is immutable'
                    USING ERRCODE = '55000';
            END IF;
            RETURN OLD;
        END
        $$
        """
    )


def _create_source_tables() -> None:
    op.create_table(
        "eda_source_snapshots",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("dataset_id", sa.Text(), nullable=False),
        sa.Column("source_sha256", sa.Text(), nullable=False),
        sa.Column("manifest_sha256", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column(
            "source_from_ts",
            postgresql.TIMESTAMP(timezone=False, precision=0),
            nullable=False,
        ),
        sa.Column(
            "source_to_ts",
            postgresql.TIMESTAMP(timezone=False, precision=0),
            nullable=False,
        ),
        sa.Column("expected_row_count", sa.BigInteger(), nullable=False),
        sa.Column("expected_channel_count", sa.Integer(), nullable=False),
        sa.Column("importer_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.CheckConstraint(
            "dataset_id <> '' AND importer_version <> ''",
            name="ck_eda_source_snapshots_names",
        ),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="source_sha256"),
            name="ck_eda_source_snapshots_source_sha256",
        ),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="manifest_sha256"),
            name="ck_eda_source_snapshots_manifest_sha256",
        ),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="config_hash"),
            name="ck_eda_source_snapshots_config_hash",
        ),
        sa.CheckConstraint(
            "source_from_ts <= source_to_ts",
            name="ck_eda_source_snapshots_bounds",
        ),
        sa.CheckConstraint(
            "expected_row_count > 0 AND expected_channel_count > 0",
            name="ck_eda_source_snapshots_expected_counts",
        ),
        sa.CheckConstraint(
            "status IN ('staging', 'complete', 'failed')",
            name="ck_eda_source_snapshots_status",
        ),
        sa.CheckConstraint(
            "(status = 'staging' AND completed_at IS NULL) OR "
            "(status IN ('complete', 'failed') AND completed_at IS NOT NULL)",
            name="ck_eda_source_snapshots_completion",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(manifest) = 'object'",
            name="ck_eda_source_snapshots_manifest_object",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "dataset_id",
            "source_sha256",
            name="uq_eda_source_snapshots_dataset_source",
        ),
        sa.UniqueConstraint(
            "id",
            "source_sha256",
            name="uq_eda_source_snapshots_id_source",
        ),
    )
    op.execute(
        """
        CREATE TRIGGER eda_source_snapshots_identity_immutable
        BEFORE UPDATE OF
            dataset_id, source_sha256, manifest_sha256, config_hash,
            source_from_ts, source_to_ts, expected_row_count,
            expected_channel_count, importer_version, manifest
        ON eda_source_snapshots
        FOR EACH ROW EXECUTE FUNCTION eda_reject_immutable_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER eda_source_snapshots_delete_immutable
        BEFORE DELETE ON eda_source_snapshots
        FOR EACH ROW EXECUTE FUNCTION eda_reject_immutable_change()
        """
    )

    op.create_table(
        "eda_raw_readings",
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_row_number", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("data_index", sa.Integer(), nullable=False),
        sa.Column("value", postgresql.DOUBLE_PRECISION(), nullable=False),
        sa.Column(
            "ts",
            postgresql.TIMESTAMP(timezone=False, precision=0),
            nullable=False,
        ),
        sa.Column("is_connected", sa.Boolean(), nullable=False),
        sa.CheckConstraint(
            "source_row_number > 0",
            name="ck_eda_raw_readings_source_row_number",
        ),
        sa.CheckConstraint(
            "device_id <> ''",
            name="ck_eda_raw_readings_device_id",
        ),
        sa.CheckConstraint(
            "data_index IN (0, 1)",
            name="ck_eda_raw_readings_data_index",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"],
            ["eda_source_snapshots.id"],
            name="fk_eda_raw_readings_snapshot",
        ),
        sa.PrimaryKeyConstraint("snapshot_id", "source_row_number", "ts"),
    )
    op.execute(
        "SELECT create_hypertable('eda_raw_readings', 'ts', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_eda_raw_readings_snapshot_device_ts_data_index",
        "eda_raw_readings",
        ["snapshot_id", "device_id", "ts", "data_index"],
    )
    op.execute(
        """
        CREATE TRIGGER eda_raw_readings_immutable
        BEFORE UPDATE ON eda_raw_readings
        FOR EACH ROW EXECUTE FUNCTION eda_reject_immutable_change()
        """
    )
    op.execute(
        """
        CREATE TRIGGER eda_raw_readings_delete_guard
        BEFORE DELETE ON eda_raw_readings
        FOR EACH ROW EXECUTE FUNCTION eda_guard_raw_reading_delete()
        """
    )


def _create_computation_tables() -> None:
    op.create_table(
        "eda_jobs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("logical_key", sa.Text(), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_sha256", sa.Text(), nullable=False),
        sa.Column(
            "from_ts",
            postgresql.TIMESTAMP(timezone=False, precision=0),
            nullable=False,
        ),
        sa.Column(
            "to_ts",
            postgresql.TIMESTAMP(timezone=False, precision=0),
            nullable=False,
        ),
        sa.Column("period_kind", sa.Text(), nullable=False),
        sa.Column("algorithm_version", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default="queued", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("trigger_kind", sa.Text(), nullable=False),
        sa.Column("lease_owner", sa.Text(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("terminal", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="logical_key"),
            name="ck_eda_jobs_logical_key",
        ),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="source_sha256"),
            name="ck_eda_jobs_source_sha256",
        ),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="config_hash"),
            name="ck_eda_jobs_config_hash",
        ),
        sa.CheckConstraint("from_ts < to_ts", name="ck_eda_jobs_range"),
        sa.CheckConstraint(PERIOD_KIND_CHECK, name="ck_eda_jobs_period_kind"),
        sa.CheckConstraint(
            "algorithm_version <> '' AND trigger_kind <> ''",
            name="ck_eda_jobs_names",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_eda_jobs_status",
        ),
        sa.CheckConstraint(
            "attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts",
            name="ck_eda_jobs_attempts",
        ),
        sa.CheckConstraint(
            "terminal = (status IN ('succeeded', 'failed')) "
            "AND ((terminal AND completed_at IS NOT NULL) "
            "OR (NOT terminal AND completed_at IS NULL))",
            name="ck_eda_jobs_terminal",
        ),
        sa.CheckConstraint(
            "(status = 'running' AND lease_owner IS NOT NULL "
            "AND lease_until IS NOT NULL) OR "
            "(status <> 'running' AND lease_owner IS NULL "
            "AND lease_until IS NULL)",
            name="ck_eda_jobs_lease",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "source_sha256"],
            ["eda_source_snapshots.id", "eda_source_snapshots.source_sha256"],
            name="fk_eda_jobs_snapshot_source",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_eda_jobs_active_logical_key",
        "eda_jobs",
        ["logical_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
    )
    op.execute(
        """
        CREATE TRIGGER eda_jobs_identity_immutable
        BEFORE UPDATE OF
            logical_key, snapshot_id, source_sha256, from_ts, to_ts,
            period_kind, algorithm_version, config_hash, trigger_kind
        ON eda_jobs
        FOR EACH ROW EXECUTE FUNCTION eda_reject_immutable_change()
        """
    )

    op.create_table(
        "eda_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("logical_key", sa.Text(), nullable=False),
        sa.Column("snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_sha256", sa.Text(), nullable=False),
        sa.Column(
            "from_ts",
            postgresql.TIMESTAMP(timezone=False, precision=0),
            nullable=False,
        ),
        sa.Column(
            "to_ts",
            postgresql.TIMESTAMP(timezone=False, precision=0),
            nullable=False,
        ),
        sa.Column("period_kind", sa.Text(), nullable=False),
        sa.Column("algorithm_version", sa.Text(), nullable=False),
        sa.Column("config_hash", sa.Text(), nullable=False),
        sa.Column("provenance", postgresql.JSONB(), nullable=False),
        sa.Column(
            "canonical_release", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="logical_key"),
            name="ck_eda_runs_logical_key",
        ),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="source_sha256"),
            name="ck_eda_runs_source_sha256",
        ),
        sa.CheckConstraint(
            SHA256_CHECK.format(column="config_hash"),
            name="ck_eda_runs_config_hash",
        ),
        sa.CheckConstraint("from_ts < to_ts", name="ck_eda_runs_range"),
        sa.CheckConstraint(PERIOD_KIND_CHECK, name="ck_eda_runs_period_kind"),
        sa.CheckConstraint(
            "algorithm_version <> ''",
            name="ck_eda_runs_algorithm_version",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(provenance) = 'object'",
            name="ck_eda_runs_provenance_object",
        ),
        sa.CheckConstraint(
            "NOT canonical_release OR period_kind = 'full_range'",
            name="ck_eda_runs_canonical_release",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id", "source_sha256"],
            ["eda_source_snapshots.id", "eda_source_snapshots.source_sha256"],
            name="fk_eda_runs_snapshot_source",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("logical_key", name="uq_eda_runs_logical_key"),
    )
    op.execute(
        """
        CREATE TRIGGER eda_runs_immutable
        BEFORE UPDATE OR DELETE ON eda_runs
        FOR EACH ROW EXECUTE FUNCTION eda_reject_immutable_change()
        """
    )

    op.create_table(
        "eda_result_sections",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("reason_code", sa.Text(), nullable=True),
        sa.Column("reason_detail", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("payload_sha256", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(SECTION_CHECK, name="ck_eda_result_sections_section"),
        sa.CheckConstraint(
            "status IN ('complete', 'not_eligible', 'failed')",
            name="ck_eda_result_sections_status",
        ),
        sa.CheckConstraint(
            "payload_sha256 IS NULL OR " + SHA256_CHECK.format(column="payload_sha256"),
            name="ck_eda_result_sections_payload_sha256",
        ),
        sa.CheckConstraint(
            "(status = 'complete' AND reason_code IS NULL "
            "AND reason_detail IS NULL AND payload IS NOT NULL "
            "AND payload_sha256 IS NOT NULL "
            "AND jsonb_typeof(payload) = 'object') OR "
            "(status IN ('not_eligible', 'failed') "
            "AND reason_code IS NOT NULL AND reason_detail IS NOT NULL "
            "AND payload IS NULL AND payload_sha256 IS NULL)",
            name="ck_eda_result_sections_content",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["eda_runs.id"],
            name="fk_eda_result_sections_run",
        ),
        sa.UniqueConstraint(
            "run_id",
            "section",
            name="uq_eda_result_sections_run_section",
        ),
    )
    op.execute(
        """
        CREATE TRIGGER eda_result_sections_immutable
        BEFORE UPDATE OR DELETE ON eda_result_sections
        FOR EACH ROW EXECUTE FUNCTION eda_reject_immutable_change()
        """
    )


def upgrade() -> None:
    _create_immutability_function()
    _create_source_tables()
    _create_computation_tables()


def downgrade() -> None:
    op.drop_table("eda_result_sections")
    op.drop_table("eda_runs")
    op.drop_table("eda_jobs")
    op.drop_table("eda_raw_readings")
    op.drop_table("eda_source_snapshots")
    op.execute("DROP FUNCTION IF EXISTS eda_guard_raw_reading_delete()")
    op.execute("DROP FUNCTION IF EXISTS eda_reject_immutable_change()")
