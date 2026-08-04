from collections.abc import Sequence

from alembic import op


revision: str = "20260804_0015"
down_revision: str | None = "20260803_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_alerts_window_order", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alerts_window_order",
        "alerts",
        "inference_result_window_start_ts <= inference_result_window_end_ts",
    )


def downgrade() -> None:
    op.drop_constraint("ck_alerts_window_order", "alerts", type_="check")
    op.create_check_constraint(
        "ck_alerts_window_order",
        "alerts",
        "inference_result_window_start_ts < inference_result_window_end_ts",
    )
