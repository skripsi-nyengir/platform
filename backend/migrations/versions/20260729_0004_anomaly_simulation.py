from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260729_0004"
down_revision: str | None = "20260726_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow injected telemetry to stay active beside historical replay.

    Per-kind uniqueness prevents an active injected device from being marked
    archived merely to bypass the former global active-device constraint.
    """
    op.add_column(
        "devices",
        sa.Column("telemetry_kind", sa.Text(), nullable=True),
    )
    op.execute("UPDATE devices SET telemetry_kind = 'historical_replay' WHERE telemetry_kind IS NULL")
    op.alter_column("devices", "telemetry_kind", nullable=False)
    op.create_check_constraint(
        "ck_devices_telemetry_kind",
        "devices",
        "telemetry_kind IN ('historical_replay', 'anomaly_injected')",
    )
    op.drop_index("uq_devices_one_public_active", table_name="devices")
    op.create_index(
        "uq_devices_one_active_per_kind",
        "devices",
        ["telemetry_kind", "is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )

    _ = op.create_table(
        "injection_events",
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("corpus_id", sa.Text(), nullable=False),
        sa.Column("device_id", sa.Text(), nullable=False),
        sa.Column("family", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("channel_index", sa.Integer(), nullable=False),
        sa.Column("start_idx", sa.BigInteger(), nullable=False),
        sa.Column("end_idx_exclusive", sa.BigInteger(), nullable=False),
        sa.Column(
            "start_ts",
            postgresql.TIMESTAMP(timezone=False),
            nullable=False,
        ),
        sa.Column(
            "end_ts",
            postgresql.TIMESTAMP(timezone=False),
            nullable=False,
        ),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "end_idx_exclusive > start_idx AND start_idx >= 0",
            name="ck_injection_events_range",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="ck_injection_events_severity",
        ),
        sa.CheckConstraint(
            "family IN ('spike', 'drift', 'stuck', 'erratic', 'bias', "
            + "'data_loss', 'garbage')",
            name="ck_injection_events_family",
        ),
        sa.ForeignKeyConstraint(
            ["corpus_id"],
            ["corpora.corpus_id"],
            name="fk_injection_events_corpus",
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.device_id"],
            name="fk_injection_events_device",
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(
        "ix_injection_events_corpus",
        "injection_events",
        ["corpus_id", "start_idx"],
    )


def downgrade() -> None:
    op.drop_table("injection_events")
    op.drop_index("uq_devices_one_active_per_kind", table_name="devices")
    op.create_index(
        "uq_devices_one_public_active",
        "devices",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.drop_constraint("ck_devices_telemetry_kind", "devices", type_="check")
    op.drop_column("devices", "telemetry_kind")
