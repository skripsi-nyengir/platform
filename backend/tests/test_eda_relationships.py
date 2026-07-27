from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast

import numpy as np  # pyright: ignore[reportMissingImports]
import pytest

from anomaly_backend.eda_contracts import RelationshipsPayload, UncertaintyPayload
from anomaly_eda.pair_product import (
    ExactPairProduct,
    PairFlags,
    PairView,
    VIEW_SCREENED,
)
from anomaly_eda.relationships import compute_relationships
from anomaly_eda.temporal import TemporalComputeResult
from anomaly_eda.uncertainty import (
    compute_uncertainty,
    paired_moving_block_bootstrap,
)


def _pair_product(
    count: int,
    *,
    constant_temperature: bool = False,
    gap_after: int | None = None,
) -> ExactPairProduct:
    timestamps = np.arange(count, dtype=np.int64) * 6
    if gap_after is not None:
        timestamps[gap_after:] += 31
    temperature = (
        np.ones(count, dtype=np.float64)
        if constant_temperature
        else np.arange(count, dtype=np.float64)
    )
    humidity = np.arange(count, dtype=np.float64) * 2.0 + 1.0
    values = np.column_stack((temperature, humidity))
    segments = {
        boundary: np.concatenate(
            (
                np.zeros(1, dtype=np.int32),
                np.cumsum(np.diff(timestamps) > boundary, dtype=np.int32),
            )
        )
        if count
        else np.empty(0, dtype=np.int32)
        for boundary in (15, 30, 60)
    }
    view = PairView(timestamps, values, segments)
    false = np.zeros(count, dtype=bool)
    flags = PairFlags(
        non_finite=false,
        disconnected=false,
        zero=false,
        range=false,
        duplicate=false,
        conflicting_duplicate=false,
        stale=false,
        near_zero=false,
        rule_screened=np.ones(count, dtype=bool),
    )
    return ExactPairProduct(view, view, flags, (), {})


def test_relationships_publish_static_and_physical_rolling_variants() -> None:
    result = compute_relationships(_pair_product(240))

    assert result.status == "complete"
    assert result.reason_code is None
    payload = RelationshipsPayload.model_validate(result.payload)
    assert set(result.payload or {}) == {"static", "rolling_pearson"}
    assert payload.static["resolved_raw_pairs"].pearson == pytest.approx(1.0)
    primary = payload.rolling_pearson["resolved_raw_pairs"][
        "window_30m_gap_30s"
    ]
    assert primary.status == "complete"
    assert primary.eligible_window_count == 1
    sensitivity = payload.rolling_pearson["resolved_raw_pairs"]["window_180m_gap_30s"]
    assert sensitivity.status == "not_eligible"
    assert sensitivity.reason_code == "insufficient_rolling_windows"


def test_relationships_require_an_eligible_primary_rolling_window() -> None:
    result = compute_relationships(_pair_product(30))

    assert result.status == "not_eligible"
    assert result.reason_code == "insufficient_rolling_windows"
    assert result.payload is None
    static = cast(dict[str, dict[str, object]], result.audit_metadata["static"])
    rolling = cast(
        dict[str, dict[str, dict[str, object]]],
        result.audit_metadata["rolling_pearson"],
    )
    assert static["resolved_raw_pairs"]["status"] == "ok"
    primary = rolling["resolved_raw_pairs"][
        "window_30m_gap_30s"
    ]
    assert primary["eligible_window_count"] == 0


def test_relationships_reject_constant_static_channels_before_rolling() -> None:
    result = compute_relationships(_pair_product(301, constant_temperature=True))

    assert result.status == "not_eligible"
    assert result.reason_code == "insufficient_nonconstant_pairs"
    assert result.payload is None
    static = cast(dict[str, dict[str, object]], result.audit_metadata["static"])
    assert static["resolved_raw_pairs"]["status"] == "constant"
    assert result.audit_metadata["rolling_pearson"] == {}


def test_relationships_fail_safely_for_empty_short_and_fragmented_pairs(
) -> None:
    empty = compute_relationships(_pair_product(0))
    short = compute_relationships(_pair_product(29))
    fragmented = compute_relationships(_pair_product(240, gap_after=120))

    assert (empty.status, empty.reason_code) == ("not_eligible", "no_exact_pairs")
    assert (short.status, short.reason_code) == (
        "not_eligible",
        "insufficient_nonconstant_pairs",
    )
    assert (fragmented.status, fragmented.reason_code) == (
        "not_eligible",
        "insufficient_rolling_windows",
    )


def _daily_temporal(
    day_offsets: np.ndarray, values: np.ndarray
) -> TemporalComputeResult:
    jakarta = timezone(timedelta(hours=7))
    origin = datetime(2025, 1, 1, tzinfo=jakarta)
    daily: list[dict[str, object]] = []
    months: dict[str, dict[str, object]] = {}
    for offset, pair in zip(day_offsets, values, strict=True):
        start = origin + timedelta(days=int(offset))
        month = start.replace(day=1)
        months.setdefault(
            month.isoformat(),
            {"start": month.isoformat(), "regime": {"0.80": "dense"}},
        )
        daily.append(
            {
                "start": start.isoformat(),
                "end": (start + timedelta(days=1)).isoformat(),
                "eligible": {"0.80": True},
                "partial": False,
                "statistics": {
                    "suhu": {"median": float(pair[0])},
                    "rh": {"median": float(pair[1])},
                },
            }
        )
    return TemporalComputeResult(
        pair_product=cast(ExactPairProduct, object()),
        temporal_coverage={},
        temporal_distribution={},
        aggregates={
            VIEW_SCREENED: {
                "hourly": [],
                "daily": daily,
                "monthly": list(months.values()),
            }
        },
    )


def test_paired_moving_block_bootstrap_is_seeded_and_run_aware() -> None:
    days = np.concatenate((np.arange(40), np.arange(100, 160))).astype(np.int64)
    x = np.concatenate((np.arange(40), np.arange(60))).astype(np.float64)
    generator = np.random.default_rng(7)
    values = np.column_stack((x, 0.5 * x + generator.normal(0.0, 3.0, x.size)))

    first = paired_moving_block_bootstrap(
        days,
        values,
        block_days=7,
        replicates=100,
        seed=20260724,
        minimum_pairs=30,
        confidence_level=0.95,
    )
    second = paired_moving_block_bootstrap(
        days,
        values,
        block_days=7,
        replicates=100,
        seed=20260724,
        minimum_pairs=30,
        confidence_level=0.95,
    )

    assert first == second
    assert first[0].status == "ok"
    assert first[0].pair_count == 100
    assert first[0].run_count == 2
    assert first[0].replicate_count == 100


def test_uncertainty_publishes_default_blocks_deterministically() -> None:
    days = np.arange(90, dtype=np.int64)
    generator = np.random.default_rng(19)
    x = generator.normal(size=days.size)
    temporal = _daily_temporal(
        days,
        np.column_stack((x, 0.4 * x + generator.normal(size=days.size))),
    )

    first = compute_uncertainty(temporal)
    second = compute_uncertainty(temporal)

    assert first.status == "complete"
    assert first.payload == second.payload
    payload = UncertaintyPayload.model_validate(first.payload)
    assert payload.seed == 20260724
    assert payload.replicates == 2000
    assert set(payload.blocks) == {"7", "14", "28"}
    assert all(block.status == "complete" for block in payload.blocks.values())


def test_uncertainty_rejects_runs_shorter_than_the_primary_block() -> None:
    days = np.concatenate((np.arange(13), np.arange(20, 33))).astype(np.int64)
    values = np.column_stack((days, days**2)).astype(np.float64)
    result = compute_uncertainty(_daily_temporal(days, values))

    assert result.status == "not_eligible"
    assert result.reason_code == "block_longer_than_run"
    assert result.payload is None
