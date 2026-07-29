"""GPU artifact-inference scorer.

Runs a trained reconstruction autoencoder on the batch's normalized windows and
returns the per-window global mean-squared reconstruction error. This is a real
model score, unlike the deterministic preview simulator. CUDA is mandatory: an
artifact job fails loudly rather than silently scoring on CPU.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

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


_ARTIFACT_DIRS = {
    "artifact-lstm-ae-v3": "lstm",
    "artifact-conv1d-v3": "conv1d",
    "artifact-transformer-v3": "transformer",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ArtifactScorer:
    def __init__(
        self,
        model_version: str,
        manifest_sha256: str,
        temporal_semantics: TemporalSemantics = TemporalSemantics.CONTEXT_END,
    ) -> None:
        if not torch.cuda.is_available():
            raise ScorerProtocolError(
                "artifact inference requires CUDA, which is unavailable"
            )
        directory = _ARTIFACT_DIRS.get(model_version)
        if directory is None:
            raise ScorerProtocolError(
                f"no artifact weights registered for {model_version!r}"
            )
        root = Path(os.environ.get("MODEL_ARTIFACTS_PATH", "/models"))
        checkpoint_path = root / directory / "model.pt"
        if not checkpoint_path.is_file():
            raise ScorerProtocolError(f"artifact weights missing at {checkpoint_path}")
        actual = _sha256(checkpoint_path)
        if actual != manifest_sha256:
            raise ScorerProtocolError(
                f"artifact weights sha256 {actual} do not match "
                f"registry manifest {manifest_sha256}"
            )
        self.model_version = model_version
        self.temporal_semantics = temporal_semantics
        self._device = torch.device("cuda")
        checkpoint = torch.load(
            checkpoint_path, map_location=self._device, weights_only=True
        )
        self._model = (
            build_model(model_version, checkpoint["state_dict"])
            .to(self._device)
            .eval()
        )

    def score(self, batch: ScoreBatch) -> ScoreBatchResult:
        validate_batch(batch, self.temporal_semantics)
        inputs = torch.tensor(
            batch.model_values, dtype=torch.float32, device=self._device
        )
        with torch.no_grad():
            reconstruction = self._model(inputs)
            errors = (inputs - reconstruction).square().mean(dim=(1, 2))
        scores = errors.cpu().tolist()
        # CONTEXT_END scores the window's last sample, so its reconstruction is
        # the model's expected signal at score_ts (the tolerance-band centre).
        recon_at_target = (
            reconstruction[:, -1, :].cpu().tolist()
            if self.temporal_semantics is TemporalSemantics.CONTEXT_END
            else None
        )
        points = tuple(
            ScorePoint(
                score_ts=batch.target_ts[index],
                score=float(scores[index]),
                reconstruction=(
                    tuple(float(value) for value in recon_at_target[index])
                    if recon_at_target is not None
                    else None
                ),
            )
            for index in range(batch.size)
        )
        result = ScoreBatchResult(points=points)
        validate_result(batch, result, self.temporal_semantics)
        return result
