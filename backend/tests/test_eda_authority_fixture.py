from __future__ import annotations

from copy import deepcopy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest


FIXTURE_DIR = Path(__file__).parent / "fixtures/eda_authority"
GOLDENS_PATH = FIXTURE_DIR / "goldens.json"
ARRAYS_PATH = FIXTURE_DIR / "golden_arrays.json.gz"
EXTRACTOR_PATH = FIXTURE_DIR / "extract_goldens.py"


def _load_extractor() -> ModuleType:
    spec = importlib.util.spec_from_file_location("eda_authority_extractor", EXTRACTOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


extractor = _load_extractor()


def _fixtures() -> tuple[dict[str, Any], dict[str, Any]]:
    goldens = json.loads(GOLDENS_PATH.read_bytes())
    arrays = json.loads(gzip.decompress(ARRAYS_PATH.read_bytes()))
    assert isinstance(goldens, dict) and isinstance(arrays, dict)
    return goldens, arrays


def test_scalar_fixture_locks_authority_counts_and_required_fields() -> None:
    goldens, arrays = _fixtures()

    extractor.validate_fixture_shapes(goldens, arrays)
    authority = goldens["authority"]
    source = goldens["source"]
    assert authority["source_authority_id"] == "bivariate_b02f3872_v1"
    assert authority["aggregate_eda_authority_id"] == "bivariate_b02f3872_eda_v3"
    assert authority["historical_aggregate_eda_ids"] == [
        "bivariate_b02f3872_eda_v1",
        "bivariate_b02f3872_eda_v2",
    ]
    assert "talpha" not in authority["aggregate_eda_authority_id"].lower()
    assert authority["artifact_sha256"]["source_archive"] == (
        "b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f"
    )
    assert authority["artifact_sha256"]["source_manifest"] == (
        "196178e7424bd2e92268606f0ef33237d2329bdfefd9dce592283c07a697d486"
    )
    assert source["row_count"] == 6_931_792
    assert source["exact_pair_count"] == 3_460_865
    assert source["rule_screened_pair_count"] == 3_405_332
    assert source["excluded_pair_count"] == 55_533
    assert source["exact_pair_count"] == (
        source["rule_screened_pair_count"] + source["excluded_pair_count"]
    )
    assert goldens["releases"]["v2"]["seed"] == 20_260_724
    assert goldens["releases"]["v3"]["seed"] == 20_260_724
    expected_parent_sha256 = {
        **goldens["releases"]["v2"]["output_sha256"],
        "config": authority["artifact_sha256"]["v2_config"],
        "run_manifest": authority["artifact_sha256"]["v2_run_manifest"],
    }
    assert goldens["releases"]["v3"]["parent_sha256"] == expected_parent_sha256
    assert goldens["conservation"]["status"] == "pass"
    assert len(goldens["conservation"]["equations"]) == 5
    assert len(goldens["change_points"]["blocks"][2]["stable_candidates"]) == 4
    assert set(goldens["bootstrap_intervals"]["blocks"]) == {"7", "14", "28"}


def test_array_fixture_is_canonical_complete_and_zero_mtime_gzip() -> None:
    goldens, arrays = _fixtures()
    compressed = ARRAYS_PATH.read_bytes()

    assert compressed[4:8] == b"\0\0\0\0"
    assert gzip.decompress(compressed) == extractor.canonical_json_bytes(arrays)
    joint = arrays["v3"]["joint_density"]
    assert len(joint["edges"]["suhu"]) == 121
    assert len(joint["edges"]["rh"]) == 201
    raw_joint = joint["views"]["resolved_raw_pairs"]["histogram"]
    screened_joint = joint["views"]["rule_screened_pairs"]["histogram"]
    assert (len(raw_joint), len(raw_joint[0])) == (120, 200)
    assert (len(screened_joint), len(screened_joint[0])) == (120, 200)
    for channel, edge_count, value_count in (("Suhu", 601, 600), ("RH", 401, 400)):
        record = arrays["v3"]["univariate"]["channels"][channel]
        assert len(record["edges"]) == edge_count
        for view in ("resolved_raw_pairs", "rule_screened_pairs"):
            assert len(record["views"][view]["histogram"]) == value_count
            assert len(record["views"][view]["ecdf_count"]) == value_count
            assert len(record["views"][view]["ecdf_fraction"]) == value_count
    assert len(arrays["v3"]["quality_excerpt_records"]) == 810
    assert len(
        arrays["v2"]["rolling_samples"]["rule_screened_pairs"]
        ["window_30m_gap_30s"]["plotted_correlations"]
    ) == 2_000
    stationarity = arrays["v2"]["stationarity"]["primary"]["channels"]
    assert len(stationarity["suhu"]["autocorrelation"]) == 73
    assert len(stationarity["rh"]["partial_autocorrelation"]) == 73
    assert len(stationarity["suhu"]["spectrum"]["frequencies"]) == 375
    assert len(stationarity["rh"]["stl"]["trend"]) == 749
    assert sum(map(sum, raw_joint)) == goldens["conservation"]["joint"][
        "resolved_raw_pairs"
    ]["axis_status_matrix"][1][1]


def test_fixture_validation_rejects_missing_fields() -> None:
    goldens, arrays = _fixtures()
    broken = deepcopy(goldens)
    del broken["source"]["excluded_pair_count"]

    with pytest.raises(extractor.AuthorityError, match="source.excluded_pair_count"):
        extractor.validate_fixture_shapes(broken, arrays)


def test_fixture_validation_rejects_incomplete_statistical_branches() -> None:
    goldens, arrays = _fixtures()
    missing_rolling = deepcopy(arrays)
    del missing_rolling["v2"]["rolling_samples"]["resolved_raw_pairs"][
        "window_15m_gap_30s"
    ]
    with pytest.raises(extractor.AuthorityError, match="rolling variants"):
        extractor.validate_fixture_shapes(goldens, missing_rolling)

    missing_sensitivity = deepcopy(arrays)
    missing_sensitivity["v2"]["stationarity"]["sensitivity"].pop()
    with pytest.raises(extractor.AuthorityError, match="three sensitivity"):
        extractor.validate_fixture_shapes(goldens, missing_sensitivity)

    missing_interval = deepcopy(goldens)
    del missing_interval["bootstrap_intervals"]["blocks"]["14"][0]["upper"]
    with pytest.raises(extractor.AuthorityError, match="interval fields"):
        extractor.validate_fixture_shapes(missing_interval, arrays)


def test_source_hash_drift_is_rejected_before_json_parsing(tmp_path: Path) -> None:
    path = tmp_path / "summary.json"
    path.write_bytes(b"{not valid json")

    with pytest.raises(extractor.AuthorityError, match="source hash drift"):
        extractor._verified_json(
            tmp_path,
            path.name,
            hashlib.sha256(b"{}").hexdigest(),
        )


@pytest.mark.parametrize(
    "locator",
    ["../outside.json", "/etc/passwd", "C:\\outside.json", "\\\\server\\share"],
)
def test_authoritative_locators_must_stay_inside_source_repo(
    tmp_path: Path,
    locator: str,
) -> None:
    with pytest.raises(extractor.AuthorityError, match="repository-relative"):
        extractor._source_path(tmp_path, locator)


def test_authoritative_locators_reject_symlinks(tmp_path: Path) -> None:
    link = tmp_path / "linked.json"
    link.symlink_to("/etc/passwd")

    with pytest.raises(extractor.AuthorityError, match="symlink"):
        extractor._source_path(tmp_path, link.name)


def test_pinned_yaml_subset_parses_quotes_and_rejects_unsupported_forms() -> None:
    assert extractor._parse_yaml_scalar('"Suhu °C"') == "Suhu °C"
    assert extractor._parse_yaml_scalar("'O''Brien'") == "O'Brien"
    assert extractor._parse_yaml_scalar("[1, 2, median]") == [1, 2, "median"]

    for value in ('["a,b", c]', "0x10", "value # comment"):
        with pytest.raises(extractor.AuthorityError, match="unsupported"):
            extractor._parse_yaml_scalar(value)


def test_fixture_serialization_is_byte_deterministic() -> None:
    goldens, arrays = _fixtures()

    first = (
        extractor.canonical_json_bytes(goldens),
        extractor.gzip_canonical_json(arrays),
    )
    second = (
        extractor.canonical_json_bytes(goldens),
        extractor.gzip_canonical_json(arrays),
    )
    assert first == second
    assert first == (GOLDENS_PATH.read_bytes(), ARRAYS_PATH.read_bytes())


ACTIVE_CATALOG = f"""\
schema_version: artifact_authority_catalog_v3
active_lane: bivariate_b02f3872_v1
authority_domains:
  source_snapshot:
    current: bivariate_b02f3872_v1
    source_sha256: {extractor.PINNED_SHA256["source_archive"]}
  aggregate_eda:
    current: bivariate_b02f3872_eda_v3
    historical:
    - bivariate_b02f3872_eda_v1
    - bivariate_b02f3872_eda_v2
    run_manifest_sha256: {extractor.PINNED_SHA256["v3_run_manifest"]}
"""


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("active_lane: bivariate_b02f3872_v1", "active_lane: legacy_talpha_2node_v1"),
        ("current: bivariate_b02f3872_eda_v3", "current: bivariate_b02f3872_eda_v2"),
        ("current: bivariate_b02f3872_eda_v3", "current: bivariate_b02f3872_eda_v1"),
        ("current: bivariate_b02f3872_eda_v3", "current: talpha_v2_dataset_and_eda"),
    ],
)
def test_non_v3_active_authority_is_rejected(old: str, new: str) -> None:
    extractor.validate_active_authority(ACTIVE_CATALOG)

    with pytest.raises(extractor.AuthorityError, match="active authority mismatch"):
        extractor.validate_active_authority(ACTIVE_CATALOG.replace(old, new))
