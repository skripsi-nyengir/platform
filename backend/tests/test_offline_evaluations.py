import asyncio
import hashlib
import json
from importlib import resources
from typing import cast

import pytest
from anomaly_backend.routes.offline_evaluations import offline_evaluations, router

MODEL_ORDER = ["conv1d", "gru", "lstm", "rnn", "transformer"]
EXPECTED_MODEL_SHA256 = {
    "conv1d": "85c901e8fed463207a44151adc14772d3660384ae88daf9fcc53431e6acc39c9",
    "gru": "0506d1da27d92a259e62c32ce43db7fd19dfa8ad679c08c6d67bf727653a2caa",
    "lstm": "0dde621c1fe4117fd57602a94c30bd764e900108ceea3675fba6295e9500cccb",
    "rnn": "c801a284c95c16ce9031a24f774d941c314bc0758e7b20d593af64fb630f0ebd",
    "transformer": "364b0c73be1054b05a33924615d53ee1ebcb12af4bbb7d4efc0c1a144af3e015",
}
EXPECTED_STEP7_NOTEBOOK_SHA256 = {
    "conv1d": "b14aa0b399936b0ce289771a35c0db72d911fcf42cff346776c8d4fbbf16f918",
    "gru": "0b6c47870bc202a9a32bd2fd0e2477c2f985dcc186e3d3aecfdd3a69a309baf3",
    "lstm": "70c44870d914617e125997c4defeb360ca813de342c5a8dbf7519af1881a5469",
    "rnn": "e7a5e21c67e9906bdc2b1843b6753c10fd56fd84f466255f538b02397afe4925",
    "transformer": "b0a48d96f920d9178b1cbb1849a0c68d206b66046de7234ed1f4cebbda0894f1",
}
EXPECTED_STEP5_NOTEBOOK_SHA256 = {
    "conv1d": "782c8d9906fe9a6c45e32a1e624e4dabc8c1ce9cc33915608ecd4ba21afb5dbf",
    "gru": "ab827505d106df33614ac6f6f3a064a8b99df31e2557a5ce38407e75e734c788",
    "lstm": "17cc1f584a5445c2b986517fd391419c56270ca9ff295df40e46fc2c57bc3ef6",
    "rnn": "8e45fd2f21e4ecc8bd3bf7e4cf8dcc3ab8e70427cabbd82c91f3b5995172ce7a",
    "transformer": "eb199b32d5264c8b94ba394502b429353c2ca5e1fca5dc7b6c1b048e98d6bd43",
}
EXPECTED_ARTIFACT_SHA256 = {
    "conv1d_step5_artifacts.zip": "6698d40f2476343801ab64285ddd9e900e47a2857aa5c090beaf69eda1a30bbf",
    "lstm_step5_artifacts.zip": "b05bd9adb10fcc0d6d4eeb5e992fdc5f3f9507b03495067896b7436dd5e0dc27",
    "transformer_step5_artifacts.zip": "a7ae8937e9ef97403f63d32cc9be17adc6301d4daa9e5668beb5834c5a99351c",
    "transformer_step7_artifacts.zip": "f65c7128f55bdddcbd37d0d63ecde8caa59ba0338997b70d472dee48f6892da8",
}
EXPECTED_PRIMARY = {
    "conv1d": (0.0003201981883103135, 1605, 61, 111, 294, 0.7736842105263158),
    "gru": (0.0005618056084495022, 1606, 60, 98, 307, 0.7953367875647669),
    "lstm": (0.0009487349475675721, 1631, 35, 151, 254, 0.7319884726224783),
    "rnn": (0.0005023972923204374, 1615, 51, 116, 289, 0.7758389261744967),
    "transformer": (0.00026567234380490805, 1590, 76, 78, 327, 0.8094059405940595),
}
EXPECTED_SCOPE_SIZES = {
    "timestamp": 105_408,
    "overlapping_model_windows": 105_327,
    "non_overlapping_evaluation_bins": 2_071,
}


def _fixture_payload() -> dict[str, object]:
    from anomaly_backend.offline_evaluations import FIXTURE_PATH

    parsed = json.loads(
        resources.files("anomaly_backend").joinpath(FIXTURE_PATH).read_text()
    )
    return cast(dict[str, object], parsed)


def test_offline_evaluations_fixture_matches_step7_notebooks() -> None:
    from anomaly_backend.offline_evaluations import (
        FIXTURE_PATH,
        FIXTURE_SHA256,
        load_offline_evaluations,
    )

    payload = resources.files("anomaly_backend").joinpath(FIXTURE_PATH).read_bytes()
    loaded = load_offline_evaluations().model_dump(mode="json")

    assert hashlib.sha256(payload).hexdigest() == FIXTURE_SHA256
    assert loaded == _fixture_payload()
    assert loaded["evaluation"] == {
        "dataset_reference": "b02f3872_ruang_produksi_v3_march07",
        "evaluation_split": "val_injected",
        "test_consumed": False,
        "primary_scope": "non_overlapping_evaluation_bins",
        "primary_metric": "f1",
        "n_points_total": 105_425,
        "n_points_evaluated": 105_408,
        "n_model_windows": 105_327,
        "n_positive_windows": 12_392,
        "n_events": 207,
        "evaluation_bin_size_points": 51,
        "n_evaluation_bins": 2_071,
        "n_skipped_bins": 6,
    }

    items = cast(list[dict[str, object]], loaded["items"])
    assert [item["model_family"] for item in items] == MODEL_ORDER
    assert {
        cast(str, item["model_family"]): cast(str, item["model_sha256"])
        for item in items
    } == EXPECTED_MODEL_SHA256

    for item in items:
        family = cast(str, item["model_family"])
        threshold = cast(dict[str, object], item["threshold"])
        scopes = cast(dict[str, dict[str, object]], item["scopes"])
        provenance = cast(dict[str, object], item["provenance"])
        step5_notebook = cast(dict[str, object], provenance["step5_notebook"])
        step7_notebook = cast(dict[str, object], provenance["step7_notebook"])

        expected_threshold, tn, fp, fn, tp, expected_f1 = EXPECTED_PRIMARY[family]
        assert threshold == {
            "value": expected_threshold,
            "method": "clean_percentile_99_5",
            "percentile": 99.5,
            "calibration_split": "clean_validation",
            "comparison": "strict_gt",
            "score_unit": "timestamp",
            "uses_anomaly_labels": False,
            "clean_alert_rate": 0.005009107468123861,
        }
        assert set(scopes) == set(EXPECTED_SCOPE_SIZES)
        for scope_name, metrics in scopes.items():
            assert metrics["n_evaluated"] == EXPECTED_SCOPE_SIZES[scope_name]
            scope_tn = cast(int, metrics["tn"])
            scope_fp = cast(int, metrics["fp"])
            scope_fn = cast(int, metrics["fn"])
            scope_tp = cast(int, metrics["tp"])
            assert scope_tn + scope_fp + scope_fn + scope_tp == metrics["n_evaluated"]
            assert metrics["accuracy"] == pytest.approx(
                (scope_tn + scope_tp) / cast(int, metrics["n_evaluated"]), abs=1e-15
            )
            assert metrics["precision"] == pytest.approx(
                scope_tp / (scope_tp + scope_fp), abs=1e-15
            )
            assert metrics["recall"] == pytest.approx(
                scope_tp / (scope_tp + scope_fn), abs=1e-15
            )
            assert metrics["f1"] == pytest.approx(
                (2 * scope_tp) / (2 * scope_tp + scope_fp + scope_fn), abs=1e-15
            )

        primary = scopes["non_overlapping_evaluation_bins"]
        assert (primary["tn"], primary["fp"], primary["fn"], primary["tp"]) == (
            tn,
            fp,
            fn,
            tp,
        )
        assert primary["f1"] == pytest.approx(expected_f1, abs=1e-15)
        assert provenance["metric_authority"] == "executed_step7_notebook_output"
        assert step5_notebook["sha256"] == EXPECTED_STEP5_NOTEBOOK_SHA256[family]
        assert step7_notebook["sha256"] == EXPECTED_STEP7_NOTEBOOK_SHA256[family]

    actual_artifact_sha256 = {
        cast(str, check["filename"]): cast(str, check["sha256"])
        for item in items
        for check in cast(
            list[dict[str, object]],
            cast(dict[str, object], item["provenance"])["artifact_checks"],
        )
    }
    assert actual_artifact_sha256 == EXPECTED_ARTIFACT_SHA256


def test_transformer_quarantines_stale_step7_selector() -> None:
    loaded = _fixture_payload()
    items = cast(list[dict[str, object]], loaded["items"])
    transformer = next(item for item in items if item["model_family"] == "transformer")
    threshold = cast(dict[str, object], transformer["threshold"])
    scopes = cast(dict[str, dict[str, object]], transformer["scopes"])
    provenance = cast(dict[str, object], transformer["provenance"])
    artifact_checks = cast(list[dict[str, object]], provenance["artifact_checks"])

    assert threshold["value"] == 0.00026567234380490805
    assert threshold["value"] != 4.264292007974145e-05
    assert scopes["non_overlapping_evaluation_bins"]["f1"] == pytest.approx(
        0.8094059405940595, abs=1e-15
    )
    assert any(
        check["filename"] == "transformer_step7_artifacts.zip"
        and check["consistency"] == "conflict"
        for check in artifact_checks
    )


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


def test_fixture_shape_validation_rejects_missing_scope() -> None:
    from anomaly_backend.offline_evaluations import (
        OfflineEvaluationsIntegrityError,
        normalize_offline_evaluations,
    )

    payload = json.loads(json.dumps(_fixture_payload()))
    del payload["items"][0]["scopes"]["timestamp"]

    with pytest.raises(OfflineEvaluationsIntegrityError, match="invalid shape"):
        _ = normalize_offline_evaluations(payload)


def test_offline_evaluations_endpoint_returns_report() -> None:
    assert any(
        getattr(route, "path", None) == "/api/offline-evaluations"
        for route in router.routes
    )
    response = asyncio.run(offline_evaluations())

    assert response.model_dump(mode="json") == _fixture_payload()
