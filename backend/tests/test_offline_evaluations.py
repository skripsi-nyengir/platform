import hashlib
import json
from importlib import resources
from typing import cast

import pytest
from anomaly_backend.main import app
from fastapi.testclient import TestClient
from httpx import Response

EXPECTED_EVALUATION = {
    "model_family": "lstm",
    "model_sha256": "f26a67d378c4b5a90e64f7dc3844d2971cb414d1bf60926fefa188b13df99212",
    "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
    "forward_validation": {
        "recon_max_abs_diff": 0.0007296204566955566,
        "score_rel_error": 0.003807021537795663,
        "passed": True,
    },
    "threshold": {
        "value": 0.0004298445419408381,
        "policy": "clean_val_quantile",
        "alpha": 0.01,
        "comparison": "strict_gt",
    },
    "n_val_windows": 105338,
    "n_test_windows": 105564,
    "n_events": 28,
    "n_positive_windows": 1489,
    "metrics": {
        "window_precision": 0.46153846153846156,
        "window_recall": 0.8381464069845533,
        "window_f1": 0.5952778440257572,
        "event_hit_rate": 0.9285714285714286,
        "event_hit_by_family": {
            "spike": 1.0,
            "contextual_shift": 1.0,
            "gradual_slope": 1.0,
            "stuck": 1.0,
            "dropout": 1.0,
            "coe": 0.5,
        },
        "clean_test_fpr": 0.013792580804061991,
        "composite_fc1": 0.6166007905138341,
        "alert_rate": 4.629043085272344,
    },
    "provenance": {
        "forward": (
            "reverse-engineered from state-dict + hyperparams, validated against "
            "artifact validation_reconstruction.npz"
        ),
        "torch_version": "2.12.1+cu130",
        "computed_at": "2026-07-28T18:34:58.085621Z",
    },
}


def test_offline_evaluations_fixture_matches_pinned_sha() -> None:
    from anomaly_backend.offline_evaluations import (
        FIXTURE_PATH,
        FIXTURE_SHA256,
        load_offline_evaluations,
    )

    payload = resources.files("anomaly_backend").joinpath(FIXTURE_PATH).read_bytes()

    assert hashlib.sha256(payload).hexdigest() == FIXTURE_SHA256
    assert [
        item.model_dump(mode="json") for item in load_offline_evaluations()
    ] == [EXPECTED_EVALUATION]


def test_loader_rejects_fixture_sha_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from anomaly_backend import offline_evaluations

    monkeypatch.setattr(offline_evaluations, "FIXTURE_SHA256", "0" * 64)

    with pytest.raises(
        offline_evaluations.OfflineEvaluationsIntegrityError,
        match="SHA-256 mismatch",
    ):
        _ = offline_evaluations.load_offline_evaluations()


def test_fixture_shape_validation_rejects_incomplete_threshold() -> None:
    from anomaly_backend.offline_evaluations import (
        OfflineEvaluationsIntegrityError,
        normalize_offline_evaluations,
    )

    payload = {"items": [json.loads(json.dumps(EXPECTED_EVALUATION))]}
    del payload["items"][0]["threshold"]["comparison"]

    with pytest.raises(OfflineEvaluationsIntegrityError, match="invalid shape"):
        _ = normalize_offline_evaluations(payload)


def test_offline_evaluations_endpoint_returns_report() -> None:
    with TestClient(app) as client:
        response = cast(
            Response,
            client.get(  # pyright: ignore[reportUnknownMemberType]
                "/api/offline-evaluations"
            ),
        )

    assert response.status_code == 200
    assert response.json() == {"items": [EXPECTED_EVALUATION]}
