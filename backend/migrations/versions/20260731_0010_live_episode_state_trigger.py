from collections.abc import Sequence

from alembic import op


revision: str = "20260731_0010"
down_revision: str | None = "20260731_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION live_guard_episode_update() RETURNS trigger AS $$
        BEGIN
            IF (to_jsonb(NEW) - 'status' - 'ended_score_ts' - 'close_reason')
               IS DISTINCT FROM
               (to_jsonb(OLD) - 'status' - 'ended_score_ts' - 'close_reason') THEN
                RAISE EXCEPTION 'live alert episode identity is immutable';
            END IF;
            IF NEW.status = OLD.status
               AND NEW.ended_score_ts IS NOT DISTINCT FROM OLD.ended_score_ts
               AND NEW.close_reason IS NOT DISTINCT FROM OLD.close_reason THEN
                RETURN NEW;
            END IF;
            IF OLD.status <> 'open' OR NEW.status <> 'resolved'
               OR NEW.ended_score_ts IS NULL
               OR NEW.close_reason IS NULL
               OR NEW.ended_score_ts < OLD.started_score_ts THEN
                RAISE EXCEPTION 'invalid live alert episode transition';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )


def downgrade() -> None:
    raise RuntimeError("live episode state trigger rollback requires database restore")
