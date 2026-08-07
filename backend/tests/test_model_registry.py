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

RECURRENT_ARCHITECTURE = {
    "hidden_size": 32,
    "latent_size": 8,
    "layers": 2,
    "dropout": 0.1,
}

EXPECTED_MODELS = [
    {
        "id": "conv1d_step5",
        "family": "conv1d",
        "display_name": "Conv1D Autoencoder",
        "architecture": {"latent_channels": 16},
        "param_count": 7474,
        "best_val_mse": 2.1572509291888413e-05,
        "best_epoch": 4,
        "model_sha256": "85c901e8fed463207a44151adc14772d3660384ae88daf9fcc53431e6acc39c9",
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "window_size": 10,
        "features": ["suhu", "rh"],
        "score_semantics": "window_mean_squared_reconstruction_error",
        "report_source": "reported_model_registry",
        "summary": SUMMARY,
    },
    {
        "id": "gru_step5",
        "family": "gru",
        "display_name": "GRU Autoencoder",
        "architecture": dict(RECURRENT_ARCHITECTURE),
        "param_count": 20490,
        "best_val_mse": 6.004524724196261e-05,
        "best_epoch": 13,
        "model_sha256": "0506d1da27d92a259e62c32ce43db7fd19dfa8ad679c08c6d67bf727653a2caa",
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "window_size": 10,
        "features": ["suhu", "rh"],
        "score_semantics": "window_mean_squared_reconstruction_error",
        "report_source": "reported_model_registry",
        "summary": SUMMARY,
    },
    {
        "id": "lstm_step5",
        "family": "lstm",
        "display_name": "LSTM Autoencoder",
        "architecture": dict(RECURRENT_ARCHITECTURE),
        "param_count": 27210,
        "best_val_mse": 5.146170129209432e-05,
        "best_epoch": 24,
        "model_sha256": "0dde621c1fe4117fd57602a94c30bd764e900108ceea3675fba6295e9500cccb",
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "window_size": 10,
        "features": ["suhu", "rh"],
        "score_semantics": "window_mean_squared_reconstruction_error",
        "report_source": "reported_model_registry",
        "summary": SUMMARY,
    },
    {
        "id": "rnn_step5",
        "family": "rnn",
        "display_name": "RNN Autoencoder",
        "architecture": dict(RECURRENT_ARCHITECTURE),
        "param_count": 7050,
        "best_val_mse": 3.3277092602658214e-05,
        "best_epoch": 15,
        "model_sha256": "c801a284c95c16ce9031a24f774d941c314bc0758e7b20d593af64fb630f0ebd",
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "window_size": 10,
        "features": ["suhu", "rh"],
        "score_semantics": "window_mean_squared_reconstruction_error",
        "report_source": "reported_model_registry",
        "summary": SUMMARY,
    },
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
        "param_count": 43362,
        "best_val_mse": 3.5587262735700976e-05,
        "best_epoch": 17,
        "model_sha256": "364b0c73be1054b05a33924615d53ee1ebcb12af4bbb7d4efc0c1a144af3e015",
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "window_size": 10,
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
    del payload["items"][4]["architecture"]["d_model"]

    with pytest.raises(ModelRegistryIntegrityError, match="architecture"):
        _ = normalize_reported_models(payload)


def test_model_registry_endpoint_returns_reported_models(
    session_cookies: dict[str, str],
) -> None:
    with TestClient(app, cookies=session_cookies) as client:
        response = cast(
            Response,
            client.get(  # pyright: ignore[reportUnknownMemberType]
                "/api/model-registry"
            ),
        )

    assert response.status_code == 200
    assert response.json() == {"items": EXPECTED_MODELS}
