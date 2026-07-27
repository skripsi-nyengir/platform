from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import time
from datetime import datetime
from typing import Any, cast

import numpy as np  # pyright: ignore[reportMissingImports]
import pytest

from anomaly_backend.eda_contracts import (
    ChangePointsPayload,
    EDA_SECTION_NAMES,
    EDA_SOURCE_FROM,
    EDA_SOURCE_TO,
    RelationshipsPayload,
    StationarityPayload,
    TemporalCoveragePayload,
    TemporalDistributionPayload,
    UncertaintyPayload,
)
from anomaly_backend.sql.eda_runs import build_logical_key
from anomaly_eda import ALGORITHM_VERSION, CONFIG_HASH, RawInputAdapter
from anomaly_eda.change_points import compute_change_points
from anomaly_eda.config import (
    CANONICAL_CONFIG_PARAMETERS,
    DATASET_ID,
    DEVICE_ID,
    MAXIMUM_PEAK_RSS_BYTES,
    SEED,
    TIME_ZONE,
)
from anomaly_eda.quality import compute_quality  # pyright: ignore[reportMissingImports]
from anomaly_eda.relationships import compute_relationships
from anomaly_eda.stationarity import compute_stationarity
from anomaly_eda.temporal import (  # pyright: ignore[reportMissingImports]
    TemporalComputeResult,
    build_temporal_sections,
)
from anomaly_eda.uncertainty import compute_uncertainty
import anomaly_worker.eda_service as eda_service


FIXTURE_DIR = Path(__file__).parent / "fixtures/eda_authority"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _arrays() -> dict[str, Any]:
    value = json.loads(gzip.decompress((FIXTURE_DIR / "golden_arrays.json.gz").read_bytes()))
    assert isinstance(value, dict)
    return value


def _temporal_summary(result: TemporalComputeResult) -> dict[str, Any]:
    coverage = result.temporal_coverage
    distribution = result.temporal_distribution
    views: dict[str, Any] = {}
    for view, view_data in coverage["views"].items():
        resolutions: dict[str, Any] = {}
        for resolution in ("hourly", "daily", "monthly"):
            bins = view_data[resolution]
            source_bins = _source_temporal_bins(
                result.aggregates[view][resolution], resolution
            )
            keys = bins[0]["eligible"] if bins else {}
            resolutions[resolution] = {
                "bin_count": len(bins),
                "bins_sha256": hashlib.sha256(
                    json.dumps(
                        source_bins,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest(),
                "eligible_bin_counts": {
                    key: sum(bool(item["eligible"][key]) for item in bins)
                    for key in keys
                },
                "exact_pair_count_sum": sum(item["exact_pair_count"] for item in bins),
                "expected_slots_sum": sum(item["expected_slots"] for item in bins),
                "partial_bin_count": sum(bool(item["partial"]) for item in bins),
                "view_pair_count_sum": sum(item["view_pair_count"] for item in bins),
            }
        views[view] = {
            "dense_regimes": view_data["dense_regimes"],
            "drift_conclusions": distribution["views"][view]["drift_conclusions"],
            "eligible_hour_segments": view_data["eligible_hour_segments"],
            "resolutions": resolutions,
        }
    return {
        "cadence": distribution["cadence"],
        "calendar_semantics": coverage["calendar_semantics"],
        "views": views,
    }


def _source_temporal_bins(
    bins: list[dict[str, Any]], resolution: str
) -> list[dict[str, Any]]:
    keys = (
        "start",
        "end",
        "exposure_seconds",
        "full_bin_seconds",
        "expected_slots",
        "exact_pair_count",
        "view_pair_count",
        "coverage",
        "partial",
        "eligible",
        "statistics",
    )
    monthly = ("eligible_nonpartial_days", "complete", "regime")
    selected = keys + monthly if resolution == "monthly" else keys
    return [{key: record[key] for key in selected} for record in bins]


def _assert_nested_close(actual: Any, expected: Any) -> None:
    if isinstance(expected, dict):
        assert isinstance(actual, dict)
        assert set(actual) == set(expected)
        for key, value in expected.items():
            _assert_nested_close(actual[key], value)
        return
    if isinstance(expected, list):
        assert isinstance(actual, list)
        assert len(actual) == len(expected)
        for actual_item, expected_item in zip(actual, expected, strict=True):
            _assert_nested_close(actual_item, expected_item)
        return
    if isinstance(expected, float):
        assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)
        return
    assert actual == expected


def _stationarity_metadata(segment: dict[str, Any]) -> dict[str, Any]:
    result = {key: segment[key] for key in ("start", "end", "hours", "status")}
    for channel in ("suhu", "rh"):
        result[channel] = {
            name: {
                key: value
                for key, value in cast(dict[str, Any], record).items()
                if not isinstance(value, list)
            }
            for name, record in cast(dict[str, Any], segment[channel]).items()
        }
    return result


def _assert_stationarity_arrays(
    actual: dict[str, Any], expected: dict[str, Any]
) -> None:
    assert {key: actual[key] for key in ("start", "end", "hours", "status")} == {
        key: expected[key] for key in ("start", "end", "hours", "status")
    }
    for channel in ("suhu", "rh"):
        actual_channel = cast(dict[str, Any], actual[channel])
        expected_channel = expected["channels"][channel]
        for diagnostic in ("autocorrelation", "partial_autocorrelation"):
            np.testing.assert_allclose(
                actual_channel[diagnostic]["values"],
                expected_channel[diagnostic],
                rtol=1e-12,
                atol=1e-12,
            )
        for diagnostic, fields in (
            ("spectrum", ("frequencies", "power")),
            ("stl", ("residual", "seasonal", "trend")),
        ):
            for field in fields:
                np.testing.assert_allclose(
                    actual_channel[diagnostic][field],
                    expected_channel[diagnostic][field],
                    rtol=1e-12,
                    atol=1e-12,
                )


def _production_section_hashes(
    quality: Any,
    temporal: TemporalComputeResult,
    relationships: Any,
    stationarity: Any,
    change_points: Any,
    uncertainty: Any,
    manifest_sha256: str,
) -> dict[str, str]:
    source_from = datetime.fromisoformat(EDA_SOURCE_FROM)
    source_to = datetime.fromisoformat(EDA_SOURCE_TO)
    job: dict[str, object] = {
        "id": "00000000-0000-0000-0000-000000000021",
        "source_sha256": quality.source_audit["sha256"],
        "from_ts": source_from,
        "to_ts": source_to,
        "period_kind": "full_range",
        "algorithm_version": ALGORITHM_VERSION,
        "config_hash": CONFIG_HASH,
    }
    payloads = eda_service._quality_payloads(quality)  # pyright: ignore[reportPrivateUsage]
    quality_overview = deepcopy(payloads["quality_overview"])
    source_audit = cast(dict[str, object], quality_overview["source_audit"])
    source_audit["size_bytes"] = None
    source_audit["raw_open_count"] = 0
    payloads["quality_overview"] = quality_overview
    payloads.update(
        temporal_coverage=temporal.temporal_coverage,
        temporal_distribution=temporal.temporal_distribution,
        relationships=cast(dict[str, object], relationships.payload),
        stationarity=cast(dict[str, object], stationarity.payload),
        change_points=cast(dict[str, object], change_points.payload),
        uncertainty=cast(dict[str, object], uncertainty.payload),
        audit_metadata=eda_service._audit_payload(  # pyright: ignore[reportPrivateUsage]
            {"manifest_sha256": manifest_sha256}
        ),
    )
    assert set(payloads) == set(EDA_SECTION_NAMES)
    counts = eda_service._sample_counts(quality)  # pyright: ignore[reportPrivateUsage]
    hashes: dict[str, str] = {}
    for section in EDA_SECTION_NAMES:
        staged = eda_service._stage_section(  # pyright: ignore[reportPrivateUsage]
            job,
            counts,
            section,
            status="complete",
            payload=payloads[section],
        )
        hashes[section] = cast(str, staged["payload_sha256"])
    return hashes


@pytest.mark.canonical
def test_canonical_v3_quality_outputs_match_frozen_authority() -> None:
    started = time.monotonic()
    raw_path_value = os.environ.get("EDA_CANONICAL_RAW_CSV")
    if not raw_path_value:
        pytest.skip("EDA_CANONICAL_RAW_CSV is required for canonical parity")
    raw_path = Path(raw_path_value)
    goldens = _json(FIXTURE_DIR / "goldens.json")
    arrays = _arrays()
    source = goldens["source"]

    assert source["row_count"] == 6_931_792
    assert source["exact_pair_count"] == 3_460_865
    assert source["rule_screened_pair_count"] == 3_405_332
    assert source["excluded_pair_count"] == 55_533
    assert goldens["authority"]["artifact_sha256"]["source_archive"] == (
        "b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f"
    )
    manifest_sha256 = goldens["authority"]["artifact_sha256"]["source_manifest"]
    assert manifest_sha256 == (
        "196178e7424bd2e92268606f0ef33237d2329bdfefd9dce592283c07a697d486"
    )
    assert CONFIG_HASH == (
        "1081a79b8452075df4baf2f88f6ed3094f90286c0e17ee7d666e0b8072ba8452"
    )
    assert ALGORITHM_VERSION == (
        "bivariate_b02f3872_eda_v3+vendor."
        "37565a5341be56e9a0a88d55ce1dbfe6ae25b0fe"
    )
    assert (DATASET_ID, DEVICE_ID, TIME_ZONE, SEED) == (
        "bivariate_b02f3872_v1",
        "b02f3872-39a2-4b6f-a4ec-045a287fde4b",
        "Asia/Jakarta",
        20_260_724,
    )
    for family in ("v2", "v3"):
        identity = CANONICAL_CONFIG_PARAMETERS[family]["identity"]
        assert identity["dataset_id"] == DATASET_ID
        assert identity["timezone"] == TIME_ZONE
        assert identity["seed"] == SEED

    result = compute_quality(
        RawInputAdapter.from_csv(
            raw_path,
            expected_sha256=goldens["authority"]["artifact_sha256"]["source_archive"],
            expected_size_bytes=source["size_bytes"],
            expected_row_count=source["row_count"],
            source_start=source["start"],
            source_cutoff_inclusive=source["cutoff_inclusive"],
        )
    )

    assert ALGORITHM_VERSION == (
        f"{goldens['releases']['v3']['release_id']}+vendor."
        f"{goldens['releases']['v3']['implementation_commit']}"
    )
    assert result.algorithm_version == ALGORITHM_VERSION
    assert result.config_hash == CONFIG_HASH
    assert result.source_audit == goldens["scalar_counts"]["v3_source_audit"]
    expected_quality_audit = goldens["scalar_counts"]["v2_quality_audit"]
    assert {
        key: result.pair_product.audit[key] for key in expected_quality_audit
    } == expected_quality_audit
    assert result.count_conservation == goldens["conservation"]
    assert result.pair_product.raw_view.pair_count == source["exact_pair_count"]
    assert (
        result.pair_product.rule_screened_view.pair_count
        == source["rule_screened_pair_count"]
    )
    assert (
        result.pair_product.raw_view.pair_count
        - result.pair_product.rule_screened_view.pair_count
        == source["excluded_pair_count"]
    )
    assert result.diagnostics.instrumentation == goldens["scalar_counts"][
        "v3_instrumentation"
    ]

    expected_v3 = arrays["v3"]
    actual_joint = result.diagnostics.joint_density
    expected_joint = expected_v3["joint_density"]
    for axis in ("suhu", "rh"):
        np.testing.assert_array_equal(
            actual_joint["edges"][axis], expected_joint["edges"][axis]
        )
    for view in ("resolved_raw_pairs", "rule_screened_pairs"):
        np.testing.assert_array_equal(
            actual_joint["views"][view]["histogram"],
            expected_joint["views"][view]["histogram"],
        )

    actual_channels = result.diagnostics.univariate["channels"]
    expected_channels = expected_v3["univariate"]["channels"]
    for channel in ("Suhu", "RH"):
        np.testing.assert_array_equal(
            actual_channels[channel]["edges"], expected_channels[channel]["edges"]
        )
        for view in ("resolved_raw_pairs", "rule_screened_pairs"):
            for field in ("histogram", "ecdf_count", "ecdf_fraction"):
                np.testing.assert_array_equal(
                    actual_channels[channel]["views"][view][field],
                    expected_channels[channel]["views"][view][field],
                )

    excerpt = result.diagnostics.quality_excerpt
    assert {
        key: value for key, value in excerpt.items() if key != "records"
    } == goldens["quality_excerpt"]
    assert excerpt["records"] == expected_v3["quality_excerpt_records"]

    temporal = build_temporal_sections(result.pair_product)
    assert _temporal_summary(temporal) == goldens["temporal_summaries"]
    assert TemporalCoveragePayload.model_validate(temporal.temporal_coverage)
    assert TemporalDistributionPayload.model_validate(temporal.temporal_distribution)
    published_temporal = build_temporal_sections(
        result.pair_product,
        period_kind="full_range",
        range_start=datetime.fromisoformat(EDA_SOURCE_FROM),
        range_end=datetime.fromisoformat(EDA_SOURCE_TO),
        enforce_cadence_gate=False,
    )

    relationships = compute_relationships(result.pair_product)
    assert relationships.status == "complete"
    assert relationships.payload is not None
    assert RelationshipsPayload.model_validate(relationships.payload)
    relationship_audit = cast(dict[str, Any], relationships.audit_metadata)
    for view, expected in goldens["associations"]["static"].items():
        actual = relationship_audit["static"][view]
        _assert_nested_close({key: actual[key] for key in expected}, expected)
    for view, variants in goldens["associations"]["rolling_pearson"].items():
        for name, expected in variants.items():
            actual = relationship_audit["rolling_pearson"][view][name]
            _assert_nested_close(
                {key: value for key, value in actual.items() if not isinstance(value, list)},
                expected,
            )
            expected_arrays = arrays["v2"]["rolling_samples"][view][name]
            np.testing.assert_array_equal(
                actual["plotted_end_timestamps"],
                expected_arrays["plotted_end_timestamps"],
            )
            np.testing.assert_allclose(
                actual["plotted_correlations"],
                expected_arrays["plotted_correlations"],
                rtol=1e-12,
                atol=1e-12,
            )

    stationarity = compute_stationarity(temporal)
    assert stationarity.status == "complete"
    assert stationarity.payload is not None
    assert StationarityPayload.model_validate(stationarity.payload)
    stationarity_audit = cast(dict[str, Any], stationarity.audit_metadata)
    stationarity_metadata = {
        "method_notice": stationarity_audit["method_notice"],
        "primary": _stationarity_metadata(stationarity_audit["primary"]),
        "sensitivity": [
            _stationarity_metadata(segment)
            for segment in stationarity_audit["sensitivity"]
        ],
        "status": stationarity_audit["status"],
    }
    _assert_nested_close(stationarity_metadata, goldens["stationarity"])
    expected_stationarity = arrays["v2"]["stationarity"]
    _assert_stationarity_arrays(
        stationarity_audit["primary"], expected_stationarity["primary"]
    )
    for actual_segment, expected_segment in zip(
        stationarity_audit["sensitivity"],
        expected_stationarity["sensitivity"],
        strict=True,
    ):
        _assert_stationarity_arrays(actual_segment, expected_segment)

    change_points = compute_change_points(temporal)
    assert change_points.status == "complete"
    assert change_points.payload is not None
    assert ChangePointsPayload.model_validate(change_points.payload)
    _assert_nested_close(change_points.audit_metadata, goldens["change_points"])

    uncertainty = compute_uncertainty(temporal)
    repeated_uncertainty = compute_uncertainty(temporal)
    assert uncertainty.status == "complete"
    assert uncertainty.payload is not None
    assert UncertaintyPayload.model_validate(uncertainty.payload)
    assert repeated_uncertainty.payload == uncertainty.payload
    _assert_nested_close(
        uncertainty.audit_metadata,
        goldens["bootstrap_intervals"],
    )

    section_hashes = _production_section_hashes(
        result,
        published_temporal,
        relationships,
        stationarity,
        change_points,
        uncertainty,
        manifest_sha256,
    )
    logical_key = build_logical_key(
        source_sha256=goldens["authority"]["artifact_sha256"]["source_archive"],
        from_ts=datetime.fromisoformat(EDA_SOURCE_FROM),
        to_ts=datetime.fromisoformat(EDA_SOURCE_TO),
        period_kind="full_range",
        algorithm_version=ALGORITHM_VERSION,
        config_hash=CONFIG_HASH,
    )
    peak_rss_bytes = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1_024
    runtime_seconds = time.monotonic() - started
    report = {
        "parity_status": "pass",
        "runtime_seconds": runtime_seconds,
        "peak_rss_bytes": peak_rss_bytes,
        "logical_key": logical_key,
        "section_hashes": section_hashes,
        "counts": {
            "raw_rows": source["row_count"],
            "exact_pairs": source["exact_pair_count"],
            "screened_pairs": source["rule_screened_pair_count"],
            "excluded_pairs": source["excluded_pair_count"],
        },
        "identity": {
            "source_sha256": goldens["authority"]["artifact_sha256"][
                "source_archive"
            ],
            "manifest_sha256": manifest_sha256,
            "config_hash": CONFIG_HASH,
            "algorithm_version": ALGORITHM_VERSION,
            "seed": SEED,
            "device_id": DEVICE_ID,
        },
    }
    os.environ["EDA_CANONICAL_PARITY_REPORT"] = json.dumps(
        report, sort_keys=True, separators=(",", ":")
    )
    print(f"task21 canonical parity report {os.environ['EDA_CANONICAL_PARITY_REPORT']}")
    print(
        "task7 canonical parity "
        f"pairs={result.pair_product.raw_view.pair_count} "
        f"screened={result.pair_product.rule_screened_view.pair_count} "
        f"rss_bytes={peak_rss_bytes} "
        f"algorithm_version={ALGORITHM_VERSION} config_hash={CONFIG_HASH}"
    )
    print(
        "task8 canonical temporal parity "
        f"hourly_bins={len(temporal.aggregates['resolved_raw_pairs']['hourly'])} "
        f"daily_bins={len(temporal.aggregates['resolved_raw_pairs']['daily'])} "
        f"monthly_bins={len(temporal.aggregates['resolved_raw_pairs']['monthly'])}"
    )
    print(
        "task9 canonical statistical parity "
        f"rolling_views={len(relationship_audit['rolling_pearson'])} "
        f"stationarity_segments={len(stationarity_audit['sensitivity'])} "
        f"change_blocks={len(cast(list[object], change_points.audit_metadata['blocks']))} "
        f"bootstrap_blocks={len(cast(dict[str, object], uncertainty.audit_metadata['blocks']))}"
    )
    assert peak_rss_bytes < MAXIMUM_PEAK_RSS_BYTES
