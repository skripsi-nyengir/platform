from __future__ import annotations

import hashlib
from importlib import resources
import json
import math
from typing import cast


type JSONValue = (
    None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
)
type JSONObject = dict[str, JSONValue]

SOURCE_COMMIT = "6d265f0b3d3c91097e2295a43c6a6dee034374d8"
STEP8_PATH = "fixtures/dandy_pilot/source/final_test_summary.json"
STEP8_SHA256 = "592d0d69bbb9e985d2db3f7314a635a04cd870bd0ae683b5aa28caf70966eb24"
STEP10_PATH = "fixtures/dandy_pilot/source/step10_comparison_summary.json"
STEP10_SHA256 = "ed03bf3d823d7a47c3f18f946d6222844476cc83ee28bdd64a436df356caa18d"
NORMALIZED_PATH = "fixtures/dandy_pilot/normalized_pilot_snapshot.json"

MODEL_KEY_MAP = {
    "ewma": "ewma",
    "pca": "pca",
    "wsn_dense_ae": "wsn-dense-ae",
    "lstm_ae": "lstm-ae",
    "usad": "usad",
    "cfc_autoencoder": "cfc-autoencoder",
    "mtad_gat": "mtad-gat",
}

PILOT_DISCLAIMER = (
    "Snapshot pilot Dandy berasal dari satu seed/run; test sudah diamati, "
    "belum merupakan evaluasi independen/final, dan seluruh model gagal "
    "skenario stuck."
)


class PilotIntegrityError(ValueError):
    pass


def _read_and_verify(relative_path: str, expected_sha256: str) -> JSONObject:
    payload = (
        resources.files("anomaly_backend")
        .joinpath(relative_path)
        .read_bytes()
    )
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if actual_sha256 != expected_sha256:
        raise PilotIntegrityError(
            f"{relative_path} SHA-256 mismatch: expected {expected_sha256}"
        )
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise PilotIntegrityError(f"{relative_path} must contain an object")
    return cast(JSONObject, parsed)


def _finite_or_none(value: object) -> JSONValue:
    if value is None or isinstance(value, bool | str | int):
        return cast(JSONValue, value)
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, list):
        return [_finite_or_none(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _finite_or_none(item)
            for key, item in value.items()
        }
    raise PilotIntegrityError("pilot payload contains an unsupported value")


def normalized_pilot_snapshot() -> JSONObject:
    step8 = _read_and_verify(STEP8_PATH, STEP8_SHA256)
    step10 = _read_and_verify(STEP10_PATH, STEP10_SHA256)

    ranking = step10.get("ranking_by_composite_primary")
    hit_rates = step10.get("event_hit_rate_by_family")
    step8_results = step8.get("results")
    if (
        step10.get("model_count") != 7
        or not isinstance(ranking, list)
        or len(ranking) != 7
        or not isinstance(hit_rates, dict)
        or not isinstance(step8_results, dict)
    ):
        raise PilotIntegrityError("Dandy pilot payload does not contain seven models")

    stuck = hit_rates.get("stuck")
    if not isinstance(stuck, dict) or len(stuck) != 7:
        raise PilotIntegrityError("Dandy pilot stuck scenario is missing")
    if any(value != 0.0 for value in stuck.values()):
        raise PilotIntegrityError("every Dandy pilot model must fail stuck")

    models: list[JSONValue] = []
    for row in ranking:
        if not isinstance(row, dict):
            raise PilotIntegrityError("ranking rows must be objects")
        source_key = row.get("model_key")
        if not isinstance(source_key, str) or source_key not in MODEL_KEY_MAP:
            raise PilotIntegrityError("ranking contains an unknown model key")
        source_result = step8_results.get(source_key)
        if not isinstance(source_result, dict):
            raise PilotIntegrityError(f"step8 result missing for {source_key}")
        composite = source_result.get("composite")
        if not isinstance(composite, dict):
            raise PilotIntegrityError(f"step8 composite missing for {source_key}")
        dynamic = composite.get("dynamic_score_by_family")
        if not isinstance(dynamic, dict) or dynamic.get("stuck") != 0.0:
            raise PilotIntegrityError(f"{source_key} did not fail stuck")
        models.append(
            {
                "model_key": MODEL_KEY_MAP[source_key],
                "display_name": row.get("model"),
                "family": row.get("family"),
                "rank": row.get("Peringkat Composite Final"),
                "score_key": row.get("score_key"),
                "reported_threshold": row.get("threshold"),
                "composite_primary": row.get("composite_primary"),
                "window_f1": row.get("window_f1"),
                "window_precision": row.get("window_precision"),
                "window_recall": row.get("window_recall"),
                "event_hit_rate": row.get("event_hit_rate"),
                "clean_test_fpr": row.get("clean_test_fpr"),
                "alert_rate": row.get("alert_rate"),
                "n_predicted_windows": row.get("n_predicted_windows"),
                "stuck_event_hit_rate": 0.0,
                "dynamic_score_by_family": _finite_or_none(dynamic),
            }
        )

    snapshot: JSONObject = {
        "schema_version": "reported_dandy_pilot_v1",
        "report_source": "reported_dandy_pilot",
        "label_source": "synthetic_injection",
        "evaluation_kind": "comparison_snapshot",
        "source_commit": SOURCE_COMMIT,
        "test_observed": True,
        "independent_final": False,
        "seed": step10.get("seed"),
        "disclaimer": PILOT_DISCLAIMER,
        "sources": [
            {
                "path": "notebooks/step8/summaries/final_test_summary.json",
                "sha256": STEP8_SHA256,
            },
            {
                "path": "notebooks/step10/summaries/step10_comparison_summary.json",
                "sha256": STEP10_SHA256,
            },
        ],
        "models": models,
    }
    return cast(JSONObject, _finite_or_none(snapshot))


def canonical_snapshot_bytes(snapshot: JSONObject | None = None) -> bytes:
    return (
        json.dumps(
            snapshot if snapshot is not None else normalized_pilot_snapshot(),
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def load_tracked_normalized_snapshot() -> JSONObject:
    expected = normalized_pilot_snapshot()
    payload = (
        resources.files("anomaly_backend")
        .joinpath(NORMALIZED_PATH)
        .read_bytes()
    )
    parsed = json.loads(payload)
    if parsed != expected:
        raise PilotIntegrityError(
            "tracked normalized pilot snapshot does not match pinned source payloads"
        )
    return cast(JSONObject, parsed)
