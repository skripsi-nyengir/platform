from collections.abc import Sequence

from alembic import op

revision: str = "20260731_0011"
down_revision: str | None = "20260731_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE alerts SET replay_job_id = NULL WHERE live_episode_id IS NOT NULL"
    )
    op.drop_constraint(
        "ck_alerts_lineage_time_domain",
        "alerts",
        type_="check",
    )
    op.create_check_constraint(
        "ck_alerts_lineage_time_domain",
        "alerts",
        "(detection_basis = 'threshold_model_fixture' "
        "AND detected_at IS NOT NULL AND created_at IS NULL "
        "AND replay_job_id IS NULL "
        "AND closure_reason = 'legacy_m1_fixture') OR ("
        "detection_basis IN ('simulated_preview', 'artifact_backed') "
        "AND detected_at IS NULL AND created_at IS NOT NULL "
        "AND ((live_episode_id IS NULL AND replay_job_id IS NOT NULL) "
        "OR (detection_basis = 'artifact_backed' "
        "AND live_episode_id IS NOT NULL AND replay_job_id IS NULL)) "
        "AND closure_reason IN ('normal', 'gap', 'replay_end'))",
    )


def downgrade() -> None:
    raise RuntimeError("live alert lineage rollback requires database restore")
