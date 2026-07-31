from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TypedDict
from uuid import uuid4

import torch

from anomaly_worker.architectures import LstmAutoencoder


class BundleFiles(TypedDict):
    bundle: Path
    checkpoint: Path
    scaler_manifest: Path
    model_manifest: Path
    scaler: dict[str, object]
    model: dict[str, object]


def canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_bundle(
    root: Path,
    *,
    bundle_id: str | None = None,
    model_version: str | None = None,
) -> tuple[str, BundleFiles]:
    bundle_id = bundle_id or f"approved-{uuid4().hex}"
    model_version = model_version or f"artifact-lstm-live-{uuid4().hex}"
    bundle = root / bundle_id
    bundle.mkdir(parents=True)

    checkpoint = bundle / "model.pt"
    torch.save({"state_dict": LstmAutoencoder().state_dict()}, checkpoint)

    source_identity = f"dataset://b02f3872/{uuid4().hex}"
    scaler: dict[str, object] = {
        "manifest_version": 1,
        "channels": ["suhu", "rh"],
        "minimum": [20.0, 40.0],
        "maximum": [35.0, 90.0],
        "fit_split": "train",
        "source": {
            "identity": source_identity,
            "sha256": hashlib.sha256(source_identity.encode()).hexdigest(),
        },
    }
    scaler["scaler_sha256"] = hashlib.sha256(canonical_bytes(scaler)).hexdigest()
    scaler_manifest = bundle / "scaler-manifest-v1.json"
    scaler_manifest.write_bytes(canonical_bytes(scaler))

    model: dict[str, object] = {
        "manifest_version": 1,
        "bundle_id": bundle_id,
        "model_version": model_version,
        "architecture": "artifact-lstm-ae-v3",
        "checkpoint_file": checkpoint.name,
        "checkpoint_sha256": sha256(checkpoint),
        "scaler_manifest_file": scaler_manifest.name,
        "scaler_manifest_sha256": sha256(scaler_manifest),
        "schema_version": "b02-live-v1",
        "channels": ["suhu", "rh"],
        "window_size": 10,
        "stride": 1,
        "temporal_semantics": "context_end",
        "threshold": 0.25,
        "threshold_policy": {
            "comparison": ">",
            "fit_split": "validation",
            "name": "validation-p995",
        },
    }
    model_manifest = bundle / "model-manifest-v1.json"
    model_manifest.write_bytes(canonical_bytes(model))
    files: BundleFiles = {
        "bundle": bundle,
        "checkpoint": checkpoint,
        "scaler_manifest": scaler_manifest,
        "model_manifest": model_manifest,
        "scaler": scaler,
        "model": model,
    }
    return bundle_id, files


def rewrite_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=True,
            allow_nan=True,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
