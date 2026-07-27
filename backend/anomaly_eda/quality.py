from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
import math
import struct
import tempfile
from typing import Any, cast

import numpy as np  # pyright: ignore[reportMissingImports]

from .config import (
    ALGORITHM_VERSION,
    CONFIG_HASH,
    DEFAULT_CONFIG,
    EdaComputeConfig,
)
from .input_adapter import RawInputAdapter
from .pair_product import (
    ExactPairProduct,
    PairChunk,
    VIEW_RAW,
    VIEW_SCREENED,
    build_pair_product,
    iter_pair_chunks,
    v3_source_audit,
)


STATUS_NAMES = ("underflow", "in_domain", "overflow")
_RECORD = struct.Struct("<qddIB")
_NONFINITE = 1 << 0
_DISCONNECTED = 1 << 1
_ZERO = 1 << 2
_RANGE = 1 << 3
_DUPLICATE = 1 << 4
_CONFLICTING = 1 << 5
_STALE = 1 << 6
_SCREENED = 1 << 7


@dataclass(frozen=True, slots=True)
class VisualDiagnostics:
    joint_density: dict[str, Any]
    univariate: dict[str, Any]
    quality_excerpt: dict[str, Any]
    instrumentation: dict[str, int]

    def payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class QualityComputeResult:
    pair_product: ExactPairProduct
    diagnostics: VisualDiagnostics
    source_audit: dict[str, Any]
    count_conservation: dict[str, Any]
    algorithm_version: str = ALGORITHM_VERSION
    config_hash: str = CONFIG_HASH


@dataclass(frozen=True, slots=True)
class _Event:
    kind: str
    start: int
    end: int
    segment_id: int
    channel_index: int | None = None

    @property
    def duration(self) -> int:
        return self.end - self.start


def bin_edges(config: EdaComputeConfig = DEFAULT_CONFIG) -> dict[str, np.ndarray]:
    bins = config.binning
    return {
        "joint_suhu": np.linspace(
            bins.suhu_lower, bins.suhu_upper, bins.joint_suhu_bins + 1
        ),
        "joint_rh": np.linspace(
            bins.rh_lower, bins.rh_upper, bins.joint_rh_bins + 1
        ),
        "univariate_suhu": np.linspace(
            bins.suhu_lower, bins.suhu_upper, bins.univariate_suhu_bins + 1
        ),
        "univariate_rh": np.linspace(
            bins.rh_lower, bins.rh_upper, bins.univariate_rh_bins + 1
        ),
    }


def _axis_status(values: np.ndarray, lower: float, upper: float) -> np.ndarray:
    status = np.ones(values.shape, dtype=np.int8)
    status[values < lower] = 0
    status[values > upper] = 2
    return status


class VisualDiagnosticsReducer:
    def __init__(self, config: EdaComputeConfig = DEFAULT_CONFIG) -> None:
        self.config = config
        self.edges = bin_edges(config)
        self._joint = {
            view: np.zeros(
                (config.binning.joint_suhu_bins, config.binning.joint_rh_bins),
                dtype=np.int64,
            )
            for view in (VIEW_RAW, VIEW_SCREENED)
        }
        self._one = {
            channel: {
                view: np.zeros(
                    config.binning.univariate_suhu_bins
                    if channel == 0
                    else config.binning.univariate_rh_bins,
                    dtype=np.int64,
                )
                for view in (VIEW_RAW, VIEW_SCREENED)
            }
            for channel in (0, 1)
        }
        self._joint_audit = {
            view: self._empty_joint_audit() for view in (VIEW_RAW, VIEW_SCREENED)
        }
        self._one_audit = {
            channel: {
                view: self._empty_axis_audit() for view in (VIEW_RAW, VIEW_SCREENED)
            }
            for channel in (0, 1)
        }
        self._spool = tempfile.TemporaryFile(mode="w+b")
        self._maximum_chunk = 0
        self._pairs = 0
        self._maximum_retained = 0
        self._best_zero: _Event | None = None
        self._open_zero: _Event | None = None
        self._best_stale: _Event | None = None
        self._open_stale: list[_Event | None] = [None, None]
        self._first_conflicting: _Event | None = None
        self._first_dense: _Event | None = None
        self._previous_timestamp: int | None = None
        self._previous_values: tuple[float, float] | None = None
        self._previous_segment: int | None = None
        self._active_segment = 0

    @staticmethod
    def _empty_axis_audit() -> dict[str, int]:
        return {
            key: 0
            for key in (
                "total",
                "finite",
                "non_finite",
                "underflow",
                "in_domain",
                "overflow",
                "excluded_finite",
            )
        }

    @staticmethod
    def _empty_joint_audit() -> dict[str, Any]:
        return {
            "total_pairs": 0,
            "non_finite_pairs": 0,
            "axis_status_matrix": [[0, 0, 0] for _ in range(3)],
            "excluded_pairs": 0,
        }

    def update(self, chunk: PairChunk) -> None:
        size = int(chunk.timestamps_epoch_s.size)
        if size > self.config.streaming.maximum_chunk_pairs:
            raise ValueError("emitted pair chunk exceeds configured maximum")
        if size == 0:
            return
        if np.any(np.diff(chunk.timestamps_epoch_s) <= 0):
            raise ValueError("pair timestamps must be strictly increasing within a chunk")
        if (
            self._previous_timestamp is not None
            and int(chunk.timestamps_epoch_s[0]) <= self._previous_timestamp
        ):
            raise ValueError("pair timestamps must be strictly increasing across chunks")
        self._maximum_chunk = max(self._maximum_chunk, size)
        self._pairs += size
        self._update_histograms(chunk)
        for position in range(size):
            self._update_events_and_spool(chunk, position)

    def _update_histograms(self, chunk: PairChunk) -> None:
        values = np.asarray(chunk.values, dtype=np.float64)
        screened = np.asarray(chunk.rule_screened, dtype=bool)
        finite_pair = np.isfinite(values).all(axis=1)
        joint_edges = (self.edges["joint_suhu"], self.edges["joint_rh"])
        weights = {
            VIEW_RAW: np.ones(values.shape[0], dtype=np.int64),
            VIEW_SCREENED: screened.astype(np.int64),
        }
        for view, view_weights in weights.items():
            histogram = np.histogram2d(
                values[:, 0], values[:, 1], bins=joint_edges, weights=view_weights
            )[0]
            self._joint[view] += histogram.astype(np.int64)
            selected = (
                np.ones(values.shape[0], dtype=bool)
                if view == VIEW_RAW
                else screened
            )
            audit = self._joint_audit[view]
            audit["total_pairs"] += int(np.count_nonzero(selected))
            audit["non_finite_pairs"] += int(
                np.count_nonzero(selected & ~finite_pair)
            )
            finite_selected = selected & finite_pair
            statuses = (
                _axis_status(
                    values[:, 0],
                    self.config.binning.suhu_lower,
                    self.config.binning.suhu_upper,
                ),
                _axis_status(
                    values[:, 1],
                    self.config.binning.rh_lower,
                    self.config.binning.rh_upper,
                ),
            )
            matrix = cast(list[list[int]], audit["axis_status_matrix"])
            for first in range(3):
                for second in range(3):
                    matrix[first][second] += int(
                        np.count_nonzero(
                            finite_selected
                            & (statuses[0] == first)
                            & (statuses[1] == second)
                        )
                    )
            if view == VIEW_SCREENED:
                audit["excluded_pairs"] += int(
                    values.shape[0] - np.count_nonzero(screened)
                )
        for channel, edge_name in ((0, "univariate_suhu"), (1, "univariate_rh")):
            channel_values = values[:, channel]
            finite = np.isfinite(channel_values)
            lower = float(self.edges[edge_name][0])
            upper = float(self.edges[edge_name][-1])
            for view, view_weights in weights.items():
                self._one[channel][view] += np.histogram(
                    channel_values, bins=self.edges[edge_name], weights=view_weights
                )[0].astype(np.int64)
                selected = (
                    np.ones(values.shape[0], dtype=bool)
                    if view == VIEW_RAW
                    else screened
                )
                audit = self._one_audit[channel][view]
                audit["total"] += int(np.count_nonzero(selected))
                audit["finite"] += int(np.count_nonzero(selected & finite))
                audit["non_finite"] += int(np.count_nonzero(selected & ~finite))
                audit["underflow"] += int(
                    np.count_nonzero(selected & finite & (channel_values < lower))
                )
                audit["in_domain"] += int(
                    np.count_nonzero(
                        selected
                        & finite
                        & (channel_values >= lower)
                        & (channel_values <= upper)
                    )
                )
                audit["overflow"] += int(
                    np.count_nonzero(selected & finite & (channel_values > upper))
                )
                if view == VIEW_SCREENED:
                    audit["excluded_finite"] += int(
                        np.count_nonzero(~screened & finite)
                    )

    def _update_events_and_spool(self, chunk: PairChunk, position: int) -> None:
        timestamp = int(chunk.timestamps_epoch_s[position])
        values = (
            float(chunk.values[position, 0]),
            float(chunk.values[position, 1]),
        )
        if (
            self._previous_timestamp is not None
            and timestamp - self._previous_timestamp
            > self.config.cadence.primary_gap_seconds
        ):
            self._active_segment += 1
        segment = self._active_segment
        flags = (
            (_NONFINITE if bool(chunk.non_finite[position]) else 0)
            | (_DISCONNECTED if bool(chunk.disconnected[position]) else 0)
            | (_ZERO if bool(chunk.zero[position]) else 0)
            | (_RANGE if bool(chunk.range_flag[position]) else 0)
            | (_DUPLICATE if bool(chunk.duplicate[position]) else 0)
            | (
                _CONFLICTING
                if bool(chunk.conflicting_duplicate[position])
                else 0
            )
            | (_STALE if bool(chunk.stale[position]) else 0)
            | (_SCREENED if bool(chunk.rule_screened[position]) else 0)
        )
        self._spool.write(_RECORD.pack(timestamp, values[0], values[1], segment, flags))
        same_segment = self._previous_segment == segment
        delta = (
            timestamp - self._previous_timestamp
            if self._previous_timestamp is not None
            else None
        )
        both_zero = values[0] == 0.0 and values[1] == 0.0
        if both_zero:
            if (
                self._open_zero is None
                or not same_segment
                or delta is None
                or not 0 < delta <= self.config.cadence.primary_gap_seconds
            ):
                self._finish_zero()
                self._open_zero = _Event("both_zero", timestamp, timestamp, segment)
            else:
                self._open_zero = _Event(
                    "both_zero", self._open_zero.start, timestamp, segment
                )
        else:
            self._finish_zero()
        for channel in (0, 1):
            same_value = (
                self._previous_values is not None
                and values[channel] == self._previous_values[channel]
            )
            if (
                same_segment
                and delta is not None
                and 0 < delta <= self.config.cadence.primary_gap_seconds
                and same_value
            ):
                current = self._open_stale[channel]
                start = self._previous_timestamp if current is None else current.start
                self._open_stale[channel] = _Event(
                    "stale", cast(int, start), timestamp, segment, channel
                )
            else:
                self._finish_stale(channel)
        if (
            bool(chunk.conflicting_duplicate[position])
            and self._first_conflicting is None
        ):
            self._first_conflicting = _Event(
                "conflicting_duplicate", timestamp, timestamp, segment
            )
        if (
            self._first_dense is None
            and same_segment
            and delta is not None
            and self.config.cadence.acceptance_min_seconds
            <= delta
            <= self.config.cadence.acceptance_max_seconds
        ):
            self._first_dense = _Event(
                "dense", cast(int, self._previous_timestamp), timestamp, segment
            )
        self._previous_timestamp = timestamp
        self._previous_values = values
        self._previous_segment = segment

    def _finish_zero(self) -> None:
        candidate = self._open_zero
        if candidate is not None and (
            self._best_zero is None
            or (-candidate.duration, candidate.start)
            < (-self._best_zero.duration, self._best_zero.start)
        ):
            self._best_zero = candidate
        self._open_zero = None

    def _finish_stale(self, channel: int) -> None:
        candidate = self._open_stale[channel]
        if (
            candidate is not None
            and candidate.duration >= self.config.quality.stale_duration_seconds
            and (
                self._best_stale is None
                or (
                    -candidate.duration,
                    candidate.start,
                    cast(int, candidate.channel_index),
                )
                < (
                    -self._best_stale.duration,
                    self._best_stale.start,
                    cast(int, self._best_stale.channel_index),
                )
            )
        ):
            self._best_stale = candidate
        self._open_stale[channel] = None

    def _selected_event(self) -> _Event | None:
        self._finish_zero()
        self._finish_stale(0)
        self._finish_stale(1)
        return (
            self._best_zero
            or self._best_stale
            or self._first_conflicting
            or self._first_dense
        )

    def _iter_spool(self) -> Iterator[tuple[int, float, float, int, int]]:
        self._spool.seek(0)
        while raw := self._spool.read(_RECORD.size):
            if len(raw) != _RECORD.size:
                raise ValueError("internal excerpt spool is truncated")
            yield cast(tuple[int, float, float, int, int], _RECORD.unpack(raw))

    def _excerpt(self) -> dict[str, Any]:
        event = self._selected_event()
        if event is None:
            return {
                "selection_kind": "empty",
                "event_start_epoch_s": None,
                "event_end_epoch_s": None,
                "window_start_epoch_s": None,
                "window_end_epoch_s": None,
                "channel_index": None,
                "records": [],
            }
        lower = event.start - self.config.excerpt.context_seconds
        upper = event.end + self.config.excerpt.context_seconds
        counts = [0, 0, 0]
        observed_start: int | None = None
        observed_end: int | None = None
        for timestamp, _, _, segment, _ in self._iter_spool():
            if segment != event.segment_id or timestamp < lower or timestamp > upper:
                continue
            observed_start = timestamp if observed_start is None else observed_start
            observed_end = timestamp
            counts[0 if timestamp < event.start else 1 if timestamp <= event.end else 2] += 1
        cap = self.config.excerpt.maximum_points
        event_take = min(counts[1], cap)
        remaining = cap - event_take
        before_take = min(counts[0], remaining // 2)
        after_take = min(counts[2], remaining - before_take)
        leftover = remaining - before_take - after_take
        if leftover:
            extra_before = min(counts[0] - before_take, leftover)
            before_take += extra_before
            leftover -= extra_before
            after_take += min(counts[2] - after_take, leftover)
        before_skip = counts[0] - before_take
        selected: list[dict[str, Any]] = []
        seen_before = seen_event = seen_after = 0
        for timestamp, suhu, rh, segment, flags in self._iter_spool():
            if segment != event.segment_id or timestamp < lower or timestamp > upper:
                continue
            if timestamp < event.start:
                keep = seen_before >= before_skip
                seen_before += 1
            elif timestamp <= event.end:
                keep = seen_event < event_take
                seen_event += 1
            else:
                keep = seen_after < after_take
                seen_after += 1
            if keep:
                selected.append(_record_payload(timestamp, suhu, rh, flags))
        self._maximum_retained = max(self._maximum_retained, len(selected))
        return {
            "selection_kind": event.kind,
            "event_start_epoch_s": event.start,
            "event_end_epoch_s": event.end,
            "window_start_epoch_s": observed_start,
            "window_end_epoch_s": observed_end,
            "channel_index": event.channel_index,
            "records": selected,
        }

    def finalize(self) -> VisualDiagnostics:
        excerpt = self._excerpt()
        joint_views = {
            view: {
                "histogram": self._joint[view].tolist(),
                "audit": self._joint_audit[view],
            }
            for view in (VIEW_RAW, VIEW_SCREENED)
        }
        channels: dict[str, Any] = {}
        for channel, name, edge_name in (
            (0, "Suhu", "univariate_suhu"),
            (1, "RH", "univariate_rh"),
        ):
            views: dict[str, Any] = {}
            for view in (VIEW_RAW, VIEW_SCREENED):
                histogram = self._one[channel][view]
                cumulative = np.cumsum(histogram, dtype=np.int64)
                finite_count = self._one_audit[channel][view]["finite"]
                fraction = (
                    cumulative.astype(np.float64) / finite_count
                    if finite_count
                    else np.zeros(histogram.size, dtype=np.float64)
                )
                views[view] = {
                    "histogram": histogram.tolist(),
                    "ecdf_count": cumulative.tolist(),
                    "ecdf_fraction": fraction.tolist(),
                    "audit": self._one_audit[channel][view],
                }
            channels[name] = {
                "unit": "°C" if channel == 0 else "%",
                "edges": self.edges[edge_name].tolist(),
                "views": views,
            }
        result = VisualDiagnostics(
            joint_density={
                "edges": {
                    "suhu": self.edges["joint_suhu"].tolist(),
                    "rh": self.edges["joint_rh"].tolist(),
                },
                "views": joint_views,
            },
            univariate={"channels": channels},
            quality_excerpt=excerpt,
            instrumentation={
                "pair_count": self._pairs,
                "maximum_emitted_chunk_pairs": self._maximum_chunk,
                "maximum_retained_excerpt_records": self._maximum_retained,
                "excerpt_spool_record_bytes": _RECORD.size,
            },
        )
        _validate_conservation(result)
        return result

    def close(self) -> None:
        self._spool.close()


def build_visual_diagnostics(
    chunks: Iterable[PairChunk],
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> VisualDiagnostics:
    reducer = VisualDiagnosticsReducer(config)
    try:
        for chunk in chunks:
            reducer.update(chunk)
        return reducer.finalize()
    finally:
        reducer.close()


def select_excerpt(
    chunks: Iterable[PairChunk],
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    return build_visual_diagnostics(chunks, config).quality_excerpt


def compute_quality(
    adapter: RawInputAdapter,
    config: EdaComputeConfig = DEFAULT_CONFIG,
    *,
    enforce_cadence_gate: bool = True,
) -> QualityComputeResult:
    product = build_pair_product(adapter, config)
    if enforce_cadence_gate and product.audit["cadence_gate"] != "pass":
        raise ValueError("observed cadence publication gate failed")
    diagnostics = build_visual_diagnostics(
        iter_pair_chunks(
            product,
            config=config,
            chunk_pairs=config.streaming.maximum_chunk_pairs,
        ),
        config,
    )
    return QualityComputeResult(
        pair_product=product,
        diagnostics=diagnostics,
        source_audit=v3_source_audit(product),
        count_conservation=count_conservation(diagnostics),
    )


def count_conservation(diagnostics: VisualDiagnostics) -> dict[str, Any]:
    return {
        "status": "pass",
        "joint": {
            view: diagnostics.joint_density["views"][view]["audit"]
            for view in (VIEW_RAW, VIEW_SCREENED)
        },
        "univariate": {
            channel: {
                view: diagnostics.univariate["channels"][channel]["views"][view][
                    "audit"
                ]
                for view in (VIEW_RAW, VIEW_SCREENED)
            }
            for channel in ("Suhu", "RH")
        },
        "equations": [
            "total = finite + non_finite",
            "finite = underflow + in_domain + overflow",
            "raw_finite = screened_finite + excluded_finite",
            "total_pairs = non_finite_pairs + sum(axis_status_matrix)",
            "raw_total_pairs = screened_total_pairs + excluded_pairs",
        ],
    }


def _validate_conservation(result: VisualDiagnostics) -> None:
    for channel in (0, 1):
        raw = result.univariate["channels"][("Suhu", "RH")[channel]]["views"][
            VIEW_RAW
        ]["audit"]
        screened = result.univariate["channels"][("Suhu", "RH")[channel]][
            "views"
        ][VIEW_SCREENED]["audit"]
        for audit in (raw, screened):
            if audit["total"] != audit["finite"] + audit["non_finite"]:
                raise ValueError("univariate finite count conservation failed")
            if audit["finite"] != (
                audit["underflow"] + audit["in_domain"] + audit["overflow"]
            ):
                raise ValueError("univariate domain count conservation failed")
        if raw["finite"] != screened["finite"] + screened["excluded_finite"]:
            raise ValueError("univariate screened count conservation failed")
    for view in (VIEW_RAW, VIEW_SCREENED):
        record = result.joint_density["views"][view]
        audit = record["audit"]
        matrix = cast(list[list[int]], audit["axis_status_matrix"])
        if audit["total_pairs"] != audit["non_finite_pairs"] + sum(
            map(sum, matrix)
        ):
            raise ValueError("joint pair count conservation failed")
        if sum(map(sum, record["histogram"])) != matrix[1][1]:
            raise ValueError("joint histogram count conservation failed")
    raw_total = result.joint_density["views"][VIEW_RAW]["audit"]["total_pairs"]
    screened = result.joint_density["views"][VIEW_SCREENED]["audit"]
    if raw_total != screened["total_pairs"] + screened["excluded_pairs"]:
        raise ValueError("joint screened count conservation failed")


def _record_payload(timestamp: int, suhu: float, rh: float, flags: int) -> dict[str, Any]:
    return {
        "timestamp_epoch_s": timestamp,
        "suhu": suhu if math.isfinite(suhu) else None,
        "rh": rh if math.isfinite(rh) else None,
        "rule_screened": bool(flags & _SCREENED),
        "non_finite": bool(flags & _NONFINITE),
        "disconnected": bool(flags & _DISCONNECTED),
        "zero": bool(flags & _ZERO),
        "range": bool(flags & _RANGE),
        "duplicate": bool(flags & _DUPLICATE),
        "conflicting_duplicate": bool(flags & _CONFLICTING),
        "stale": bool(flags & _STALE),
    }


__all__ = [
    "QualityComputeResult",
    "VisualDiagnostics",
    "VisualDiagnosticsReducer",
    "bin_edges",
    "build_visual_diagnostics",
    "compute_quality",
    "count_conservation",
    "select_excerpt",
]
