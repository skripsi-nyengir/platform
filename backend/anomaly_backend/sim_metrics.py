"""Assemble research + operational detection metrics from stored replay rows.

Pure over its inputs (DB rows in, dataclass out) so it unit-tests without a
database. Rebuilds per-timestamp ground truth from injection-event index ranges,
de-overlaps stored per-window scores to point scores, then computes the research
three-scope metrics and the operational event list from the same point scores.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

from anomaly_backend.evaluation import (
    ScopeMetrics,
    non_overlapping_bin_metrics,
    overlapping_window_metrics,
    timestamp_metrics,
    window_scores_to_point_scores,
)
from anomaly_backend.operational import DEFAULT_COOLDOWN_SAMPLES, AlertEvent, detect_events


@dataclass(frozen=True, slots=True)
class SimMetrics:
    model_version: str
    threshold: float
    window_size: int
    frame_count: int
    event_count: int
    scored_windows: int
    timestamp: ScopeMetrics
    overlapping: ScopeMetrics
    bins: ScopeMetrics
    operational_event_count: int
    operational_events: list[AlertEvent]


def _segment_bounds(segment_rows: Sequence[tuple[int, int]]) -> np.ndarray:
    ordered = sorted((int(s), int(e)) for s, e in segment_rows)
    bounds = [start for start, _ in ordered]
    bounds.append(ordered[-1][1])
    return np.asarray(bounds, dtype=np.int64)


def assemble_sim_metrics(
    *,
    model_version: str,
    threshold: float,
    window_size: int,
    frame_count: int,
    window_rows: Sequence[tuple[int, int, float]],
    event_rows: Sequence[tuple[int, int]],
    segment_rows: Sequence[tuple[int, int]],
    cooldown_samples: int = DEFAULT_COOLDOWN_SAMPLES,
) -> SimMetrics:
    if not window_rows:
        raise ValueError("no scored windows for this model")
    starts = np.fromiter((int(r[0]) for r in window_rows), dtype=np.int64, count=len(window_rows))
    ends = np.fromiter((int(r[1]) for r in window_rows), dtype=np.int64, count=len(window_rows))
    scores = np.fromiter((float(r[2]) for r in window_rows), dtype=np.float64, count=len(window_rows))

    frame_labels = np.zeros(frame_count, dtype=bool)
    for start, end in event_rows:
        frame_labels[int(start):int(end)] = True
    seg_bounds = _segment_bounds(segment_rows)

    points, coverage = window_scores_to_point_scores(scores, starts, ends, frame_count)
    events = detect_events(points, coverage, seg_bounds, threshold, cooldown_samples)
    return SimMetrics(
        model_version=model_version,
        threshold=threshold,
        window_size=window_size,
        frame_count=frame_count,
        event_count=len(event_rows),
        scored_windows=len(window_rows),
        timestamp=timestamp_metrics(frame_labels, points, coverage, threshold),
        overlapping=overlapping_window_metrics(
            frame_labels, points, coverage, starts, ends, threshold
        ),
        bins=non_overlapping_bin_metrics(
            frame_labels, points, coverage, seg_bounds, len(event_rows), threshold
        ),
        operational_event_count=len(events),
        operational_events=events,
    )


@dataclass(frozen=True, slots=True)
class OperationalBucket:
    bucket_start: datetime
    bucket_end: datetime
    event_count: int


def bucket_operational_events(
    events: Sequence[AlertEvent],
    event_start_ts: Mapping[int, datetime],
    corpus_from: datetime,
    corpus_to: datetime,
    bucket_hours: int,
) -> list[OperationalBucket]:
    """Group operational events into fixed time buckets across the corpus range.

    Each event is placed in the bucket of its start timestamp. Empty buckets are
    kept so the result is a continuous operational-period timeline (events per
    period), not just periods that happened to fire.
    """
    if bucket_hours < 1:
        raise ValueError("bucket_hours must be >= 1")
    if corpus_to < corpus_from:
        raise ValueError("corpus_to must not precede corpus_from")
    width = timedelta(hours=bucket_hours)
    edges: list[datetime] = []
    edge = corpus_from
    while edge <= corpus_to:
        edges.append(edge)
        edge = edge + width
    if not edges:
        edges.append(corpus_from)
    counts = [0] * len(edges)
    for event in events:
        timestamp = event_start_ts.get(event.start_idx)
        if timestamp is None:
            continue
        index = int((timestamp - corpus_from) // width)
        if 0 <= index < len(counts):
            counts[index] += 1
    return [
        OperationalBucket(edges[i], edges[i] + width, counts[i])
        for i in range(len(edges))
    ]
