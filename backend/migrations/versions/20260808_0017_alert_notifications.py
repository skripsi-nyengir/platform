from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260808_0017"
down_revision: str | None = "20260807_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "alert_notifications",
        sa.Column(
            "notification_id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("live_episode_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "kind IN ('opened', 'escalated', 'closed')",
            name="ck_alert_notifications_kind",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'sent', 'failed')",
            name="ck_alert_notifications_status",
        ),
        sa.CheckConstraint(
            "attempts >= 0",
            name="ck_alert_notifications_attempts_non_negative",
        ),
        sa.CheckConstraint(
            "(status = 'sent') = (sent_at IS NOT NULL)",
            name="ck_alert_notifications_sent_at_matches_status",
        ),
        sa.ForeignKeyConstraint(
            ["live_episode_id"],
            ["live_alert_episodes.live_episode_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("notification_id"),
        sa.UniqueConstraint(
            "live_episode_id",
            "kind",
            name="uq_alert_notifications_episode_kind",
        ),
    )
    op.create_index(
        "ix_alert_notifications_pending",
        "alert_notifications",
        ["created_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_alert_notifications_pending", table_name="alert_notifications"
    )
    op.drop_table("alert_notifications")
