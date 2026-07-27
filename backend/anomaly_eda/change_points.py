from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
import math
from typing import Any, Literal, cast

import numpy as np  # pyright: ignore[reportMissingImports]

from .config import ChangePointParameters, DEFAULT_CONFIG, EdaComputeConfig
from .pair_product import VIEW_SCREENED
from .temporal import TemporalComputeResult, daily_median_aggregates


ChangePointStatus = Literal[
    "ok", "insufficient_data", "constant", "dependency_unavailable", "error"
]
ChangePointReason = Literal[
    "insufficient_daily_medians", "dependency_unavailable", "section_compute_failed"
]


@dataclass(frozen=True, slots=True)
class DenseDailyBlock:
    day_ordinals: np.ndarray
    median_values: np.ndarray
    aggregation: Literal["daily_median"] = "daily_median"
    dense_eligible: Literal[True] = True

    @classmethod
    def from_arrays(
        cls, day_ordinals: np.ndarray, median_values: np.ndarray
    ) -> DenseDailyBlock:
        days = np.asarray(day_ordinals, dtype=np.int64)
        values = np.asarray(median_values, dtype=np.float64)
        if days.ndim != 1:
            raise ValueError("day ordinals must be one-dimensional")
        if values.ndim != 2 or values.shape != (days.size, 2):
            raise ValueError("daily medians must have shape (n, 2)")
        if days.size > 1 and not np.all(np.diff(days) == 1):
            raise ValueError("dense daily block must be calendar-contiguous")
        if not np.all(np.isfinite(values)):
            raise ValueError("daily medians must be finite")
        return cls(days.copy(), values.copy())


@dataclass(frozen=True, slots=True)
class PenaltyBoundary:
    penalty_factor: int
    boundary_index: int
    left_day: int
    right_day: int


@dataclass(frozen=True, slots=True)
class StableChange:
    representative_day: int
    representative_boundary_index: int
    penalty_factors: tuple[int, ...]
    observed_days: tuple[int, ...]
    temperature_shift: float
    humidity_shift: float
    temperature_mad_effect: float | None
    humidity_mad_effect: float | None


@dataclass(frozen=True, slots=True)
class BinsegConfirmation:
    minimum_segment_days: int
    status: ChangePointStatus
    requested_breakpoints: int
    boundary_days: tuple[int, ...]
    matched_stable_candidates: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ChangePointBlockResult:
    status: ChangePointStatus
    pair_count: int
    scale_median: tuple[float, float] | None
    scale_mad: tuple[float, float] | None
    constant_channels: tuple[int, ...]
    penalty_candidates: tuple[PenaltyBoundary, ...]
    stable_candidates: tuple[StableChange, ...]
    confirmations: tuple[BinsegConfirmation, ...]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class ChangePointsComputeResult:
    status: Literal["complete", "not_eligible", "failed"]
    reason_code: ChangePointReason | None
    payload: dict[str, object] | None
    audit_metadata: dict[str, object]


@dataclass(slots=True)
class _BoundaryCluster:
    observations: list[PenaltyBoundary]

    @property
    def median_day(self) -> int:
        days = sorted(item.right_day for item in self.observations)
        return days[(len(days) - 1) // 2]

    @property
    def factors(self) -> set[int]:
        return {item.penalty_factor for item in self.observations}


def _cluster_boundaries(
    boundaries: tuple[PenaltyBoundary, ...], *, radius_days: int, minimum_penalties: int
) -> tuple[tuple[PenaltyBoundary, ...], ...]:
    clusters: list[_BoundaryCluster] = []
    for boundary in sorted(
        boundaries, key=lambda item: (item.right_day, item.penalty_factor)
    ):
        eligible: list[tuple[int, int, _BoundaryCluster]] = []
        for cluster in clusters:
            distance = abs(boundary.right_day - cluster.median_day)
            if distance <= radius_days and boundary.penalty_factor not in cluster.factors:
                eligible.append((distance, cluster.median_day, cluster))
        if eligible:
            eligible.sort(key=lambda item: (item[0], item[1]))
            eligible[0][2].observations.append(boundary)
        else:
            clusters.append(_BoundaryCluster([boundary]))
    return tuple(
        tuple(
            sorted(
                cluster.observations,
                key=lambda item: (item.right_day, item.penalty_factor),
            )
        )
        for cluster in clusters
        if len(cluster.factors) >= minimum_penalties
    )


def _robust_standardize(
    values: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, tuple[int, ...]]:
    median = np.median(values, axis=0)
    mad = np.median(np.abs(values - median), axis=0)
    constant_channels = tuple(int(index) for index in np.flatnonzero(mad == 0.0))
    scale = np.where(mad == 0.0, 1.0, mad)
    return (
        np.ascontiguousarray((values - median) / scale, dtype=np.float64),
        median,
        mad,
        constant_channels,
    )


def _stable_change(
    observations: tuple[PenaltyBoundary, ...], block: DenseDailyBlock, mad: np.ndarray
) -> StableChange:
    ordered_days = sorted(item.right_day for item in observations)
    representative_day = ordered_days[(len(ordered_days) - 1) // 2]
    boundary_index = min(
        item.boundary_index
        for item in observations
        if item.right_day == representative_day
    )
    shifts = np.median(block.median_values[boundary_index:], axis=0) - np.median(
        block.median_values[:boundary_index], axis=0
    )
    effects = np.divide(
        shifts,
        mad,
        out=np.full(2, np.nan, dtype=np.float64),
        where=mad != 0.0,
    )
    return StableChange(
        representative_day,
        boundary_index,
        tuple(sorted(item.penalty_factor for item in observations)),
        tuple(ordered_days),
        float(shifts[0]),
        float(shifts[1]),
        float(effects[0]) if np.isfinite(effects[0]) else None,
        float(effects[1]) if np.isfinite(effects[1]) else None,
    )


def _ruptures() -> tuple[object | None, type[Exception]]:
    try:
        import ruptures as rpt  # pyright: ignore[reportMissingImports]
        from ruptures.exceptions import (  # pyright: ignore[reportMissingImports]
            BadSegmentationParameters,
        )
    except ImportError:
        return None, ValueError
    return rpt, BadSegmentationParameters


def _confirm(
    rpt: object,
    bad_parameters: type[Exception],
    standardized: np.ndarray,
    block: DenseDailyBlock,
    stable: tuple[StableChange, ...],
    minimum_segment_days: int,
    config: ChangePointParameters,
) -> BinsegConfirmation:
    count = len(stable)
    if count == 0:
        return BinsegConfirmation(minimum_segment_days, "ok", 0, (), 0)
    if standardized.shape[0] < (count + 1) * minimum_segment_days:
        return BinsegConfirmation(
            minimum_segment_days,
            "insufficient_data",
            count,
            (),
            0,
            "requested breakpoints are infeasible for the minimum segment",
        )
    try:
        boundaries = (
            cast(Any, getattr(rpt, "Binseg"))(
                model=config.binseg_model, min_size=minimum_segment_days, jump=1
            )
            .fit(standardized)
            .predict(n_bkps=count)
        )
    except (bad_parameters, ValueError, np.linalg.LinAlgError) as error:
        return BinsegConfirmation(
            minimum_segment_days, "error", count, (), 0, str(error)
        )
    boundary_days = tuple(
        int(block.day_ordinals[boundary])
        for boundary in boundaries
        if 0 < boundary < block.day_ordinals.size
    )
    unmatched = list(boundary_days)
    matched = 0
    for change in sorted(stable, key=lambda item: item.representative_day):
        feasible = sorted(
            (abs(day - change.representative_day), day)
            for day in unmatched
            if abs(day - change.representative_day) <= config.stability_radius_days
        )
        if feasible:
            unmatched.remove(feasible[0][1])
            matched += 1
    return BinsegConfirmation(
        minimum_segment_days, "ok", count, boundary_days, matched
    )


def detect_change_points(
    block: DenseDailyBlock, config: ChangePointParameters
) -> ChangePointBlockResult:
    if not isinstance(block, DenseDailyBlock):
        raise TypeError("change-point input must be DenseDailyBlock")
    count = int(block.day_ordinals.size)
    if count < config.minimum_block_days:
        return ChangePointBlockResult(
            "insufficient_data",
            count,
            None,
            None,
            (),
            (),
            (),
            (),
            "dense daily block is shorter than the minimum",
        )
    standardized, median, mad, constant_channels = _robust_standardize(
        block.median_values
    )
    scale_median = (float(median[0]), float(median[1]))
    scale_mad = (float(mad[0]), float(mad[1]))
    if len(constant_channels) == 2:
        return ChangePointBlockResult(
            "constant", count, scale_median, scale_mad, constant_channels, (), (), ()
        )
    rpt, bad_parameters = _ruptures()
    if rpt is None:
        return ChangePointBlockResult(
            "dependency_unavailable",
            count,
            scale_median,
            scale_mad,
            constant_channels,
            (),
            (),
            (),
            "ruptures is not installed",
        )
    boundaries: list[PenaltyBoundary] = []
    try:
        detector = cast(Any, getattr(rpt, "KernelCPD"))(
            kernel=config.kernel,
            min_size=config.kernel_minimum_segment_days,
            jump=config.kernel_jump,
        ).fit(standardized)
        for factor in config.penalty_factors:
            for boundary in detector.predict(pen=math.log(count) * factor):
                if 0 < boundary < count:
                    boundaries.append(
                        PenaltyBoundary(
                            factor,
                            int(boundary),
                            int(block.day_ordinals[boundary - 1]),
                            int(block.day_ordinals[boundary]),
                        )
                    )
    except (bad_parameters, ValueError, np.linalg.LinAlgError) as error:
        return ChangePointBlockResult(
            "error",
            count,
            scale_median,
            scale_mad,
            constant_channels,
            tuple(boundaries),
            (),
            (),
            str(error),
        )
    clusters = _cluster_boundaries(
        tuple(boundaries),
        radius_days=config.stability_radius_days,
        minimum_penalties=config.stability_minimum_penalties,
    )
    stable = tuple(_stable_change(cluster, block, mad) for cluster in clusters)
    confirmations = tuple(
        _confirm(
            rpt,
            bad_parameters,
            standardized,
            block,
            stable,
            minimum,
            config,
        )
        for minimum in config.binseg_minimum_segment_days
    )
    return ChangePointBlockResult(
        "ok",
        count,
        scale_median,
        scale_mad,
        constant_channels,
        tuple(boundaries),
        stable,
        confirmations,
    )


def dense_eligible_daily_arrays(
    result: TemporalComputeResult,
    view: str,
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> tuple[np.ndarray, np.ndarray]:
    primary_key = f"{config.coverage.primary_threshold:.2f}"
    daily = daily_median_aggregates(result, view)
    dense_months = {
        cast(str, record["start"])[:7]
        for record in result.aggregates[view]["monthly"]
        if cast(dict[str, object], record["regime"])[primary_key] == "dense"
    }

    days: list[int] = []
    values: list[tuple[float, float]] = []
    for record in daily:
        if cast(str, record["start"])[:7] not in dense_months:
            continue
        if (
            not bool(cast(dict[str, object], record["eligible"])[primary_key])
            or bool(record["partial"])
        ):
            continue
        statistics = cast(dict[str, object], record["statistics"])
        suhu = cast(dict[str, object], statistics["suhu"])["median"]
        rh = cast(dict[str, object], statistics["rh"])["median"]
        if suhu is None or rh is None:
            continue
        days.append(int(datetime.fromisoformat(cast(str, record["start"])).timestamp()) // 86_400)
        values.append((cast(float, suhu), cast(float, rh)))
    return (
        np.asarray(days, dtype=np.int64),
        np.asarray(values, dtype=np.float64).reshape((-1, 2)),
    )


def _json_ready(value: object) -> object:
    if isinstance(value, np.ndarray):
        return cast(np.ndarray, value).tolist()
    if is_dataclass(value) and not isinstance(value, type):
        return _json_ready(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_ready(item) for item in value]
    if isinstance(value, np.generic):
        return cast(np.generic, value).item()
    return value


def _published_block(
    days: np.ndarray, result: ChangePointBlockResult
) -> dict[str, object]:
    return {
        "status": result.status,
        "pair_count": result.pair_count,
        "start_day": int(days[0]),
        "end_day": int(days[-1]),
        "scale_median": list(result.scale_median) if result.scale_median else None,
        "scale_mad": list(result.scale_mad) if result.scale_mad else None,
        "constant_channels": list(result.constant_channels),
        "stable_changes": cast(object, _json_ready(result.stable_candidates)),
        "confirmations": [
            {
                "minimum_segment_days": confirmation.minimum_segment_days,
                "status": confirmation.status,
                "requested_breakpoints": confirmation.requested_breakpoints,
                "boundary_days": list(confirmation.boundary_days),
                "matched_stable_changes": confirmation.matched_stable_candidates,
                "error": confirmation.error,
            }
            for confirmation in result.confirmations
        ],
    }


def compute_change_points(
    result: TemporalComputeResult,
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> ChangePointsComputeResult:
    days, values = dense_eligible_daily_arrays(result, VIEW_SCREENED, config)
    breaks = np.flatnonzero(np.diff(days) != 1) + 1 if days.size else np.empty(0)
    day_runs = [run for run in np.split(days, breaks) if run.size]
    value_runs = [run for run in np.split(values, breaks) if run.size]
    results = [
        detect_change_points(DenseDailyBlock.from_arrays(run_days, run_values), config.change_point)
        for run_days, run_values in zip(day_runs, value_runs, strict=True)
    ]
    audit_results = cast(list[dict[str, object]], _json_ready(results))
    block_statuses = {result.status for result in results}
    confirmation_statuses = {
        confirmation.status
        for result in results
        for confirmation in result.confirmations
    }
    audit_status = (
        "failed"
        if block_statuses & {"dependency_unavailable", "error"}
        or "error" in confirmation_statuses
        else "complete"
        if block_statuses & {"ok", "constant"}
        else "not_applicable"
    )
    audit: dict[str, object] = {
        "status": audit_status,
        "candidate_notice": "Candidate regime changes are not anomaly labels.",
        "blocks": audit_results,
    }
    if audit_status == "failed":
        reason: ChangePointReason = (
            "dependency_unavailable"
            if "dependency_unavailable" in block_statuses
            else "section_compute_failed"
        )
        return ChangePointsComputeResult("failed", reason, None, audit)
    if not any(result.pair_count >= config.change_point.minimum_block_days for result in results):
        return ChangePointsComputeResult(
            "not_eligible", "insufficient_daily_medians", None, audit
        )
    return ChangePointsComputeResult(
        "complete",
        None,
        {
            "blocks": [
                _published_block(run_days, result)
                for run_days, result in zip(day_runs, results, strict=True)
            ]
        },
        audit,
    )


__all__ = [
    "ChangePointsComputeResult",
    "DenseDailyBlock",
    "compute_change_points",
    "dense_eligible_daily_arrays",
    "detect_change_points",
]
