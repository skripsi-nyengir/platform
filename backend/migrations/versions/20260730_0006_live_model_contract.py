from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

from anomaly_backend.replay_contract import REPLAY_CONTRACT_LOCK_KEY


revision: str = "20260730_0006"
down_revision: str | None = "20260730_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CANONICAL_CHANNELS = "'[\"temperature_c\", \"relative_humidity_pct\"]'::jsonb"


def _precheck() -> None:
    op.execute(
        "SELECT pg_advisory_xact_lock(" f"{REPLAY_CONTRACT_LOCK_KEY}" ")"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM replay_jobs
                WHERE status NOT IN ('succeeded', 'failed')
            ) THEN
                RAISE EXCEPTION 'live model contract cutover requires terminal replay jobs';
            END IF;

        END
        $$;
        """
    )


def upgrade() -> None:
    _precheck()

    op.add_column(
        "preprocessing_snapshots",
        sa.Column(
            "contract_status",
            sa.Text(),
            nullable=False,
            server_default="legacy_30",
        ),
    )
    op.add_column(
        "model_versions",
        sa.Column(
            "contract_status",
            sa.Text(),
            nullable=False,
            server_default="legacy_30",
        ),
    )
    for column in (
        "model_manifest_sha256",
        "checkpoint_sha256",
        "scaler_manifest_sha256",
        "scaler_sha256",
    ):
        op.add_column("model_versions", sa.Column(column, sa.Text(), nullable=True))
    op.drop_constraint(
        "ck_preprocessing_window_stride",
        "preprocessing_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        "ck_preprocessing_window_stride_transition",
        "preprocessing_snapshots",
        "window_size IN (10, 30) AND stride = 1",
    )

    op.execute(
        """
        UPDATE preprocessing_snapshots
        SET channels = '["temperature_c", "relative_humidity_pct"]'::jsonb
        WHERE channels = '["suhu", "rh"]'::jsonb
        """
    )
    op.execute(
        """
        UPDATE preprocessing_snapshots
        SET scaler = jsonb_set(
            scaler,
            '{channels}',
            '["temperature_c", "relative_humidity_pct"]'::jsonb
        )
        WHERE jsonb_typeof(scaler) = 'object'
          AND scaler->'channels' = '["suhu", "rh"]'::jsonb
        """
    )
    op.execute(
        """
        UPDATE preprocessing_snapshots
        SET contract_status = CASE
            WHEN channels = '["temperature_c", "relative_humidity_pct"]'::jsonb
             AND window_size = 10
             AND stride = 1
             AND jsonb_typeof(scaler) = 'object'
             AND scaler->'channels' =
                 '["temperature_c", "relative_humidity_pct"]'::jsonb
             AND jsonb_typeof(scaler->'minimum') = 'array'
             AND jsonb_array_length(scaler->'minimum') = 2
             AND jsonb_typeof(scaler->'maximum') = 'array'
             AND jsonb_array_length(scaler->'maximum') = 2
             AND NOT EXISTS (
                 SELECT 1
                 FROM jsonb_array_elements(
                     scaler->'minimum' || scaler->'maximum'
                 ) AS value
                 WHERE jsonb_typeof(value) <> 'number'
             )
             AND jsonb_typeof(split_boundaries) = 'object'
             AND jsonb_typeof(split_boundaries->'fit_split') = 'string'
             AND split_boundaries->>'fit_split' <> ''
             AND jsonb_typeof(segment_metadata) = 'object'
             AND (
                 segment_metadata ? 'provenance'
                 OR segment_metadata ? 'source'
             )
            THEN 'live_10'
            ELSE 'legacy_30'
        END
        """
    )
    op.execute(
        """
        UPDATE model_versions
        SET contract_status = 'legacy_30', is_selectable = FALSE
        """
    )
    op.execute(
        """
        DELETE FROM active_model_selections AS selection
        USING model_versions
        WHERE model_versions.version = selection.model_version
          AND model_versions.contract_status = 'legacy_30'
        """
    )
    op.alter_column(
        "preprocessing_snapshots",
        "contract_status",
        server_default="live_10",
    )
    op.alter_column(
        "model_versions",
        "contract_status",
        server_default="live_10",
    )

    op.drop_constraint(
        "ck_preprocessing_window_stride_transition",
        "preprocessing_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        "ck_preprocessing_contract_status",
        "preprocessing_snapshots",
        "(contract_status = 'live_10' "
        f"AND channels = {_CANONICAL_CHANNELS} "
        "AND window_size = 10 AND stride = 1) OR "
        "(contract_status = 'legacy_30' "
        "AND window_size IN (10, 30) AND stride = 1)",
    )
    op.create_check_constraint(
        "ck_model_versions_contract_status",
        "model_versions",
        "(contract_status = 'live_10' "
        f"AND channels = {_CANONICAL_CHANNELS} "
        "AND window_size = 10 AND stride = 1) OR "
        "(contract_status = 'legacy_30' "
        "AND window_size IN (10, 30) AND stride = 1)",
    )
    op.create_check_constraint(
        "ck_model_versions_live_hashes",
        "model_versions",
        "contract_status = 'legacy_30' OR ("
        "model_manifest_sha256 ~ '^[0-9a-f]{64}$' AND "
        "checkpoint_sha256 ~ '^[0-9a-f]{64}$' AND "
        "scaler_manifest_sha256 ~ '^[0-9a-f]{64}$' AND "
        "scaler_sha256 ~ '^[0-9a-f]{64}$')",
    )
    op.create_unique_constraint(
        "uq_preprocessing_snapshots_live_identity",
        "preprocessing_snapshots",
        ["corpus_id", "contract_status"],
    )
    op.create_unique_constraint(
        "uq_model_versions_live_artifact_identity",
        "model_versions",
        [
            "version",
            "contract_status",
            "model_manifest_sha256",
            "checkpoint_sha256",
            "scaler_manifest_sha256",
            "scaler_sha256",
        ],
    )


def downgrade() -> None:
    raise RuntimeError("live model contract rollback requires database restore")
