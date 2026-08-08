from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260808_0018"
down_revision: str | None = "20260808_0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "slack_settings",
        sa.Column(
            "singleton", sa.Boolean(), server_default=sa.text("true"), nullable=False
        ),
        sa.Column(
            "enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("bot_token", sa.Text(), nullable=True),
        sa.Column("channel_id", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("updated_by_user_id", sa.Text(), nullable=True),
        sa.CheckConstraint("singleton", name="ck_slack_settings_singleton"),
        sa.CheckConstraint(
            "NOT enabled OR ("
            "bot_token IS NOT NULL AND length(btrim(bot_token)) > 0 AND "
            "channel_id IS NOT NULL AND length(btrim(channel_id)) > 0)",
            name="ck_slack_settings_enabled_credentials",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by_user_id"], ["users.user_id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("singleton"),
    )
    op.execute(
        sa.text(
            "INSERT INTO slack_settings "
            "(singleton, enabled, bot_token, channel_id, updated_at, updated_by_user_id) "
            "VALUES (true, false, NULL, NULL, now(), NULL)"
        )
    )


def downgrade() -> None:
    op.drop_table("slack_settings")
