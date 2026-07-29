from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260730_0005"
down_revision: str | None = "20260729_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_BAND_COLUMNS = (
    "recon_temperature_c",
    "recon_relative_humidity_pct",
    "band_half_temperature_c",
    "band_half_relative_humidity_pct",
)
_TABLES = ("replay_result_staging", "inference_results")


def upgrade() -> None:
    for table in _TABLES:
        for column in _BAND_COLUMNS:
            op.add_column(table, sa.Column(column, sa.Float(), nullable=True))


def downgrade() -> None:
    for table in _TABLES:
        for column in _BAND_COLUMNS:
            op.drop_column(table, column)
