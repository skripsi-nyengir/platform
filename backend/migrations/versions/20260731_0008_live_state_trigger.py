from collections.abc import Sequence

from alembic import op


revision: str = "20260731_0008"
down_revision: str | None = "20260730_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
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
                           OR ROW(
                               (new_row->>'received_ts')::timestamp,
                               (new_row->>'telemetry_id')::uuid
                           ) < ROW(
                               (old_row->>'received_ts')::timestamp,
                               (old_row->>'telemetry_id')::uuid
                           )
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
    )


def downgrade() -> None:
    raise RuntimeError("live state trigger rollback requires database restore")
