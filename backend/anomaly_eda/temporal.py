from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from typing import Any, Literal, TypeAlias
from zoneinfo import ZoneInfo

import numpy as np  # pyright: ignore[reportMissingImports]

from anomaly_backend.eda_contracts import (
    precomputed_period_end,
    precomputed_period_start,
)

from .config import DEFAULT_CONFIG, EdaComputeConfig, TIME_ZONE
from .input_adapter import RawInputAdapter
from .pair_product import (
    ExactPairProduct,
    VIEW_RAW,
    VIEW_SCREENED,
    build_pair_product,
)


Frequency: TypeAlias = Literal["hour", "day", "month"]
PeriodKind: TypeAlias = Literal["daily", "weekly", "monthly", "custom", "full_range"]
RangeValue: TypeAlias = datetime | str


@dataclass(frozen=True, slots=True)
class TemporalComputeResult:
    pair_product: ExactPairProduct
    temporal_coverage: dict[str, Any]
    temporal_distribution: dict[str, Any]
    aggregates: dict[str, dict[str, list[dict[str, Any]]]]


def compute_temporal(
    adapter: RawInputAdapter,
    config: EdaComputeConfig = DEFAULT_CONFIG,
    *,
    period_kind: PeriodKind = "full_range",
    range_start: RangeValue | None = None,
    range_end: RangeValue | None = None,
    enforce_cadence_gate: bool = True,
) -> TemporalComputeResult:
    product = build_pair_product(adapter, config)
    return build_temporal_sections(
        product,
        config,
        period_kind=period_kind,
        range_start=range_start,
        range_end=range_end,
        enforce_cadence_gate=enforce_cadence_gate,
    )


def build_temporal_sections(
    product: ExactPairProduct,
    config: EdaComputeConfig = DEFAULT_CONFIG,
    *,
    period_kind: PeriodKind = "full_range",
    range_start: RangeValue | None = None,
    range_end: RangeValue | None = None,
    enforce_cadence_gate: bool = True,
) -> TemporalComputeResult:
    start, end = _resolve_range(product, config, range_start, range_end)
    _validate_period_range(start, end, period_kind)
    cadence = _cadence(product, config)
    if enforce_cadence_gate and cadence["publication_gate"] != "pass":
        raise ValueError("observed cadence publication gate failed")

    frequencies: tuple[tuple[str, Frequency], ...] = (
        ("hourly", "hour"),
        ("daily", "day"),
        ("monthly", "month"),
    )
    aggregates = {
        view: {
            frequency_name: _calendar(
                product,
                config,
                frequency,
                view=view,
                range_start=start,
                range_end=end,
                period_kind=period_kind,
            )
            for frequency_name, frequency in frequencies
        }
        for view in (VIEW_RAW, VIEW_SCREENED)
    }
    density: dict[str, dict[str, Any]] = {}
    for view in (VIEW_RAW, VIEW_SCREENED):
        density[view] = _month_annotations(
            aggregates[view]["monthly"], aggregates[view]["daily"], config
        )

    coverage_views: dict[str, Any] = {}
    distribution_views: dict[str, Any] = {}
    continuity = _continuity(product, config, period_kind)
    for view in (VIEW_RAW, VIEW_SCREENED):
        coverage_views[view] = {
            frequency: [
                _coverage_record(record) for record in aggregates[view][frequency]
            ]
            for frequency in ("hourly", "daily", "monthly")
        }
        coverage_views[view].update(
            {
                "dense_regimes": density[view]["dense_regimes"],
                "eligible_hour_segments": contiguous_eligible_hour_segments(
                    aggregates[view]["hourly"], config
                ),
            }
        )
        distribution_views[view] = {
            frequency: [
                _distribution_record(record)
                for record in aggregates[view][frequency]
            ]
            for frequency in ("hourly", "daily", "monthly")
        }
        distribution_views[view].update(
            {
                "channels": {
                    "suhu": {"name": "Suhu", "unit": "°C"},
                    "rh": {"name": "RH", "unit": "%"},
                },
                "continuity": continuity,
                "drift_conclusions": density[view]["drift_conclusions"],
            }
        )

    return TemporalComputeResult(
        pair_product=product,
        temporal_coverage={
            "calendar_semantics": {
                "timezone": TIME_ZONE,
                "bins": "half_open",
                "expected_slots": "ceil(exposure_seconds/expected_cadence_seconds)",
                "empty_bins_explicit": True,
                "coverage_not_capped": True,
            },
            "views": coverage_views,
        },
        temporal_distribution={
            "cadence": cadence,
            "views": distribution_views,
        },
        aggregates=aggregates,
    )


def hourly_median_aggregates(
    result: TemporalComputeResult,
    view: str,
) -> list[dict[str, Any]]:
    return result.aggregates[view]["hourly"]


def daily_median_aggregates(
    result: TemporalComputeResult,
    view: str,
) -> list[dict[str, Any]]:
    return result.aggregates[view]["daily"]


def _calendar(
    product: ExactPairProduct,
    config: EdaComputeConfig,
    frequency: Frequency,
    *,
    view: str,
    range_start: datetime,
    range_end: datetime,
    period_kind: PeriodKind,
) -> list[dict[str, Any]]:
    raw = product.raw_view
    selected = product.view(view)
    cursor = _floor(range_start, frequency)
    records: list[dict[str, Any]] = []
    while cursor < range_end:
        bin_end = _advance(cursor, frequency)
        exposure_start = max(cursor, range_start)
        exposure_end = min(bin_end, range_end)
        exposure_seconds = max(0.0, (exposure_end - exposure_start).total_seconds())
        full_seconds = (bin_end - cursor).total_seconds()
        expected_slots = (
            math.ceil(exposure_seconds / config.cadence.expected_seconds)
            if exposure_seconds > 0
            else 0
        )
        start_epoch = int(exposure_start.timestamp())
        end_epoch = int(exposure_end.timestamp())
        raw_left = int(np.searchsorted(raw.timestamps_epoch_s, start_epoch, side="left"))
        raw_right = int(np.searchsorted(raw.timestamps_epoch_s, end_epoch, side="left"))
        view_left = int(
            np.searchsorted(selected.timestamps_epoch_s, start_epoch, side="left")
        )
        view_right = int(
            np.searchsorted(selected.timestamps_epoch_s, end_epoch, side="left")
        )
        exact_count = raw_right - raw_left
        view_count = view_right - view_left
        coverage = exact_count / expected_slots if expected_slots else None
        retention = view_count / exact_count if exact_count else None
        records.append(
            {
                "start": cursor.isoformat(),
                "end": bin_end.isoformat(),
                "exposure_seconds": exposure_seconds,
                "full_bin_seconds": full_seconds,
                "expected_slots": expected_slots,
                "exact_pair_count": exact_count,
                "view_pair_count": view_count,
                "coverage": coverage,
                "retention": retention,
                "partial": (
                    exposure_seconds
                    < config.coverage.partial_exposure_fraction * full_seconds
                ),
                "from_censored": period_kind == "custom" and not records,
                "to_censored": period_kind == "custom" and bin_end >= range_end,
                "eligible": {
                    f"{threshold:.2f}": (
                        coverage is not None and coverage >= threshold
                    )
                    for threshold in config.coverage.sensitivity_thresholds
                },
                "statistics": _safe_stats(selected.values[view_left:view_right]),
            }
        )
        cursor = bin_end
    return records


def _safe_stats(values: np.ndarray) -> dict[str, Any]:
    finite = values[np.isfinite(values).all(axis=1)]
    if finite.size == 0:
        return {
            "count": 0,
            "suhu": {"median": None, "q1": None, "q3": None, "mad": None},
            "rh": {"median": None, "q1": None, "q3": None, "mad": None},
        }
    result: dict[str, Any] = {"count": int(finite.shape[0])}
    for position, channel in enumerate(("suhu", "rh")):
        series = finite[:, position]
        median = float(np.median(series))
        result[channel] = {
            "median": median,
            "q1": float(np.quantile(series, 0.25)),
            "q3": float(np.quantile(series, 0.75)),
            "mad": float(np.median(np.abs(series - median))),
        }
    return result


def _month_annotations(
    months: list[dict[str, Any]],
    days: list[dict[str, Any]],
    config: EdaComputeConfig,
) -> dict[str, Any]:
    for month in months:
        matching_days = [
            day for day in days if month["start"] <= day["start"] < month["end"]
        ]
        month["complete"] = month["exposure_seconds"] == month["full_bin_seconds"]
        month["eligible_nonpartial_days"] = {}
        for threshold in config.coverage.sensitivity_thresholds:
            key = f"{threshold:.2f}"
            eligible_days = sum(
                bool(day["eligible"][key]) and not bool(day["partial"])
                for day in matching_days
            )
            month["eligible_nonpartial_days"][key] = eligible_days
            month["eligible"][key] = bool(
                eligible_days >= config.coverage.minimum_eligible_nonpartial_days
                and month["coverage"] is not None
                and month["coverage"] >= threshold
            )

    regimes: dict[str, list[dict[str, Any]]] = {}
    conclusions: dict[str, dict[str, str]] = {"suhu": {}, "rh": {}}
    for threshold in config.coverage.sensitivity_thresholds:
        key = f"{threshold:.2f}"
        eligible_positions = [
            position
            for position, month in enumerate(months)
            if month["complete"] and month["eligible"][key]
        ]
        runs: list[list[int]] = []
        for position in eligible_positions:
            if runs and position == runs[-1][-1] + 1:
                runs[-1].append(position)
            else:
                runs.append([position])
        dense_runs = [
            run
            for run in runs
            if len(run) >= config.coverage.dense_consecutive_months
        ]
        dense_positions = {position for run in dense_runs for position in run}
        for position, month in enumerate(months):
            month.setdefault("regime", {})[key] = (
                "dense" if position in dense_positions else "sparse_or_transition"
            )
        regimes[key] = [
            {
                "start": months[run[0]]["start"],
                "end": months[run[-1]]["end"],
                "months": len(run),
            }
            for run in dense_runs
        ]
        for channel in ("suhu", "rh"):
            finite_medians = [
                float(months[position]["statistics"][channel]["median"])
                for run in dense_runs
                for position in run
                if months[position]["statistics"][channel]["median"] is not None
            ]
            if len(finite_medians) < config.coverage.dense_consecutive_months:
                conclusions[channel][key] = "insufficient_data"
                continue
            baseline = float(
                np.median(finite_medians[: config.coverage.dense_consecutive_months])
            )
            delta = finite_medians[-1] - baseline
            conclusions[channel][key] = (
                "decrease" if delta < 0 else "increase" if delta > 0 else "stable"
            )

    robust: dict[str, Any] = {}
    for channel, labels_by_threshold in conclusions.items():
        labels = list(labels_by_threshold.values())
        if any(label == "insufficient_data" for label in labels):
            status = "insufficient_data"
        elif len(set(labels)) == 1:
            status = "robust"
        else:
            status = "not_robust"
        robust[channel] = {"status": status, "directions": labels_by_threshold}
    return {"dense_regimes": regimes, "drift_conclusions": robust}


def contiguous_eligible_hour_segments(
    hourly: list[dict[str, Any]],
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> dict[str, Any]:
    key = f"{config.coverage.primary_threshold:.2f}"
    runs: list[list[int]] = []
    for position, record in enumerate(hourly):
        eligible = bool(record["eligible"][key]) and not bool(record["partial"])
        if eligible:
            if runs and position == runs[-1][-1] + 1:
                runs[-1].append(position)
            else:
                runs.append([position])
    ranked = sorted(runs, key=lambda run: (-len(run), run[0]))
    primary_hours = config.stationarity.primary_minimum_days * 24
    sensitivity_hours = config.stationarity.sensitivity_minimum_days * 24
    primary = next((run for run in ranked if len(run) >= primary_hours), None)
    sensitivity = [
        run for run in ranked if len(run) >= sensitivity_hours
    ][: config.stationarity.maximum_sensitivity_segments]

    def describe(run: list[int] | None) -> dict[str, Any]:
        if run is None:
            return {"status": "short"}
        return {
            "status": "ok",
            "start": hourly[run[0]]["start"],
            "end": hourly[run[-1]]["end"],
            "hours": len(run),
            "positions": [run[0], run[-1]],
        }

    return {
        "primary": describe(primary),
        "sensitivity": [describe(run) for run in sensitivity],
    }


def _coverage_record(record: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "start",
        "end",
        "exposure_seconds",
        "full_bin_seconds",
        "expected_slots",
        "exact_pair_count",
        "view_pair_count",
        "coverage",
        "retention",
        "partial",
        "from_censored",
        "to_censored",
        "eligible",
        "eligible_nonpartial_days",
        "complete",
        "regime",
    )
    return {key: record[key] for key in keys if key in record}


def _distribution_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: record[key]
        for key in (
            "start",
            "end",
            "view_pair_count",
            "from_censored",
            "to_censored",
            "statistics",
        )
    }


def _cadence(product: ExactPairProduct, config: EdaComputeConfig) -> dict[str, Any]:
    median = product.audit["observed_median_positive_delta_at_most_gap"]
    return {
        "expected_seconds": config.cadence.expected_seconds,
        "observed_median_positive_delta_at_most_ceiling": (
            float(median) if median is not None else None
        ),
        "positive_delta_count": int(product.audit["positive_delta_at_most_gap_count"]),
        "acceptance_interval_seconds": [
            config.cadence.acceptance_min_seconds,
            config.cadence.acceptance_max_seconds,
        ],
        "publication_gate": (
            "pass" if median == config.cadence.expected_seconds else "fail"
        ),
    }


def _continuity(
    product: ExactPairProduct,
    config: EdaComputeConfig,
    period_kind: PeriodKind,
) -> dict[str, Any]:
    ids = product.raw_view.segment_ids[config.cadence.primary_gap_seconds]
    segment_count = int(ids[-1]) + 1 if ids.size else 0
    open_ended = period_kind != "full_range"
    return {
        "gap_boundary_seconds": config.cadence.primary_gap_seconds,
        "gap_count": max(0, segment_count - 1),
        "segment_count": segment_count,
        "from_open_ended": open_ended,
        "to_open_ended": open_ended,
    }


def _resolve_range(
    product: ExactPairProduct,
    config: EdaComputeConfig,
    range_start: RangeValue | None,
    range_end: RangeValue | None,
) -> tuple[datetime, datetime]:
    if (range_start is None) != (range_end is None):
        raise ValueError("range_start and range_end must be provided together")
    timezone = ZoneInfo(TIME_ZONE)
    if range_start is None and range_end is None:
        raw_start = product.audit.get("start")
        raw_cutoff = product.audit.get("cutoff_inclusive")
        if not isinstance(raw_start, str) or not isinstance(raw_cutoff, str):
            raise ValueError("temporal range is unavailable from the pair-product audit")
        start = _local_datetime(raw_start, timezone)
        end = _local_datetime(raw_cutoff, timezone) + timedelta(
            seconds=config.cadence.expected_seconds
        )
    elif range_start is not None and range_end is not None:
        start = _local_datetime(range_start, timezone)
        end = _local_datetime(range_end, timezone)
        raw_start = product.audit.get("start")
        raw_cutoff = product.audit.get("cutoff_inclusive")
        if not isinstance(raw_start, str) or not isinstance(raw_cutoff, str):
            raise ValueError("source extent is unavailable from the pair-product audit")
        source_start = _local_datetime(raw_start, timezone)
        source_end = _local_datetime(raw_cutoff, timezone) + timedelta(seconds=1)
        if start < source_start or end > source_end:
            raise ValueError("requested range extends outside the source extent")
    else:
        raise AssertionError("unreachable range state")
    if start >= end:
        raise ValueError("range_start must be earlier than range_end")
    timestamps = product.raw_view.timestamps_epoch_s
    if timestamps.size and (
        int(timestamps[0]) < int(start.timestamp())
        or int(timestamps[-1]) >= int(end.timestamp())
    ):
        raise ValueError("pair product contains timestamps outside the requested range")
    return start, end


def _validate_period_range(
    start: datetime,
    end: datetime,
    period_kind: PeriodKind,
) -> None:
    if period_kind == "daily" and (
        start != precomputed_period_start("daily", start)
        or end != precomputed_period_end("daily", start)
    ):
        raise ValueError("daily range must be Jakarta [00:00,next day 00:00)")
    if period_kind == "weekly" and (
        start != precomputed_period_start("weekly", start)
        or end != precomputed_period_end("weekly", start)
    ):
        raise ValueError("weekly range must be Jakarta [Monday 00:00,next Monday)")
    if period_kind == "monthly" and (
        start != precomputed_period_start("monthly", start)
        or end != precomputed_period_end("monthly", start)
    ):
        raise ValueError("monthly range must be Jakarta calendar-month aligned")


def _local_datetime(value: RangeValue, timezone: ZoneInfo) -> datetime:
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(value)
    return parsed.replace(tzinfo=timezone) if parsed.tzinfo is None else parsed.astimezone(timezone)


def _floor(value: datetime, frequency: Frequency) -> datetime:
    if frequency == "hour":
        return value.replace(minute=0, second=0, microsecond=0)
    if frequency == "day":
        return precomputed_period_start("daily", value)
    return precomputed_period_start("monthly", value)


def _advance(value: datetime, frequency: Frequency) -> datetime:
    if frequency == "hour":
        return value + timedelta(hours=1)
    if frequency == "day":
        return precomputed_period_end("daily", value)
    return precomputed_period_end("monthly", value)


__all__ = [
    "TemporalComputeResult",
    "build_temporal_sections",
    "compute_temporal",
    "contiguous_eligible_hour_segments",
    "daily_median_aggregates",
    "hourly_median_aggregates",
]
