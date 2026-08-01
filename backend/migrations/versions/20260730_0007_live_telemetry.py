from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260730_0007"
down_revision: str | None = "20260730_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_DEVICE_ID = "b02f3872-ruang-produksi"
_DEVICE_CHECK = f"device_id = '{_DEVICE_ID}'"
_FINITE = "{column} > '-Infinity'::double precision AND {column} < 'Infinity'::double precision"
_NAIVE_TS = postgresql.TIMESTAMP(timezone=False, precision=0)


def _create_model_state_tables() -> None:
    op.create_table(
        "live_model_pairs",
        sa.Column(
            "model_pair_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("checkpoint_identity", sa.Text(), nullable=False),
        sa.Column("scaler_snapshot_corpus_id", sa.Text(), nullable=False),
        sa.Column("model_manifest_sha256", sa.Text(), nullable=False),
        sa.Column("checkpoint_sha256", sa.Text(), nullable=False),
        sa.Column("scaler_manifest_sha256", sa.Text(), nullable=False),
        sa.Column("scaler_sha256", sa.Text(), nullable=False),
        sa.Column("threshold", postgresql.DOUBLE_PRECISION(), nullable=False),
        sa.Column("contract_status", sa.Text(), nullable=False),
        sa.Column(
            "created_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _FINITE.format(column="threshold"),
            name="ck_live_model_pairs_threshold_finite",
        ),
        sa.CheckConstraint(
            "contract_status = 'live_10'",
            name="ck_live_model_pairs_contract_status",
        ),
        sa.CheckConstraint(
            "model_manifest_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_live_model_pairs_model_manifest_sha256",
        ),
        sa.CheckConstraint(
            "checkpoint_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_live_model_pairs_checkpoint_sha256",
        ),
        sa.CheckConstraint(
            "scaler_manifest_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_live_model_pairs_scaler_manifest_sha256",
        ),
        sa.CheckConstraint(
            "scaler_sha256 ~ '^[0-9a-f]{64}$'",
            name="ck_live_model_pairs_scaler_sha256",
        ),
        sa.ForeignKeyConstraint(
            [
                "model_version",
                "contract_status",
                "model_manifest_sha256",
                "checkpoint_sha256",
                "scaler_manifest_sha256",
                "scaler_sha256",
            ],
            [
                "model_versions.version",
                "model_versions.contract_status",
                "model_versions.model_manifest_sha256",
                "model_versions.checkpoint_sha256",
                "model_versions.scaler_manifest_sha256",
                "model_versions.scaler_sha256",
            ],
            name="fk_live_model_pairs_artifact_identity",
        ),
        sa.ForeignKeyConstraint(
            ["scaler_snapshot_corpus_id", "contract_status"],
            [
                "preprocessing_snapshots.corpus_id",
                "preprocessing_snapshots.contract_status",
            ],
            name="fk_live_model_pairs_snapshot_contract",
        ),
        sa.PrimaryKeyConstraint("model_pair_id"),
        sa.UniqueConstraint(
            "model_version",
            "checkpoint_identity",
            "scaler_snapshot_corpus_id",
            name="uq_live_model_pairs_identity",
        ),
        sa.UniqueConstraint(
            "model_pair_id",
            "model_version",
            "scaler_snapshot_corpus_id",
            name="uq_live_model_pairs_lineage",
        ),
    )
    op.create_table(
        "live_writer_leases",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("lease_owner", sa.Text(), nullable=False),
        sa.Column("lease_expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_DEVICE_CHECK, name="ck_live_writer_leases_device"),
        sa.CheckConstraint(
            "fencing_token > 0", name="ck_live_writer_leases_fencing"
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.PrimaryKeyConstraint("device_id"),
    )
    op.create_table(
        "live_model_activation_requests",
        sa.Column(
            "request_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("model_pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column(
            "requested_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _DEVICE_CHECK, name="ck_live_model_activation_requests_device"
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["model_pair_id"], ["live_model_pairs.model_pair_id"]
        ),
        sa.PrimaryKeyConstraint("request_id"),
        sa.UniqueConstraint("request_hash", name="uq_live_model_activation_requests_hash"),
        sa.UniqueConstraint(
            "request_id",
            "device_id",
            "model_pair_id",
            name="uq_live_activation_request_lineage",
        ),
    )
    op.create_table(
        "live_model_activations",
        sa.Column(
            "activation_event_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column(
            "activation_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column(
            "activated_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _DEVICE_CHECK, name="ck_live_model_activations_device"
        ),
        sa.CheckConstraint(
            "activation_id > 0 AND fencing_token > 0",
            name="ck_live_model_activations_monotonic",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["request_id", "device_id", "model_pair_id"],
            [
                "live_model_activation_requests.request_id",
                "live_model_activation_requests.device_id",
                "live_model_activation_requests.model_pair_id",
            ],
            name="fk_live_activation_request_lineage",
        ),
        sa.PrimaryKeyConstraint("activation_event_id"),
        sa.UniqueConstraint(
            "device_id", "activation_id", name="uq_live_model_activations_device_id"
        ),
        sa.UniqueConstraint("request_id", name="uq_live_model_activations_request"),
        sa.UniqueConstraint(
            "device_id",
            "activation_id",
            "model_pair_id",
            name="uq_live_activation_lineage",
        ),
        sa.UniqueConstraint(
            "activation_event_id",
            "device_id",
            "activation_id",
            "model_pair_id",
            name="uq_live_activation_event_lineage",
        ),
    )
    op.create_table(
        "live_model_selections",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("activation_event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activation_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "selected_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            _DEVICE_CHECK, name="ck_live_model_selections_device"
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["activation_event_id", "device_id", "activation_id", "model_pair_id"],
            [
                "live_model_activations.activation_event_id",
                "live_model_activations.device_id",
                "live_model_activations.activation_id",
                "live_model_activations.model_pair_id",
            ],
            name="fk_live_selection_activation_lineage",
        ),
        sa.PrimaryKeyConstraint("device_id"),
    )


def _create_live_telemetry_tables() -> None:
    op.create_table(
        "live_telemetry",
        sa.Column("received_ts", _NAIVE_TS, nullable=False),
        sa.Column(
            "telemetry_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("received_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature_c", postgresql.DOUBLE_PRECISION(), nullable=False),
        sa.Column(
            "relative_humidity_pct", postgresql.DOUBLE_PRECISION(), nullable=False
        ),
        sa.Column(
            "ingress_sequence",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("ingress_generation", sa.BigInteger(), nullable=False),
        sa.Column("activation_id", sa.BigInteger(), nullable=False),
        sa.Column("continuity_epoch", sa.BigInteger(), nullable=False),
        sa.Column("segment_start_reason", sa.Text(), nullable=True),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("processing_status", sa.Text(), nullable=False),
        sa.CheckConstraint(_DEVICE_CHECK, name="ck_live_telemetry_device"),
        sa.CheckConstraint(
            _FINITE.format(column="temperature_c"),
            name="ck_live_telemetry_temperature_finite",
        ),
        sa.CheckConstraint(
            _FINITE.format(column="relative_humidity_pct"),
            name="ck_live_telemetry_humidity_finite",
        ),
        sa.CheckConstraint(
            "ingress_sequence > 0 AND ingress_generation >= 0 "
            "AND continuity_epoch >= 0 AND fencing_token > 0",
            name="ck_live_telemetry_progress",
        ),
        sa.CheckConstraint(
            "processing_status IN ('pending', 'processed')",
            name="ck_live_telemetry_processing_status",
        ),
        sa.CheckConstraint(
            "segment_start_reason IS NULL OR segment_start_reason IN "
            "('startup', 'data_gap', 'model_change', 'overload', 'lease_takeover')",
            name="ck_live_telemetry_segment_reason",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["device_id", "activation_id"],
            ["live_model_activations.device_id", "live_model_activations.activation_id"],
            name="fk_live_telemetry_activation",
        ),
        sa.PrimaryKeyConstraint("received_ts", "telemetry_id"),
        sa.UniqueConstraint(
            "received_ts",
            "device_id",
            "ingress_generation",
            "ingress_sequence",
            name="uq_live_telemetry_ingress_sequence",
        ),
        sa.UniqueConstraint(
            "received_ts",
            "telemetry_id",
            "device_id",
            name="uq_live_telemetry_device_anchor",
        ),
    )
    op.execute(
        "SELECT create_hypertable('live_telemetry', 'received_ts', if_not_exists => TRUE)"
    )
    op.create_index(
        "ix_live_telemetry_device_received_tail",
        "live_telemetry",
        ["device_id", sa.text("received_ts DESC"), sa.text("telemetry_id DESC")],
    )

    op.create_table(
        "live_inference",
        sa.Column("score_ts", _NAIVE_TS, nullable=False),
        sa.Column(
            "inference_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("window_start_ts", _NAIVE_TS, nullable=False),
        sa.Column("window_end_ts", _NAIVE_TS, nullable=False),
        sa.Column("score", postgresql.DOUBLE_PRECISION(), nullable=False),
        sa.Column("threshold", postgresql.DOUBLE_PRECISION(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("severity_at_score", sa.Text(), nullable=False),
        sa.Column("model_pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activation_id", sa.BigInteger(), nullable=False),
        sa.Column("continuity_epoch", sa.BigInteger(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("snapshot_corpus_id", sa.Text(), nullable=False),
        sa.Column("ordered_source_fingerprint", sa.Text(), nullable=False),
        sa.CheckConstraint(_DEVICE_CHECK, name="ck_live_inference_device"),
        sa.CheckConstraint(
            "window_start_ts <= window_end_ts AND score_ts = window_end_ts",
            name="ck_live_inference_window_order",
        ),
        sa.CheckConstraint(
            _FINITE.format(column="score"), name="ck_live_inference_score_finite"
        ),
        sa.CheckConstraint(
            _FINITE.format(column="threshold"),
            name="ck_live_inference_threshold_finite",
        ),
        sa.CheckConstraint(
            "severity_at_score IN ('info', 'warning', 'critical')",
            name="ck_live_inference_severity",
        ),
        sa.CheckConstraint(
            "activation_id > 0 AND continuity_epoch >= 0 "
            "AND ordered_source_fingerprint <> ''",
            name="ck_live_inference_identity",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["device_id", "activation_id", "model_pair_id"],
            [
                "live_model_activations.device_id",
                "live_model_activations.activation_id",
                "live_model_activations.model_pair_id",
            ],
            name="fk_live_inference_activation_lineage",
        ),
        sa.ForeignKeyConstraint(
            ["model_pair_id", "model_version", "snapshot_corpus_id"],
            [
                "live_model_pairs.model_pair_id",
                "live_model_pairs.model_version",
                "live_model_pairs.scaler_snapshot_corpus_id",
            ],
            name="fk_live_inference_pair_snapshot",
        ),
        sa.PrimaryKeyConstraint("score_ts", "inference_id"),
        sa.UniqueConstraint(
            "score_ts",
            "device_id",
            "model_pair_id",
            "activation_id",
            "continuity_epoch",
            "ordered_source_fingerprint",
            name="uq_live_inference_idempotency",
        ),
        sa.UniqueConstraint(
            "score_ts",
            "inference_id",
            "device_id",
            name="uq_live_inference_device_anchor",
        ),
        sa.UniqueConstraint(
            "score_ts",
            "inference_id",
            "device_id",
            "model_pair_id",
            "activation_id",
            "continuity_epoch",
            "model_version",
            "snapshot_corpus_id",
            name="uq_live_inference_device_identity",
        ),
    )
    op.execute(
        "SELECT create_hypertable('live_inference', 'score_ts', if_not_exists => TRUE)"
    )
    op.create_table(
        "live_inference_sources",
        sa.Column("score_ts", _NAIVE_TS, nullable=False),
        sa.Column("inference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("received_ts", _NAIVE_TS, nullable=False),
        sa.Column("telemetry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 0 AND ordinal < 10",
            name="ck_live_inference_sources_ordinal",
        ),
        sa.ForeignKeyConstraint(
            ["score_ts", "inference_id", "device_id"],
            [
                "live_inference.score_ts",
                "live_inference.inference_id",
                "live_inference.device_id",
            ],
            name="fk_live_inference_source_inference",
        ),
        sa.ForeignKeyConstraint(
            ["received_ts", "telemetry_id", "device_id"],
            [
                "live_telemetry.received_ts",
                "live_telemetry.telemetry_id",
                "live_telemetry.device_id",
            ],
            name="fk_live_inference_source_telemetry",
        ),
        sa.PrimaryKeyConstraint("score_ts", "inference_id", "ordinal"),
    )


def _create_processing_state_tables() -> None:
    op.create_table(
        "live_processing_boundaries",
        sa.Column(
            "boundary_id",
            sa.BigInteger(),
            sa.Identity(always=True),
            nullable=False,
        ),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("boundary_reason", sa.Text(), nullable=False),
        sa.Column(
            "recorded_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("ingress_generation", sa.BigInteger(), nullable=False),
        sa.Column("continuity_epoch", sa.BigInteger(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("after_received_ts", _NAIVE_TS, nullable=True),
        sa.Column("after_telemetry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.CheckConstraint(
            _DEVICE_CHECK, name="ck_live_processing_boundaries_device"
        ),
        sa.CheckConstraint(
            "boundary_reason IN "
            "('startup', 'data_gap', 'model_change', 'overload', 'lease_takeover')",
            name="ck_live_processing_boundaries_reason",
        ),
        sa.CheckConstraint(
            "ingress_generation >= 0 AND continuity_epoch >= 0 "
            "AND fencing_token > 0",
            name="ck_live_processing_boundaries_progress",
        ),
        sa.CheckConstraint(
            "(after_received_ts IS NULL) = (after_telemetry_id IS NULL)",
            name="ck_live_processing_boundaries_anchor",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["after_received_ts", "after_telemetry_id", "device_id"],
            [
                "live_telemetry.received_ts",
                "live_telemetry.telemetry_id",
                "live_telemetry.device_id",
            ],
            name="fk_live_boundary_telemetry_anchor",
        ),
        sa.PrimaryKeyConstraint("boundary_id"),
        sa.UniqueConstraint(
            "boundary_id",
            "device_id",
            name="uq_live_boundary_device_id",
        ),
        sa.UniqueConstraint(
            "device_id", "continuity_epoch", name="uq_live_processing_boundaries_epoch"
        ),
    )
    op.create_table(
        "live_cursors",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("received_ts", _NAIVE_TS, nullable=True),
        sa.Column("telemetry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_boundary_id", sa.BigInteger(), nullable=True),
        sa.Column("continuity_epoch", sa.BigInteger(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_DEVICE_CHECK, name="ck_live_cursors_device"),
        sa.CheckConstraint(
            "continuity_epoch >= 0 AND fencing_token > 0",
            name="ck_live_cursors_progress",
        ),
        sa.CheckConstraint(
            "(received_ts IS NULL) = (telemetry_id IS NULL)",
            name="ck_live_cursors_position",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["received_ts", "telemetry_id", "device_id"],
            [
                "live_telemetry.received_ts",
                "live_telemetry.telemetry_id",
                "live_telemetry.device_id",
            ],
            name="fk_live_cursor_telemetry_anchor",
        ),
        sa.ForeignKeyConstraint(
            ["last_boundary_id", "device_id"],
            [
                "live_processing_boundaries.boundary_id",
                "live_processing_boundaries.device_id",
            ],
            name="fk_live_cursor_boundary_device",
        ),
        sa.PrimaryKeyConstraint("device_id"),
    )
    op.create_table(
        "live_health",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("detail_code", sa.Text(), nullable=True),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column(
            "observed_at_utc",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(_DEVICE_CHECK, name="ck_live_health_device"),
        sa.CheckConstraint(
            "status IN ('healthy', 'degraded', 'unhealthy')",
            name="ck_live_health_status",
        ),
        sa.CheckConstraint(
            "fencing_token > 0", name="ck_live_health_fencing"
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.PrimaryKeyConstraint("device_id"),
    )


def _create_alert_provenance_tables() -> None:
    op.create_table(
        "live_alert_episodes",
        sa.Column(
            "live_episode_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("alert_id", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("model_pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activation_id", sa.BigInteger(), nullable=False),
        sa.Column("continuity_epoch", sa.BigInteger(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("snapshot_corpus_id", sa.Text(), nullable=False),
        sa.Column("started_score_ts", _NAIVE_TS, nullable=False),
        sa.Column("ended_score_ts", _NAIVE_TS, nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.CheckConstraint(
            _DEVICE_CHECK, name="ck_live_alert_episodes_device"
        ),
        sa.CheckConstraint(
            "status IN ('open', 'resolved')",
            name="ck_live_alert_episodes_status",
        ),
        sa.CheckConstraint(
            "(status = 'open' AND ended_score_ts IS NULL) OR "
            "(status = 'resolved' AND ended_score_ts IS NOT NULL "
            "AND ended_score_ts >= started_score_ts)",
            name="ck_live_alert_episodes_end_state",
        ),
        sa.CheckConstraint(
            "continuity_epoch >= 0 AND activation_id > 0",
            name="ck_live_alert_episodes_identity",
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.alert_id"]),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(
            ["device_id", "activation_id", "model_pair_id"],
            [
                "live_model_activations.device_id",
                "live_model_activations.activation_id",
                "live_model_activations.model_pair_id",
            ],
            name="fk_live_episode_activation_lineage",
        ),
        sa.ForeignKeyConstraint(
            ["model_pair_id", "model_version", "snapshot_corpus_id"],
            [
                "live_model_pairs.model_pair_id",
                "live_model_pairs.model_version",
                "live_model_pairs.scaler_snapshot_corpus_id",
            ],
            name="fk_live_episode_pair_snapshot",
        ),
        sa.PrimaryKeyConstraint("live_episode_id"),
        sa.UniqueConstraint("alert_id", name="uq_live_alert_episodes_alert"),
        sa.UniqueConstraint(
            "alert_id",
            "live_episode_id",
            name="uq_live_episode_alert_link",
        ),
        sa.UniqueConstraint(
            "live_episode_id",
            "device_id",
            "model_pair_id",
            "activation_id",
            "continuity_epoch",
            "model_version",
            "snapshot_corpus_id",
            name="uq_live_episode_lineage",
        ),
    )
    op.add_column(
        "alerts",
        sa.Column("live_episode_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_alerts_live_episode",
        "alerts",
        "live_alert_episodes",
        ["alert_id", "live_episode_id"],
        ["alert_id", "live_episode_id"],
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_table(
        "live_alert_episode_points",
        sa.Column("live_episode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("score_ts", _NAIVE_TS, nullable=False),
        sa.Column("inference_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.BigInteger(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("model_pair_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activation_id", sa.BigInteger(), nullable=False),
        sa.Column("continuity_epoch", sa.BigInteger(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("snapshot_corpus_id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "ordinal >= 0", name="ck_live_alert_episode_points_ordinal"
        ),
        sa.ForeignKeyConstraint(
            [
                "live_episode_id",
                "device_id",
                "model_pair_id",
                "activation_id",
                "continuity_epoch",
                "model_version",
                "snapshot_corpus_id",
            ],
            [
                "live_alert_episodes.live_episode_id",
                "live_alert_episodes.device_id",
                "live_alert_episodes.model_pair_id",
                "live_alert_episodes.activation_id",
                "live_alert_episodes.continuity_epoch",
                "live_alert_episodes.model_version",
                "live_alert_episodes.snapshot_corpus_id",
            ],
            name="fk_live_episode_point_episode_lineage",
        ),
        sa.ForeignKeyConstraint(
            [
                "score_ts",
                "inference_id",
                "device_id",
                "model_pair_id",
                "activation_id",
                "continuity_epoch",
                "model_version",
                "snapshot_corpus_id",
            ],
            [
                "live_inference.score_ts",
                "live_inference.inference_id",
                "live_inference.device_id",
                "live_inference.model_pair_id",
                "live_inference.activation_id",
                "live_inference.continuity_epoch",
                "live_inference.model_version",
                "live_inference.snapshot_corpus_id",
            ],
            name="fk_live_episode_point_inference_lineage",
        ),
        sa.PrimaryKeyConstraint("live_episode_id", "ordinal"),
        sa.UniqueConstraint(
            "live_episode_id",
            "score_ts",
            "inference_id",
            name="uq_live_alert_episode_points_inference",
        ),
    )


def _create_immutability_guards() -> None:
    op.execute(
        """
        CREATE FUNCTION live_reject_mutation() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in (
        "live_model_pairs",
        "live_model_activation_requests",
        "live_model_activations",
        "live_processing_boundaries",
        "live_inference",
        "live_inference_sources",
        "live_alert_episode_points",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_immutable "
            f"BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION live_reject_mutation()"
        )
    op.execute(
        """
        CREATE FUNCTION live_guard_telemetry_update() RETURNS trigger AS $$
        BEGIN
            IF (to_jsonb(NEW) - 'processing_status') IS DISTINCT FROM
               (to_jsonb(OLD) - 'processing_status') THEN
                RAISE EXCEPTION 'live telemetry identity is immutable';
            END IF;
            IF NEW.processing_status = OLD.processing_status THEN
                RETURN NEW;
            END IF;
            IF OLD.processing_status <> 'pending'
               OR NEW.processing_status <> 'processed' THEN
                RAISE EXCEPTION 'invalid live telemetry state transition';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER live_telemetry_state_guard
        BEFORE UPDATE ON live_telemetry
        FOR EACH ROW EXECUTE FUNCTION live_guard_telemetry_update()
        """
    )
    op.execute(
        "CREATE TRIGGER live_telemetry_delete_guard "
        "BEFORE DELETE ON live_telemetry "
        "FOR EACH ROW EXECUTE FUNCTION live_reject_mutation()"
    )
    op.execute(
        """
        CREATE FUNCTION live_guard_episode_update() RETURNS trigger AS $$
        BEGIN
            IF (to_jsonb(NEW) - 'status' - 'ended_score_ts') IS DISTINCT FROM
               (to_jsonb(OLD) - 'status' - 'ended_score_ts') THEN
                RAISE EXCEPTION 'live alert episode identity is immutable';
            END IF;
            IF NEW.status = OLD.status
               AND NEW.ended_score_ts IS NOT DISTINCT FROM OLD.ended_score_ts THEN
                RETURN NEW;
            END IF;
            IF OLD.status <> 'open' OR NEW.status <> 'resolved'
               OR NEW.ended_score_ts IS NULL
               OR NEW.ended_score_ts < OLD.started_score_ts THEN
                RAISE EXCEPTION 'invalid live alert episode transition';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER live_alert_episodes_state_guard "
        "BEFORE UPDATE ON live_alert_episodes "
        "FOR EACH ROW EXECUTE FUNCTION live_guard_episode_update()"
    )
    op.execute(
        "CREATE TRIGGER live_alert_episodes_delete_guard "
        "BEFORE DELETE ON live_alert_episodes "
        "FOR EACH ROW EXECUTE FUNCTION live_reject_mutation()"
    )
    op.execute(
        """
        CREATE FUNCTION live_guard_state_update() RETURNS trigger AS $$
        BEGIN
            IF NEW.device_id IS DISTINCT FROM OLD.device_id THEN
                RAISE EXCEPTION '% device identity is immutable', TG_TABLE_NAME;
            END IF;
            IF TG_TABLE_NAME = 'live_model_selections'
               AND NEW.activation_id < OLD.activation_id THEN
                RAISE EXCEPTION 'live model activation cannot move backwards';
            ELSIF TG_TABLE_NAME = 'live_writer_leases' THEN
                IF NEW.fencing_token < OLD.fencing_token
                   OR (
                       NEW.lease_owner IS DISTINCT FROM OLD.lease_owner
                       AND NEW.fencing_token <= OLD.fencing_token
                   ) THEN
                    RAISE EXCEPTION 'live writer fencing token must advance';
                END IF;
            ELSIF TG_TABLE_NAME = 'live_cursors' THEN
                IF NEW.continuity_epoch < OLD.continuity_epoch
                   OR NEW.fencing_token < OLD.fencing_token
                   OR (
                       OLD.last_boundary_id IS NOT NULL
                       AND (
                           NEW.last_boundary_id IS NULL
                           OR NEW.last_boundary_id < OLD.last_boundary_id
                       )
                   )
                   OR (
                       OLD.received_ts IS NOT NULL
                       AND (
                           NEW.received_ts IS NULL
                           OR ROW(NEW.received_ts, NEW.telemetry_id)
                              < ROW(OLD.received_ts, OLD.telemetry_id)
                       )
                   ) THEN
                    RAISE EXCEPTION 'live cursor cannot move backwards';
                END IF;
            ELSIF TG_TABLE_NAME = 'live_health'
               AND NEW.fencing_token < OLD.fencing_token THEN
                RAISE EXCEPTION 'live health fencing token cannot move backwards';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in (
        "live_model_selections",
        "live_writer_leases",
        "live_cursors",
        "live_health",
    ):
        op.execute(
            f"CREATE TRIGGER {table}_state_guard "
            f"BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION live_guard_state_update()"
        )
        op.execute(
            f"CREATE TRIGGER {table}_delete_guard "
            f"BEFORE DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION live_reject_mutation()"
        )


def upgrade() -> None:
    _create_model_state_tables()
    _create_live_telemetry_tables()
    _create_processing_state_tables()
    _create_alert_provenance_tables()
    _create_immutability_guards()


def downgrade() -> None:
    raise RuntimeError("live telemetry rollback requires database restore")
