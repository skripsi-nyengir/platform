from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Literal, cast

import numpy as np  # pyright: ignore[reportMissingImports]
from scipy.stats import rankdata  # pyright: ignore[reportMissingImports]

from .change_points import dense_eligible_daily_arrays
from .config import DEFAULT_CONFIG, EdaComputeConfig
from .pair_product import VIEW_SCREENED
from .temporal import TemporalComputeResult


BootstrapStatus = Literal["ok", "insufficient_data", "constant"]
UncertaintyReason = Literal["insufficient_dense_daily_pairs", "block_longer_than_run"]


@dataclass(frozen=True, slots=True)
class BootstrapInterval:
    statistic: Literal["pearson", "spearman"]
    block_days: int
    status: BootstrapStatus
    pair_count: int
    run_count: int
    replicate_count: int
    estimate: float | None
    lower: float | None
    upper: float | None


@dataclass(frozen=True, slots=True)
class UncertaintyComputeResult:
    status: Literal["complete", "not_eligible"]
    reason_code: UncertaintyReason | None
    payload: dict[str, object] | None
    audit_metadata: dict[str, object]


def _correlations(
    values: np.ndarray, minimum_pairs: int
) -> tuple[BootstrapStatus, float | None, float | None]:
    if values.shape[0] < minimum_pairs:
        return "insufficient_data", None, None
    if np.ptp(values[:, 0]) == 0.0 or np.ptp(values[:, 1]) == 0.0:
        return "constant", None, None
    ranked = np.column_stack((rankdata(values[:, 0]), rankdata(values[:, 1])))
    return (
        "ok",
        float(np.corrcoef(values[:, 0], values[:, 1])[0, 1]),
        float(np.corrcoef(ranked[:, 0], ranked[:, 1])[0, 1]),
    )


def _calendar_runs(day_ordinals: np.ndarray, values: np.ndarray) -> list[np.ndarray]:
    if day_ordinals.size == 0:
        return []
    breaks = np.flatnonzero(np.diff(day_ordinals) != 1) + 1
    return [chunk for chunk in np.split(values, breaks) if chunk.size]


def paired_moving_block_bootstrap(
    day_ordinals: np.ndarray,
    daily_values: np.ndarray,
    *,
    block_days: int,
    replicates: int,
    seed: int,
    minimum_pairs: int,
    confidence_level: float,
) -> tuple[BootstrapInterval, BootstrapInterval]:
    days = np.asarray(day_ordinals, dtype=np.int64)
    pairs = np.asarray(daily_values, dtype=np.float64)
    if days.ndim != 1 or pairs.shape != (days.size, 2):
        raise ValueError("daily medians and day ordinals must align")
    if days.size > 1 and np.any(np.diff(days) <= 0):
        raise ValueError("day ordinals must be strictly increasing")
    if not np.all(np.isfinite(pairs)):
        raise ValueError("daily medians must be finite")
    if block_days < 1 or replicates < 1:
        raise ValueError("block_days and replicates must be positive")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be in (0, 1)")

    runs = [run for run in _calendar_runs(days, pairs) if run.shape[0] >= block_days]
    retained = int(sum(run.shape[0] for run in runs))
    base = np.concatenate(runs, axis=0) if runs else np.empty((0, 2))
    status, pearson, spearman = _correlations(base, minimum_pairs)
    if status != "ok":
        return cast(
            tuple[BootstrapInterval, BootstrapInterval],
            tuple(
                BootstrapInterval(
                    statistic,
                    block_days,
                    status,
                    retained,
                    len(runs),
                    0,
                    None,
                    None,
                    None,
                )
                for statistic in ("pearson", "spearman")
            ),
        )

    generator = np.random.default_rng(seed)
    pearson_values = np.empty(replicates, dtype=np.float64)
    spearman_values = np.empty(replicates, dtype=np.float64)
    for replicate in range(replicates):
        sampled_runs: list[np.ndarray] = []
        for run in runs:
            starts = generator.integers(
                0,
                run.shape[0] - block_days + 1,
                size=math.ceil(run.shape[0] / block_days),
            )
            sampled_runs.append(
                np.concatenate(
                    [run[start : start + block_days] for start in starts], axis=0
                )[: run.shape[0]]
            )
        sampled = np.concatenate(sampled_runs, axis=0)
        sampled_status, sampled_pearson, sampled_spearman = _correlations(
            sampled, minimum_pairs
        )
        if (
            sampled_status != "ok"
            or sampled_pearson is None
            or sampled_spearman is None
        ):
            raise ValueError("moving-block replicate lost correlation eligibility")
        pearson_values[replicate] = sampled_pearson
        spearman_values[replicate] = sampled_spearman

    if pearson is None or spearman is None:
        raise AssertionError("eligible base correlation is missing")
    alpha = (1.0 - confidence_level) / 2.0
    samples_by_statistic: tuple[
        tuple[Literal["pearson", "spearman"], float, np.ndarray], ...
    ] = (
        ("pearson", pearson, pearson_values),
        ("spearman", spearman, spearman_values),
    )
    return cast(
        tuple[BootstrapInterval, BootstrapInterval],
        tuple(
            BootstrapInterval(
                statistic,
                block_days,
                "ok",
                retained,
                len(runs),
                replicates,
                estimate,
                float(np.quantile(samples, alpha)),
                float(np.quantile(samples, 1.0 - alpha)),
            )
            for statistic, estimate, samples in samples_by_statistic
        ),
    )


def _block_reason(interval: BootstrapInterval) -> UncertaintyReason | None:
    if interval.status == "ok":
        return None
    return "block_longer_than_run" if interval.run_count == 0 else "insufficient_dense_daily_pairs"


def compute_uncertainty(
    result: TemporalComputeResult,
    config: EdaComputeConfig = DEFAULT_CONFIG,
) -> UncertaintyComputeResult:
    days, values = dense_eligible_daily_arrays(result, VIEW_SCREENED, config)
    blocks: dict[str, tuple[BootstrapInterval, BootstrapInterval]] = {}
    for block_days in (
        config.bootstrap.primary_block_days,
        *config.bootstrap.sensitivity_block_days,
    ):
        blocks[str(block_days)] = paired_moving_block_bootstrap(
            days,
            values,
            block_days=block_days,
            replicates=config.bootstrap.replicates,
            seed=config.bootstrap.seed,
            minimum_pairs=config.bootstrap.minimum_paired_days,
            confidence_level=config.bootstrap.confidence_level,
        )
    directions = [
        1 if interval[0].estimate > 0 else -1 if interval[0].estimate < 0 else 0
        for interval in blocks.values()
        if interval[0].status == "ok" and interval[0].estimate is not None
    ]
    sensitivity_status = (
        "insufficient_data"
        if len(directions) != 3
        else "robust"
        if len(set(directions)) == 1
        else "not_robust"
    )
    audit: dict[str, object] = {
        "method": "paired_moving_block_bootstrap",
        "confidence_level": config.bootstrap.confidence_level,
        "blocks": {
            key: [asdict(interval) for interval in intervals]
            for key, intervals in blocks.items()
        },
        "sensitivity_status": sensitivity_status,
    }
    primary = blocks[str(config.bootstrap.primary_block_days)][0]
    primary_reason = _block_reason(primary)
    if primary_reason is not None:
        return UncertaintyComputeResult(
            "not_eligible", primary_reason, None, audit
        )
    payload_blocks = {
        key: {
            "status": "complete" if intervals[0].status == "ok" else "not_eligible",
            "reason_code": _block_reason(intervals[0]),
            "intervals": [asdict(interval) for interval in intervals],
        }
        for key, intervals in blocks.items()
    }
    return UncertaintyComputeResult(
        "complete",
        None,
        {
            "method": "paired_moving_block_bootstrap",
            "confidence_level": config.bootstrap.confidence_level,
            "seed": config.bootstrap.seed,
            "replicates": config.bootstrap.replicates,
            "blocks": payload_blocks,
            "sensitivity_status": sensitivity_status,
        },
        audit,
    )


__all__ = [
    "BootstrapInterval",
    "UncertaintyComputeResult",
    "compute_uncertainty",
    "paired_moving_block_bootstrap",
]
