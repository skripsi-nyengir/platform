from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import cast

from pydantic import ValidationError

from anomaly_backend.contracts import ModelRegistryItem, ModelRegistryResponse

FIXTURE_PATH = "fixtures/model_registry/reported_models.json"
FIXTURE_SHA256 = "b0dcd9a5b44a8daf3d6ecc92d5b5c80c077c0ebcb0bc6fb412041b5e9756cdbe"

_RECURRENT_ARCHITECTURE: dict[str, int | float] = {
    "hidden_size": 32,
    "latent_size": 8,
    "layers": 2,
    "dropout": 0.1,
}

_EXPECTED_MODELS: dict[str, tuple[str, dict[str, int | float]]] = {
    "conv1d_step5": ("conv1d", {"latent_channels": 16}),
    "gru_step5": ("gru", dict(_RECURRENT_ARCHITECTURE)),
    "lstm_step5": ("lstm", dict(_RECURRENT_ARCHITECTURE)),
    "rnn_step5": ("rnn", dict(_RECURRENT_ARCHITECTURE)),
    "transformer_step5": (
        "transformer",
        {
            "d_model": 32,
            "n_heads": 4,
            "encoder_layers": 2,
            "decoder_layers": 2,
            "ff_dim": 64,
            "dropout": 0.1,
        },
    ),
}


class ModelRegistryIntegrityError(ValueError):
    pass


def normalize_reported_models(payload: object) -> list[ModelRegistryItem]:
    try:
        response = ModelRegistryResponse.model_validate(payload, strict=True)
    except ValidationError as error:
        raise ModelRegistryIntegrityError(
            "reported model registry has an invalid shape"
        ) from error

    if [item.id for item in response.items] != list(_EXPECTED_MODELS):
        raise ModelRegistryIntegrityError(
            "reported model registry must contain the five expected models"
        )
    for item in response.items:
        family, architecture = _EXPECTED_MODELS[item.id]
        if item.family != family or item.architecture != architecture:
            raise ModelRegistryIntegrityError(
                f"reported model registry architecture mismatch for {item.id}"
            )
    return response.items


def load_reported_models() -> list[ModelRegistryItem]:
    payload = resources.files("anomaly_backend").joinpath(FIXTURE_PATH).read_bytes()
    if hashlib.sha256(payload).hexdigest() != FIXTURE_SHA256:
        raise ModelRegistryIntegrityError(
            f"{FIXTURE_PATH} SHA-256 mismatch: expected {FIXTURE_SHA256}"
        )
    try:
        parsed = cast(object, json.loads(payload))
    except json.JSONDecodeError as error:
        raise ModelRegistryIntegrityError(
            f"{FIXTURE_PATH} must contain valid JSON"
        ) from error
    return normalize_reported_models(parsed)
