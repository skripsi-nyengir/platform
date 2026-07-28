import hashlib
import json
from importlib import resources
from typing import cast

import pytest
from anomaly_backend.main import app
from fastapi.testclient import TestClient
from httpx import Response

SUMMARY = (
    "Validation MSE reported from training; it was not computed by the "
    "platform, and no operational threshold is defined."
)

EXPECTED_MODELS = [
    {
        "id": "transformer_step5",
        "family": "transformer",
        "display_name": "Transformer Autoencoder",
        "architecture": {
            "d_model": 32,
            "n_heads": 4,
            "encoder_layers": 2,
            "decoder_layers": 2,
            "ff_dim": 64,
            "dropout": 0.1,
        },
        "param_count": 44002,
        "best_val_mse": 5.157235643571508e-05,
        "best_epoch": 8,
        "model_sha256": "21ec02b261b64f4491f0e5ecac1cbc41cba55fb7cb07d85b0596ca467e213b3b",
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "window_size": 30,
        "features": ["suhu", "rh"],
        "score_semantics": "window_mean_squared_reconstruction_error",
        "report_source": "reported_model_registry",
        "summary": SUMMARY,
    },
    {
        "id": "conv1d_step5",
        "family": "conv1d",
        "display_name": "Conv1D Autoencoder",
        "architecture": {"latent_channels": 16},
        "param_count": 7474,
        "best_val_mse": 1.8269720032613215e-05,
        "best_epoch": 5,
        "model_sha256": "189a935b547163d00505deb4f654d59ca36d7077e54b87f4b5c472cf41c5fcc6",
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "window_size": 30,
        "features": ["suhu", "rh"],
        "score_semantics": "window_mean_squared_reconstruction_error",
        "report_source": "reported_model_registry",
        "summary": SUMMARY,
    },
    {
        "id": "lstm_step5",
        "family": "lstm",
        "display_name": "LSTM Autoencoder",
        "architecture": {
            "hidden_size": 32,
            "latent_size": 16,
            "layers": 2,
            "dropout": 0.1,
        },
        "param_count": 28498,
        "best_val_mse": 4.789443077487578e-05,
        "best_epoch": 24,
        "model_sha256": "f26a67d378c4b5a90e64f7dc3844d2971cb414d1bf60926fefa188b13df99212",
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "window_size": 30,
        "features": ["suhu", "rh"],
        "score_semantics": "window_mean_squared_reconstruction_error",
        "report_source": "reported_model_registry",
        "summary": SUMMARY,
    },
]


def test_reported_models_fixture_matches_pinned_sha() -> None:
    from anomaly_backend.model_registry import (
        FIXTURE_PATH,
        FIXTURE_SHA256,
        load_reported_models,
    )

    payload = resources.files("anomaly_backend").joinpath(FIXTURE_PATH).read_bytes()

    assert hashlib.sha256(payload).hexdigest() == FIXTURE_SHA256
    assert [item.model_dump(mode="json") for item in load_reported_models()] == EXPECTED_MODELS


def test_loader_rejects_fixture_sha_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from anomaly_backend import model_registry

    monkeypatch.setattr(model_registry, "FIXTURE_SHA256", "0" * 64)

    with pytest.raises(
        model_registry.ModelRegistryIntegrityError, match="SHA-256 mismatch"
    ):
        _ = model_registry.load_reported_models()


def test_fixture_shape_validation_rejects_incomplete_architecture() -> None:
    from anomaly_backend.model_registry import (
        ModelRegistryIntegrityError,
        normalize_reported_models,
    )

    payload = {"items": json.loads(json.dumps(EXPECTED_MODELS))}
    del payload["items"][0]["architecture"]["d_model"]

    with pytest.raises(ModelRegistryIntegrityError, match="architecture"):
        _ = normalize_reported_models(payload)


def test_model_registry_endpoint_returns_reported_models() -> None:
    with TestClient(app) as client:
        response = cast(
            Response,
            client.get(  # pyright: ignore[reportUnknownMemberType]
                "/api/model-registry"
            ),
        )

    assert response.status_code == 200
    assert response.json() == {"items": EXPECTED_MODELS}
