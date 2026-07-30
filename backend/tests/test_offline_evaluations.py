import hashlib
import json
from importlib import resources
from typing import cast

import pytest
from anomaly_backend.main import app
from fastapi.testclient import TestClient
from httpx import Response

EXPECTED_MODEL_SHA256 = {
    "conv1d": "85c901e8fed463207a44151adc14772d3660384ae88daf9fcc53431e6acc39c9",
    "gru": "0506d1da27d92a259e62c32ce43db7fd19dfa8ad679c08c6d67bf727653a2caa",
    "lstm": "0dde621c1fe4117fd57602a94c30bd764e900108ceea3675fba6295e9500cccb",
    "rnn": "c801a284c95c16ce9031a24f774d941c314bc0758e7b20d593af64fb630f0ebd",
    "transformer": "364b0c73be1054b05a33924615d53ee1ebcb12af4bbb7d4efc0c1a144af3e015",
}
EXPECTED_EVENT_FAMILIES = {
    "bias",
    "data_loss",
    "drift",
    "erratic",
    "garbage",
    "spike",
    "stuck",
}


def _fixture_payload() -> dict[str, list[dict[str, object]]]:
    from anomaly_backend.offline_evaluations import FIXTURE_PATH

    parsed = json.loads(
        resources.files("anomaly_backend").joinpath(FIXTURE_PATH).read_text()
    )
    return cast(dict[str, list[dict[str, object]]], parsed)


def test_offline_evaluations_fixture_matches_pinned_sha() -> None:
    from anomaly_backend.offline_evaluations import (
        FIXTURE_PATH,
        FIXTURE_SHA256,
        load_offline_evaluations,
    )

    payload = resources.files("anomaly_backend").joinpath(FIXTURE_PATH).read_bytes()
    expected = _fixture_payload()["items"]
    loaded = [
        item.model_dump(mode="json") for item in load_offline_evaluations()
    ]

    assert hashlib.sha256(payload).hexdigest() == FIXTURE_SHA256
    assert loaded == expected
    assert [cast(str, item["model_family"]) for item in loaded] == list(
        EXPECTED_MODEL_SHA256
    )
    assert {
        cast(str, item["model_family"]): cast(str, item["model_sha256"])
        for item in loaded
    } == EXPECTED_MODEL_SHA256
    assert {
        (
            item["n_val_windows"],
            item["n_test_windows"],
            item["n_events"],
            item["n_positive_windows"],
        )
        for item in loaded
    } == {(105327, 105598, 210, 12432)}

    for item in loaded:
        family = cast(str, item["model_family"])
        forward = cast(dict[str, object], item["forward_validation"])
        threshold = cast(dict[str, object], item["threshold"])
        metrics = cast(dict[str, object], item["metrics"])
        provenance = cast(dict[str, object], item["provenance"])
        family_hits = cast(dict[str, float], metrics["event_hit_by_family"])

        assert forward["passed"] is True
        assert cast(float, forward["recon_max_abs_diff"]) <= 1e-3
        assert threshold == {
            "value": threshold["value"],
            "policy": "clean_val_quantile",
            "alpha": 0.01,
            "comparison": "strict_gt",
        }
        assert set(family_hits) == EXPECTED_EVENT_FAMILIES
        for metric in (
            "window_precision",
            "window_recall",
            "window_f1",
            "event_hit_rate",
            "clean_test_fpr",
            "composite_fc1",
            "alert_rate",
        ):
            assert 0.0 <= cast(float, metrics[metric]) <= 1.0
        if family in {"conv1d", "lstm", "transformer"}:
            assert "stale window-30" in cast(str, provenance["forward"])
        else:
            assert "shipped window-10" in cast(str, provenance["forward"])


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

    payload = json.loads(json.dumps(_fixture_payload()))
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
    assert response.json() == _fixture_payload()
