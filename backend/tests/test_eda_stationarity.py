from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
from typing import cast

import numpy as np  # pyright: ignore[reportMissingImports]
import pytest
from scipy.signal import periodogram  # pyright: ignore[reportMissingImports]
from statsmodels.tsa.stattools import acf, pacf  # pyright: ignore[reportMissingImports]

from anomaly_backend.eda_contracts import ChangePointsPayload, StationarityPayload
from anomaly_eda import stationarity
from anomaly_eda.change_points import (
    DenseDailyBlock,
    compute_change_points,
    detect_change_points,
)
from anomaly_eda.config import DEFAULT_CONFIG
from anomaly_eda.pair_product import ExactPairProduct, VIEW_SCREENED
from anomaly_eda.temporal import (
    TemporalComputeResult,
    contiguous_eligible_hour_segments,
)


def _hourly_records(
    hours: int,
    *,
    constant: bool = False,
    ineligible: frozenset[int] = frozenset(),
) -> list[dict[str, object]]:
    start = datetime(2025, 6, 23, tzinfo=timezone(timedelta(hours=7)))
    records: list[dict[str, object]] = []
    for position in range(hours):
        bin_start = start + timedelta(hours=position)
        angle = 2.0 * math.pi * position / 24.0
        records.append(
            {
                "start": bin_start.isoformat(),
                "end": (bin_start + timedelta(hours=1)).isoformat(),
                "eligible": {"0.80": position not in ineligible},
                "partial": False,
                "statistics": {
                    "suhu": {
                        "median": 25.0
                        if constant
                        else 25.0 + 0.002 * position + math.sin(angle)
                    },
                    "rh": {
                        "median": 60.0
                        if constant
                        else 60.0 - 0.003 * position + math.cos(angle)
                    },
                },
            }
        )
    return records


def _compute(
    hours: int,
    *,
    constant: bool = False,
    ineligible: frozenset[int] = frozenset(),
) -> stationarity.StationarityComputeResult:
    hourly = _hourly_records(hours, constant=constant, ineligible=ineligible)
    temporal = TemporalComputeResult(
        pair_product=cast(ExactPairProduct, object()),
        temporal_coverage={
            "views": {
                VIEW_SCREENED: {
                    "eligible_hour_segments": contiguous_eligible_hour_segments(
                        hourly, DEFAULT_CONFIG
                    )
                }
            }
        },
        temporal_distribution={},
        aggregates={
            VIEW_SCREENED: {"hourly": hourly, "daily": [], "monthly": []}
        },
    )
    return stationarity.compute_stationarity(temporal)


def test_stationarity_publishes_only_safe_diagnostics_at_sensitivity_tier() -> None:
    result = _compute(336)

    assert result.status == "complete"
    assert result.reason_code is None
    payload = StationarityPayload.model_validate(result.payload)
    assert payload.eligibility_tier == "sensitivity"
    assert payload.primary is None
    assert len(payload.sensitivity) == 1
    channel = payload.sensitivity[0].channels["suhu"]
    assert set(channel.model_dump()) == {
        "autocorrelation",
        "partial_autocorrelation",
        "spectrum",
        "stl",
    }
    assert channel.autocorrelation.maximum_lag == 72
    assert len(channel.autocorrelation.values) == 73
    assert channel.stl.status == "ok"
    assert len(channel.stl.seasonal) == 336

    sensitivity = cast(list[dict[str, object]], result.audit_metadata["sensitivity"])
    audit_channel = cast(dict[str, object], sensitivity[0]["suhu"])
    assert "level_adf" in audit_channel
    assert "difference_adf" in audit_channel
    assert "level_kpss" in audit_channel
    assert "difference_kpss" in audit_channel


def test_stationarity_requires_fourteen_complete_days() -> None:
    result = _compute(335)

    assert result.status == "not_eligible"
    assert result.reason_code == "insufficient_stationarity_sensitivity_tier"
    assert result.payload is None
    assert result.audit_metadata["sensitivity"] == []


def test_stationarity_does_not_join_across_an_ineligible_hour() -> None:
    result = _compute(400, ineligible=frozenset({200}))

    assert result.status == "not_eligible"
    assert result.reason_code == "insufficient_stationarity_sensitivity_tier"


def test_stationarity_constant_channels_publish_status_without_hypothesis_tests(
) -> None:
    result = _compute(336, constant=True)

    payload = StationarityPayload.model_validate(result.payload)
    channel = payload.sensitivity[0].channels["suhu"]
    assert result.status == "complete"
    assert channel.autocorrelation.status == "constant"
    assert channel.spectrum.status == "constant"
    assert channel.stl.status == "constant"
    assert "level_adf" not in channel.model_dump()
    assert "level_kpss" not in channel.model_dump()


def test_stationarity_bundle_matches_statsmodels_and_scipy_goldens() -> None:
    generator = np.random.default_rng(22)
    values = generator.normal(size=500)
    bundle = stationarity.stationarity_bundle(values, DEFAULT_CONFIG.stationarity)
    frequencies, power = periodogram(values)

    np.testing.assert_allclose(
        bundle.autocorrelation.values, acf(values, nlags=72, fft=True)
    )
    np.testing.assert_allclose(
        bundle.partial_autocorrelation.values,
        pacf(values, nlags=72, method="ywm"),
    )
    np.testing.assert_allclose(bundle.spectrum.frequencies, frequencies)
    np.testing.assert_allclose(bundle.spectrum.power, power)


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


def test_change_points_require_one_contiguous_ninety_day_block() -> None:
    short_days = np.arange(89, dtype=np.int64)
    fragmented_days = np.concatenate((np.arange(60), np.arange(61, 121))).astype(
        np.int64
    )
    short_values = np.column_stack((short_days, short_days**2)).astype(np.float64)
    fragmented_values = np.column_stack(
        (fragmented_days, fragmented_days**2)
    ).astype(np.float64)

    short = compute_change_points(_daily_temporal(short_days, short_values))
    fragmented = compute_change_points(
        _daily_temporal(fragmented_days, fragmented_values)
    )

    assert (short.status, short.reason_code) == (
        "not_eligible",
        "insufficient_daily_medians",
    )
    assert (fragmented.status, fragmented.reason_code) == (
        "not_eligible",
        "insufficient_daily_medians",
    )


def test_change_points_publish_constant_and_separate_channel_step_effects() -> None:
    constant_days = np.arange(90, dtype=np.int64)
    constant = compute_change_points(
        _daily_temporal(constant_days, np.ones((90, 2), dtype=np.float64))
    )
    payload = ChangePointsPayload.model_validate(constant.payload)

    days = np.arange(180, dtype=np.int64)
    step = np.column_stack(
        (
            np.concatenate((np.zeros(90), np.full(90, 8.0))),
            np.concatenate((np.zeros(90), np.full(90, -5.0))),
        )
    )
    detected = detect_change_points(
        DenseDailyBlock.from_arrays(days, step), DEFAULT_CONFIG.change_point
    )

    assert payload.blocks[0].status == "constant"
    assert payload.blocks[0].constant_channels == [0, 1]
    assert detected.status == "ok"
    change = next(
        item
        for item in detected.stable_candidates
        if abs(item.representative_day - 90) <= 3
    )
    assert change.penalty_factors == (1, 2, 4, 8)
    assert change.temperature_shift == pytest.approx(8.0)
    assert change.humidity_shift == pytest.approx(-5.0)
    assert change.temperature_mad_effect == pytest.approx(2.0)
    assert change.humidity_mad_effect == pytest.approx(-2.0)
    assert {item.minimum_segment_days for item in detected.confirmations} == {
        7,
        14,
        28,
    }
