from __future__ import annotations

import hashlib
import json
from importlib import resources
from typing import cast

from pydantic import ValidationError

from anomaly_backend.contracts import OfflineEvaluationItem, OfflineEvaluationsResponse

FIXTURE_PATH = "fixtures/offline_eval/offline_evaluations.json"
FIXTURE_SHA256 = "d530329696f947e37c63760ba026dd0df3736cafacd213b7d02a08a573fb5861"


class OfflineEvaluationsIntegrityError(ValueError):
    pass


def normalize_offline_evaluations(payload: object) -> list[OfflineEvaluationItem]:
    try:
        response = OfflineEvaluationsResponse.model_validate(payload, strict=True)
    except ValidationError as error:
        raise OfflineEvaluationsIntegrityError(
            "offline evaluations fixture has an invalid shape"
        ) from error
    return response.items


def load_offline_evaluations() -> list[OfflineEvaluationItem]:
    payload = resources.files("anomaly_backend").joinpath(FIXTURE_PATH).read_bytes()
    if hashlib.sha256(payload).hexdigest() != FIXTURE_SHA256:
        raise OfflineEvaluationsIntegrityError(
            f"{FIXTURE_PATH} SHA-256 mismatch: expected {FIXTURE_SHA256}"
        )
    try:
        parsed = cast(object, json.loads(payload))
    except json.JSONDecodeError as error:
        raise OfflineEvaluationsIntegrityError(
            f"{FIXTURE_PATH} must contain valid JSON"
        ) from error
    return normalize_offline_evaluations(parsed)
