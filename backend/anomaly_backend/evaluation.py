"""Research-scope detection metrics (offline, requires ground-truth labels).

Reproduces the step8 notebook evaluation exactly: overlapping window scores are
de-overlapped to per-timestamp point scores, thresholded, then scored at three
scopes with non-overlapping-bin F1 as the primary metric. This is a research
measurement that consumes the true event count, so it cannot drive live alerts;
operational alerting lives elsewhere.

Pure numpy: no pandas/sklearn, so it runs in the standard test image. Manual
binary metrics are integer-exact and match scikit-learn / torchmetrics.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class ScopeMetrics:
    scope: str
    precision: float
    recall: float
    f1: float
    accuracy: float
    tn: int
    fp: int
    fn: int
    tp: int
    n_evaluated: int
    n_anomalous: int


def window_scores_to_point_scores(
    window_scores: np.ndarray,
    window_start_idx: np.ndarray,
    window_end_idx: np.ndarray,
    frame_count: int,
) -> tuple[np.ndarray, np.ndarray]:
    scores = np.asarray(window_scores, dtype=np.float64)
    starts = np.asarray(window_start_idx, dtype=np.int64)
    ends = np.asarray(window_end_idx, dtype=np.int64)
    if not (scores.shape == starts.shape == ends.shape) or scores.ndim != 1:
        raise ValueError("window scores and index arrays must be aligned 1-D")
    if frame_count <= 0:
        raise ValueError("frame_count must be positive")
    # Difference arrays add each window's score across its inclusive [start, end]
    # span in O(n_windows + n_points) instead of materializing every assignment;
    # a point's score is the mean over all windows covering it.
    score_delta = np.zeros(frame_count + 1, dtype=np.float64)
    count_delta = np.zeros(frame_count + 1, dtype=np.int64)
    np.add.at(score_delta, starts, scores)
    np.add.at(score_delta, ends + 1, -scores)
    np.add.at(count_delta, starts, 1)
    np.add.at(count_delta, ends + 1, -1)
    score_sums = np.cumsum(score_delta[:-1])
    coverage = np.cumsum(count_delta[:-1])
    covered = coverage > 0
    point_scores = np.full(frame_count, np.nan, dtype=np.float64)
    point_scores[covered] = score_sums[covered] / coverage[covered]
    return point_scores, coverage


def evaluation_bin_size(n_timestamps: int, event_count: int, fraction: float = 0.10) -> int:
    if int(n_timestamps) <= 0 or int(event_count) <= 0:
        raise ValueError("n_timestamps and event_count must be positive")
    return max(1, int(round(float(fraction) * int(n_timestamps) / int(event_count))))


def _binary_metrics(scope: str, actual: np.ndarray, predicted: np.ndarray) -> ScopeMetrics:
    actual = np.asarray(actual, dtype=bool)
    predicted = np.asarray(predicted, dtype=bool)
    tp = int((actual & predicted).sum())
    tn = int((~actual & ~predicted).sum())
    fp = int((~actual & predicted).sum())
    fn = int((actual & ~predicted).sum())
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
    total = tp + tn + fp + fn
    accuracy = (tp + tn) / total if total else 0.0
    return ScopeMetrics(
        scope=scope, precision=precision, recall=recall, f1=f1, accuracy=accuracy,
        tn=tn, fp=fp, fn=fn, tp=tp, n_evaluated=total, n_anomalous=int(actual.sum()),
    )


def non_overlapping_bin_metrics(
    frame_labels: np.ndarray,
    point_scores: np.ndarray,
    coverage: np.ndarray,
    seg_bounds: np.ndarray,
    event_count: int,
    threshold: float,
    fraction: float = 0.10,
) -> ScopeMetrics:
    labels = np.asarray(frame_labels, dtype=bool)
    covered = np.asarray(coverage, dtype=bool)
    scores = np.asarray(point_scores, dtype=np.float64)
    bounds = np.asarray(seg_bounds, dtype=np.int64)
    bin_size = evaluation_bin_size(len(labels), event_count, fraction)
    predictions = np.zeros(len(labels), dtype=bool)
    predictions[covered] = scores[covered] > float(threshold)
    actual_bins: list[bool] = []
    predicted_bins: list[bool] = []
    for seg_start, seg_end in zip(bounds[:-1], bounds[1:]):
        seg_start, seg_end = int(seg_start), int(seg_end)
        for bin_start in range(seg_start, seg_end, bin_size):
            bin_end = min(bin_start + bin_size, seg_end)
            bin_cov = covered[bin_start:bin_end]
            if len(bin_cov) == 0 or not bool(bin_cov.all()):
                continue
            actual_bins.append(bool(labels[bin_start:bin_end].any()))
            predicted_bins.append(bool(predictions[bin_start:bin_end].any()))
    if not actual_bins:
        raise ValueError("no fully scored non-overlapping evaluation bins")
    return _binary_metrics(
        "non_overlapping_evaluation_bins",
        np.asarray(actual_bins, dtype=bool),
        np.asarray(predicted_bins, dtype=bool),
    )


def timestamp_metrics(
    frame_labels: np.ndarray,
    point_scores: np.ndarray,
    coverage: np.ndarray,
    threshold: float,
) -> ScopeMetrics:
    covered = np.asarray(coverage, dtype=bool)
    labels = np.asarray(frame_labels, dtype=bool)[covered]
    scores = np.asarray(point_scores, dtype=np.float64)[covered]
    return _binary_metrics("timestamp", labels, scores > float(threshold))


def overlapping_window_metrics(
    frame_labels: np.ndarray,
    point_scores: np.ndarray,
    coverage: np.ndarray,
    window_start_idx: np.ndarray,
    window_end_idx: np.ndarray,
    threshold: float,
) -> ScopeMetrics:
    labels = np.asarray(frame_labels, dtype=bool)
    covered = np.asarray(coverage, dtype=bool)
    scores = np.asarray(point_scores, dtype=np.float64)
    starts = np.asarray(window_start_idx, dtype=np.int64)
    ends = np.asarray(window_end_idx, dtype=np.int64)
    predictions = np.zeros(len(labels), dtype=bool)
    predictions[covered] = scores[covered] > float(threshold)
    actual = np.array(
        [bool(labels[s:e + 1].any()) for s, e in zip(starts, ends)], dtype=bool
    )
    predicted = np.array(
        [bool(predictions[s:e + 1].any()) for s, e in zip(starts, ends)], dtype=bool
    )
    return _binary_metrics("overlapping_model_windows", actual, predicted)
