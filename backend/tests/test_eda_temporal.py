from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path

import pytest

from anomaly_backend.eda_contracts import (
    QualityOverviewPayload,
    TemporalCoveragePayload,
    TemporalDistributionPayload,
)
from anomaly_eda.config import DEFAULT_CONFIG, DEVICE_ID
from anomaly_eda.input_adapter import RawInputAdapter, RawSourceMetadata
from anomaly_eda.pair_product import VIEW_RAW, VIEW_SCREENED
from anomaly_eda.temporal import (
    compute_temporal,
    daily_median_aggregates,
    hourly_median_aggregates,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures/eda_authority"


def _adapter(
    start: datetime,
    offsets: list[int],
    *,
    temperatures: list[float] | None = None,
    humidities: list[float] | None = None,
    duplicate_temperature_at: int | None = None,
    source_end: datetime | None = None,
) -> RawInputAdapter:
    temperatures = temperatures or [20.0 + index for index in range(len(offsets))]
    humidities = humidities or [50.0 + index for index in range(len(offsets))]
    rows: list[dict[str, object]] = []
    row_number = 1
    for position, offset in enumerate(offsets):
        timestamp = start + timedelta(seconds=offset)
        temperature_values = [temperatures[position]]
        if duplicate_temperature_at == position:
            temperature_values.append(temperatures[position] + 2.0)
        for value in sorted(temperature_values):
            rows.append(_row(row_number, timestamp, 0, value))
            row_number += 1
        rows.append(_row(row_number, timestamp, 1, humidities[position]))
        row_number += 1
    return RawInputAdapter.from_database_rows(
        rows,
        metadata=RawSourceMetadata(
            row_count=len(rows),
            start=start.strftime("%Y-%m-%d %H:%M:%S"),
            cutoff_inclusive=(
                source_end - timedelta(seconds=1)
                if source_end is not None
                else start + timedelta(seconds=offsets[-1])
            ).strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )


def _row(
    number: int,
    timestamp: datetime,
    channel: int,
    value: float,
) -> dict[str, object]:
    return {
        "source_row_number": number,
        "device_id": DEVICE_ID,
        "data_index": channel,
        "value": value,
        "ts": timestamp,
        "is_connected": True,
    }


def test_source_temporal_goldens_define_the_frozen_contract() -> None:
    goldens = json.loads((FIXTURE_DIR / "goldens.json").read_text(encoding="utf-8"))[
        "temporal_summaries"
    ]

    assert goldens["cadence"] == {
        "acceptance_interval_seconds": [5, 7],
        "expected_seconds": 6,
        "observed_median_positive_delta_at_most_ceiling": 6.0,
        "positive_delta_count": 3_454_027,
        "publication_gate": "pass",
    }
    assert goldens["calendar_semantics"] == {
        "bins": "half_open",
        "coverage_not_capped": True,
        "empty_bins_explicit": True,
        "expected_slots": "ceil(exposure_seconds/expected_cadence_seconds)",
        "timezone": "Asia/Jakarta",
    }
    assert DEFAULT_CONFIG.coverage.sensitivity_thresholds == (0.50, 0.80, 0.95)
    assert DEFAULT_CONFIG.coverage.dense_consecutive_months == 3


def test_custom_calendar_has_zero_bins_censored_edges_and_weighted_coverage() -> None:
    start = datetime(2025, 6, 23, 12, 0, 0)
    end = datetime(2025, 6, 25, 0, 0, 0)
    offsets = [0, 6, 43_200, 43_206, 43_212, 43_218, 43_224, 43_230]
    result = compute_temporal(
        _adapter(start, offsets, source_end=end),
        DEFAULT_CONFIG,
        period_kind="custom",
        range_start=start,
        range_end=end,
    )
    raw = result.temporal_coverage["views"][VIEW_RAW]
    hourly = raw["hourly"]
    daily = raw["daily"]
    monthly = raw["monthly"][0]

    assert len(hourly) == 36
    assert hourly[1]["exact_pair_count"] == 0
    assert hourly[1]["view_pair_count"] == 0
    assert hourly[1]["coverage"] == 0.0
    assert hourly[0]["from_censored"] is True
    assert hourly[-1]["to_censored"] is True
    assert daily[0]["partial"] is True
    assert daily[0]["from_censored"] is True
    assert daily[-1]["to_censored"] is True
    assert monthly["exact_pair_count"] == sum(item["exact_pair_count"] for item in daily)
    assert monthly["expected_slots"] == sum(item["expected_slots"] for item in daily)
    assert monthly["coverage"] == pytest.approx(
        monthly["exact_pair_count"] / monthly["expected_slots"]
    )
    assert monthly["coverage"] != pytest.approx(
        sum(item["coverage"] for item in daily) / len(daily)
    )


def test_uncapped_coverage_retention_and_channel_statistics_stay_separate() -> None:
    start = datetime(2025, 6, 23, 0, 0, 0)
    end = start + timedelta(minutes=1)
    offsets = [0, 6, 12, 18, 24, 30, 36, 41, 46, 51, 56]
    result = compute_temporal(
        _adapter(
            start,
            offsets,
            duplicate_temperature_at=0,
            temperatures=[20.0 + index for index in range(len(offsets))],
            humidities=[50.0 + 2 * index for index in range(len(offsets))],
            source_end=end,
        ),
        DEFAULT_CONFIG,
        period_kind="custom",
        range_start=start,
        range_end=end,
    )
    coverage = result.temporal_coverage["views"]
    distribution = result.temporal_distribution["views"]
    raw_bin = coverage[VIEW_RAW]["hourly"][0]
    screened_bin = coverage[VIEW_SCREENED]["hourly"][0]
    screened_stats = distribution[VIEW_SCREENED]["hourly"][0]["statistics"]

    assert result.temporal_distribution["cadence"]["publication_gate"] == "pass"
    assert raw_bin["coverage"] == pytest.approx(1.1)
    assert raw_bin["coverage"] > 1.0
    assert raw_bin["retention"] == 1.0
    assert screened_bin["retention"] == pytest.approx(10 / 11)
    assert screened_stats["count"] == 10
    assert screened_stats["suhu"]["median"] != screened_stats["rh"]["median"]
    assert result.temporal_distribution["views"][VIEW_SCREENED]["channels"] == {
        "suhu": {"name": "Suhu", "unit": "°C"},
        "rh": {"name": "RH", "unit": "%"},
    }
    assert TemporalCoveragePayload.model_validate(result.temporal_coverage)
    assert TemporalDistributionPayload.model_validate(result.temporal_distribution)


def test_thirty_seconds_stays_in_segment_and_thirty_one_breaks() -> None:
    start = datetime(2025, 6, 23, 0, 0, 0)
    end = start + timedelta(seconds=90)
    result = compute_temporal(
        _adapter(start, [0, 6, 36, 42, 73, 79, 85], source_end=end),
        DEFAULT_CONFIG,
        period_kind="custom",
        range_start=start,
        range_end=end,
    )
    continuity = result.temporal_distribution["views"][VIEW_RAW]["continuity"]

    assert result.pair_product.raw_view.segment_ids[30].tolist() == [0, 0, 0, 0, 1, 1, 1]
    assert continuity == {
        "gap_boundary_seconds": 30,
        "gap_count": 1,
        "segment_count": 2,
        "from_open_ended": True,
        "to_open_ended": True,
    }


def test_weekly_run_uses_monday_to_monday_raw_range() -> None:
    monday = datetime(2025, 6, 23, 0, 0, 0)
    next_monday = monday + timedelta(days=7)
    result = compute_temporal(
        _adapter(
            monday,
            [0, 6, 7 * 86_400 - 12, 7 * 86_400 - 6],
            source_end=next_monday,
        ),
        DEFAULT_CONFIG,
        period_kind="weekly",
        range_start=monday,
        range_end=next_monday,
    )
    raw = result.temporal_coverage["views"][VIEW_RAW]

    assert len(raw["hourly"]) == 7 * 24
    assert len(raw["daily"]) == 7
    assert raw["daily"][0]["start"] == "2025-06-23T00:00:00+07:00"
    assert raw["daily"][-1]["end"] == "2025-06-30T00:00:00+07:00"
    assert raw["monthly"][0]["exposure_seconds"] == 7 * 86_400
    assert raw["monthly"][0]["expected_slots"] == 100_800
    assert raw["monthly"][0]["coverage"] == pytest.approx(4 / 100_800)
    assert raw["hourly"][0]["from_censored"] is False
    assert raw["hourly"][-1]["to_censored"] is False


def test_hourly_and_daily_helpers_are_the_shared_task9_aggregations() -> None:
    start = datetime(2025, 6, 23, 0, 0, 0)
    end = start + timedelta(days=1)
    computed = compute_temporal(
        _adapter(start, [0, 6, 12], source_end=end),
        DEFAULT_CONFIG,
        period_kind="daily",
        range_start=start,
        range_end=end,
    )
    assert hourly_median_aggregates(computed, VIEW_SCREENED) == computed.aggregates[
        VIEW_SCREENED
    ]["hourly"]
    assert daily_median_aggregates(computed, VIEW_SCREENED) == computed.aggregates[
        VIEW_SCREENED
    ]["daily"]


def test_exact_six_second_cadence_gate_rejects_five_second_median() -> None:
    start = datetime(2025, 6, 23, 0, 0, 0)

    with pytest.raises(ValueError, match="observed cadence publication gate failed"):
        _ = compute_temporal(_adapter(start, [0, 5, 10]))


def test_custom_range_cannot_fabricate_exposure_outside_source_extent() -> None:
    source_start = datetime(2025, 6, 23, 0, 1, 0)
    source_end = source_start + timedelta(seconds=13)

    with pytest.raises(ValueError, match="outside the source extent"):
        _ = compute_temporal(
            _adapter(source_start, [0, 6, 12], source_end=source_end),
            DEFAULT_CONFIG,
            period_kind="custom",
            range_start=source_start - timedelta(seconds=30),
            range_end=source_end,
        )


def test_temporal_payload_has_a_narrow_larger_calendar_allowance() -> None:
    calendar = {f"part_{index}": [0] * 40_000 for index in range(3)}

    assert TemporalCoveragePayload.model_validate(
        {"calendar_semantics": {"bins": "half_open"}, "views": calendar}
    )
    with pytest.raises(ValueError, match="at most 100000 values"):
        _ = QualityOverviewPayload.model_validate(
            {
                "source_audit": {},
                "count_conservation": {},
                "quality_metrics": calendar,
            }
        )
