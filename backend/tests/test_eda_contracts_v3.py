from __future__ import annotations

# pyright: reportMissingImports=false

import json
from collections.abc import Callable

import pytest
from fastapi import FastAPI
from pydantic import TypeAdapter, ValidationError

from anomaly_backend.eda_contracts import (
    EDA_DEVICE_ID,
    EDA_ELIGIBILITY_REASONS,
    EDA_ELIGIBILITY_REASONS_BY_SECTION,
    EDA_MANDATORY_SECTIONS,
    EDA_OPTIONAL_STATISTICAL_SECTIONS,
    EDA_SECTION_NAMES,
    EDA_SOURCE_FROM,
    EDA_SOURCE_TO,
    EDA_TIME_ZONE,
    AuditMetadataSection,
    ChangePointsSection,
    EdaComputeRequest,
    EdaJobSummary,
    EdaPeriodListQuery,
    EdaPeriodListResponse,
    EdaRunSummary,
    EdaScope,
    EdaSection,
    EdaSectionMetadata,
    JointDensitySection,
    QualityExcerptSection,
    QualityOverviewSection,
    RelationshipsSection,
    StationaritySection,
    TemporalCoverageSection,
    TemporalDistributionSection,
    UncertaintySection,
    UnivariateSection,
)

HASH = "a" * 64
OTHER_HASH = "b" * 64
RUN_ID = "run-v3"
CREATED_AT = "2026-07-26T08:00:00Z"
SECTION_ADAPTER: TypeAdapter[EdaSection] = TypeAdapter(EdaSection)


def _scope(
    period_kind: str = "custom",
    from_ts: str = "2025-07-01T00:00:00",
    to_ts: str = "2025-07-02T00:00:00",
) -> dict[str, object]:
    return {
        "device_id": EDA_DEVICE_ID,
        "time_zone": EDA_TIME_ZONE,
        "period_kind": period_kind,
        "from": from_ts,
        "to": to_ts,
    }


def _metadata(
    section: str,
    *,
    status: str = "complete",
    reason_code: str | None = None,
    run_id: str = RUN_ID,
) -> dict[str, object]:
    return {
        "run_id": run_id,
        "section": section,
        "status": status,
        "reason_code": reason_code,
        "detail": "Bagian EDA tervalidasi untuk rentang aktif.",
        "active_view": "rule_screened_pairs",
        "units": {
            "temperature": "°C",
            "relative_humidity": "%",
            "time": "second",
        },
        "sample_counts": {
            "raw_rows": 4,
            "exact_pairs": 2,
            "screened_pairs": 2,
            "active_pairs": 2,
        },
        "algorithm_version": "b02-v3-live-1",
        "config_hash": HASH,
        "source_sha256": OTHER_HASH,
        "range_boundary": {
            "from_censored": False,
            "to_censored": False,
            "from_open_ended": False,
            "to_open_ended": False,
        },
        "payload_sha256": HASH if status == "complete" else None,
        "created_at": CREATED_AT,
    }


def _complete_payloads() -> dict[str, dict[str, object]]:
    view = {
        "histogram": [2],
        "ecdf_count": [2],
        "ecdf_fraction": [1.0],
    }
    def rolling(window: int, gap: int) -> dict[str, object]:
        return {
            "status": "complete",
            "reason_code": None,
            "window_seconds": window,
            "gap_boundary_seconds": gap,
            "eligible_window_count": 1,
            "total_endpoint_count": 300,
            "minimum": 0.2,
            "q05": 0.2,
            "q25": 0.2,
            "median": 0.2,
            "q75": 0.2,
            "q95": 0.2,
            "maximum": 0.2,
            "plotted_end_timestamps": [1],
            "plotted_correlations": [0.2],
        }

    rolling_variants = {
        "window_15m_gap_30s": rolling(900, 30),
        "window_30m_gap_15s": rolling(1800, 15),
        "window_30m_gap_30s": rolling(1800, 30),
        "window_30m_gap_60s": rolling(1800, 60),
        "window_60m_gap_30s": rolling(3600, 30),
        "window_180m_gap_30s": rolling(10800, 30),
    }
    constant_sequence = {
        "status": "constant",
        "method": "acf_fft",
        "values": [],
        "maximum_lag": 72,
        "error": None,
    }
    stationarity_channel = {
        "autocorrelation": constant_sequence,
        "partial_autocorrelation": {**constant_sequence, "method": "pacf_ywm"},
        "spectrum": {
            "status": "constant",
            "frequencies": [],
            "power": [],
            "error": None,
        },
        "stl": {
            "status": "constant",
            "seasonal": [],
            "trend": [],
            "residual": [],
            "error": None,
        },
    }
    def bootstrap_block(block_days: int) -> dict[str, object]:
        return {
            "status": "complete",
            "reason_code": None,
            "intervals": [
                {
                    "statistic": statistic,
                    "block_days": block_days,
                    "status": "ok",
                    "pair_count": 90,
                    "run_count": 1,
                    "replicate_count": 2000,
                    "estimate": 0.2,
                    "lower": 0.1,
                    "upper": 0.3,
                }
                for statistic in ("pearson", "spearman")
            ],
        }

    return {
        "quality_overview": {
            "source_audit": {"row_count": 4},
            "count_conservation": {"status": "pass"},
            "quality_metrics": {"excluded_pairs": 0},
        },
        "joint_density": {
            "edges": {
                "temperature_c": [0.0, 60.0],
                "relative_humidity_pct": [0.0, 100.0],
            },
            "views": {
                "resolved_raw_pairs": {"histogram": [[2]]},
                "rule_screened_pairs": {"histogram": [[2]]},
            },
        },
        "univariate": {
            "channels": {
                "Suhu": {
                    "unit": "°C",
                    "edges": [0.0, 60.0],
                    "views": {
                        "resolved_raw_pairs": view,
                        "rule_screened_pairs": view,
                    },
                },
                "RH": {
                    "unit": "%",
                    "edges": [0.0, 100.0],
                    "views": {
                        "resolved_raw_pairs": view,
                        "rule_screened_pairs": view,
                    },
                },
            }
        },
        "quality_excerpt": {
            "selection_kind": "dense_fallback",
            "from": "2025-07-01T00:00:00",
            "to": "2025-07-01T00:00:06",
            "records": [{"timestamp": "2025-07-01T00:00:00", "temperature_c": 25.0}],
        },
        "temporal_coverage": {
            "calendar_semantics": {"time_zone": EDA_TIME_ZONE},
            "views": {"resolved_raw_pairs": {"bins": []}},
        },
        "temporal_distribution": {
            "cadence": {"expected_seconds": 6},
            "views": {"rule_screened_pairs": {"hourly": []}},
        },
        "relationships": {
            "static": {
                "resolved_raw_pairs": {
                    "status": "ok",
                    "pair_count": 30,
                    "pearson": 0.2,
                    "spearman": 0.3,
                },
                "rule_screened_pairs": {
                    "status": "ok",
                    "pair_count": 30,
                    "pearson": 0.2,
                    "spearman": 0.3,
                },
            },
            "rolling_pearson": {
                "resolved_raw_pairs": rolling_variants,
                "rule_screened_pairs": rolling_variants,
            },
        },
        "stationarity": {
            "eligibility_tier": "sensitivity",
            "primary": None,
            "sensitivity": [
                {
                    "status": "ok",
                    "start": "2025-07-01T00:00:00+07:00",
                    "end": "2025-07-15T00:00:00+07:00",
                    "hours": 336,
                    "channels": {
                        "suhu": stationarity_channel,
                        "rh": stationarity_channel,
                    },
                }
            ],
        },
        "change_points": {
            "blocks": [
                {
                    "status": "constant",
                    "pair_count": 90,
                    "start_day": 1,
                    "end_day": 90,
                    "scale_median": [25.0, 60.0],
                    "scale_mad": [0.0, 0.0],
                    "constant_channels": [0, 1],
                    "stable_changes": [],
                    "confirmations": [],
                }
            ],
        },
        "uncertainty": {
            "method": "paired_moving_block_bootstrap",
            "confidence_level": 0.95,
            "seed": 20260724,
            "replicates": 2000,
            "blocks": {
                "7": bootstrap_block(7),
                "14": bootstrap_block(14),
                "28": bootstrap_block(28),
            },
            "sensitivity_status": "robust",
        },
        "audit_metadata": {
            "dataset_id": "bivariate_b02f3872_v1",
            "source_manifest_sha256": HASH,
            "release_id": "bivariate_b02f3872_eda_v3",
            "seed": 20260724,
            "dependencies": {"numpy": "2.4.6"},
        },
    }


def _complete_section(section: str) -> object:
    return SECTION_ADAPTER.validate_python(
        {**_metadata(section), "payload": _complete_payloads()[section]}, strict=True
    )


def _diagnostic_section(section: str, reason: str, status: str = "not_eligible") -> object:
    return SECTION_ADAPTER.validate_python(
        {
            **_metadata(section, status=status, reason_code=reason),
            "payload": None,
        },
        strict=True,
    )


def _expect_validation_error(call: Callable[[], object]) -> None:
    with pytest.raises(ValidationError):
        call()


def test_section_taxonomy_matches_migration_and_failure_policy() -> None:
    assert EDA_SECTION_NAMES == (
        "quality_overview",
        "joint_density",
        "univariate",
        "quality_excerpt",
        "temporal_coverage",
        "temporal_distribution",
        "relationships",
        "stationarity",
        "change_points",
        "uncertainty",
        "audit_metadata",
    )
    assert EDA_MANDATORY_SECTIONS | EDA_OPTIONAL_STATISTICAL_SECTIONS == set(
        EDA_SECTION_NAMES
    )
    assert not EDA_MANDATORY_SECTIONS & EDA_OPTIONAL_STATISTICAL_SECTIONS


def test_all_eleven_section_schemas_accept_complete_and_diagnostic_states() -> None:
    expected_types = {
        "quality_overview": QualityOverviewSection,
        "joint_density": JointDensitySection,
        "univariate": UnivariateSection,
        "quality_excerpt": QualityExcerptSection,
        "temporal_coverage": TemporalCoverageSection,
        "temporal_distribution": TemporalDistributionSection,
        "relationships": RelationshipsSection,
        "stationarity": StationaritySection,
        "change_points": ChangePointsSection,
        "uncertainty": UncertaintySection,
        "audit_metadata": AuditMetadataSection,
    }

    for section in EDA_SECTION_NAMES:
        complete = _complete_section(section)
        reason = next(iter(EDA_ELIGIBILITY_REASONS_BY_SECTION[section]))
        diagnostic = _diagnostic_section(section, reason)
        assert isinstance(complete, expected_types[section])
        assert isinstance(diagnostic, expected_types[section])
        assert getattr(diagnostic, "payload") is None


def test_every_eligibility_reason_has_a_validated_section_combination() -> None:
    observed: set[str] = set()
    for section, reasons in EDA_ELIGIBILITY_REASONS_BY_SECTION.items():
        for reason in reasons:
            result = _diagnostic_section(section, reason)
            assert getattr(result, "reason_code") == reason
            observed.add(reason)

    assert observed == EDA_ELIGIBILITY_REASONS
    assert {
        "insufficient_nonconstant_pairs",
        "insufficient_rolling_windows",
        "insufficient_daily_medians",
        "insufficient_stationarity_sensitivity_tier",
        "insufficient_stationarity_primary_tier",
        "no_exact_pairs",
        "no_selectable_excerpt",
    } <= observed


def test_status_reason_and_payload_combinations_fail_closed() -> None:
    _diagnostic_section("relationships", "section_compute_failed", status="failed")
    _diagnostic_section("relationships", "dependency_unavailable", status="failed")
    _diagnostic_section("relationships", "resource_limit_exceeded", status="failed")

    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {
                **_metadata(
                    "relationships",
                    status="not_eligible",
                    reason_code="insufficient_nonconstant_pairs",
                ),
                "payload": _complete_payloads()["relationships"],
            },
            strict=True,
        )
    )
    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {
                **_metadata("relationships"),
                "reason_code": "insufficient_nonconstant_pairs",
                "payload": _complete_payloads()["relationships"],
            },
            strict=True,
        )
    )
    _expect_validation_error(
        lambda: _diagnostic_section(
            "change_points", "insufficient_nonconstant_pairs"
        )
    )
    for section in EDA_MANDATORY_SECTIONS:
        _expect_validation_error(
            lambda name=section: _diagnostic_section(
                name, "section_compute_failed", status="failed"
            )
        )


def test_exported_section_metadata_rejects_unknown_sections_and_active_count_drift() -> None:
    for status, reason in (("complete", None), ("not_eligible", "no_exact_pairs")):
        _expect_validation_error(
            lambda state=status, code=reason: EdaSectionMetadata.model_validate(
                _metadata("unknown", status=state, reason_code=code), strict=True
            )
        )

    payload = _metadata("relationships")
    payload["sample_counts"] = {
        "raw_rows": 4,
        "exact_pairs": 2,
        "screened_pairs": 2,
        "active_pairs": 1,
    }
    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {**payload, "payload": _complete_payloads()["relationships"]},
            strict=True,
        )
    )

    impossible_counts = _metadata("relationships")
    impossible_counts["sample_counts"] = {
        "raw_rows": 1,
        "exact_pairs": 1,
        "screened_pairs": 1,
        "active_pairs": 1,
    }
    _expect_validation_error(
        lambda: EdaSectionMetadata.model_validate(impossible_counts, strict=True)
    )


def test_strict_extra_fields_and_legacy_analytic_keys_are_rejected_recursively() -> None:
    _expect_validation_error(
        lambda: EdaScope.model_validate(
            {**_scope(), "unexpected": True}, strict=True
        )
    )
    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {
                **_metadata("quality_overview"),
                "payload": {
                    **_complete_payloads()["quality_overview"],
                    "unexpected": {},
                },
            },
            strict=True,
        )
    )

    for forbidden in (
        "model_version",
        "score_provenance",
        "score",
        "threshold",
        "is_anomaly",
        "candidate_outlier",
        "s\u200bcore",
        "mo\u200bdel",
        "cand\u200bidate",
        "thresh\u200bold",
        "isAnomaly",
    ):
        payload = _complete_payloads()["quality_overview"]
        payload["quality_metrics"] = {"nested": {forbidden: 1}}
        _expect_validation_error(
            lambda value=payload: SECTION_ADAPTER.validate_python(
                {
                    **_metadata("quality_overview"),
                    "payload": value,
                },
                strict=True,
            )
        )


def test_audit_dependencies_reject_legacy_fields_but_allow_package_identity() -> None:
    payload = _complete_payloads()["audit_metadata"]
    payload["dependencies"] = {"statsmodels": "0.14.6"}
    SECTION_ADAPTER.validate_python(
        {**_metadata("audit_metadata"), "payload": payload}, strict=True
    )

    for forbidden in ("score", "model_version", "candidate", "threshold"):
        invalid = _complete_payloads()["audit_metadata"]
        invalid["dependencies"] = {forbidden: "1"}
        _expect_validation_error(
            lambda value=invalid: SECTION_ADAPTER.validate_python(
                {**_metadata("audit_metadata"), "payload": value}, strict=True
            )
        )


def test_analytic_payload_resource_and_shape_invariants_fail_closed() -> None:
    oversized = _complete_payloads()["quality_overview"]
    oversized["quality_metrics"] = {"detail": "x" * 4_097}
    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {**_metadata("quality_overview"), "payload": oversized}, strict=True
        )
    )

    density = _complete_payloads()["joint_density"]
    density["views"] = {
        "resolved_raw_pairs": {"histogram": [[1, 2]]},
        "rule_screened_pairs": {"histogram": [[1]]},
    }
    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {**_metadata("joint_density"), "payload": density}, strict=True
        )
    )

    empty_density = _complete_payloads()["joint_density"]
    empty_density["views"] = {
        "resolved_raw_pairs": {"histogram": [[0]]},
        "rule_screened_pairs": {"histogram": [[0]]},
    }
    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {**_metadata("joint_density"), "payload": empty_density}, strict=True
        )
    )

    univariate = _complete_payloads()["univariate"]
    channels = univariate["channels"]
    assert isinstance(channels, dict)
    suhu = channels["Suhu"]
    assert isinstance(suhu, dict)
    views = suhu["views"]
    assert isinstance(views, dict)
    raw_view = views["resolved_raw_pairs"]
    assert isinstance(raw_view, dict)
    raw_view["ecdf_fraction"] = [1.0, 0.5]
    raw_view["ecdf_count"] = [1, 2]
    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {**_metadata("univariate"), "payload": univariate}, strict=True
        )
    )

    incomplete_ecdf = _complete_payloads()["univariate"]
    channels = incomplete_ecdf["channels"]
    assert isinstance(channels, dict)
    suhu = channels["Suhu"]
    assert isinstance(suhu, dict)
    views = suhu["views"]
    assert isinstance(views, dict)
    screened_view = views["rule_screened_pairs"]
    assert isinstance(screened_view, dict)
    screened_view["ecdf_count"] = [1]
    screened_view["ecdf_fraction"] = [0.5]
    _expect_validation_error(
        lambda: SECTION_ADAPTER.validate_python(
            {**_metadata("univariate"), "payload": incomplete_ecdf}, strict=True
        )
    )


@pytest.mark.parametrize(
    ("period_kind", "from_ts", "to_ts"),
    (
        ("daily", "2025-06-23T00:00:00", "2025-06-24T00:00:00"),
        ("weekly", "2025-06-23T00:00:00", "2025-06-30T00:00:00"),
        ("monthly", "2025-07-01T00:00:00", "2025-08-01T00:00:00"),
        ("custom", "2025-06-23T00:00:01", "2025-06-23T00:00:02"),
        ("full_range", EDA_SOURCE_FROM, EDA_SOURCE_TO),
    ),
)
def test_period_kinds_accept_exact_half_open_jakarta_ranges(
    period_kind: str, from_ts: str, to_ts: str
) -> None:
    scope = EdaScope.model_validate(
        _scope(period_kind, from_ts, to_ts), strict=True
    )
    assert scope.period_kind == period_kind
    assert scope.from_ts == from_ts
    assert scope.to_ts == to_ts


@pytest.mark.parametrize(
    "payload",
    (
        _scope(from_ts="2025-07-02T00:00:00", to_ts="2025-07-01T00:00:00"),
        _scope(from_ts="2025-06-22T23:59:59"),
        _scope(to_ts="2026-07-24T09:02:06"),
        _scope(from_ts="2025-07-01T00:00:00+07:00"),
        _scope(from_ts="2025-07-01T00:00:00.000"),
        _scope("daily", "2025-07-01T00:00:01", "2025-07-02T00:00:01"),
        _scope("weekly", "2025-07-01T00:00:00", "2025-07-08T00:00:00"),
        _scope("monthly", "2025-07-02T00:00:00", "2025-08-02T00:00:00"),
        _scope("full_range", "2025-06-23T00:00:01", EDA_SOURCE_TO),
        {**_scope(), "device_id": "unknown-device"},
        {**_scope(), "time_zone": "UTC"},
    ),
)
def test_scope_rejects_invalid_identity_time_or_range(payload: dict[str, object]) -> None:
    _expect_validation_error(lambda: EdaScope.model_validate(payload, strict=True))


def test_compute_request_is_custom_only_and_period_cursor_is_bounded() -> None:
    request = EdaComputeRequest.model_validate(_scope(), strict=True)
    assert request.period_kind == "custom"
    _expect_validation_error(
        lambda: EdaComputeRequest.model_validate(
            _scope("daily", "2025-07-01T00:00:00", "2025-07-02T00:00:00"),
            strict=True,
        )
    )

    query = EdaPeriodListQuery.model_validate(
        {"period_kind": "monthly", "limit": 25, "cursor": "eda-periods:25"},
        strict=True,
    )
    assert query.cursor == "eda-periods:25"
    response = EdaPeriodListResponse(
        request_id="request-1",
        period_kind="monthly",
        items=[],
        next_cursor=None,
        returned_count=0,
    )
    assert response.returned_count == 0
    _expect_validation_error(
        lambda: EdaPeriodListQuery.model_validate(
            {"period_kind": "custom", "cursor": "telemetry:1"}, strict=True
        )
    )


def _run_section_metadata(run_id: str) -> list[dict[str, object]]:
    return [
        _metadata(section, run_id=run_id)
        for section in EDA_SECTION_NAMES
    ]


def test_canonical_release_requires_full_range_and_exact_provenance_label() -> None:
    canonical = EdaRunSummary.model_validate(
        {
            "run_id": RUN_ID,
            "logical_key": HASH,
            "scope": _scope("full_range", EDA_SOURCE_FROM, EDA_SOURCE_TO),
            "source_sha256": OTHER_HASH,
            "algorithm_version": "b02-v3-live-1",
            "config_hash": HASH,
            "provenance_label": "published v3 release",
            "canonical_release": True,
            "completed_at": CREATED_AT,
            "sections": _run_section_metadata(RUN_ID),
        },
        strict=True,
    )
    assert canonical.provenance_label == "published v3 release"

    base = canonical.model_dump()
    custom_scope = _scope()
    _expect_validation_error(
        lambda: EdaRunSummary.model_validate(
            {**base, "scope": custom_scope}, strict=True
        )
    )
    _expect_validation_error(
        lambda: EdaRunSummary.model_validate(
            {
                **base,
                "canonical_release": False,
                "provenance_label": "published v3 release",
            },
            strict=True,
        )
    )

    equivalent = EdaRunSummary.model_validate(
        {
            **base,
            "scope": custom_scope,
            "canonical_release": False,
            "provenance_label": "algorithm-equivalent range computation",
        },
        strict=True,
    )
    assert equivalent.provenance_label == "algorithm-equivalent range computation"

    mismatched_sections = _run_section_metadata(RUN_ID)
    mismatched_sections[0] = {
        **mismatched_sections[0],
        "source_sha256": HASH,
        "config_hash": OTHER_HASH,
        "algorithm_version": "different-algorithm",
    }
    _expect_validation_error(
        lambda: EdaRunSummary.model_validate(
            {
                **base,
                "canonical_release": False,
                "provenance_label": "algorithm-equivalent range computation",
                "sections": mismatched_sections,
            },
            strict=True,
        )
    )


def test_job_summary_validates_terminal_lifecycle() -> None:
    job = EdaJobSummary.model_validate(
        {
            "job_id": "job-v3",
            "logical_key": HASH,
            "scope": _scope(),
            "source_sha256": OTHER_HASH,
            "algorithm_version": "b02-v3-live-1",
            "config_hash": HASH,
            "status": "succeeded",
            "trigger_kind": "api",
            "attempt_count": 1,
            "max_attempts": 3,
            "terminal": True,
            "created_at": CREATED_AT,
            "started_at": "2026-07-26T08:00:01Z",
            "completed_at": "2026-07-26T08:00:02Z",
            "run_id": RUN_ID,
            "error_code": None,
            "error_detail": None,
        },
        strict=True,
    )
    assert job.run_id == RUN_ID
    _expect_validation_error(
        lambda: EdaJobSummary.model_validate(
            {**job.model_dump(), "terminal": False}, strict=True
        )
    )
    for changes in (
        {"run_id": ""},
        {"attempt_count": 0},
        {
            "started_at": "2026-07-26T08:00:03Z",
            "completed_at": "2026-07-26T08:00:02Z",
        },
    ):
        _expect_validation_error(
            lambda value=changes: EdaJobSummary.model_validate(
                {**job.model_dump(), **value}, strict=True
            )
        )

    _expect_validation_error(
        lambda: EdaJobSummary.model_validate(
            {
                **job.model_dump(),
                "status": "failed",
                "started_at": None,
                "run_id": None,
                "error_code": "compute_failed",
                "error_detail": "Komputasi gagal.",
            },
            strict=True,
        )
    )


def _property_names(value: object) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            names.update(str(name) for name in properties)
        for child in value.values():
            names.update(_property_names(child))
    elif isinstance(value, list):
        for child in value:
            names.update(_property_names(child))
    return names


def test_openapi_contains_all_sections_statuses_reasons_and_no_legacy_properties() -> None:
    app = FastAPI()

    @app.get("/section", response_model=EdaSection)
    def section() -> None:
        return None

    schema = app.openapi()
    rendered = json.dumps(schema, sort_keys=True)
    for section_name in EDA_SECTION_NAMES:
        assert section_name in rendered
    for status in ("complete", "not_eligible", "failed"):
        assert status in rendered
    for reason in EDA_ELIGIBILITY_REASONS:
        assert reason in rendered

    property_names = _property_names(schema)
    forbidden_parts = ("score", "model", "candidate")
    assert not {
        name
        for name in property_names
        if name == "is_anomaly"
        or name == "threshold"
        or any(part in name.casefold() for part in forbidden_parts)
    }
