from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import ClassVar, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.sql.live import LIVE_DEVICE_ID
from anomaly_worker.artifact_scorer import (
    ArtifactBundleError,
    ArtifactDescriptor,
    ArtifactScorer,
)
from anomaly_worker.scorer import CHANNELS, FloatChannels


class LiveModelUnavailable(RuntimeError):
    retryable: ClassVar[bool] = True


@dataclass(frozen=True, slots=True)
class LiveModelIdentity:
    model_pair_id: UUID
    activation_id: int
    snapshot_corpus_id: str


@dataclass(frozen=True, slots=True)
class IngressModelBinding:
    identity: LiveModelIdentity
    ingress_generation: int
    continuity_epoch: int


@dataclass(frozen=True, slots=True)
class ModelChangeMarker:
    request_id: UUID
    after_ingress_sequence: int | None
    binding: IngressModelBinding


class LiveActivationControl:
    def __init__(
        self,
        identity: LiveModelIdentity,
        *,
        ingress_generation: int,
        continuity_epoch: int,
    ) -> None:
        self._identity = identity
        self._ingress_generation = ingress_generation
        self._continuity_epoch = continuity_epoch

    def capture(self) -> IngressModelBinding:
        return IngressModelBinding(
            identity=self._identity,
            ingress_generation=self._ingress_generation,
            continuity_epoch=self._continuity_epoch,
        )

    def activate(
        self,
        identity: LiveModelIdentity,
        *,
        request_id: UUID,
        after_ingress_sequence: int | None,
    ) -> ModelChangeMarker:
        if identity.activation_id <= self._identity.activation_id:
            raise ValueError("live activation_id must increase")
        if after_ingress_sequence is not None and after_ingress_sequence < 1:
            raise ValueError("activation anchor must be a positive ingress_sequence")
        self._identity = identity
        self._ingress_generation += 1
        self._continuity_epoch += 1
        return ModelChangeMarker(
            request_id=request_id,
            after_ingress_sequence=after_ingress_sequence,
            binding=self.capture(),
        )


@dataclass(frozen=True, slots=True)
class LoadedLiveModel:
    identity: LiveModelIdentity
    model_version: str
    threshold: float
    threshold_policy: Mapping[str, object]
    minimum: FloatChannels
    maximum: FloatChannels
    scorer: ArtifactScorer
    reset_required: bool

    def scale_pair(self, value: FloatChannels) -> FloatChannels:
        return (
            (value[0] - self.minimum[0]) / (self.maximum[0] - self.minimum[0]),
            (value[1] - self.minimum[1]) / (self.maximum[1] - self.minimum[1]),
        )


async def load_live_model(
    connection: AsyncConnection,
    *,
    device_id: str = LIVE_DEVICE_ID,
    activation_id: int | None = None,
    previous_identity: LiveModelIdentity | None = None,
) -> LoadedLiveModel:
    selection = (
        tables.live_model_selections
        if activation_id is None
        else tables.live_model_activations
    )
    predicate = selection.c.device_id == device_id
    if activation_id is not None:
        predicate = predicate & (selection.c.activation_id == activation_id)
    row = (
        (
            await connection.execute(
                select(
                    selection.c.model_pair_id,
                    selection.c.activation_id,
                    tables.live_model_pairs.c.model_version,
                    tables.live_model_pairs.c.scaler_snapshot_corpus_id,
                    tables.live_model_pairs.c.threshold,
                    tables.live_model_pairs.c.model_manifest_sha256,
                    tables.live_model_pairs.c.checkpoint_sha256,
                    tables.live_model_pairs.c.scaler_manifest_sha256,
                    tables.live_model_pairs.c.scaler_sha256,
                    tables.model_versions.c.schema_version,
                    tables.model_versions.c.channels.label("model_channels"),
                    tables.model_versions.c.window_size,
                    tables.model_versions.c.stride,
                    tables.model_versions.c.threshold_policy,
                    tables.model_versions.c.temporal_semantics,
                    tables.model_versions.c.source_config,
                    tables.preprocessing_snapshots.c.channels.label(
                        "snapshot_channels"
                    ),
                    tables.preprocessing_snapshots.c.window_size.label(
                        "snapshot_window_size"
                    ),
                    tables.preprocessing_snapshots.c.stride.label("snapshot_stride"),
                    tables.preprocessing_snapshots.c.scaler,
                )
                .select_from(selection)
                .join(
                    tables.live_model_pairs,
                    tables.live_model_pairs.c.model_pair_id
                    == selection.c.model_pair_id,
                )
                .join(
                    tables.model_versions,
                    tables.model_versions.c.version
                    == tables.live_model_pairs.c.model_version,
                )
                .join(
                    tables.preprocessing_snapshots,
                    tables.preprocessing_snapshots.c.corpus_id
                    == tables.live_model_pairs.c.scaler_snapshot_corpus_id,
                )
                .where(predicate)
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        message = (
            "no active live model selection"
            if activation_id is None
            else "prepared live model activation is unavailable"
        )
        raise LiveModelUnavailable(message)

    try:
        if (
            tuple(row["model_channels"]) != CHANNELS
            or tuple(row["snapshot_channels"]) != CHANNELS
        ):
            raise ArtifactBundleError("active model channel contract is invalid")
        if (
            row["window_size"] != 10
            or row["snapshot_window_size"] != 10
            or row["stride"] != 1
            or row["snapshot_stride"] != 1
            or row["temporal_semantics"] != "context_end"
        ):
            raise ArtifactBundleError("active model temporal contract is invalid")
        hashes = {
            "model_manifest_sha256": str(row["model_manifest_sha256"]),
            "checkpoint_sha256": str(row["checkpoint_sha256"]),
            "scaler_manifest_sha256": str(row["scaler_manifest_sha256"]),
            "scaler_sha256": str(row["scaler_sha256"]),
        }
        source_config_value = row["source_config"]
        if not isinstance(source_config_value, str):
            raise ArtifactBundleError("active model source_config is invalid")
        source_config = json.loads(source_config_value)
        if not isinstance(source_config, dict):
            raise ArtifactBundleError("active model source_config is invalid")
        bundle_id = source_config.get("bundle_id")
        if not isinstance(bundle_id, str) or not bundle_id:
            raise ArtifactBundleError("active model bundle identity is invalid")
        artifacts_path = os.environ.get("MODEL_ARTIFACTS_PATH")
        if not artifacts_path:
            raise ArtifactBundleError("MODEL_ARTIFACTS_PATH is required")
        descriptor = ArtifactDescriptor.load(
            Path(artifacts_path),
            bundle_id,
            expected_hashes=hashes,
        )
        if descriptor.model_version != row["model_version"]:
            raise ArtifactBundleError("selected bundle model version is not active")
        if descriptor.schema_version != row["schema_version"]:
            raise ArtifactBundleError("selected bundle schema version is not active")
        if descriptor.threshold != float(row["threshold"]):
            raise ArtifactBundleError("selected bundle threshold is not active")
        if descriptor.threshold_policy != row["threshold_policy"]:
            raise ArtifactBundleError("selected bundle threshold policy is not active")
        if descriptor.scaler != row["scaler"]:
            raise ArtifactBundleError("active scaler snapshot differs from manifest")
        minimum = descriptor.minimum
        maximum = descriptor.maximum
        if not all(math.isfinite(value) for value in (*minimum, *maximum)):
            raise ArtifactBundleError("active scaler contains non-finite values")
        scorer = ArtifactScorer(descriptor)
    except (ArtifactBundleError, KeyError, OSError, TypeError, ValueError) as error:
        raise LiveModelUnavailable(str(error)) from error

    identity = LiveModelIdentity(
        model_pair_id=cast(UUID, row["model_pair_id"]),
        activation_id=cast(int, row["activation_id"]),
        snapshot_corpus_id=cast(str, row["scaler_snapshot_corpus_id"]),
    )
    return LoadedLiveModel(
        identity=identity,
        model_version=descriptor.model_version,
        threshold=descriptor.threshold,
        threshold_policy=MappingProxyType(dict(descriptor.threshold_policy)),
        minimum=minimum,
        maximum=maximum,
        scorer=scorer,
        reset_required=previous_identity is not None and previous_identity != identity,
    )
