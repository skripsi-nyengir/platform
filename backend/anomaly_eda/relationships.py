from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Literal, cast

import numpy as np  # pyright: ignore[reportMissingImports]
from scipy.stats import rankdata  # pyright: ignore[reportMissingImports]

from .config import DEFAULT_CONFIG, EdaComputeConfig
from .pair_product import (
    ExactPairProduct,
    PairView,
    VIEW_RAW,
    VIEW_SCREENED,
    _segment_ids,
)


RelationshipStatus = Literal["ok", "insufficient_data", "constant"]
RelationshipReason = Literal[
    "no_exact_pairs",
    "insufficient_nonconstant_pairs",
    "insufficient_rolling_windows",
]


@dataclass(frozen=True, slots=True)
class RelationshipsComputeResult:
    status: Literal["complete", "not_eligible"]
    reason_code: RelationshipReason | None
    payload: dict[str, object] | None
    audit_metadata: dict[str, object]


def _correlations(values: np.ndarray, *, minimum_pairs: int) -> dict[str, object]:
    pairs = np.asarray(values, dtype=np.float64)
    if pairs.ndim != 2 or pairs.shape[1] != 2:
        raise ValueError("values must have shape (n, 2)")
    count = int(pairs.shape[0])
    if count < minimum_pairs:
        return {
            "status": "insufficient_data",
            "pair_count": count,
            "pearson": None,
            "spearman": None,
        }
    if np.ptp(pairs[:, 0]) == 0.0 or np.ptp(pairs[:, 1]) == 0.0:
        return {
            "status": "constant",
            "pair_count": count,
            "pearson": None,
            "spearman": None,
        }
    ranked = np.column_stack((rankdata(pairs[:, 0]), rankdata(pairs[:, 1])))
    return {
        "status": "ok",
        "pair_count": count,
        "pearson": float(np.corrcoef(pairs[:, 0], pairs[:, 1])[0, 1]),
        "spearman": float(np.corrcoef(ranked[:, 0], ranked[:, 1])[0, 1]),
    }


def _finite_view(view: PairView) -> tuple[np.ndarray, np.ndarray]:
    finite = np.isfinite(view.values).all(axis=1)
    return view.timestamps_epoch_s[finite], view.values[finite]


def _rolling_physical_correlation(
    timestamps: np.ndarray,
    values: np.ndarray,
    segment_ids: np.ndarray,
    *,
    window_seconds: int,
    gap_boundary_seconds: int,
    cadence_seconds: int,
    minimum_coverage: float,
    minimum_pairs: int,
    maximum_plot_points: int,
) -> dict[str, object]:
    expected = math.ceil(window_seconds / cadence_seconds)
    ends: list[np.ndarray] = []
    coefficients: list[np.ndarray] = []
    for segment in np.unique(segment_ids):
        selected = segment_ids == segment
        segment_times = timestamps[selected]
        segment_pairs = values[selected]
        starts = np.searchsorted(
            segment_times,
            segment_times - window_seconds,
            side="right",
        )
        stops = np.arange(1, segment_times.size + 1, dtype=np.int64)
        counts = stops - starts
        x = segment_pairs[:, 0]
        y = segment_pairs[:, 1]

        def window_sum(series: np.ndarray) -> np.ndarray:
            prefix = np.concatenate((np.zeros(1, dtype=np.float64), np.cumsum(series)))
            return prefix[stops] - prefix[starts]

        sum_x = window_sum(x)
        sum_y = window_sum(y)
        count_float = counts.astype(np.float64)
        covariance = window_sum(x * y) - (sum_x * sum_y / count_float)
        variance_x = window_sum(x * x) - (sum_x * sum_x / count_float)
        variance_y = window_sum(y * y) - (sum_y * sum_y / count_float)
        eligible = (
            (counts >= minimum_pairs)
            & (count_float / expected >= minimum_coverage)
            & (variance_x > 0.0)
            & (variance_y > 0.0)
        )
        denominator = np.sqrt(
            np.maximum(variance_x, 0.0) * np.maximum(variance_y, 0.0)
        )
        segment_coefficients = np.divide(
            covariance,
            denominator,
            out=np.full(segment_times.size, np.nan, dtype=np.float64),
            where=eligible & (denominator > 0.0),
        )
        eligible &= np.isfinite(segment_coefficients)
        ends.append(segment_times[eligible])
        coefficients.append(np.clip(segment_coefficients[eligible], -1.0, 1.0))

    all_values = np.concatenate(coefficients) if coefficients else np.empty(0)
    all_ends = np.concatenate(ends) if ends else np.empty(0, dtype=np.int64)
    if all_values.size:
        summary: tuple[float | None, ...] = (
            float(np.min(all_values)),
            float(np.quantile(all_values, 0.05)),
            float(np.quantile(all_values, 0.25)),
            float(np.median(all_values)),
            float(np.quantile(all_values, 0.75)),
            float(np.quantile(all_values, 0.95)),
            float(np.max(all_values)),
        )
        plotted = np.unique(
            np.linspace(
                0,
                all_values.size - 1,
                num=min(maximum_plot_points, all_values.size),
                dtype=np.int64,
            )
        )
    else:
        summary = (None,) * 7
        plotted = np.empty(0, dtype=np.int64)
    return {
        "window_seconds": window_seconds,
        "gap_boundary_seconds": gap_boundary_seconds,
        "eligible_window_count": int(all_values.size),
        "total_endpoint_count": int(timestamps.size),
        "minimum": summary[0],
        "q05": summary[1],
        "q25": summary[2],
        "median": summary[3],
        "q75": summary[4],
        "q95": summary[5],
        "maximum": summary[6],
        "plotted_end_timestamps": all_ends[plotted].tolist(),
        "plotted_correlations": all_values[plotted].tolist(),
    }


def compute_relationships(
    product: ExactPairProduct,
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> RelationshipsComputeResult:
    if product.raw_view.pair_count == 0:
        return RelationshipsComputeResult(
            "not_eligible", "no_exact_pairs", None, {"static": {}, "rolling_pearson": {}}
        )

    finite_views = {
        name: _finite_view(product.view(name)) for name in (VIEW_RAW, VIEW_SCREENED)
    }
    static = {
        name: _correlations(values, minimum_pairs=30)
        for name, (_, values) in finite_views.items()
    }
    if any(result["status"] != "ok" for result in static.values()):
        return RelationshipsComputeResult(
            "not_eligible",
            "insufficient_nonconstant_pairs",
            None,
            {"static": static, "rolling_pearson": {}},
        )

    variants = (
        (config.rolling.primary_window_minutes, config.cadence.primary_gap_seconds),
        *(
            (minutes, config.cadence.primary_gap_seconds)
            for minutes in config.rolling.sensitivity_window_minutes
        ),
        *(
            (config.rolling.primary_window_minutes, gap)
            for gap in config.cadence.gap_sensitivity_seconds
        ),
    )
    rolling: dict[str, dict[str, dict[str, object]]] = {}
    for name, (timestamps, values) in finite_views.items():
        rolling[name] = {}
        for minutes, gap in variants:
            key = f"window_{minutes}m_gap_{gap}s"
            segment_ids = _segment_ids(timestamps, gap)
            record = _rolling_physical_correlation(
                timestamps,
                values,
                segment_ids,
                window_seconds=minutes * 60,
                gap_boundary_seconds=gap,
                cadence_seconds=config.cadence.expected_seconds,
                minimum_coverage=config.rolling.minimum_coverage,
                minimum_pairs=config.rolling.minimum_pairs,
                maximum_plot_points=config.rolling.maximum_reported_points,
            )
            rolling[name][key] = record

    primary_key = (
        f"window_{config.rolling.primary_window_minutes}m_"
        f"gap_{config.cadence.primary_gap_seconds}s"
    )
    if any(
        cast(int, rolling[name][primary_key]["eligible_window_count"]) == 0
        for name in (VIEW_RAW, VIEW_SCREENED)
    ):
        return RelationshipsComputeResult(
            "not_eligible",
            "insufficient_rolling_windows",
            None,
            {"static": static, "rolling_pearson": rolling},
        )

    payload_rolling = {
        name: {
            key: {
                **record,
                "status": (
                    "complete"
                    if cast(int, record["eligible_window_count"]) > 0
                    else "not_eligible"
                ),
                "reason_code": (
                    None
                    if cast(int, record["eligible_window_count"]) > 0
                    else "insufficient_rolling_windows"
                ),
            }
            for key, record in records.items()
        }
        for name, records in rolling.items()
    }
    return RelationshipsComputeResult(
        "complete",
        None,
        {"static": static, "rolling_pearson": payload_rolling},
        {"static": static, "rolling_pearson": rolling},
    )


__all__ = ["RelationshipsComputeResult", "compute_relationships"]
