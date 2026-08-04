"""Device-aware artifact inference with strict deployment-bundle verification."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
from typing import cast

import torch

from .architectures import build_model
from .scorer import (
    ScoreBatch,
    ScoreBatchResult,
    ScorePoint,
    ScorerProtocolError,
    TemporalSemantics,
    validate_batch,
    validate_result,
)


_SHA256 = re.compile(r"[0-9a-f]{64}")
_SOURCE_CHANNELS = ("suhu", "rh")
_LIVE_SCHEMA_VERSION = "b02-live-v1"
_INFERENCE_DEVICE_ENV = "INFERENCE_DEVICE"
_INFERENCE_DEVICES = {"cpu", "cuda"}
_DATASET_SPLITS = {"train", "validation", "test"}
_MODEL_MANIFEST_FIELDS = {
    "architecture",
    "bundle_id",
    "channels",
    "checkpoint_file",
    "checkpoint_sha256",
    "manifest_version",
    "model_version",
    "scaler_manifest_file",
    "scaler_manifest_sha256",
    "schema_version",
    "stride",
    "temporal_semantics",
    "threshold",
    "threshold_policy",
    "window_size",
}
_SCALER_MANIFEST_FIELDS = {
    "channels",
    "fit_split",
    "manifest_version",
    "maximum",
    "minimum",
    "scaler_sha256",
    "source",
}
_THRESHOLD_POLICY_FIELDS = {"comparison", "fit_split", "name"}


class ArtifactBundleError(ScorerProtocolError):
    pass


def _sha256(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        raise ArtifactBundleError(
            f"artifact file {path.name!r} cannot be hashed"
        ) from error


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    except (TypeError, ValueError) as error:
        raise ArtifactBundleError("artifact manifest is not canonical JSON") from error


def _read_json(path: Path, label: str) -> dict[str, object]:
    def object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise ArtifactBundleError(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    try:
        value = json.loads(path.read_bytes(), object_pairs_hook=object_from_pairs)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ArtifactBundleError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ArtifactBundleError(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _require_schema(value: Mapping[str, object], fields: set[str], label: str) -> None:
    if set(value) != fields:
        raise ArtifactBundleError(f"{label} does not match the required schema")


def _required_integer(value: object, expected: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value != expected:
        raise ArtifactBundleError(f"{field} must equal integer {expected}")
    return value


def _single_sidecar(bundle: Path, pattern: str, label: str) -> Path:
    try:
        matches = list(bundle.glob(pattern))
    except OSError as error:
        raise ArtifactBundleError(f"selected bundle cannot be inspected for {label}") from error
    if len(matches) != 1:
        raise ArtifactBundleError(f"bundle must contain exactly one {label}")
    try:
        resolved = matches[0].resolve()
        is_file = resolved.is_file()
    except OSError as error:
        raise ArtifactBundleError(f"selected bundle {label} cannot be resolved") from error
    if resolved.parent != bundle:
        raise ArtifactBundleError(f"{label} must remain inside the selected bundle")
    if not is_file:
        raise ArtifactBundleError(f"bundle must contain exactly one {label}")
    return resolved


def _required_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ArtifactBundleError(f"{field} must be a non-empty string")
    return value


def _required_sha(value: object, field: str) -> str:
    digest = _required_string(value, field)
    if _SHA256.fullmatch(digest) is None:
        raise ArtifactBundleError(f"{field} must be a lowercase SHA-256")
    return digest


def _finite_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ArtifactBundleError(f"{field} must be numeric")
    converted = float(value)
    if not math.isfinite(converted):
        raise ArtifactBundleError(f"{field} must be finite")
    return converted


def _require_source_channels(value: object, field: str) -> None:
    if not isinstance(value, list) or tuple(value) != _SOURCE_CHANNELS:
        raise ArtifactBundleError(f"{field} must be exactly [suhu, rh]")


def _resolved_member(bundle: Path, filename: object, field: str) -> Path:
    name = _required_string(filename, field)
    if Path(name).name != name:
        raise ArtifactBundleError(f"{field} must not escape the selected bundle")
    try:
        path = (bundle / name).resolve()
        is_file = path.is_file()
    except OSError as error:
        raise ArtifactBundleError(f"{field} cannot be resolved") from error
    if path.parent != bundle or not is_file:
        raise ArtifactBundleError(f"{field} is missing from the selected bundle")
    return path


@dataclass(frozen=True, slots=True)
class ArtifactDescriptor:
    bundle_id: str
    bundle_path: Path
    model_manifest_path: Path
    scaler_manifest_path: Path
    checkpoint_path: Path
    model_version: str
    architecture: str
    schema_version: str
    window_size: int
    stride: int
    temporal_semantics: TemporalSemantics
    threshold: float
    threshold_policy: dict[str, object]
    minimum: tuple[float, float]
    maximum: tuple[float, float]
    fit_split: str
    source: dict[str, object]
    scaler: dict[str, object]
    model_manifest_sha256: str
    checkpoint_sha256: str
    scaler_manifest_sha256: str
    scaler_sha256: str

    @classmethod
    def from_environ(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        expected_hashes: Mapping[str, str] | None = None,
    ) -> "ArtifactDescriptor":
        values = os.environ if environ is None else environ
        root = values.get("MODEL_ARTIFACTS_PATH")
        if not root:
            raise ArtifactBundleError("MODEL_ARTIFACTS_PATH is required")
        bundle_id = values.get("LIVE_MODEL_BUNDLE_ID")
        if not bundle_id:
            raise ArtifactBundleError("LIVE_MODEL_BUNDLE_ID is required")
        return cls.load(Path(root), bundle_id, expected_hashes=expected_hashes)

    @classmethod
    def load(
        cls,
        artifacts_path: Path,
        bundle_id: str,
        *,
        expected_hashes: Mapping[str, str] | None = None,
    ) -> "ArtifactDescriptor":
        try:
            root = artifacts_path.resolve()
        except OSError as error:
            raise ArtifactBundleError("MODEL_ARTIFACTS_PATH cannot be resolved") from error
        if Path(bundle_id).name != bundle_id or bundle_id in {".", ".."}:
            raise ArtifactBundleError(
                "LIVE_MODEL_BUNDLE_ID must not escape the mounted path"
            )
        try:
            bundle = (root / bundle_id).resolve()
            is_bundle = bundle.is_dir()
        except OSError as error:
            raise ArtifactBundleError("selected live model bundle cannot be resolved") from error
        if bundle.parent != root:
            raise ArtifactBundleError(
                "LIVE_MODEL_BUNDLE_ID must not escape the mounted path"
            )
        if not is_bundle:
            raise ArtifactBundleError("selected live model bundle is missing")

        model_path = _single_sidecar(
            bundle, "model-manifest-v*.json", "versioned model manifest"
        )
        scaler_path = _single_sidecar(
            bundle, "scaler-manifest-v*.json", "versioned scaler manifest"
        )
        model = _read_json(model_path, "model manifest")
        scaler = _read_json(scaler_path, "scaler manifest")
        _require_schema(model, _MODEL_MANIFEST_FIELDS, "model manifest schema")
        _require_schema(scaler, _SCALER_MANIFEST_FIELDS, "scaler manifest schema")

        model_manifest_version = _required_integer(
            model.get("manifest_version"), 1, "model manifest_version"
        )
        scaler_manifest_version = _required_integer(
            scaler.get("manifest_version"), 1, "scaler manifest_version"
        )
        if model_path.name != f"model-manifest-v{model_manifest_version}.json":
            raise ArtifactBundleError(
                "model manifest filename must match manifest_version"
            )
        if scaler_path.name != f"scaler-manifest-v{scaler_manifest_version}.json":
            raise ArtifactBundleError(
                "scaler manifest filename must match manifest_version"
            )
        if model.get("bundle_id") != bundle_id:
            raise ArtifactBundleError(
                "model manifest bundle_id does not match selection"
            )
        _require_source_channels(model.get("channels"), "model channels")
        _require_source_channels(scaler.get("channels"), "scaler channels")
        schema_version = _required_string(
            model.get("schema_version"), "model schema_version"
        )
        if schema_version != _LIVE_SCHEMA_VERSION:
            raise ArtifactBundleError(
                f"model schema_version must equal {_LIVE_SCHEMA_VERSION}"
            )

        window_size = _required_integer(model.get("window_size"), 10, "model window_size")
        stride = _required_integer(model.get("stride"), 1, "model stride")
        try:
            temporal = TemporalSemantics(model.get("temporal_semantics"))
        except (TypeError, ValueError) as error:
            raise ArtifactBundleError("model temporal semantics are invalid") from error
        if temporal is not TemporalSemantics.CONTEXT_END:
            raise ArtifactBundleError("model temporal semantics must be context_end")

        threshold = _finite_number(model.get("threshold"), "model threshold")
        if threshold <= 0:
            raise ArtifactBundleError("model threshold must be positive")
        policy_value = model.get("threshold_policy")
        if not isinstance(policy_value, dict):
            raise ArtifactBundleError("model threshold policy must be an object")
        _require_schema(
            policy_value,
            _THRESHOLD_POLICY_FIELDS,
            "model threshold policy schema",
        )
        if policy_value.get("comparison") != ">":
            raise ArtifactBundleError("model threshold policy must compare with >")
        policy_split = _required_string(
            policy_value.get("fit_split"), "threshold policy fit_split"
        )
        if policy_split not in _DATASET_SPLITS:
            raise ArtifactBundleError("threshold policy fit_split is invalid")
        _required_string(policy_value.get("name"), "threshold policy name")
        threshold_policy = cast(dict[str, object], dict(policy_value))

        minimum_value = scaler.get("minimum")
        maximum_value = scaler.get("maximum")
        if not isinstance(minimum_value, list) or len(minimum_value) != 2:
            raise ArtifactBundleError("scaler minimum must contain exactly two values")
        if not isinstance(maximum_value, list) or len(maximum_value) != 2:
            raise ArtifactBundleError("scaler maximum must contain exactly two values")
        minimum = (
            _finite_number(minimum_value[0], "scaler minimum"),
            _finite_number(minimum_value[1], "scaler minimum"),
        )
        maximum = (
            _finite_number(maximum_value[0], "scaler maximum"),
            _finite_number(maximum_value[1], "scaler maximum"),
        )
        if any(high <= low for low, high in zip(minimum, maximum, strict=True)):
            raise ArtifactBundleError("scaler maximum must be greater than minimum")
        fit_split = _required_string(scaler.get("fit_split"), "scaler fit_split")
        if fit_split not in _DATASET_SPLITS:
            raise ArtifactBundleError("scaler fit_split is invalid")

        source_value = scaler.get("source")
        if not isinstance(source_value, dict) or set(source_value) != {
            "identity",
            "sha256",
        }:
            raise ArtifactBundleError("scaler source must contain identity and sha256")
        source = cast(dict[str, object], dict(source_value))
        source_identity = _required_string(
            source.get("identity"), "scaler source identity"
        )
        source_sha = _required_sha(source.get("sha256"), "scaler source sha256")
        if hashlib.sha256(source_identity.encode()).hexdigest() != source_sha:
            raise ArtifactBundleError("scaler source hash does not match its identity")

        declared_scaler_sha = _required_sha(
            scaler.get("scaler_sha256"), "scaler canonical SHA-256"
        )
        canonical_scaler = dict(scaler)
        _ = canonical_scaler.pop("scaler_sha256")
        actual_scaler_sha = hashlib.sha256(
            _canonical_bytes(canonical_scaler)
        ).hexdigest()
        if actual_scaler_sha != declared_scaler_sha:
            raise ArtifactBundleError("scaler canonical SHA-256 does not match content")

        checkpoint_path = _resolved_member(
            bundle, model.get("checkpoint_file"), "checkpoint_file"
        )
        try:
            checkpoints = [path.resolve() for path in bundle.glob("*.pt")]
        except OSError as error:
            raise ArtifactBundleError("bundle checkpoints cannot be inspected") from error
        if len(checkpoints) != 1 or checkpoints[0] != checkpoint_path:
            raise ArtifactBundleError("bundle must contain exactly one checkpoint")
        referenced_scaler_path = _resolved_member(
            bundle, model.get("scaler_manifest_file"), "scaler_manifest_file"
        )
        if referenced_scaler_path != scaler_path:
            raise ArtifactBundleError("model references a different scaler manifest")

        actual_checkpoint_sha = _sha256(checkpoint_path)
        declared_checkpoint_sha = _required_sha(
            model.get("checkpoint_sha256"), "checkpoint_sha256"
        )
        if actual_checkpoint_sha != declared_checkpoint_sha:
            raise ArtifactBundleError(
                "checkpoint SHA-256 does not match model manifest"
            )
        actual_scaler_manifest_sha = _sha256(scaler_path)
        declared_scaler_manifest_sha = _required_sha(
            model.get("scaler_manifest_sha256"), "scaler_manifest_sha256"
        )
        if actual_scaler_manifest_sha != declared_scaler_manifest_sha:
            raise ArtifactBundleError(
                "scaler manifest SHA-256 does not match model manifest"
            )
        actual_model_manifest_sha = _sha256(model_path)

        hashes = {
            "model_manifest_sha256": actual_model_manifest_sha,
            "checkpoint_sha256": actual_checkpoint_sha,
            "scaler_manifest_sha256": actual_scaler_manifest_sha,
            "scaler_sha256": actual_scaler_sha,
        }
        if len(set(hashes.values())) != len(hashes):
            raise ArtifactBundleError("artifact hashes must be independently distinct")
        for field, expected in (expected_hashes or {}).items():
            if field not in hashes:
                raise ArtifactBundleError(f"unknown expected artifact hash {field}")
            if hashes[field] != expected:
                label = field.replace("_", " ").replace("sha256", "SHA-256")
                raise ArtifactBundleError(f"{label} does not match active registry")

        return cls(
            bundle_id=bundle_id,
            bundle_path=bundle,
            model_manifest_path=model_path,
            scaler_manifest_path=scaler_path,
            checkpoint_path=checkpoint_path,
            model_version=_required_string(model.get("model_version"), "model_version"),
            architecture=_required_string(model.get("architecture"), "architecture"),
            schema_version=schema_version,
            window_size=window_size,
            stride=stride,
            temporal_semantics=temporal,
            threshold=threshold,
            threshold_policy=threshold_policy,
            minimum=minimum,
            maximum=maximum,
            fit_split=fit_split,
            source=source,
            scaler=scaler,
            **hashes,
        )


def _cuda_device() -> torch.device:
    return torch.device("cuda")


def _inference_device() -> torch.device:
    configured = os.environ.get(_INFERENCE_DEVICE_ENV, "cuda")
    if configured not in _INFERENCE_DEVICES:
        raise ArtifactBundleError(f"{_INFERENCE_DEVICE_ENV} must be one of: cpu, cuda")
    if configured == "cuda":
        if not torch.cuda.is_available():
            raise ArtifactBundleError(
                "artifact inference requires CUDA, which is unavailable"
            )
        return _cuda_device()
    return torch.device("cpu")


class ArtifactScorer:
    def __init__(self, descriptor: ArtifactDescriptor) -> None:
        self.model_version = descriptor.model_version
        self.temporal_semantics = descriptor.temporal_semantics
        self._device = _inference_device()
        try:
            if _sha256(descriptor.checkpoint_path) != descriptor.checkpoint_sha256:
                raise ArtifactBundleError(
                    "checkpoint SHA-256 changed after bundle validation"
                )
            checkpoint = torch.load(
                descriptor.checkpoint_path,
                map_location=self._device,
                weights_only=True,
            )
            state_dict = checkpoint["state_dict"]
            if not isinstance(state_dict, dict):
                raise TypeError("state_dict must be a mapping")
            self._model = (
                build_model(descriptor.architecture, state_dict).to(self._device).eval()
            )
        except ArtifactBundleError:
            raise
        except (KeyError, OSError, RuntimeError, TypeError, ValueError) as error:
            raise ArtifactBundleError("artifact checkpoint cannot be loaded") from error

    def score(self, batch: ScoreBatch) -> ScoreBatchResult:
        validate_batch(batch, self.temporal_semantics)
        if batch.model_version != self.model_version:
            raise ScorerProtocolError(
                "batch model_version does not match loaded artifact"
            )
        inputs = torch.tensor(
            batch.model_values, dtype=torch.float32, device=self._device
        )
        with torch.no_grad():
            reconstruction = self._model(inputs)
            errors = (inputs - reconstruction).square().mean(dim=(1, 2))
        scores = errors.cpu().tolist()
        recon_at_target = reconstruction[:, -1, :].cpu().tolist()
        points = tuple(
            ScorePoint(
                score_ts=batch.target_ts[index],
                score=float(scores[index]),
                reconstruction=tuple(float(value) for value in recon_at_target[index]),
            )
            for index in range(batch.size)
        )
        result = ScoreBatchResult(points=points)
        validate_result(batch, result, self.temporal_semantics)
        return result
