"""Small deterministic oracle for transforming rows already streamed to staging."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from types import MappingProxyType
from typing import Iterable, Literal, Mapping


TARGET_SOURCE_UUID = "b02f3872-39a2-4b6f-a4ec-045a287fde4b"
CROP_START = datetime(2026, 2, 1)
CROP_END = datetime(2026, 6, 1)
VALIDATION_START = datetime(2026, 5, 10)
TEST_START = datetime(2026, 5, 20)
MAX_CONTIGUOUS_GAP = timedelta(seconds=600)
SUSPECT_BUFFER = timedelta(seconds=600)

DatasetSplit = Literal["train", "validation", "test"]


class ImportTransformError(ValueError):
    """The staged input cannot satisfy the preprocessing contract."""


@dataclass(frozen=True, slots=True)
class StagingRow:
    device_id: str
    data_index: int
    value: float
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class CorpusPoint:
    timestamp: datetime
    suhu: float
    rh: float
    corpus_index: int
    segment_id: int
    dataset_split: DatasetSplit


@dataclass(frozen=True, slots=True)
class ChannelScale:
    minimum: float
    maximum: float


@dataclass(frozen=True, slots=True)
class ImportTransformResult:
    points: tuple[CorpusPoint, ...]
    scaler: Mapping[str, ChannelScale]
    rejection_counts: Mapping[str, int]
    ignored_index_count: int


def _validate_staging_row(row: StagingRow) -> None:
    if not isinstance(row, StagingRow):
        raise ImportTransformError("staging rows must be StagingRow instances")
    if row.timestamp.tzinfo is not None:
        raise ImportTransformError("corpus timestamps must be naive Asia/Jakarta time")
    if isinstance(row.data_index, bool) or not isinstance(row.data_index, int):
        raise ImportTransformError("data_index must be an integer")
    if isinstance(row.value, bool) or not isinstance(row.value, (float, int)):
        raise ImportTransformError("value must be numeric")
    if not math.isfinite(row.value):
        raise ImportTransformError("value must be finite")


def _split(timestamp: datetime) -> DatasetSplit:
    if timestamp < VALIDATION_START:
        return "train"
    if timestamp < TEST_START:
        return "validation"
    return "test"


def _suspect_intervals(
    pairs: list[tuple[datetime, float, float]],
) -> tuple[tuple[datetime, datetime], ...]:
    suspect_times = [
        timestamp for timestamp, suhu, rh in pairs if suhu > 35 or rh > 80
    ]
    if not suspect_times:
        return ()

    episodes: list[tuple[datetime, datetime]] = []
    start = end = suspect_times[0]
    for timestamp in suspect_times[1:]:
        if timestamp - end <= MAX_CONTIGUOUS_GAP:
            end = timestamp
        else:
            episodes.append((start - SUSPECT_BUFFER, end + SUSPECT_BUFFER))
            start = end = timestamp
    episodes.append((start - SUSPECT_BUFFER, end + SUSPECT_BUFFER))
    return tuple(episodes)


def _in_intervals(
    timestamp: datetime, intervals: tuple[tuple[datetime, datetime], ...]
) -> bool:
    return any(start <= timestamp <= end for start, end in intervals)


def transform_staging_rows(
    rows: Iterable[StagingRow],
    *,
    target_source_uuid: str = TARGET_SOURCE_UUID,
) -> ImportTransformResult:
    """Apply the B02 preprocessing contract to an iterable of staged rows.

    The production importer is responsible for bounded CSV/COPY staging.  This
    deterministic oracle operates on the selected staging relation and is kept
    dependency-free so SQL/import implementations can parity-test against it.
    """

    grouped: dict[datetime, dict[int, set[float]]] = {}
    rejection_counts = {
        "wrong_device": 0,
        "outside_crop": 0,
        "unsupported_index": 0,
        "duplicate_identical": 0,
        "duplicate_conflict": 0,
        "incomplete_pair": 0,
        "invalid_or_sentinel": 0,
        "suspect_buffer": 0,
    }
    ignored_index_count = 0

    for row in rows:
        _validate_staging_row(row)
        if row.device_id != target_source_uuid:
            rejection_counts["wrong_device"] += 1
            continue
        if not CROP_START <= row.timestamp < CROP_END:
            rejection_counts["outside_crop"] += 1
            continue
        if 2 <= row.data_index <= 7:
            ignored_index_count += 1
            continue
        if row.data_index not in (0, 1):
            rejection_counts["unsupported_index"] += 1
            continue

        values = grouped.setdefault(row.timestamp, {}).setdefault(
            row.data_index, set()
        )
        if row.value in values:
            rejection_counts["duplicate_identical"] += 1
        values.add(float(row.value))

    valid_pairs: list[tuple[datetime, float, float]] = []
    for timestamp in sorted(grouped):
        channels = grouped[timestamp]
        if any(len(values) > 1 for values in channels.values()):
            rejection_counts["duplicate_conflict"] += 1
            continue
        if set(channels) != {0, 1}:
            rejection_counts["incomplete_pair"] += 1
            continue
        suhu = next(iter(channels[0]))
        rh = next(iter(channels[1]))
        if suhu <= 0 or rh <= 0 or suhu >= 200 or rh >= 200 or rh > 100:
            rejection_counts["invalid_or_sentinel"] += 1
            continue
        valid_pairs.append((timestamp, suhu, rh))

    suspect_intervals = _suspect_intervals(valid_pairs)
    clean_pairs = []
    for pair in valid_pairs:
        if _in_intervals(pair[0], suspect_intervals):
            rejection_counts["suspect_buffer"] += 1
        else:
            clean_pairs.append(pair)

    points: list[CorpusPoint] = []
    segment_id = -1
    previous_timestamp: datetime | None = None
    for corpus_index, (timestamp, suhu, rh) in enumerate(clean_pairs):
        if (
            previous_timestamp is None
            or timestamp - previous_timestamp > MAX_CONTIGUOUS_GAP
        ):
            segment_id += 1
        points.append(
            CorpusPoint(
                timestamp=timestamp,
                suhu=suhu,
                rh=rh,
                corpus_index=corpus_index,
                segment_id=segment_id,
                dataset_split=_split(timestamp),
            )
        )
        previous_timestamp = timestamp

    train = [point for point in points if point.dataset_split == "train"]
    if not train:
        raise ImportTransformError("at least one clean train point is required")
    scaler = MappingProxyType(
        {
            "suhu": ChannelScale(
                minimum=min(point.suhu for point in train),
                maximum=max(point.suhu for point in train),
            ),
            "rh": ChannelScale(
                minimum=min(point.rh for point in train),
                maximum=max(point.rh for point in train),
            ),
        }
    )
    return ImportTransformResult(
        points=tuple(points),
        scaler=scaler,
        rejection_counts=MappingProxyType(rejection_counts),
        ignored_index_count=ignored_index_count,
    )
