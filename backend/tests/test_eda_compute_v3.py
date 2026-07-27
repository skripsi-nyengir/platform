from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path

import numpy as np  # pyright: ignore[reportMissingImports]
import pytest

from anomaly_eda import (
    CONFIG_HASH,
    PairChunk,
    RawInputAdapter,
    RawSourceMetadata,
    build_pair_product,
    iter_pair_chunks,
)
from anomaly_eda.config import (
    CANONICAL_CONFIG_PARAMETERS,
    DEFAULT_CONFIG,
    DEVICE_ID,
    canonical_json_bytes,
)
from anomaly_eda.quality import (  # pyright: ignore[reportMissingImports]
    build_visual_diagnostics,
    compute_quality,
    select_excerpt,
)


def _row(
    number: int,
    second: int,
    channel: int,
    value: float,
    connected: bool = True,
) -> dict[str, object]:
    return {
        "source_row_number": number,
        "device_id": DEVICE_ID,
        "data_index": channel,
        "value": value,
        "ts": datetime(2025, 6, 23, 0, 0, second),
        "is_connected": connected,
    }


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    body = ["device_id,data_index,value,timestamp,is_connected"]
    for row in rows:
        timestamp = row["ts"]
        assert isinstance(timestamp, datetime)
        body.append(
            ",".join(
                (
                    str(row["device_id"]),
                    str(row["data_index"]),
                    str(row["value"]),
                    timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "true" if row["is_connected"] else "false",
                )
            )
        )
    path.write_text("\n".join(body) + "\n", encoding="utf-8")


def _pair_chunks(
    timestamps: np.ndarray,
    values: np.ndarray,
    *,
    chunk_size: int | None = None,
    rule_screened: np.ndarray | None = None,
    conflicting: np.ndarray | None = None,
) -> list[PairChunk]:
    size = int(timestamps.size)
    chunk_size = chunk_size or max(1, size)
    false = np.zeros(size, dtype=bool)
    screened = np.ones(size, dtype=bool) if rule_screened is None else rule_screened
    segments = np.zeros(size, dtype=np.int32)
    if size > 1:
        segments[1:] = np.cumsum(np.diff(timestamps) > 30, dtype=np.int32)
    return [
        PairChunk(
            timestamps_epoch_s=timestamps[start:end],
            values=values[start:end],
            non_finite=false[start:end],
            disconnected=false[start:end],
            zero=false[start:end],
            range_flag=false[start:end],
            duplicate=false[start:end],
            conflicting_duplicate=(false if conflicting is None else conflicting)[
                start:end
            ],
            stale=false[start:end],
            rule_screened=screened[start:end],
            segment_ids=segments[start:end],
        )
        for start in range(0, size, chunk_size)
        for end in [min(size, start + chunk_size)]
    ]


def test_algorithm_config_hash_covers_frozen_v3_and_inherited_v2() -> None:
    fixture = Path(__file__).parent / "fixtures/eda_authority/goldens.json"
    settings = json.loads(fixture.read_text(encoding="utf-8"))["settings"]

    assert CONFIG_HASH == hashlib.sha256(canonical_json_bytes(settings)).hexdigest()


def test_canonical_config_parameters_are_recursively_immutable() -> None:
    with pytest.raises(TypeError):
        CANONICAL_CONFIG_PARAMETERS["v3"]["quality"]["stale_duration_seconds"] = 30

    assert CANONICAL_CONFIG_PARAMETERS["v2"]["views"]["resolvers"] == (
        "median",
        "min",
        "max",
        "drop_conflicting",
    )


def test_csv_and_database_adapters_feed_identical_compute(tmp_path: Path) -> None:
    rows = [
        _row(1, 0, 0, 20.0),
        _row(2, 0, 1, 50.0),
        _row(3, 6, 0, 0.0),
        _row(4, 6, 1, 0.0),
        _row(5, 12, 0, 20.0),
        _row(6, 12, 0, 22.0),
        _row(7, 12, 1, 50.0),
    ]
    path = tmp_path / "raw.csv"
    _write_csv(path, rows)
    metadata = RawSourceMetadata(
        sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        size_bytes=path.stat().st_size,
        row_count=len(rows),
        start="2025-06-23 00:00:00",
        cutoff_inclusive="2025-06-23 00:00:12",
    )

    csv_result = compute_quality(
        RawInputAdapter.from_csv(
            path,
            expected_sha256=metadata.sha256,
            expected_size_bytes=metadata.size_bytes,
            expected_row_count=metadata.row_count,
            source_start=metadata.start,
            source_cutoff_inclusive=metadata.cutoff_inclusive,
            chunk_rows=2,
        )
    )
    database_result = compute_quality(
        RawInputAdapter.from_database_rows(rows, metadata=metadata, chunk_rows=1)
    )

    for view_name in ("resolved_raw_pairs", "rule_screened_pairs"):
        first = csv_result.pair_product.view(view_name)
        second = database_result.pair_product.view(view_name)
        np.testing.assert_array_equal(first.timestamps_epoch_s, second.timestamps_epoch_s)
        np.testing.assert_array_equal(first.values, second.values)
        for boundary in (15, 30, 60):
            np.testing.assert_array_equal(
                first.segment_ids[boundary], second.segment_ids[boundary]
            )
    for name, first in csv_result.pair_product.flags.reason_masks().items():
        np.testing.assert_array_equal(
            first, database_result.pair_product.flags.reason_masks()[name]
        )
    assert csv_result.diagnostics == database_result.diagnostics
    assert csv_result.count_conservation == database_result.count_conservation


def test_adapter_rejects_rows_outside_authoritative_source_bounds() -> None:
    metadata = RawSourceMetadata(
        start="2025-06-23 00:00:06",
        cutoff_inclusive="2025-06-23 00:00:12",
    )

    with pytest.raises(ValueError, match="timestamp outside source bounds"):
        _ = list(
            RawInputAdapter.from_database_rows(
                [_row(1, 0, 0, 20.0)], metadata=metadata
            ).iter_chunks()
        )


def test_adapter_rejects_boolean_channel_values() -> None:
    with pytest.raises(ValueError, match="invalid data_index"):
        _ = list(
            RawInputAdapter.from_database_rows(
                [{**_row(1, 0, 0, 20.0), "data_index": True}]
            ).iter_chunks()
        )


def test_quality_masks_keep_diagnostics_separate_from_screening() -> None:
    rows = [
        _row(1, 0, 0, 20.0),
        _row(2, 0, 1, 50.0),
        _row(3, 6, 0, 20.0),
        _row(4, 6, 0, 20.0),
        _row(5, 6, 1, 50.0),
        _row(6, 12, 0, 20.0),
        _row(7, 12, 0, 22.0),
        _row(8, 12, 1, 50.0),
        _row(9, 18, 0, 20.0, False),
        _row(10, 18, 1, 50.0),
        _row(11, 24, 0, np.nan),
        _row(12, 24, 1, 50.0),
        _row(13, 30, 0, 0.0),
        _row(14, 30, 1, 50.0),
        _row(15, 36, 0, 61.0),
        _row(16, 36, 1, 50.0),
        _row(17, 42, 0, 0.0000001),
        _row(18, 42, 1, 50.0),
    ]

    product = build_pair_product(RawInputAdapter.from_database_rows(rows, chunk_rows=3))
    flags = product.flags

    assert product.raw_view.values[1:3].tolist() == [[20.0, 50.0], [21.0, 50.0]]
    assert flags.duplicate.tolist() == [False, True, True, False, False, False, False, False]
    assert flags.conflicting_duplicate.tolist() == [False, False, True, False, False, False, False, False]
    assert flags.disconnected.tolist() == [False, False, False, True, False, False, False, False]
    assert flags.non_finite.tolist() == [False, False, False, False, True, False, False, False]
    assert flags.zero.tolist() == [False, False, False, False, False, True, False, False]
    assert flags.range.tolist() == [False, False, False, False, False, False, True, False]
    assert flags.near_zero.tolist() == [False, False, False, False, False, True, False, True]
    assert flags.stale.tolist() == [False, True, True, True, True, True, True, True]
    assert flags.rule_screened.tolist() == [True, False, False, False, False, False, False, True]


def test_pairing_happens_before_screening_and_uses_inner_timestamps() -> None:
    rows = [
        _row(1, 0, 0, 61.0),
        _row(2, 0, 1, 50.0),
        _row(3, 6, 0, 20.0),
    ]

    product = build_pair_product(RawInputAdapter.from_database_rows(rows))

    assert product.audit["union_timestamps"] == 2
    assert product.audit["intersection_timestamps"] == 1
    assert product.audit["missing_idx1_timestamps"] == 1
    assert product.raw_view.pair_count == 1
    assert product.rule_screened_view.pair_count == 0
    assert product.flags.range.tolist() == [True]


def test_float64_median_keeps_nonfinite_source_semantics() -> None:
    rows = [
        _row(1, 0, 0, -np.inf),
        _row(2, 0, 0, np.inf),
        _row(3, 0, 1, 50.0),
    ]

    with np.errstate(invalid="ignore"):
        product = build_pair_product(RawInputAdapter.from_database_rows(rows))

    assert np.isnan(product.raw_view.values[0, 0])
    assert product.flags.non_finite.tolist() == [True]
    assert product.flags.duplicate.tolist() == [True]
    assert product.flags.conflicting_duplicate.tolist() == [True]
    assert product.flags.rule_screened.tolist() == [False]
    assert product.duplicate_audit == (
        {
            "timestamp_epoch_s": int(product.raw_view.timestamps_epoch_s[0]),
            "channel_index": 0,
            "channel": "Suhu",
            "group_size": 2,
            "minimum": None,
            "maximum": None,
            "range": None,
            "median": None,
            "mad": None,
            "identical": False,
            "conflicting": True,
            "connectivity_disagreement": False,
        },
    )


def test_segment_boundary_is_strictly_greater_than_thirty_seconds() -> None:
    rows = [
        _row(1, 0, 0, 20.0),
        _row(2, 0, 1, 50.0),
        _row(3, 30, 0, 21.0),
        _row(4, 30, 1, 51.0),
        {
            **_row(5, 0, 0, 22.0),
            "ts": datetime(2025, 6, 23, 0, 1, 1),
        },
        {
            **_row(6, 0, 1, 52.0),
            "ts": datetime(2025, 6, 23, 0, 1, 1),
        },
    ]

    product = build_pair_product(RawInputAdapter.from_database_rows(rows))

    assert product.raw_view.segment_ids[30].tolist() == [0, 0, 1]
    assert product.raw_view.segment_ids[15].tolist() == [0, 1, 2]
    assert product.raw_view.segment_ids[60].tolist() == [0, 0, 0]
    assert product.audit["gap_above_primary_count"] == 1
    assert product.audit["positive_delta_at_most_gap_count"] == 1


def test_pair_chunks_use_supplied_config_for_segments_and_chunk_limit() -> None:
    config = replace(
        DEFAULT_CONFIG,
        cadence=replace(
            DEFAULT_CONFIG.cadence,
            primary_gap_seconds=10,
            gap_sensitivity_seconds=(5, 20),
        ),
        streaming=replace(DEFAULT_CONFIG.streaming, maximum_chunk_pairs=1),
    )
    rows = [
        _row(1, 0, 0, 20.0),
        _row(2, 0, 1, 50.0),
        _row(3, 6, 0, 21.0),
        _row(4, 6, 1, 51.0),
        _row(5, 17, 0, 22.0),
        _row(6, 17, 1, 52.0),
    ]

    product = build_pair_product(RawInputAdapter.from_database_rows(rows), config)
    chunks = list(iter_pair_chunks(product, config=config))

    assert [chunk.timestamps_epoch_s.size for chunk in chunks] == [1, 1, 1]
    assert np.concatenate([chunk.segment_ids for chunk in chunks]).tolist() == [0, 0, 1]


def test_compute_quality_fails_closed_on_unrepresentative_cadence() -> None:
    rows = [
        _row(1, 0, 0, 20.0),
        _row(2, 0, 1, 50.0),
        _row(3, 5, 0, 21.0),
        _row(4, 5, 1, 51.0),
    ]

    with pytest.raises(ValueError, match="cadence publication gate failed"):
        _ = compute_quality(RawInputAdapter.from_database_rows(rows))

    result = compute_quality(
        RawInputAdapter.from_database_rows(rows), enforce_cadence_gate=False
    )
    assert result.source_audit["cadence_gate"] == "fail"


def test_fixed_bins_audit_out_of_domain_mass_without_clipping() -> None:
    values = np.asarray(
        [
            [-1.0, -1.0],
            [0.0, 0.0],
            [60.0, 100.0],
            [61.0, 101.0],
            [np.nan, 50.0],
            [30.0, np.inf],
            [30.0, 50.0],
        ],
        dtype=np.float64,
    )
    timestamps = np.arange(values.shape[0], dtype=np.int64) * 6
    screened = np.asarray([False, False, True, False, False, False, True])

    diagnostics = build_visual_diagnostics(
        _pair_chunks(timestamps, values, rule_screened=screened)
    )
    conservation = diagnostics.univariate["channels"]

    assert diagnostics.joint_density["views"]["resolved_raw_pairs"]["audit"] == {
        "total_pairs": 7,
        "non_finite_pairs": 2,
        "axis_status_matrix": [[1, 0, 0], [0, 3, 0], [0, 0, 1]],
        "excluded_pairs": 0,
    }
    assert sum(map(sum, diagnostics.joint_density["views"]["resolved_raw_pairs"]["histogram"])) == 3
    assert conservation["Suhu"]["views"]["resolved_raw_pairs"]["audit"] == {
        "total": 7,
        "finite": 6,
        "non_finite": 1,
        "underflow": 1,
        "in_domain": 4,
        "overflow": 1,
        "excluded_finite": 0,
    }
    assert conservation["RH"]["views"]["resolved_raw_pairs"]["audit"] == {
        "total": 7,
        "finite": 6,
        "non_finite": 1,
        "underflow": 1,
        "in_domain": 4,
        "overflow": 1,
        "excluded_finite": 0,
    }
    for channel in ("Suhu", "RH"):
        record = conservation[channel]["views"]["resolved_raw_pairs"]
        assert record["ecdf_count"] == np.cumsum(record["histogram"]).tolist()
        assert record["ecdf_fraction"][-1] == pytest.approx(4 / 6)


@pytest.mark.parametrize("chunk_size", [1, 3, 10])
def test_visual_reducer_is_chunk_invariant_and_conserves_counts(chunk_size: int) -> None:
    values = np.asarray(
        [[0.0, 0.0], [20.0, 50.0], [60.0, 100.0], [-1.0, 101.0]] * 2,
        dtype=np.float64,
    )
    timestamps = np.arange(values.shape[0], dtype=np.int64) * 6
    screened = np.asarray([False, True, True, False] * 2)

    actual = build_visual_diagnostics(
        _pair_chunks(
            timestamps,
            values,
            chunk_size=chunk_size,
            rule_screened=screened,
        )
    )
    expected = build_visual_diagnostics(
        _pair_chunks(timestamps, values, rule_screened=screened)
    )

    assert actual.joint_density == expected.joint_density
    assert actual.univariate == expected.univariate
    assert actual.quality_excerpt == expected.quality_excerpt
    assert actual.instrumentation["maximum_emitted_chunk_pairs"] == min(
        chunk_size, values.shape[0]
    )


def test_excerpt_priority_stale_conflicting_and_dense_fallbacks() -> None:
    stale_timestamps = np.arange(0, 601, 6, dtype=np.int64)
    stale_values = np.column_stack(
        (np.full(stale_timestamps.size, 20.0), np.full(stale_timestamps.size, 50.0))
    )
    stale_excerpt = select_excerpt(_pair_chunks(stale_timestamps, stale_values))
    assert (
        stale_excerpt["selection_kind"],
        stale_excerpt["event_start_epoch_s"],
        stale_excerpt["event_end_epoch_s"],
        stale_excerpt["channel_index"],
    ) == ("stale", 0, 600, 0)

    conflict_timestamps = np.asarray([0, 40, 80], dtype=np.int64)
    conflict_values = np.asarray([[20.0, 50.0], [21.0, 51.0], [22.0, 52.0]])
    conflict_excerpt = select_excerpt(
        _pair_chunks(
            conflict_timestamps,
            conflict_values,
            conflicting=np.asarray([False, True, True]),
        )
    )
    assert conflict_excerpt["selection_kind"] == "conflicting_duplicate"
    assert conflict_excerpt["event_start_epoch_s"] == 40

    dense_timestamps = np.asarray([0, 40, 46, 52], dtype=np.int64)
    dense_values = np.asarray(
        [[20.0, 50.0], [21.0, 51.0], [22.0, 52.0], [23.0, 53.0]]
    )
    dense_excerpt = select_excerpt(_pair_chunks(dense_timestamps, dense_values))
    assert dense_excerpt["selection_kind"] == "dense"
    assert dense_excerpt["event_start_epoch_s"] == 40
    assert dense_excerpt["event_end_epoch_s"] == 46


def test_both_zero_priority_context_and_two_thousand_record_cap() -> None:
    timestamps = np.arange(4_001, dtype=np.int64)
    values = np.full((timestamps.size, 2), [20.0, 50.0])
    values[2_000:2_100] = 0.0

    excerpt = select_excerpt(_pair_chunks(timestamps, values, chunk_size=137))
    selected = [record["timestamp_epoch_s"] for record in excerpt["records"]]

    assert excerpt["selection_kind"] == "both_zero"
    assert excerpt["event_start_epoch_s"] == 2_000
    assert excerpt["event_end_epoch_s"] == 2_099
    assert len(selected) == 2_000
    assert selected == list(range(1_050, 3_050))


def test_reducer_rejects_pair_chunks_over_configured_limit() -> None:
    config = replace(
        DEFAULT_CONFIG,
        streaming=replace(DEFAULT_CONFIG.streaming, maximum_chunk_pairs=2),
    )
    timestamps = np.asarray([0, 6, 12], dtype=np.int64)
    values = np.asarray([[20.0, 50.0], [21.0, 51.0], [22.0, 52.0]])

    with pytest.raises(ValueError, match="exceeds configured maximum"):
        build_visual_diagnostics(_pair_chunks(timestamps, values), config)
