"""Golden test: research evaluation reproduces Dandy's step7 published metrics.

The fixture holds per-window GRU/RNN reconstruction MSE over val_injected. This
test runs the pure-numpy evaluation module (de-overlap + three scopes) and
asserts every scope's confusion counts and F1 match the notebook artifacts
exactly. Proves the platform's metric methodology is faithful without torch.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from anomaly_backend.evaluation import (
    non_overlapping_bin_metrics,
    overlapping_window_metrics,
    timestamp_metrics,
    window_scores_to_point_scores,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "research_metrics" / "golden.npz"

# Published step7 val_injected metrics (three scopes) per model.
_EXPECTED = {
    "gru": {
        "timestamp": (0.5766676128299745, 92872, 1994, 5463, 5079),
        "overlapping": (0.6523680213559166, 90687, 2248, 5305, 7087),
        "bins": (0.7953367875647669, 1606, 60, 98, 307),
    },
    "rnn": {
        "timestamp": (0.5714450201496835, 93001, 1865, 5579, 4963),
        "overlapping": (0.6439240446685199, 90937, 1998, 5559, 6833),
        "bins": (0.7758389261744967, 1615, 51, 116, 289),
    },
}


@pytest.fixture(scope="module")
def golden() -> dict[str, np.ndarray]:
    with np.load(_FIXTURE) as data:
        return {key: data[key] for key in data.files}


@pytest.mark.parametrize("model", ["gru", "rnn"])
def test_three_scope_metrics_match_step7(golden: dict[str, np.ndarray], model: str) -> None:
    labels = golden["frame_labels"]
    seg_bounds = golden["seg_bounds"]
    event_count = int(golden["event_count"])
    scores = golden[f"{model}_scores"]
    starts = golden[f"{model}_starts"]
    ends = golden[f"{model}_ends"]
    threshold = float(golden[f"{model}_threshold"])

    points, coverage = window_scores_to_point_scores(scores, starts, ends, len(labels))

    ts = timestamp_metrics(labels, points, coverage, threshold)
    ow = overlapping_window_metrics(labels, points, coverage, starts, ends, threshold)
    nb = non_overlapping_bin_metrics(
        labels, points, coverage, seg_bounds, event_count, threshold
    )

    for metrics, key in ((ts, "timestamp"), (ow, "overlapping"), (nb, "bins")):
        f1, tn, fp, fn, tp = _EXPECTED[model][key]
        assert (metrics.tn, metrics.fp, metrics.fn, metrics.tp) == (tn, fp, fn, tp), (
            model, key, metrics
        )
        assert metrics.f1 == pytest.approx(f1, abs=1e-12), (model, key)


def test_bin_size_is_derived_from_event_count(golden: dict[str, np.ndarray]) -> None:
    from anomaly_backend.evaluation import evaluation_bin_size

    assert evaluation_bin_size(len(golden["frame_labels"]), int(golden["event_count"])) == 51
