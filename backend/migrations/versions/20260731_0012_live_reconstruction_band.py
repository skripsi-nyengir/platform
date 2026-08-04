from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260731_0012"
down_revision: str | None = "20260731_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_RECON_COLUMNS = (
    "recon_temperature_c",
    "recon_relative_humidity_pct",
)


def upgrade() -> None:
    for column in _RECON_COLUMNS:
        op.add_column("live_inference", sa.Column(column, sa.Float(), nullable=True))


def downgrade() -> None:
    for column in _RECON_COLUMNS:
        op.drop_column("live_inference", column)
