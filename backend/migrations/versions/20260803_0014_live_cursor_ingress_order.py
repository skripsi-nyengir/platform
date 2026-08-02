from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260803_0014"
down_revision: str | None = "20260731_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CURSOR_ORDER_INGRESS = """
                       OR ROW(
                           (new_row->>'received_ts')::timestamp,
                           COALESCE((new_row->>'ingress_sequence')::bigint, -1)
                       ) < ROW(
                           (old_row->>'received_ts')::timestamp,
                           COALESCE((old_row->>'ingress_sequence')::bigint, -1)
                       )
"""

_CURSOR_ORDER_TELEMETRY_ID = """
                       OR ROW(
                           (new_row->>'received_ts')::timestamp,
                           (new_row->>'telemetry_id')::uuid
                       ) < ROW(
                           (old_row->>'received_ts')::timestamp,
                           (old_row->>'telemetry_id')::uuid
                       )
"""


def _state_guard(cursor_order: str) -> str:
    return f"""
        CREATE OR REPLACE FUNCTION live_guard_state_update() RETURNS trigger AS $$
        DECLARE
            old_row jsonb := to_jsonb(OLD);
            new_row jsonb := to_jsonb(NEW);
        BEGIN
            IF new_row->>'device_id' IS DISTINCT FROM old_row->>'device_id' THEN
                RAISE EXCEPTION '% device identity is immutable', TG_TABLE_NAME;
            END IF;
            IF TG_TABLE_NAME = 'live_model_selections' THEN
                IF (new_row->>'activation_id')::bigint
                   < (old_row->>'activation_id')::bigint THEN
                    RAISE EXCEPTION 'live model activation cannot move backwards';
                END IF;
            ELSIF TG_TABLE_NAME = 'live_writer_leases' THEN
                IF (new_row->>'fencing_token')::bigint
                   < (old_row->>'fencing_token')::bigint
                   OR (
                       new_row->>'lease_owner' IS DISTINCT FROM
                       old_row->>'lease_owner'
                       AND (new_row->>'fencing_token')::bigint
                           <= (old_row->>'fencing_token')::bigint
                   ) THEN
                    RAISE EXCEPTION 'live writer fencing token must advance';
                END IF;
            ELSIF TG_TABLE_NAME = 'live_cursors' THEN
                IF (new_row->>'continuity_epoch')::bigint
                   < (old_row->>'continuity_epoch')::bigint
                   OR (new_row->>'fencing_token')::bigint
                      < (old_row->>'fencing_token')::bigint
                   OR (
                       old_row->>'last_boundary_id' IS NOT NULL
                       AND (
                           new_row->>'last_boundary_id' IS NULL
                           OR (new_row->>'last_boundary_id')::bigint
                              < (old_row->>'last_boundary_id')::bigint
                       )
                   )
                   OR (
                       old_row->>'received_ts' IS NOT NULL
                       AND (
                           new_row->>'received_ts' IS NULL
{cursor_order}
                       )
                   ) THEN
                    RAISE EXCEPTION 'live cursor cannot move backwards';
                END IF;
            ELSIF TG_TABLE_NAME = 'live_health' THEN
                IF (new_row->>'fencing_token')::bigint
                   < (old_row->>'fencing_token')::bigint THEN
                    RAISE EXCEPTION 'live health fencing token cannot move backwards';
                END IF;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """


def upgrade() -> None:
    op.add_column(
        "live_cursors", sa.Column("ingress_sequence", sa.BigInteger(), nullable=True)
    )
    op.execute(
        """
        DO $$
        DECLARE orphaned integer;
        BEGIN
            UPDATE live_cursors AS c
            SET ingress_sequence = t.ingress_sequence
            FROM live_telemetry AS t
            WHERE t.device_id = c.device_id
              AND t.received_ts = c.received_ts
              AND t.telemetry_id = c.telemetry_id;
            SELECT count(*) INTO orphaned
            FROM live_cursors
            WHERE received_ts IS NOT NULL AND ingress_sequence IS NULL;
            IF orphaned > 0 THEN
                RAISE EXCEPTION
                    'live_cursors backfill left % anchored cursor(s) without ingress_sequence',
                    orphaned;
            END IF;
        END $$;
        """
    )
    op.execute(_state_guard(_CURSOR_ORDER_INGRESS))
    op.create_index(
        "ix_live_telemetry_pending_ingress",
        "live_telemetry",
        ["device_id", "received_ts", "ingress_sequence"],
        postgresql_where=sa.text("processing_status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_live_telemetry_pending_ingress", table_name="live_telemetry"
    )
    op.execute(_state_guard(_CURSOR_ORDER_TELEMETRY_ID))
    op.drop_column("live_cursors", "ingress_sequence")
