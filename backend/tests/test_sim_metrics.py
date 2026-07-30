"""assemble_sim_metrics reproduces step7 metrics from DB-row-shaped inputs.

Feeds the golden per-window scores as (start, end, score) rows and the injection
ranges as (start, end_exclusive) rows — the exact shapes the SQL loader returns —
so this exercises frame-label reconstruction, de-overlap, all three research
scopes, and operational event detection through the endpoint's assembly path.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from anomaly_backend.sim_metrics import assemble_sim_metrics

_FIXTURE = Path(__file__).parent / "fixtures" / "research_metrics" / "golden.npz"

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
def test_assemble_reproduces_step7(golden: dict[str, np.ndarray], model: str) -> None:
    seg_bounds = golden["seg_bounds"]
    segment_rows = [
        (int(seg_bounds[i]), int(seg_bounds[i + 1])) for i in range(len(seg_bounds) - 1)
    ]
    window_rows = list(
        zip(
            golden[f"{model}_starts"].tolist(),
            golden[f"{model}_ends"].tolist(),
            golden[f"{model}_scores"].tolist(),
        )
    )
    event_rows = list(zip(golden["event_starts"].tolist(), golden["event_ends"].tolist()))

    metrics = assemble_sim_metrics(
        model_version=f"artifact-{model}-v3",
        threshold=float(golden[f"{model}_threshold"]),
        window_size=10,
        frame_count=len(golden["frame_labels"]),
        window_rows=window_rows,
        event_rows=event_rows,
        segment_rows=segment_rows,
    )

    assert metrics.event_count == 207
    for scope, key in (
        (metrics.timestamp, "timestamp"),
        (metrics.overlapping, "overlapping"),
        (metrics.bins, "bins"),
    ):
        f1, tn, fp, fn, tp = _EXPECTED[model][key]
        assert (scope.tn, scope.fp, scope.fn, scope.tp) == (tn, fp, fn, tp), (model, key)
        assert scope.f1 == pytest.approx(f1, abs=1e-12), (model, key)

    # Operational events are ground-truth-free and must not exceed candidate points.
    assert metrics.operational_event_count >= 1
    assert all(e.n_candidates >= 1 for e in metrics.operational_events)


def test_bucket_operational_events_keeps_empty_buckets() -> None:
    from datetime import datetime

    from anomaly_backend.operational import AlertEvent
    from anomaly_backend.sim_metrics import bucket_operational_events

    corpus_from = datetime(2026, 4, 19, 0, 0, 0)
    corpus_to = datetime(2026, 4, 19, 3, 0, 0)
    events = [
        AlertEvent(0, 5, 5, 1, 0.9),
        AlertEvent(0, 700, 700, 1, 0.9),
        AlertEvent(0, 720, 720, 1, 0.9),
    ]
    ts_by_idx = {
        5: datetime(2026, 4, 19, 0, 10),
        700: datetime(2026, 4, 19, 1, 10),
        720: datetime(2026, 4, 19, 1, 50),
    }
    buckets = bucket_operational_events(events, ts_by_idx, corpus_from, corpus_to, bucket_hours=1)
    # 0:00 -> 1 event, 1:00 -> 2 events, 2:00 and 3:00 buckets stay present at 0.
    assert [b.event_count for b in buckets] == [1, 2, 0, 0]
    assert buckets[0].bucket_start == corpus_from
    assert buckets[1].bucket_start == datetime(2026, 4, 19, 1, 0)


def test_bucket_operational_events_daily_and_skips_unknown_index() -> None:
    from datetime import datetime

    from anomaly_backend.operational import AlertEvent
    from anomaly_backend.sim_metrics import bucket_operational_events

    corpus_from = datetime(2026, 4, 19, 0, 0, 0)
    corpus_to = datetime(2026, 4, 21, 0, 0, 0)
    events = [AlertEvent(0, 1, 1, 1, 0.9), AlertEvent(0, 2, 2, 1, 0.9)]
    ts_by_idx = {1: datetime(2026, 4, 20, 5, 0)}  # idx 2 missing -> skipped
    buckets = bucket_operational_events(events, ts_by_idx, corpus_from, corpus_to, bucket_hours=24)
    assert [b.event_count for b in buckets] == [0, 1, 0]
