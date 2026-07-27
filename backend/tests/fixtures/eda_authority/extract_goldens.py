from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any


CATALOG_PATH = "docs/artifacts/authority-catalog.yaml"
SOURCE_ID = "bivariate_b02f3872_v1"
V2_ID = "bivariate_b02f3872_eda_v2"
V3_ID = "bivariate_b02f3872_eda_v3"
PINNED_SHA256 = {
    "source_archive": "b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f",
    "source_manifest": "196178e7424bd2e92268606f0ef33237d2329bdfefd9dce592283c07a697d486",
    "v2_config": "e80d0590cec5d011c9d3ceed21117ae406d542352ec1663162de4f95b79dbfb8",
    "v2_run_manifest": "10c301aefa66a3f4104ce43df33afd0e1ddf2c179f2cdd06d728fa0e98bd0bb4",
    "v2_summary": "68474a3db3bd095f380888237644a0cbcb6ce1bd955a266b77012652b1ffa831",
    "v3_config": "be7510afdcfad22a7a027740bc97ff0327699fbbfa2b5575c332d442b4c8de37",
    "v3_run_manifest": "6086ba879d4d6c62720e52af9cfdda26f01e852afff4cef0538a60c6d3b1d406",
    "v3_summary": "8c411d701efafef97df807cc165ee5d3bed042614e860bda59fc8a09df38dbde",
}
EXPECTED_COUNTS = {
    "row_count": 6_931_792,
    "exact_pair_count": 3_460_865,
    "rule_screened_pair_count": 3_405_332,
    "excluded_pair_count": 55_533,
}
SEED = 20_260_724
FIXTURE_DIR = Path(__file__).resolve().parent


class AuthorityError(ValueError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def gzip_canonical_json(value: Any) -> bytes:
    return gzip.compress(canonical_json_bytes(value), compresslevel=9, mtime=0)


def _source_path(root: Path, relative_path: str) -> Path:
    relative = Path(relative_path)
    if (
        not relative_path
        or relative.is_absolute()
        or ".." in relative.parts
        or re.match(r"^(?:[A-Za-z]:[\\/]|\\\\)", relative_path)
    ):
        raise AuthorityError(f"authoritative locator must be repository-relative: {relative_path}")
    resolved_root = root.resolve()
    unresolved = resolved_root
    for part in relative.parts:
        unresolved /= part
        if unresolved.is_symlink():
            raise AuthorityError(f"authoritative locator cannot traverse a symlink: {relative_path}")
    resolved = unresolved.resolve()
    if not resolved.is_relative_to(resolved_root):
        raise AuthorityError(f"authoritative locator escapes source repository: {relative_path}")
    if not resolved.is_file():
        raise AuthorityError(f"authoritative locator is not a regular file: {relative_path}")
    return resolved


def _verified_bytes(root: Path, relative_path: str, expected_sha256: str) -> bytes:
    path = _source_path(root, relative_path)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise AuthorityError(f"cannot read authoritative artifact {relative_path}: {exc}") from exc
    actual = _sha256(data)
    if actual != expected_sha256:
        raise AuthorityError(
            f"source hash drift for {relative_path}: "
            f"expected {expected_sha256}, got {actual}"
        )
    return data


def _verified_json(root: Path, relative_path: str, expected_sha256: str) -> dict[str, Any]:
    data = _verified_bytes(root, relative_path, expected_sha256)
    try:
        value = json.loads(data)
    except json.JSONDecodeError as exc:
        raise AuthorityError(f"invalid JSON in {relative_path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuthorityError(f"authoritative artifact {relative_path} is not an object")
    return value


def _match(pattern: str, text: str, description: str) -> re.Match[str]:
    match = re.search(pattern, text, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        raise AuthorityError(f"authority catalog is missing {description}")
    return match


def validate_active_authority(catalog_text: str) -> dict[str, Any]:
    schema = _match(r"^schema_version:\s*([^\n]+)$", catalog_text, "schema_version").group(1)
    active_lane = _match(r"^active_lane:\s*([^\n]+)$", catalog_text, "active_lane").group(1)
    domains = catalog_text.partition("authority_domains:\n")[2]
    source_block = _match(
        r"^  source_snapshot:\n(?P<body>.*?)(?=^  [a-z_]+:|\Z)",
        domains,
        "source_snapshot authority domain",
    ).group("body")
    eda_block = _match(
        r"^  aggregate_eda:\n(?P<body>.*?)(?=^  [a-z_]+:|\Z)",
        domains,
        "aggregate_eda authority domain",
    ).group("body")
    source_current = _match(r"^    current:\s*([^\n]+)$", source_block, "source current").group(1)
    source_sha = _match(
        r"^    source_sha256:\s*([0-9a-f]{64})$", source_block, "source SHA-256"
    ).group(1)
    eda_current = _match(r"^    current:\s*([^\n]+)$", eda_block, "EDA current").group(1)
    run_sha = _match(
        r"^    run_manifest_sha256:\s*([0-9a-f]{64})$",
        eda_block,
        "EDA run manifest SHA-256",
    ).group(1)
    historical = re.findall(r"^    -\s*([^\n]+)$", eda_block, flags=re.MULTILINE)
    expected = {
        "schema_version": "artifact_authority_catalog_v3",
        "active_lane": SOURCE_ID,
        "source_current": SOURCE_ID,
        "eda_current": V3_ID,
        "historical": ["bivariate_b02f3872_eda_v1", V2_ID],
        "source_sha256": PINNED_SHA256["source_archive"],
        "run_manifest_sha256": PINNED_SHA256["v3_run_manifest"],
    }
    actual = {
        "schema_version": schema,
        "active_lane": active_lane,
        "source_current": source_current,
        "eda_current": eda_current,
        "historical": historical,
        "source_sha256": source_sha,
        "run_manifest_sha256": run_sha,
    }
    if actual != expected:
        raise AuthorityError(f"active authority mismatch: expected {expected}, got {actual}")
    return actual


def _artifact_block(catalog_text: str, artifact_id: str) -> str:
    return _match(
        rf"^- id:\s*{re.escape(artifact_id)}\n(?P<body>.*?)(?=^- |\Z)",
        catalog_text,
        f"artifact {artifact_id}",
    ).group("body")


def _block_value(block: str, key: str) -> str:
    return _match(rf"^  {re.escape(key)}:\s*([^\n]+)$", block, key).group(1)


def _block_mapping(block: str, key: str) -> dict[str, str]:
    body = _match(
        rf"^  {re.escape(key)}:\n(?P<body>(?:    [^\n]+\n?)*)",
        block,
        key,
    ).group("body")
    result: dict[str, str] = {}
    for line in body.splitlines():
        name, separator, value = line.strip().partition(": ")
        if not separator:
            raise AuthorityError(f"invalid {key} entry: {line}")
        result[name] = value
    return result


def _parse_yaml_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        body = value[1:-1].strip()
        if "'" in body or '"' in body:
            raise AuthorityError(f"unsupported quoted YAML flow sequence: {value}")
        return [] if not body else [_parse_yaml_scalar(item) for item in body.split(",")]
    if value.startswith('"'):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise AuthorityError(f"invalid double-quoted YAML scalar: {value}") from exc
        if not isinstance(parsed, str):
            raise AuthorityError(f"quoted YAML scalar is not a string: {value}")
        return parsed
    if value.startswith("'"):
        if not value.endswith("'"):
            raise AuthorityError(f"invalid single-quoted YAML scalar: {value}")
        return value[1:-1].replace("''", "'")
    if " #" in value or re.match(r"^[+-]?0[xob]", value, flags=re.IGNORECASE):
        raise AuthorityError(f"unsupported YAML scalar syntax: {value}")
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "~"}:
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return float(value)
        except ValueError:
            return value


def _flat_yaml_sections(data: bytes, selected: set[str]) -> dict[str, dict[str, Any]]:
    text = data.decode("utf-8")
    result = {name: {} for name in selected}
    section: str | None = None
    for line in text.splitlines():
        if line and not line.startswith(" ") and line.endswith(":"):
            section = line[:-1]
            continue
        if section not in selected or not line.startswith("  ") or line.startswith("    "):
            continue
        key, separator, value = line.strip().partition(":")
        if separator and value.strip():
            result[section][key] = _parse_yaml_scalar(value)
    return result


def _without_array_fields(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if not isinstance(value, list)}


def _rolling_summaries(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        view: {
            name: _without_array_fields(record)
            for name, record in view_data["rolling_pearson"].items()
        }
        for view, view_data in summary["relationships"]["views"].items()
    }


def _rolling_arrays(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        view: {
            name: {
                "plotted_correlations": record["plotted_correlations"],
                "plotted_end_timestamps": record["plotted_end_timestamps"],
            }
            for name, record in view_data["rolling_pearson"].items()
        }
        for view, view_data in summary["relationships"]["views"].items()
    }


def _stationarity_metadata(segment: dict[str, Any]) -> dict[str, Any]:
    result = {key: segment[key] for key in ("start", "end", "hours", "status")}
    for channel in ("suhu", "rh"):
        result[channel] = {
            name: _without_array_fields(record)
            for name, record in segment[channel].items()
        }
    return result


def _stationarity_arrays(segment: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        key: segment[key] for key in ("start", "end", "hours", "status")
    }
    result["channels"] = {}
    for channel in ("suhu", "rh"):
        channel_data = segment[channel]
        result["channels"][channel] = {
            "autocorrelation": channel_data["autocorrelation"]["values"],
            "partial_autocorrelation": channel_data["partial_autocorrelation"]["values"],
            "spectrum": {
                "frequencies": channel_data["spectrum"]["frequencies"],
                "power": channel_data["spectrum"]["power"],
            },
            "stl": {
                "residual": channel_data["stl"]["residual"],
                "seasonal": channel_data["stl"]["seasonal"],
                "trend": channel_data["stl"]["trend"],
            },
        }
    return result


def _temporal_summaries(summary: dict[str, Any]) -> dict[str, Any]:
    temporal = summary["temporal"]
    views: dict[str, Any] = {}
    for view, view_data in temporal["views"].items():
        resolutions: dict[str, Any] = {}
        for resolution in ("hourly", "daily", "monthly"):
            bins = view_data[resolution]
            thresholds = bins[0]["eligible"] if bins else {}
            resolutions[resolution] = {
                "bin_count": len(bins),
                "bins_sha256": _sha256(canonical_json_bytes(bins)),
                "eligible_bin_counts": {
                    threshold: sum(bool(item["eligible"][threshold]) for item in bins)
                    for threshold in thresholds
                },
                "exact_pair_count_sum": sum(item["exact_pair_count"] for item in bins),
                "expected_slots_sum": sum(item["expected_slots"] for item in bins),
                "partial_bin_count": sum(bool(item["partial"]) for item in bins),
                "view_pair_count_sum": sum(item["view_pair_count"] for item in bins),
            }
        views[view] = {
            "dense_regimes": view_data["dense_regimes"],
            "drift_conclusions": view_data["drift_conclusions"],
            "eligible_hour_segments": view_data["eligible_hour_segments"],
            "resolutions": resolutions,
        }
    return {
        "cadence": temporal["cadence"],
        "calendar_semantics": temporal["calendar_semantics"],
        "views": views,
    }


def _artifact_catalog(catalog_text: str) -> dict[str, Any]:
    source = _artifact_block(catalog_text, SOURCE_ID)
    v2 = _artifact_block(catalog_text, V2_ID)
    v3 = _artifact_block(catalog_text, V3_ID)
    result = {
        "source": {
            "status": _block_value(source, "status"),
            "locators": _block_mapping(source, "locators"),
            "sha256": _block_mapping(source, "sha256"),
        },
        "v2": {
            "status": _block_value(v2, "status"),
            "locators": _block_mapping(v2, "locators"),
            "sha256": _block_mapping(v2, "sha256"),
        },
        "v3": {
            "status": _block_value(v3, "status"),
            "locators": _block_mapping(v3, "locators"),
            "sha256": _block_mapping(v3, "sha256"),
        },
    }
    if (result["source"]["status"], result["v2"]["status"], result["v3"]["status"]) != (
        "current",
        "historical",
        "current",
    ):
        raise AuthorityError("source/v2/v3 catalog statuses do not match the frozen contract")
    expected_catalog_hashes = {
        "source": {
            "raw_gitignored": PINNED_SHA256["source_archive"],
            "source_manifest": PINNED_SHA256["source_manifest"],
        },
        "v2": {
            "config": PINNED_SHA256["v2_config"],
            "run_manifest": PINNED_SHA256["v2_run_manifest"],
        },
        "v3": {
            "config": PINNED_SHA256["v3_config"],
            "run_manifest": PINNED_SHA256["v3_run_manifest"],
        },
    }
    for name, hashes in expected_catalog_hashes.items():
        published_hashes = result[name]["sha256"]
        if not isinstance(published_hashes, dict):
            raise AuthorityError(f"catalog SHA-256 section for {name} is not a mapping")
        for key, expected in hashes.items():
            actual = published_hashes.get(key)
            if actual != expected:
                raise AuthorityError(
                    f"catalog hash mismatch for {name}.{key}: expected {expected}, got {actual}"
                )
    return result


def _require_equal(description: str, actual: Any, expected: Any) -> None:
    if actual != expected:
        raise AuthorityError(f"{description}: expected {expected!r}, got {actual!r}")


def build_goldens(source_repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    catalog_bytes = _source_path(source_repo, CATALOG_PATH).read_bytes()
    catalog_text = catalog_bytes.decode("utf-8")
    authority = validate_active_authority(catalog_text)
    artifacts = _artifact_catalog(catalog_text)

    source_path = artifacts["source"]["locators"]["source_manifest"]
    source_manifest = _verified_json(
        source_repo, source_path, PINNED_SHA256["source_manifest"]
    )
    config_paths = {
        "v2": artifacts["v2"]["locators"]["config"],
        "v3": artifacts["v3"]["locators"]["config"],
    }
    config_bytes = {
        version: _verified_bytes(source_repo, path, PINNED_SHA256[f"{version}_config"])
        for version, path in config_paths.items()
    }
    run_paths = {
        "v2": artifacts["v2"]["locators"]["run_manifest"],
        "v3": artifacts["v3"]["locators"]["run_manifest"],
    }
    runs = {
        version: _verified_json(
            source_repo, path, PINNED_SHA256[f"{version}_run_manifest"]
        )
        for version, path in run_paths.items()
    }
    summary_paths = {
        "v2": artifacts["v2"]["locators"]["eda_summary"],
        "v3": artifacts["v3"]["locators"]["eda_summary"],
    }
    summaries: dict[str, dict[str, Any]] = {}
    for version, path in summary_paths.items():
        published = runs[version]["output_sha256"]["summary"]
        _require_equal(f"{version} published summary SHA-256", published, PINNED_SHA256[f"{version}_summary"])
        summaries[version] = _verified_json(source_repo, path, published)

    expected_parent_sha256 = {
        **runs["v2"]["output_sha256"],
        "config": PINNED_SHA256["v2_config"],
        "run_manifest": PINNED_SHA256["v2_run_manifest"],
    }
    _require_equal(
        "v3 run parent SHA-256 map",
        runs["v3"]["parent_sha256"],
        expected_parent_sha256,
    )

    config_sections = {
        "v2": _flat_yaml_sections(
            config_bytes["v2"],
            {
                "identity",
                "input",
                "views",
                "quality",
                "cadence",
                "coverage",
                "rolling",
                "lags",
                "bootstrap",
                "stationarity",
                "change_point",
            },
        ),
        "v3": _flat_yaml_sections(
            config_bytes["v3"],
            {"identity", "input", "quality", "cadence", "binning", "excerpt", "streaming"},
        ),
    }
    v2 = summaries["v2"]
    v3 = summaries["v3"]
    source_artifact = source_manifest["artifact"]
    v2_audit = v2["source"]["scan_audit"]
    v3_audit = v3["source_audit"]

    _require_equal("source archive SHA-256", source_artifact["sha256"], PINNED_SHA256["source_archive"])
    _require_equal("source row count", source_artifact["row_count"], EXPECTED_COUNTS["row_count"])
    _require_equal("source exact pairs", source_artifact["timestamps"]["intersection"], EXPECTED_COUNTS["exact_pair_count"])
    _require_equal("v2 exact pairs", v2_audit["exact_pair_count"], EXPECTED_COUNTS["exact_pair_count"])
    _require_equal("v2 screened pairs", v2_audit["rule_screened_pair_count"], EXPECTED_COUNTS["rule_screened_pair_count"])
    _require_equal("v3 row count", v3_audit["row_count"], EXPECTED_COUNTS["row_count"])
    _require_equal("v3 exact pairs", v3_audit["exact_pair_count"], EXPECTED_COUNTS["exact_pair_count"])
    _require_equal("v3 screened pairs", v3_audit["rule_screened_pair_count"], EXPECTED_COUNTS["rule_screened_pair_count"])
    _require_equal(
        "excluded pair count",
        v3_audit["exact_pair_count"] - v3_audit["rule_screened_pair_count"],
        EXPECTED_COUNTS["excluded_pair_count"],
    )
    for version in ("v2", "v3"):
        run = runs[version]
        config = config_sections[version]
        _require_equal(f"{version} release", run["release_id"], V2_ID if version == "v2" else V3_ID)
        _require_equal(f"{version} config release", config["identity"]["release_id"], run["release_id"])
        _require_equal(f"{version} seed", run["seed"], SEED)
        _require_equal(f"{version} config seed", config["identity"]["seed"], SEED)
        _require_equal(f"{version} source SHA-256", run["source_sha256"], PINNED_SHA256["source_archive"])
        _require_equal(f"{version} source manifest SHA-256", run["source_manifest_sha256"], PINNED_SHA256["source_manifest"])
        _require_equal(f"{version} config SHA-256", run["config_sha256"], PINNED_SHA256[f"{version}_config"])
    _require_equal("v3 parent release", v3["parent_binding"]["release_id"], V2_ID)
    _require_equal("v3 parent summary SHA-256", v3["parent_binding"]["summary_sha256"], PINNED_SHA256["v2_summary"])
    _require_equal(
        "v3 summary parent SHA-256 map",
        v3["parent_binding"]["configured_hashes"],
        expected_parent_sha256,
    )
    _require_equal("v3 conservation status", v3["count_conservation"]["status"], "pass")

    hashes = {
        "authority_catalog": _sha256(catalog_bytes),
        "source_archive": PINNED_SHA256["source_archive"],
        "source_manifest": PINNED_SHA256["source_manifest"],
        "v2_config": PINNED_SHA256["v2_config"],
        "v2_run_manifest": PINNED_SHA256["v2_run_manifest"],
        "v2_summary": PINNED_SHA256["v2_summary"],
        "v3_config": PINNED_SHA256["v3_config"],
        "v3_run_manifest": PINNED_SHA256["v3_run_manifest"],
        "v3_summary": PINNED_SHA256["v3_summary"],
    }
    paths = {
        "authority_catalog": CATALOG_PATH,
        "source_manifest": source_path,
        "v2_config": config_paths["v2"],
        "v2_run_manifest": run_paths["v2"],
        "v2_summary": summary_paths["v2"],
        "v3_config": config_paths["v3"],
        "v3_run_manifest": run_paths["v3"],
        "v3_summary": summary_paths["v3"],
    }
    releases = {
        version: {
            "config_sha256": run["config_sha256"],
            "implementation_commit": run["implementation_commit"],
            "output_sha256": run["output_sha256"],
            "release_id": run["release_id"],
            "run_manifest_sha256": hashes[f"{version}_run_manifest"],
            "schema_version": run["schema_version"],
            "seed": run["seed"],
            "source_manifest_sha256": run["source_manifest_sha256"],
            "source_sha256": run["source_sha256"],
            **({"parent_sha256": run["parent_sha256"]} if version == "v3" else {}),
        }
        for version, run in runs.items()
    }
    raw_static = v2["quality"]["resolver_headlines"]["median"]
    goldens = {
        "schema_version": "eda_authority_goldens_v1",
        "authority": {
            "active_lane": authority["active_lane"],
            "aggregate_eda_authority_id": authority["eda_current"],
            "artifact_paths": paths,
            "artifact_sha256": hashes,
            "catalog_schema_version": authority["schema_version"],
            "historical_aggregate_eda_ids": authority["historical"],
            "source_authority_id": authority["source_current"],
        },
        "schemas": {
            "golden_arrays": "eda_authority_golden_arrays_v1",
            "source_manifest": source_manifest["schema_version"],
            "v2_config": config_sections["v2"]["identity"]["schema_version"],
            "v2_run_manifest": runs["v2"]["schema_version"],
            "v2_summary": v2["schema_version"],
            "v3_config": config_sections["v3"]["identity"]["schema_version"],
            "v3_run_manifest": runs["v3"]["schema_version"],
            "v3_summary": v3["schema_version"],
        },
        "releases": releases,
        "source": {
            "channels": source_manifest["device"]["indices"],
            "conflicting_duplicate_pair_count": v2_audit["conflicting_duplicate_pair_count"],
            "cutoff_inclusive": source_artifact["bounds"]["cutoff"],
            "dataset_id": source_manifest["dataset_id"],
            "device_id": source_manifest["device"]["id"],
            "duplicate_group_count": v2_audit["duplicate_group_count"],
            "exact_pair_count": EXPECTED_COUNTS["exact_pair_count"],
            "excluded_pair_count": EXPECTED_COUNTS["excluded_pair_count"],
            "reason_counts": v2_audit["reason_counts"],
            "row_count": EXPECTED_COUNTS["row_count"],
            "rule_screened_pair_count": EXPECTED_COUNTS["rule_screened_pair_count"],
            "size_bytes": source_artifact["size_bytes"],
            "start": source_artifact["bounds"]["start"],
            "timezone": source_artifact["bounds"]["timezone"],
        },
        "settings": config_sections,
        "eligibility_settings": v2["method_context"],
        "scalar_counts": {
            "v2_quality_audit": v2["quality"]["audit"],
            "v3_instrumentation": v3["diagnostics"]["instrumentation"],
            "v3_interpretation_inputs": v3["interpretation_inputs"],
            "v3_source_audit": v3_audit,
        },
        "conservation": v3["count_conservation"],
        "associations": {
            "reason_ablations": v2["relationships"]["global_reason_ablations"],
            "rolling_pearson": _rolling_summaries(v2),
            "static": {
                "resolved_raw_pairs": {
                    key: raw_static[key] for key in ("pair_count", "pearson", "spearman")
                },
                "rule_screened_pairs": v2["relationships"]["global_reason_ablations"]["union_screened"]["all"],
            },
        },
        "temporal_summaries": _temporal_summaries(v2),
        "stationarity": {
            "method_notice": v2["stationarity"]["method_notice"],
            "primary": _stationarity_metadata(v2["stationarity"]["primary"]),
            "sensitivity": [
                _stationarity_metadata(segment)
                for segment in v2["stationarity"]["sensitivity"]
            ],
            "status": v2["stationarity"]["status"],
        },
        "change_points": v2["change_points"],
        "bootstrap_intervals": v2["uncertainty"],
        "quality_excerpt": {
            key: value
            for key, value in v3["diagnostics"]["quality_excerpt"].items()
            if key != "records"
        },
    }
    v3_univariate = v3["diagnostics"]["univariate"]["channels"]
    arrays = {
        "schema_version": "eda_authority_golden_arrays_v1",
        "v2": {
            "rolling_samples": _rolling_arrays(v2),
            "stationarity": {
                "primary": _stationarity_arrays(v2["stationarity"]["primary"]),
                "sensitivity": [
                    _stationarity_arrays(segment)
                    for segment in v2["stationarity"]["sensitivity"]
                ],
            },
        },
        "v3": {
            "joint_density": {
                "edges": v3["diagnostics"]["joint_density"]["edges"],
                "views": {
                    view: {"histogram": record["histogram"]}
                    for view, record in v3["diagnostics"]["joint_density"]["views"].items()
                },
            },
            "univariate": {
                "channels": {
                    channel: {
                        "edges": channel_data["edges"],
                        "views": {
                            view: {
                                key: record[key]
                                for key in ("histogram", "ecdf_count", "ecdf_fraction")
                            }
                            for view, record in channel_data["views"].items()
                        },
                    }
                    for channel, channel_data in v3_univariate.items()
                }
            },
            "quality_excerpt_records": v3["diagnostics"]["quality_excerpt"]["records"],
        },
    }
    validate_fixture_shapes(goldens, arrays)
    return goldens, arrays


def _nested(value: dict[str, Any], path: str) -> Any:
    current: Any = value
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            raise AuthorityError(f"fixture is missing required field {path}")
        current = current[key]
    return current


def _absolute_strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in _absolute_strings(child)]
    if isinstance(value, list):
        return [item for child in value for item in _absolute_strings(child)]
    if isinstance(value, str) and (value.startswith("/") or re.match(r"^[A-Za-z]:[\\/]", value)):
        return [value]
    return []


def validate_fixture_shapes(goldens: dict[str, Any], arrays: dict[str, Any]) -> None:
    required_goldens = (
        "authority.artifact_sha256.source_archive",
        "source.row_count",
        "source.exact_pair_count",
        "source.rule_screened_pair_count",
        "source.excluded_pair_count",
        "settings.v2.bootstrap",
        "settings.v3.binning",
        "eligibility_settings.stationarity",
        "conservation.equations",
        "associations.static.resolved_raw_pairs",
        "associations.rolling_pearson.rule_screened_pairs.window_30m_gap_30s",
        "temporal_summaries.views.rule_screened_pairs.resolutions.hourly.bins_sha256",
        "change_points.blocks",
        "bootstrap_intervals.blocks",
        "quality_excerpt.selection_kind",
        "releases.v3.parent_sha256.config",
        "releases.v3.parent_sha256.run_manifest",
        "releases.v3.parent_sha256.summary",
    )
    required_arrays = (
        "v3.joint_density.edges",
        "v3.joint_density.views.resolved_raw_pairs.histogram",
        "v3.univariate.channels.Suhu.views.rule_screened_pairs.ecdf_fraction",
        "v3.quality_excerpt_records",
        "v2.rolling_samples.rule_screened_pairs.window_30m_gap_30s.plotted_correlations",
        "v2.stationarity.primary.channels.suhu.autocorrelation",
        "v2.stationarity.primary.channels.rh.partial_autocorrelation",
        "v2.stationarity.primary.channels.suhu.spectrum.power",
        "v2.stationarity.primary.channels.rh.stl.trend",
    )
    for path in required_goldens:
        _nested(goldens, path)
    for path in required_arrays:
        _nested(arrays, path)
    rolling_variants = {
        "window_15m_gap_30s",
        "window_30m_gap_15s",
        "window_30m_gap_30s",
        "window_30m_gap_60s",
        "window_60m_gap_30s",
        "window_180m_gap_30s",
    }
    rolling = _nested(arrays, "v2.rolling_samples")
    if set(rolling) != {"resolved_raw_pairs", "rule_screened_pairs"}:
        raise AuthorityError("fixture rolling samples must contain both canonical views")
    for view, records in rolling.items():
        if set(records) != rolling_variants:
            raise AuthorityError(f"fixture rolling variants are incomplete for {view}")
        for name, record in records.items():
            if set(record) != {"plotted_correlations", "plotted_end_timestamps"}:
                raise AuthorityError(f"fixture rolling sample fields are incomplete for {view}.{name}")
    stationarity = _nested(arrays, "v2.stationarity")
    segments = [stationarity["primary"], *stationarity["sensitivity"]]
    if len(stationarity["sensitivity"]) != 3:
        raise AuthorityError("fixture stationarity must contain three sensitivity segments")
    for segment in segments:
        if set(segment["channels"]) != {"suhu", "rh"}:
            raise AuthorityError("fixture stationarity segment must contain both channels")
        for channel, record in segment["channels"].items():
            if set(record) != {
                "autocorrelation",
                "partial_autocorrelation",
                "spectrum",
                "stl",
            }:
                raise AuthorityError(f"fixture stationarity arrays are incomplete for {channel}")
    change_blocks = _nested(goldens, "change_points.blocks")
    if len(change_blocks) != 4:
        raise AuthorityError("fixture must contain all four change-point blocks")
    complete_change_block = change_blocks[2]
    for field in ("penalty_candidates", "stable_candidates", "confirmations"):
        if not complete_change_block[field]:
            raise AuthorityError(f"fixture change-point block is missing {field}")
    bootstrap_blocks = _nested(goldens, "bootstrap_intervals.blocks")
    if set(bootstrap_blocks) != {"7", "14", "28"}:
        raise AuthorityError("fixture bootstrap blocks must be exactly 7, 14, and 28 days")
    required_interval_fields = {
        "block_days",
        "estimate",
        "lower",
        "pair_count",
        "replicate_count",
        "run_count",
        "statistic",
        "status",
        "upper",
    }
    for block, intervals in bootstrap_blocks.items():
        if {interval["statistic"] for interval in intervals} != {"pearson", "spearman"}:
            raise AuthorityError(f"fixture bootstrap statistics are incomplete for block {block}")
        if any(set(interval) != required_interval_fields for interval in intervals):
            raise AuthorityError(f"fixture bootstrap interval fields are incomplete for block {block}")
    absolute = _absolute_strings(goldens) + _absolute_strings(arrays)
    if absolute:
        raise AuthorityError(f"fixtures contain absolute paths: {absolute}")


def fixture_bytes(source_repo: Path) -> dict[str, bytes]:
    goldens, arrays = build_goldens(source_repo.resolve())
    return {
        "goldens.json": canonical_json_bytes(goldens),
        "golden_arrays.json.gz": gzip_canonical_json(arrays),
    }


def _run(source_repo: Path, output_dir: Path, check: bool) -> int:
    generated = fixture_bytes(source_repo)
    if check:
        for name, expected in generated.items():
            path = output_dir / name
            try:
                actual = path.read_bytes()
            except OSError as exc:
                raise AuthorityError(f"cannot read fixture {path}: {exc}") from exc
            if actual != expected:
                raise AuthorityError(
                    f"fixture drift for {name}: expected {_sha256(expected)}, got {_sha256(actual)}"
                )
        print("authority fixtures are current")
        return 0
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in generated.items():
        path = output_dir / name
        path.write_bytes(data)
        print(f"wrote {path} sha256={_sha256(data)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze compact B02 EDA authority fixtures")
    parser.add_argument("--source-repo", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=FIXTURE_DIR)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        return _run(args.source_repo, args.output_dir, args.check)
    except (AuthorityError, OSError, UnicodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (KeyError, TypeError) as exc:
        print(f"error: authoritative source schema mismatch: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
