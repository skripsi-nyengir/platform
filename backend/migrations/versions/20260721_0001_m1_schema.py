from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260721_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEVICE_CHECK = "device_id IN ('talpha-1', 'talpha-2')"
FINITE_SCORE_CHECK = (
    "score > '-Infinity'::double precision "
    "AND score < 'Infinity'::double precision"
)
FINITE_THRESHOLD_CHECK = (
    "threshold > '-Infinity'::double precision "
    "AND threshold < 'Infinity'::double precision"
)


def upgrade() -> None:
    op.create_table(
        "telemetry",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("temperature_c", sa.Float(), nullable=True),
        sa.Column("relative_humidity_pct", sa.Float(), nullable=True),
        sa.Column("payload_hash", sa.Text(), nullable=False),
        sa.Column("source_index", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(DEVICE_CHECK, name="ck_telemetry_device_id"),
        sa.CheckConstraint(
            "temperature_c > '-Infinity'::double precision "
            "AND temperature_c < 'Infinity'::double precision",
            name="ck_telemetry_temperature_c_finite",
        ),
        sa.CheckConstraint(
            "relative_humidity_pct > '-Infinity'::double precision "
            "AND relative_humidity_pct < 'Infinity'::double precision",
            name="ck_telemetry_relative_humidity_pct_finite",
        ),
        sa.CheckConstraint("source_index >= 0", name="ck_telemetry_source_index"),
        sa.PrimaryKeyConstraint("device_id", "ts"),
    )
    op.execute("SELECT create_hypertable('telemetry', 'ts', if_not_exists => TRUE)")

    op.create_table(
        "inference_results",
        sa.Column("device_id", sa.Text(), nullable=False),
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
        sa.CheckConstraint(DEVICE_CHECK, name="ck_inference_results_device_id"),
        sa.CheckConstraint(
            FINITE_SCORE_CHECK,
            name="ck_inference_results_score_finite",
        ),
        sa.CheckConstraint(
            FINITE_THRESHOLD_CHECK,
            name="ck_inference_results_threshold_finite",
        ),
        sa.CheckConstraint(
            "window_start_ts < window_end_ts",
            name="ck_inference_results_window_order",
        ),
        sa.CheckConstraint(
            "score_provenance = 'deterministic_threshold_fixture'",
            name="ck_inference_results_score_provenance",
        ),
        sa.CheckConstraint(
            "source_start_index <= source_end_index",
            name="ck_inference_results_source_index_order",
        ),
        sa.CheckConstraint(
            "source_start_index >= 0",
            name="ck_inference_results_source_start_index",
        ),
        sa.CheckConstraint(
            "reading_count > 0",
            name="ck_inference_results_reading_count",
        ),
        sa.CheckConstraint("stride > 0", name="ck_inference_results_stride"),
        sa.PrimaryKeyConstraint("device_id", "window_end_ts", "model_version"),
    )
    op.execute(
        "SELECT create_hypertable("
        "'inference_results', 'window_end_ts', if_not_exists => TRUE)"
    )

    op.create_table(
        "alerts",
        sa.Column("alert_id", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=False), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column(
            "inference_result_window_start_ts",
            sa.DateTime(timezone=False),
            nullable=False,
        ),
        sa.Column(
            "inference_result_window_end_ts",
            sa.DateTime(timezone=False),
            nullable=False,
        ),
        sa.Column("detection_basis", sa.Text(), nullable=False),
        sa.CheckConstraint(DEVICE_CHECK, name="ck_alerts_device_id"),
        sa.CheckConstraint(FINITE_SCORE_CHECK, name="ck_alerts_score_finite"),
        sa.CheckConstraint(
            FINITE_THRESHOLD_CHECK,
            name="ck_alerts_threshold_finite",
        ),
        sa.CheckConstraint(
            "inference_result_window_start_ts < inference_result_window_end_ts",
            name="ck_alerts_window_order",
        ),
        sa.CheckConstraint(
            "detection_basis = 'threshold_model_fixture'",
            name="ck_alerts_detection_basis",
        ),
        sa.PrimaryKeyConstraint("alert_id"),
    )
    op.create_index(
        "ix_alerts_current_order",
        "alerts",
        [sa.text("detected_at DESC"), "alert_id"],
    )

    op.create_table(
        "alert_events",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("alert_id", sa.Text(), nullable=False),
        sa.Column("event_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "inference_result_window_start_ts",
            sa.DateTime(timezone=False),
            nullable=True,
        ),
        sa.Column(
            "inference_result_window_end_ts",
            sa.DateTime(timezone=False),
            nullable=True,
        ),
        sa.Column("inference_model_version", sa.Text(), nullable=True),
        sa.Column("detection_basis", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "event_type IN ('detected', 'acknowledged', 'resolved')",
            name="ck_alert_events_event_type",
        ),
        sa.CheckConstraint(DEVICE_CHECK, name="ck_alert_events_device_id"),
        sa.CheckConstraint(
            "detection_basis = 'threshold_model_fixture'",
            name="ck_alert_events_detection_basis",
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.alert_id"]),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_alert_events_alert_latest",
        "alert_events",
        ["alert_id", sa.text("event_ts DESC"), sa.text("event_id DESC")],
    )
    op.create_index(
        "ix_alert_events_time_order",
        "alert_events",
        ["event_ts", "event_id"],
    )

    op.create_table(
        "alert_commands",
        sa.Column("command_id", sa.Text(), nullable=False),
        sa.Column("alert_id", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("event_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("accepted_event_id", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "action IN ('acknowledged', 'resolved')",
            name="ck_alert_commands_action",
        ),
        sa.ForeignKeyConstraint(["accepted_event_id"], ["alert_events.event_id"]),
        sa.ForeignKeyConstraint(["alert_id"], ["alerts.alert_id"]),
        sa.PrimaryKeyConstraint("command_id"),
    )
    op.create_index(
        "ix_alert_commands_alert_id",
        "alert_commands",
        ["alert_id"],
    )

    op.create_table(
        "model_evaluations",
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("track", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("score_key", sa.Text(), nullable=False),
        sa.Column("score_semantics", sa.Text(), nullable=False),
        sa.Column("evaluation_period", sa.Text(), nullable=False),
        sa.Column("validation_only", sa.Boolean(), nullable=False),
        sa.Column("test_evaluated", sa.Boolean(), nullable=False),
        sa.Column("n_val_windows", sa.Integer(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("threshold_policy", postgresql.JSONB(), nullable=False),
        sa.Column("has_labeled_ground_truth", sa.Boolean(), nullable=False),
        sa.Column("available_metrics", postgresql.JSONB(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("model_hash", sa.Text(), nullable=True),
        sa.Column("preprocessing_hash", sa.Text(), nullable=True),
        sa.Column("threshold_hash", sa.Text(), nullable=True),
        sa.Column("metrics", postgresql.JSONB(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            FINITE_THRESHOLD_CHECK,
            name="ck_model_evaluations_threshold_finite",
        ),
        sa.CheckConstraint(
            "n_val_windows > 0",
            name="ck_model_evaluations_n_val_windows",
        ),
        sa.PrimaryKeyConstraint("version"),
    )


def downgrade() -> None:
    op.drop_table("model_evaluations")
    op.drop_table("alert_commands")
    op.drop_table("alert_events")
    op.drop_table("alerts")
    op.drop_table("inference_results")
    op.drop_table("telemetry")
