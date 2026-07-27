"""Immutable scorer boundary shared by preview and future artifact adapters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
import math
import struct
from typing import Protocol

from .simulator import preview_score


WINDOW_SIZE = 30
CHANNELS = ("suhu", "rh")


class ScorerProtocolError(ValueError):
    """A scorer request or response violates the worker-owned protocol."""


class TemporalSemantics(StrEnum):
    CONTEXT_END = "context_end"
    NEXT_TARGET = "next_target"


FloatChannels = tuple[float, float]
FloatWindow = tuple[FloatChannels, ...]
TimestampWindow = tuple[datetime, ...]


@dataclass(frozen=True, slots=True)
class ScoreBatch:
    model_version: str
    schema_version: str
    channels: tuple[str, str]
    raw_values: tuple[FloatWindow, ...]
    model_values: tuple[FloatWindow, ...]
    context_ts: tuple[TimestampWindow, ...]
    context_start_indices: tuple[int, ...]
    context_end_indices: tuple[int, ...]
    segment_ids: tuple[int, ...]
    eligible_window_ordinals: tuple[int, ...]
    target_ts: tuple[datetime, ...]
    target_raw_values: tuple[FloatChannels, ...] | None = None
    target_model_values: tuple[FloatChannels, ...] | None = None

    @property
    def size(self) -> int:
        return len(self.raw_values)


@dataclass(frozen=True, slots=True)
class ScorePoint:
    score_ts: datetime
    score: float


@dataclass(frozen=True, slots=True)
class ScoreBatchResult:
    points: tuple[ScorePoint, ...]


class Scorer(Protocol):
    def score(self, batch: ScoreBatch) -> ScoreBatchResult: ...


def _validate_timestamp(value: datetime, field: str) -> None:
    if not isinstance(value, datetime):
        raise ScorerProtocolError(f"{field} must contain datetime values")
    if value.tzinfo is not None:
        raise ScorerProtocolError(f"{field} must contain naive corpus timestamps")


def _validate_finite_pair(value: object, field: str) -> None:
    if not isinstance(value, tuple) or len(value) != len(CHANNELS):
        raise ScorerProtocolError(f"{field} must have exactly two ordered channels")
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (float, int)):
            raise ScorerProtocolError(f"{field} must contain numeric values")
        if not math.isfinite(item):
            raise ScorerProtocolError(f"{field} must contain only finite values")
        try:
            struct.pack(">f", item)
        except OverflowError as error:
            raise ScorerProtocolError(
                f"{field} values must be representable as float32"
            ) from error


def _validate_values(values: tuple[FloatWindow, ...], size: int, field: str) -> None:
    if not isinstance(values, tuple) or len(values) != size:
        raise ScorerProtocolError(f"{field} batch dimension must equal N")
    for window in values:
        if not isinstance(window, tuple) or len(window) != WINDOW_SIZE:
            raise ScorerProtocolError(f"{field} must have shape [N,30,2]")
        for pair in window:
            _validate_finite_pair(pair, field)


def validate_batch(
    batch: ScoreBatch,
    temporal_semantics: TemporalSemantics,
) -> None:
    """Validate all scorer input invariants before invoking an adapter."""

    if not isinstance(batch, ScoreBatch):
        raise ScorerProtocolError("batch must be an immutable ScoreBatch")
    if not batch.model_version or "|" in batch.model_version:
        raise ScorerProtocolError("model_version is invalid")
    if not batch.schema_version:
        raise ScorerProtocolError("schema_version is required")
    if batch.channels != CHANNELS:
        raise ScorerProtocolError("channel order must be ('suhu', 'rh')")

    size = batch.size
    if size == 0:
        raise ScorerProtocolError("batch must contain at least one window")
    _validate_values(batch.raw_values, size, "raw_values")
    _validate_values(batch.model_values, size, "model_values")

    parallel = {
        "context_ts": batch.context_ts,
        "context_start_indices": batch.context_start_indices,
        "context_end_indices": batch.context_end_indices,
        "segment_ids": batch.segment_ids,
        "eligible_window_ordinals": batch.eligible_window_ordinals,
        "target_ts": batch.target_ts,
    }
    for field, values in parallel.items():
        if not isinstance(values, tuple) or len(values) != size:
            raise ScorerProtocolError(f"{field} length must equal N")

    for index in range(size):
        timestamps = batch.context_ts[index]
        if not isinstance(timestamps, tuple) or len(timestamps) != WINDOW_SIZE:
            raise ScorerProtocolError("context_ts must have shape [N,30]")
        for position, timestamp in enumerate(timestamps):
            _validate_timestamp(timestamp, "context_ts")
            if position and timestamp <= timestamps[position - 1]:
                raise ScorerProtocolError("context timestamps must be strictly ordered")

        start_index = batch.context_start_indices[index]
        end_index = batch.context_end_indices[index]
        target = batch.target_ts[index]
        _validate_timestamp(target, "target_ts")
        if (
            isinstance(start_index, bool)
            or isinstance(end_index, bool)
            or not isinstance(start_index, int)
            or not isinstance(end_index, int)
            or start_index < 0
            or end_index - start_index != WINDOW_SIZE - 1
        ):
            raise ScorerProtocolError("context corpus indices must span 30 readings")
        if index:
            previous_key = (
                batch.segment_ids[index - 1],
                batch.eligible_window_ordinals[index - 1],
            )
            current_key = (
                batch.segment_ids[index],
                batch.eligible_window_ordinals[index],
            )
            if current_key <= previous_key:
                raise ScorerProtocolError("windows must follow segment/ordinal order")
            if batch.segment_ids[index] == batch.segment_ids[index - 1]:
                if end_index <= batch.context_end_indices[index - 1]:
                    raise ScorerProtocolError(
                        "context indices must increase within a segment"
                    )
                if target <= batch.target_ts[index - 1]:
                    raise ScorerProtocolError(
                        "target timestamps must increase within a segment"
                    )

        segment_id = batch.segment_ids[index]
        ordinal = batch.eligible_window_ordinals[index]
        if (
            isinstance(segment_id, bool)
            or isinstance(ordinal, bool)
            or not isinstance(segment_id, int)
            or not isinstance(ordinal, int)
            or segment_id < 0
            or ordinal < 0
        ):
            raise ScorerProtocolError("segment IDs and window ordinals must be unsigned")

        if temporal_semantics is TemporalSemantics.CONTEXT_END:
            if target != timestamps[-1]:
                raise ScorerProtocolError("context-end target must equal final context time")
        elif temporal_semantics is TemporalSemantics.NEXT_TARGET:
            if target <= timestamps[-1]:
                raise ScorerProtocolError("next-target time must follow final context time")
        else:
            raise ScorerProtocolError("unsupported temporal semantics")

    for field, values in (
        ("target_raw_values", batch.target_raw_values),
        ("target_model_values", batch.target_model_values),
    ):
        if temporal_semantics is TemporalSemantics.NEXT_TARGET and values is None:
            raise ScorerProtocolError(f"{field} is required for next-target scoring")
        if values is not None:
            if not isinstance(values, tuple) or len(values) != size:
                raise ScorerProtocolError(f"{field} length must equal N")
            for value in values:
                _validate_finite_pair(value, field)


def validate_result(
    batch: ScoreBatch,
    result: ScoreBatchResult,
    temporal_semantics: TemporalSemantics,
) -> None:
    """Reject malformed adapter output before any result reaches staging."""

    validate_batch(batch, temporal_semantics)
    if not isinstance(result, ScoreBatchResult):
        raise ScorerProtocolError("scorer must return ScoreBatchResult")
    if not isinstance(result.points, tuple) or len(result.points) != batch.size:
        raise ScorerProtocolError("scorer must return exactly N ordered points")
    for index, point in enumerate(result.points):
        if not isinstance(point, ScorePoint):
            raise ScorerProtocolError("scorer points must be ScorePoint values")
        if point.score_ts != batch.target_ts[index]:
            raise ScorerProtocolError("score_ts must match the corresponding target_ts")
        if isinstance(point.score, bool) or not isinstance(point.score, (float, int)):
            raise ScorerProtocolError("score must be numeric")
        if not math.isfinite(point.score):
            raise ScorerProtocolError("score must be finite")


@dataclass(frozen=True, slots=True)
class PreviewSimulatorScorer:
    archive_sha256: str
    temporal_semantics: TemporalSemantics = TemporalSemantics.CONTEXT_END

    def score(self, batch: ScoreBatch) -> ScoreBatchResult:
        validate_batch(batch, self.temporal_semantics)
        points = tuple(
            ScorePoint(
                score_ts=batch.target_ts[index],
                score=preview_score(
                    self.archive_sha256,
                    batch.model_version,
                    batch.segment_ids[index],
                    batch.eligible_window_ordinals[index],
                    batch.context_end_indices[index],
                ),
            )
            for index in range(batch.size)
        )
        result = ScoreBatchResult(points=points)
        validate_result(batch, result, self.temporal_semantics)
        return result
