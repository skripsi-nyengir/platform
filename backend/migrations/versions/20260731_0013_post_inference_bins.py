from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260731_0013"
down_revision: str | None = "20260731_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "post_inference_bin_staging",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("bin_ordinal", sa.Integer(), nullable=False),
        sa.Column("start_score_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("end_score_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("scored_timestamp_count", sa.Integer(), nullable=False),
        sa.Column("is_alert", sa.Boolean(), nullable=False),
        sa.Column("candidate_alert_count", sa.Integer(), nullable=False),
        sa.Column("first_alert_ts", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_alert_ts", sa.DateTime(timezone=False), nullable=True),
        sa.Column("peak_score", sa.Float(), nullable=False),
        sa.Column("latest_score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.CheckConstraint(
            "scored_timestamp_count = 51",
            name="ck_post_inference_bin_staging_count",
        ),
        sa.CheckConstraint(
            "candidate_alert_count >= 0 AND candidate_alert_count <= scored_timestamp_count",
            name="ck_post_inference_bin_staging_candidate",
        ),
        sa.CheckConstraint(
            "is_alert = (candidate_alert_count > 0)",
            name="ck_post_inference_bin_staging_alert",
        ),
        sa.CheckConstraint(
            "start_score_ts <= end_score_ts",
            name="ck_post_inference_bin_staging_order",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["replay_jobs.job_id"]),
        sa.PrimaryKeyConstraint("job_id", "segment_id", "bin_ordinal"),
    )
    op.create_table(
        "post_inference_bins",
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("model_version", sa.Text(), nullable=False),
        sa.Column("score_provenance", sa.Text(), nullable=False),
        sa.Column("replay_job_id", sa.Text(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("bin_ordinal", sa.Integer(), nullable=False),
        sa.Column("start_score_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("end_score_ts", sa.DateTime(timezone=False), nullable=False),
        sa.Column("scored_timestamp_count", sa.Integer(), nullable=False),
        sa.Column("is_alert", sa.Boolean(), nullable=False),
        sa.Column("candidate_alert_count", sa.Integer(), nullable=False),
        sa.Column("first_alert_ts", sa.DateTime(timezone=False), nullable=True),
        sa.Column("last_alert_ts", sa.DateTime(timezone=False), nullable=True),
        sa.Column("peak_score", sa.Float(), nullable=False),
        sa.Column("latest_score", sa.Float(), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=False),
        sa.Column("schema_version", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scored_timestamp_count = 51",
            name="ck_post_inference_bins_count",
        ),
        sa.CheckConstraint(
            "candidate_alert_count >= 0 AND candidate_alert_count <= scored_timestamp_count",
            name="ck_post_inference_bins_candidate",
        ),
        sa.CheckConstraint(
            "is_alert = (candidate_alert_count > 0)",
            name="ck_post_inference_bins_alert",
        ),
        sa.CheckConstraint(
            "start_score_ts <= end_score_ts",
            name="ck_post_inference_bins_order",
        ),
        sa.ForeignKeyConstraint(["device_id"], ["devices.device_id"]),
        sa.ForeignKeyConstraint(["model_version"], ["model_versions.version"]),
        sa.ForeignKeyConstraint(["replay_job_id"], ["replay_jobs.job_id"]),
        sa.PrimaryKeyConstraint(
            "device_id",
            "model_version",
            "score_provenance",
            "replay_job_id",
            "segment_id",
            "bin_ordinal",
        ),
    )
    op.create_index(
        "ix_post_inference_bins_device_model_start",
        "post_inference_bins",
        ["device_id", "model_version", "start_score_ts"],
    )
    op.create_table(
        "post_inference_bin_checkpoints",
        sa.Column("job_id", sa.Text(), nullable=False),
        sa.Column("state", postgresql.JSONB(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["replay_jobs.job_id"]),
        sa.PrimaryKeyConstraint("job_id"),
    )


def downgrade() -> None:
    op.drop_table("post_inference_bin_checkpoints")
    op.drop_index(
        "ix_post_inference_bins_device_model_start",
        table_name="post_inference_bins",
    )
    op.drop_table("post_inference_bins")
    op.drop_table("post_inference_bin_staging")
