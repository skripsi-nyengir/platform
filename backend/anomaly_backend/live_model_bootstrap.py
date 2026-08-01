from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.sql.live import (
    LIVE_DEVICE_ID,
    apply_live_activation,
    register_live_artifact,
    request_live_activation,
)
from anomaly_worker.artifact_scorer import (
    ArtifactBundleError,
    ArtifactDescriptor,
    ArtifactScorer,
)
from anomaly_worker.scorer import CHANNELS


LiveModelBundleError = ArtifactBundleError


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


@dataclass(frozen=True, slots=True)
class LiveModelBootstrapResult:
    model_version: str
    model_pair_id: UUID
    request_id: UUID
    activation_id: int | None
    activated: bool
    idempotent: bool


async def bootstrap_live_model(
    connection: AsyncConnection,
    *,
    device_id: str = LIVE_DEVICE_ID,
) -> LiveModelBootstrapResult:
    descriptor = ArtifactDescriptor.from_environ()
    _ = ArtifactScorer(descriptor)

    snapshot_identity = hashlib.sha256(
        _canonical_json(
            {
                "scaler_manifest_sha256": descriptor.scaler_manifest_sha256,
                "scaler_sha256": descriptor.scaler_sha256,
                "source": descriptor.source,
            }
        ).encode()
    ).hexdigest()
    corpus_id = f"live-artifact-{snapshot_identity}"
    model_key = f"live-{descriptor.architecture.rsplit('-v', 1)[0]}"
    hashes = {
        "model_manifest_sha256": descriptor.model_manifest_sha256,
        "checkpoint_sha256": descriptor.checkpoint_sha256,
        "scaler_manifest_sha256": descriptor.scaler_manifest_sha256,
        "scaler_sha256": descriptor.scaler_sha256,
    }
    source_config = _canonical_json(
        {
            "bundle_id": descriptor.bundle_id,
            "hashes": hashes,
            "snapshot_corpus_id": corpus_id,
            "snapshot_identity": snapshot_identity,
        }
    )
    now = datetime.now(timezone.utc)

    corpus_values: dict[str, object] = {
        "corpus_id": corpus_id,
        "device_id": device_id,
        "status": "published",
        "archive_sha256": descriptor.scaler_manifest_sha256,
        "member_sha256": None,
        "preprocessing_contract_version": "live-artifact-v1",
        "source_device_uuid": None,
        "time_zone": "Asia/Jakarta",
        "interval_start": None,
        "interval_end": None,
        "filter_config": {
            "artifact_owned": True,
            "bundle_id": descriptor.bundle_id,
            "snapshot_identity": snapshot_identity,
        },
        "started_at": now,
        "completed_at": now,
        "accepted_count": 0,
        "ignored_index_count": 0,
        "rejection_counts": {},
    }
    snapshot_values: dict[str, object] = {
        "corpus_id": corpus_id,
        "channels": list(CHANNELS),
        "window_size": descriptor.window_size,
        "stride": descriptor.stride,
        "contract_status": "live_10",
        "segment_metadata": {
            "provenance": {
                "bundle_id": descriptor.bundle_id,
                "scaler_manifest_sha256": descriptor.scaler_manifest_sha256,
                "source": descriptor.source,
            },
            "snapshot_identity": snapshot_identity,
        },
        "split_boundaries": {"fit_split": descriptor.fit_split},
        "split_counts": {descriptor.fit_split: 0},
        "scaler": descriptor.scaler,
    }
    family_values: dict[str, object] = {
        "model_key": model_key,
        "display_name": descriptor.architecture,
        "is_public": False,
    }
    version_values: dict[str, object] = {
        "version": descriptor.model_version,
        "model_key": model_key,
        "runtime_kind": "artifact",
        "is_selectable": True,
        "adapter_key": descriptor.architecture,
        "schema_version": descriptor.schema_version,
        "channels": list(CHANNELS),
        "window_size": descriptor.window_size,
        "stride": descriptor.stride,
        "contract_status": "live_10",
        "score_key": "global_mse",
        "score_semantics": "higher-is-more-anomalous",
        "threshold": descriptor.threshold,
        "threshold_policy": descriptor.threshold_policy,
        "temporal_semantics": descriptor.temporal_semantics.value,
        "source_commit": None,
        "source_config": source_config,
        "manifest_sha256": descriptor.model_manifest_sha256,
        **hashes,
        "created_at": now,
    }
    pair_values: dict[str, object] = {
        "model_version": descriptor.model_version,
        "checkpoint_identity": f"sha256:{descriptor.checkpoint_sha256}",
        "scaler_snapshot_corpus_id": corpus_id,
        **hashes,
        "threshold": descriptor.threshold,
        "contract_status": "live_10",
    }

    async with connection.begin():
        pair, pair_created = await register_live_artifact(
            connection,
            corpus_values=corpus_values,
            snapshot_values=snapshot_values,
            family_values=family_values,
            version_values=version_values,
            pair_values=pair_values,
        )
        model_pair_id = cast(UUID, pair["model_pair_id"])
        request, request_duplicate = await request_live_activation(
            connection,
            device_id=device_id,
            model_pair_id=model_pair_id,
            requested_by="live-model-bootstrap",
        )
        request_id = cast(UUID, request["request_id"])
        selection = (
            (
                await connection.execute(
                    select(tables.live_model_selections).where(
                        tables.live_model_selections.c.device_id == device_id
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        activation = None
        activation_duplicate = False
        if selection is None or selection["model_pair_id"] == model_pair_id:
            activation, activation_duplicate = await apply_live_activation(
                connection,
                request_id=request_id,
                device_id=device_id,
                model_pair_id=model_pair_id,
                fencing_token=None,
            )

    return LiveModelBootstrapResult(
        model_version=descriptor.model_version,
        model_pair_id=model_pair_id,
        request_id=request_id,
        activation_id=(
            None if activation is None else cast(int, activation["activation_id"])
        ),
        activated=activation is not None,
        idempotent=(not pair_created and request_duplicate and activation_duplicate),
    )


async def _main() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            _ = await bootstrap_live_model(connection)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
