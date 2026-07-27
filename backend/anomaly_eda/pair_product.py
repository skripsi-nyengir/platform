from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, cast

import numpy as np  # pyright: ignore[reportMissingImports]

from .config import DEFAULT_CONFIG, EdaComputeConfig
from .input_adapter import RawInputAdapter


VIEW_RAW = "resolved_raw_pairs"
VIEW_SCREENED = "rule_screened_pairs"


@dataclass(frozen=True, slots=True)
class PairFlags:
    non_finite: np.ndarray
    disconnected: np.ndarray
    zero: np.ndarray
    range: np.ndarray
    duplicate: np.ndarray
    conflicting_duplicate: np.ndarray
    stale: np.ndarray
    near_zero: np.ndarray
    rule_screened: np.ndarray

    def __post_init__(self) -> None:
        size = int(self.rule_screened.size)
        for name in (
            "non_finite",
            "disconnected",
            "zero",
            "range",
            "duplicate",
            "conflicting_duplicate",
            "stale",
            "near_zero",
        ):
            if cast(np.ndarray, getattr(self, name)).shape != (size,):
                raise ValueError(f"PairFlags.{name} must have shape (n,)")

    def reason_masks(self) -> dict[str, np.ndarray]:
        return {
            "finite": self.non_finite,
            "connectivity": self.disconnected,
            "zero": self.zero,
            "range": self.range,
            "duplicate": self.duplicate,
            "stale": self.stale,
            "near_zero": self.near_zero,
            "conflicting_duplicate": self.conflicting_duplicate,
        }


@dataclass(frozen=True, slots=True)
class PairView:
    timestamps_epoch_s: np.ndarray
    values: np.ndarray
    segment_ids: Mapping[int, np.ndarray]

    def __post_init__(self) -> None:
        size = int(self.timestamps_epoch_s.size)
        if self.values.shape != (size, 2):
            raise ValueError("PairView.values must have shape (n, 2)")
        if any(value.shape != (size,) for value in self.segment_ids.values()):
            raise ValueError("PairView.segment_ids values must have shape (n,)")

    @property
    def pair_count(self) -> int:
        return int(self.timestamps_epoch_s.size)


@dataclass(frozen=True, slots=True)
class ExactPairProduct:
    """Resolved exact-timestamp pairs shared by temporal/statistical compute.

    ``raw_view`` contains every exact pair. ``rule_screened_view`` contains only
    the retained rows. Flags always align one-for-one with ``raw_view``.
    """

    raw_view: PairView
    rule_screened_view: PairView
    flags: PairFlags
    duplicate_audit: tuple[dict[str, Any], ...]
    audit: dict[str, Any]

    def view(self, name: str) -> PairView:
        if name == VIEW_RAW:
            return self.raw_view
        if name == VIEW_SCREENED:
            return self.rule_screened_view
        raise ValueError(f"unknown pair view: {name}")


@dataclass(frozen=True, slots=True)
class PairChunk:
    timestamps_epoch_s: np.ndarray
    values: np.ndarray
    non_finite: np.ndarray
    disconnected: np.ndarray
    zero: np.ndarray
    range_flag: np.ndarray
    duplicate: np.ndarray
    conflicting_duplicate: np.ndarray
    stale: np.ndarray
    rule_screened: np.ndarray
    segment_ids: np.ndarray

    def __post_init__(self) -> None:
        size = int(self.timestamps_epoch_s.size)
        if self.values.shape != (size, 2):
            raise ValueError("PairChunk.values must have shape (n, 2)")
        for name in (
            "non_finite",
            "disconnected",
            "zero",
            "range_flag",
            "duplicate",
            "conflicting_duplicate",
            "stale",
            "rule_screened",
            "segment_ids",
        ):
            if cast(np.ndarray, getattr(self, name)).shape != (size,):
                raise ValueError(f"PairChunk.{name} must have shape (n,)")


def build_pair_product(
    adapter: RawInputAdapter,
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> ExactPairProduct:
    batch: dict[str, list[Any]] = {
        "timestamps": [],
        "values": [],
        "connectivity": [],
        "duplicate": [],
        "conflicting": [],
        "stale": [],
    }
    chunks: dict[str, list[np.ndarray]] = {name: [] for name in batch}
    duplicate_audit: list[dict[str, Any]] = []
    current_timestamp: int | None = None
    groups: dict[int, list[tuple[float, bool]]] = {0: [], 1: []}
    previous_pair_timestamp: int | None = None
    previous_pair_values: tuple[float, float] | None = None
    stale_start: list[int | None] = [None, None]
    union = intersection = missing0 = missing1 = duplicate_groups = 0
    conflicting_pairs = gap_count = 0
    cadence_counts = np.zeros(
        config.cadence.positive_delta_ceiling_seconds + 1, dtype=np.int64
    )

    def flush_batch() -> None:
        if not batch["timestamps"]:
            return
        chunks["timestamps"].append(
            np.asarray(batch["timestamps"], dtype=np.int64)
        )
        chunks["values"].append(
            np.asarray(batch["values"], dtype=np.float64).reshape((-1, 2))
        )
        chunks["connectivity"].append(
            np.asarray(batch["connectivity"], dtype=bool).reshape((-1, 2))
        )
        for name in ("duplicate", "conflicting", "stale"):
            chunks[name].append(np.asarray(batch[name], dtype=bool))
        for entries in batch.values():
            entries.clear()

    def finish_timestamp() -> None:
        nonlocal union, intersection, missing0, missing1, duplicate_groups
        nonlocal conflicting_pairs, previous_pair_timestamp, previous_pair_values
        nonlocal gap_count
        if current_timestamp is None:
            return
        union += 1
        present = {channel for channel in (0, 1) if groups[channel]}
        if present != {0, 1}:
            missing0 += int(0 not in present)
            missing1 += int(1 not in present)
            return
        intersection += 1
        pair_duplicate = any(len(groups[channel]) > 1 for channel in (0, 1))
        duplicate_groups += sum(len(groups[channel]) > 1 for channel in (0, 1))
        pair_conflicting = any(_conflicting(groups[channel]) for channel in (0, 1))
        conflicting_pairs += int(pair_conflicting)
        pair_connected = tuple(
            all(item[1] for item in groups[channel]) for channel in (0, 1)
        )
        for channel in (0, 1):
            if len(groups[channel]) > 1:
                record = _duplicate_record(groups[channel], current_timestamp, channel)
                if record is not None:
                    duplicate_audit.append(record)
        resolved = (_median(groups[0]), _median(groups[1]))
        if previous_pair_timestamp is not None:
            delta = current_timestamp - previous_pair_timestamp
            if delta > config.cadence.primary_gap_seconds:
                gap_count += 1
                stale_start[:] = [None, None]
            if 0 < delta <= config.cadence.positive_delta_ceiling_seconds:
                cadence_counts[delta] += 1
        pair_stale = False
        for channel in (0, 1):
            same = (
                previous_pair_values is not None
                and resolved[channel] == previous_pair_values[channel]
            )
            valid_gap = (
                previous_pair_timestamp is not None
                and 0 < current_timestamp - previous_pair_timestamp
                <= config.cadence.primary_gap_seconds
            )
            if same and valid_gap:
                if stale_start[channel] is None:
                    stale_start[channel] = previous_pair_timestamp
                pair_stale |= current_timestamp - cast(int, stale_start[channel]) > 0
            else:
                stale_start[channel] = None
        batch["timestamps"].append(current_timestamp)
        batch["values"].append(resolved)
        batch["connectivity"].append(cast(tuple[bool, bool], pair_connected))
        batch["duplicate"].append(pair_duplicate)
        batch["conflicting"].append(pair_conflicting)
        batch["stale"].append(pair_stale)
        previous_pair_timestamp, previous_pair_values = current_timestamp, resolved
        if len(batch["timestamps"]) == config.streaming.maximum_chunk_pairs:
            flush_batch()

    for chunk in adapter.iter_chunks():
        for position in range(chunk.timestamps_epoch_s.size):
            timestamp = int(chunk.timestamps_epoch_s[position])
            if current_timestamp is None:
                current_timestamp = timestamp
            elif timestamp != current_timestamp:
                finish_timestamp()
                current_timestamp = timestamp
                groups = {0: [], 1: []}
            channel = int(chunk.data_indices[position])
            groups[channel].append(
                (float(chunk.values[position]), bool(chunk.is_connected[position]))
            )
    finish_timestamp()
    flush_batch()
    if adapter.audit is None:
        raise RuntimeError("raw input adapter did not finish its audit")

    timestamp_array = _join_chunks(chunks["timestamps"], np.int64, (0,))
    value_array = _join_chunks(chunks["values"], np.float64, (0, 2))
    connectivity = _join_chunks(chunks["connectivity"], bool, (0, 2))
    duplicate_array = _join_chunks(chunks["duplicate"], bool, (0,))
    conflicting_array = _join_chunks(chunks["conflicting"], bool, (0,))
    stale_array = _join_chunks(chunks["stale"], bool, (0,))
    chunks.clear()
    non_finite = ~np.isfinite(value_array).all(axis=1)
    disconnected = ~connectivity.all(axis=1)
    zero = (value_array == 0.0).any(axis=1) & ~non_finite
    near_zero = (
        np.abs(value_array) <= config.quality.near_zero_absolute
    ).any(axis=1)
    range_flag = _range_mask(value_array, config)
    rule_screened = ~(
        non_finite | disconnected | zero | range_flag | duplicate_array
    )
    flags = PairFlags(
        non_finite=non_finite,
        disconnected=disconnected,
        zero=zero,
        range=range_flag,
        duplicate=duplicate_array,
        conflicting_duplicate=conflicting_array,
        stale=stale_array,
        near_zero=near_zero,
        rule_screened=rule_screened,
    )
    boundaries = (
        config.cadence.primary_gap_seconds,
        *config.cadence.gap_sensitivity_seconds,
    )
    segment_ids = {
        boundary: _segment_ids(timestamp_array, boundary) for boundary in boundaries
    }
    raw_view = PairView(timestamp_array, value_array, segment_ids)
    screened_view = PairView(
        timestamp_array[rule_screened],
        value_array[rule_screened],
        {
            boundary: ids[rule_screened] for boundary, ids in segment_ids.items()
        },
    )
    masks = flags.reason_masks()
    exclusion_names = ("finite", "connectivity", "zero", "range", "duplicate")
    overlap = {
        first: {
            second: int(np.count_nonzero(masks[first] & masks[second]))
            for second in exclusion_names
        }
        for first in exclusion_names
    }
    positive_count = int(cadence_counts.sum())
    median_delta = _histogram_median(cadence_counts, positive_count)
    input_audit = adapter.audit.as_dict()
    audit = {
        **input_audit,
        "union_timestamps": union,
        "intersection_timestamps": intersection,
        "missing_idx0_timestamps": missing0,
        "missing_idx1_timestamps": missing1,
        "duplicate_group_count": duplicate_groups,
        "conflicting_duplicate_pair_count": conflicting_pairs,
        "exact_pair_count": intersection,
        "rule_screened_pair_count": int(np.count_nonzero(rule_screened)),
        "reason_counts": {
            name: int(np.count_nonzero(mask)) for name, mask in masks.items()
        },
        "reason_mask_sha256": {
            name: _mask_hash(mask) for name, mask in masks.items()
        },
        "reason_overlap": overlap,
        "positive_delta_at_most_gap_count": positive_count,
        "observed_median_positive_delta_at_most_gap": median_delta,
        "gap_above_primary_count": gap_count,
        "cadence_gate": "pass"
        if median_delta == config.cadence.expected_seconds
        else "fail",
    }
    return ExactPairProduct(
        raw_view=raw_view,
        rule_screened_view=screened_view,
        flags=flags,
        duplicate_audit=tuple(duplicate_audit),
        audit=audit,
    )


def iter_pair_chunks(
    product: ExactPairProduct,
    *,
    config: EdaComputeConfig = DEFAULT_CONFIG,
    chunk_pairs: int | None = None,
) -> Iterator[PairChunk]:
    chunk_pairs = chunk_pairs or config.streaming.maximum_chunk_pairs
    if not 0 < chunk_pairs <= config.streaming.maximum_chunk_pairs:
        raise ValueError("chunk_pairs must be in [1, 250000]")
    raw = product.raw_view
    flags = product.flags
    segment_ids = raw.segment_ids[config.cadence.primary_gap_seconds]
    for start in range(0, raw.pair_count, chunk_pairs):
        end = min(raw.pair_count, start + chunk_pairs)
        yield PairChunk(
            timestamps_epoch_s=raw.timestamps_epoch_s[start:end],
            values=raw.values[start:end],
            non_finite=flags.non_finite[start:end],
            disconnected=flags.disconnected[start:end],
            zero=flags.zero[start:end],
            range_flag=flags.range[start:end],
            duplicate=flags.duplicate[start:end],
            conflicting_duplicate=flags.conflicting_duplicate[start:end],
            stale=flags.stale[start:end],
            rule_screened=flags.rule_screened[start:end],
            segment_ids=segment_ids[start:end],
        )


def v3_source_audit(product: ExactPairProduct) -> dict[str, Any]:
    keys = (
        "sha256",
        "size_bytes",
        "row_count",
        "start",
        "cutoff_inclusive",
        "union_timestamps",
        "intersection_timestamps",
        "missing_idx0_timestamps",
        "missing_idx1_timestamps",
        "duplicate_group_count",
        "conflicting_duplicate_pair_count",
        "exact_pair_count",
        "rule_screened_pair_count",
        "positive_delta_at_most_gap_count",
        "observed_median_positive_delta_at_most_gap",
        "gap_above_primary_count",
        "cadence_gate",
        "raw_open_count",
        "buffer_bytes",
    )
    return {key: product.audit[key] for key in keys}


def _median(values: Sequence[tuple[float, bool]]) -> float:
    return float(
        np.median(np.asarray([item[0] for item in values], dtype=np.float64))
    )


def _signature(value: float) -> tuple[str, float | None]:
    if math.isnan(value):
        return ("nan", None)
    if math.isinf(value):
        return ("inf" if value > 0 else "-inf", None)
    return ("finite", value)


def _conflicting(values: Sequence[tuple[float, bool]]) -> bool:
    return (
        len({_signature(value) for value, _ in values}) > 1
        or len({connected for _, connected in values}) > 1
    )


def _duplicate_record(
    group: Sequence[tuple[float, bool]],
    timestamp: int,
    channel: int,
) -> dict[str, Any] | None:
    if len(group) <= 1:
        return None
    finite = np.asarray(
        [value for value, _ in group if math.isfinite(value)], dtype=np.float64
    )
    median = float(np.median(finite)) if finite.size else None
    connected = {item[1] for item in group}
    conflicting = _conflicting(group)
    return {
        "timestamp_epoch_s": timestamp,
        "channel_index": channel,
        "channel": ("Suhu", "RH")[channel],
        "group_size": len(group),
        "minimum": float(np.min(finite)) if finite.size else None,
        "maximum": float(np.max(finite)) if finite.size else None,
        "range": float(np.max(finite) - np.min(finite)) if finite.size else None,
        "median": median,
        "mad": float(np.median(np.abs(finite - median)))
        if finite.size and median is not None
        else None,
        "identical": not conflicting,
        "conflicting": conflicting,
        "connectivity_disagreement": len(connected) > 1,
    }


def _range_mask(values: np.ndarray, config: EdaComputeConfig) -> np.ndarray:
    valid = np.isfinite(values)
    result = valid[:, 0] & (
        (values[:, 0] < config.quality.suhu_lower_exclusive)
        | (values[:, 0] > config.quality.suhu_upper_inclusive)
    )
    result |= valid[:, 1] & (
        (values[:, 1] < config.quality.rh_lower_exclusive)
        | (values[:, 1] > config.quality.rh_upper_inclusive)
    )
    return result


def _join_chunks(
    chunks: Sequence[np.ndarray],
    dtype: Any,
    empty_shape: tuple[int, ...],
) -> np.ndarray:
    if not chunks:
        return np.empty(empty_shape, dtype=dtype)
    if len(chunks) == 1:
        return chunks[0]
    return np.concatenate(chunks)


def _segment_ids(timestamps: np.ndarray, boundary_seconds: int) -> np.ndarray:
    result = np.zeros(timestamps.size, dtype=np.int32)
    if timestamps.size > 1:
        result[1:] = np.cumsum(
            np.diff(timestamps) > boundary_seconds, dtype=np.int32
        )
    return result


def _histogram_median(counts: np.ndarray, total: int) -> float | None:
    if total == 0:
        return None
    cumulative = np.cumsum(counts)
    left = int(np.searchsorted(cumulative, (total - 1) // 2 + 1))
    right = int(np.searchsorted(cumulative, total // 2 + 1))
    return (left + right) / 2.0


def _mask_hash(mask: np.ndarray) -> str:
    packed = np.packbits(mask.astype(np.uint8), bitorder="little")
    digest = hashlib.sha256()
    digest.update(np.asarray([mask.size], dtype="<i8").tobytes())
    digest.update(packed.tobytes())
    return digest.hexdigest()


def duplicate_audit_hash(records: Sequence[dict[str, Any]]) -> str:
    encoded = json.dumps(
        list(records),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "ExactPairProduct",
    "PairChunk",
    "PairFlags",
    "PairView",
    "VIEW_RAW",
    "VIEW_SCREENED",
    "build_pair_product",
    "duplicate_audit_hash",
    "iter_pair_chunks",
    "v3_source_audit",
]
