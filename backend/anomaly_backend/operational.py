"""Operational alerting (online-shaped, no ground-truth labels).

Distinct from research metrics: this path never sees true events, so it cannot
use non-overlapping bins. It thresholds de-overlapped point scores into alert
candidates, then merges candidates into discrete events so a run of consecutive
abnormal timestamps raises one alert, not one per timestamp. Events do not cross
segment boundaries; candidates separated by a gap shorter than the cooldown
belong to the same event.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

DEFAULT_COOLDOWN_SAMPLES = 10


@dataclass(frozen=True, slots=True)
class AlertEvent:
    segment_id: int
    start_idx: int
    end_idx: int
    n_candidates: int
    peak_score: float


def alert_candidates(
    point_scores: np.ndarray, coverage: np.ndarray, threshold: float
) -> np.ndarray:
    covered = np.asarray(coverage, dtype=bool)
    scores = np.asarray(point_scores, dtype=np.float64)
    candidates = np.zeros(scores.shape, dtype=bool)
    candidates[covered] = scores[covered] > float(threshold)
    return candidates


def merge_events(
    candidates: np.ndarray,
    point_scores: np.ndarray,
    seg_bounds: np.ndarray,
    cooldown_samples: int = DEFAULT_COOLDOWN_SAMPLES,
) -> list[AlertEvent]:
    mask = np.asarray(candidates, dtype=bool)
    scores = np.asarray(point_scores, dtype=np.float64)
    bounds = np.asarray(seg_bounds, dtype=np.int64)
    if cooldown_samples < 1:
        raise ValueError("cooldown_samples must be >= 1")
    events: list[AlertEvent] = []
    for segment_id, (seg_start, seg_end) in enumerate(zip(bounds[:-1], bounds[1:])):
        seg_start, seg_end = int(seg_start), int(seg_end)
        hits = np.flatnonzero(mask[seg_start:seg_end]) + seg_start
        if hits.size == 0:
            continue
        run_start = prev = int(hits[0])
        for idx in hits[1:]:
            idx = int(idx)
            if idx - prev >= cooldown_samples:
                events.append(_event(segment_id, run_start, prev, mask, scores))
                run_start = idx
            prev = idx
        events.append(_event(segment_id, run_start, prev, mask, scores))
    return events


def _event(
    segment_id: int, start: int, end: int, mask: np.ndarray, scores: np.ndarray
) -> AlertEvent:
    span = slice(start, end + 1)
    return AlertEvent(
        segment_id=segment_id,
        start_idx=start,
        end_idx=end,
        n_candidates=int(mask[span].sum()),
        peak_score=float(scores[span][mask[span]].max()),
    )


def detect_events(
    point_scores: np.ndarray,
    coverage: np.ndarray,
    seg_bounds: np.ndarray,
    threshold: float,
    cooldown_samples: int = DEFAULT_COOLDOWN_SAMPLES,
) -> list[AlertEvent]:
    candidates = alert_candidates(point_scores, coverage, threshold)
    return merge_events(candidates, point_scores, seg_bounds, cooldown_samples)
