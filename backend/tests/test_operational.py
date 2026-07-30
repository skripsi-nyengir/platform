"""Deterministic tests for operational alert merging.

step8 has no alerting path, so there is no published number to reproduce; these
tests pin the merge/cooldown/segment semantics against hand-built inputs.
"""
from __future__ import annotations

import numpy as np

from anomaly_backend.operational import (
    AlertEvent,
    alert_candidates,
    detect_events,
    merge_events,
)


def test_candidates_respect_threshold_and_coverage() -> None:
    scores = np.array([0.1, 0.9, 0.5, np.nan, 0.8], dtype=np.float64)
    coverage = np.array([1, 1, 1, 0, 1], dtype=np.int64)
    got = alert_candidates(scores, coverage, threshold=0.6)
    assert got.tolist() == [False, True, False, False, True]


def test_consecutive_candidates_form_one_event() -> None:
    scores = np.array([0.0, 0.9, 0.95, 0.91, 0.0], dtype=np.float64)
    coverage = np.ones(5, dtype=np.int64)
    seg_bounds = np.array([0, 5], dtype=np.int64)
    events = detect_events(scores, coverage, seg_bounds, threshold=0.5, cooldown_samples=3)
    assert events == [AlertEvent(0, 1, 3, 3, 0.95)]


def test_sub_cooldown_gap_merges_but_cooldown_gap_splits() -> None:
    # candidates at 0 and 2 (gap 2 < cooldown 3) merge; candidate at 6 splits.
    scores = np.zeros(8, dtype=np.float64)
    scores[[0, 2, 6]] = 0.9
    coverage = np.ones(8, dtype=np.int64)
    seg_bounds = np.array([0, 8], dtype=np.int64)
    events = merge_events(
        alert_candidates(scores, coverage, 0.5), scores, seg_bounds, cooldown_samples=3
    )
    assert [(e.start_idx, e.end_idx, e.n_candidates) for e in events] == [
        (0, 2, 2),
        (6, 6, 1),
    ]


def test_events_never_cross_segment_boundary() -> None:
    # adjacent candidates across a segment boundary must stay separate events.
    scores = np.array([0.9, 0.9, 0.9, 0.9], dtype=np.float64)
    coverage = np.ones(4, dtype=np.int64)
    seg_bounds = np.array([0, 2, 4], dtype=np.int64)
    events = detect_events(scores, coverage, seg_bounds, threshold=0.5, cooldown_samples=10)
    assert [(e.segment_id, e.start_idx, e.end_idx) for e in events] == [
        (0, 0, 1),
        (1, 2, 3),
    ]
