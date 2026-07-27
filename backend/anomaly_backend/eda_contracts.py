from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Generic, Literal, TypeAlias, TypeVar, cast
from unicodedata import category

from pydantic import AfterValidator, Field, JsonValue, field_validator, model_validator

from anomaly_backend.contracts import HistoricalDateTime, OperationalInstant, StrictModel

EdaPeriodKind = Literal["daily", "weekly", "monthly", "custom", "full_range"]
EdaPrecomputedPeriodKind = Literal["daily", "weekly", "monthly"]
EdaTriggerKind = Literal["api", "backfill"]
EdaJobStatus = Literal["queued", "running", "succeeded", "failed"]
EdaPanelStatus = Literal["complete", "not_eligible", "failed"]
EdaActiveView = Literal["resolved_raw_pairs", "rule_screened_pairs"]
EdaSectionName = Literal[
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
]
EdaEligibilityReasonCode = Literal[
    "no_exact_pairs",
    "no_selectable_excerpt",
    "no_positive_deltas",
    "insufficient_representative_cadence",
    "no_exposed_calendar_bins",
    "insufficient_nonconstant_pairs",
    "insufficient_rolling_windows",
    "insufficient_stationarity_sensitivity_tier",
    "insufficient_stationarity_primary_tier",
    "insufficient_daily_medians",
    "insufficient_dense_daily_pairs",
    "block_longer_than_run",
    "source_identity_unavailable",
]
EdaFailureReasonCode = Literal[
    "section_compute_failed",
    "dependency_unavailable",
    "resource_limit_exceeded",
]
EdaReasonCode: TypeAlias = EdaEligibilityReasonCode | EdaFailureReasonCode
EdaProvenanceLabel = Literal[
    "published v3 release", "algorithm-equivalent range computation"
]

EDA_DEVICE_ID = "b02f3872-39a2-4b6f-a4ec-045a287fde4b"
EDA_TIME_ZONE = "Asia/Jakarta"
EDA_SOURCE_FROM = "2025-06-23T00:00:00"
EDA_SOURCE_TO = "2026-07-24T09:02:05"
EDA_DATASET_ID = "bivariate_b02f3872_v1"
EDA_SOURCE_SHA256 = (
    "b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f"
)
EDA_ALGORITHM_VERSION = (
    "bivariate_b02f3872_eda_v3+vendor.37565a5341be56e9a0a88d55ce1dbfe6ae25b0fe"
)
EDA_CONFIG_HASH = (
    "1081a79b8452075df4baf2f88f6ed3094f90286c0e17ee7d666e0b8072ba8452"
)


def precomputed_period_start(
    period_kind: EdaPrecomputedPeriodKind, value: datetime
) -> datetime:
    day = value.replace(hour=0, minute=0, second=0, microsecond=0)
    if period_kind == "daily":
        return day
    if period_kind == "weekly":
        return day - timedelta(days=day.weekday())
    return day.replace(day=1)


def precomputed_period_end(
    period_kind: EdaPrecomputedPeriodKind, start: datetime
) -> datetime:
    if period_kind == "daily":
        return start + timedelta(days=1)
    if period_kind == "weekly":
        return start + timedelta(days=7)
    return (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )


def enumerate_precomputed_periods(
    kind: str, from_ts: datetime, to_ts: datetime
) -> list[tuple[datetime, datetime, EdaPrecomputedPeriodKind]]:
    if kind not in ("daily", "weekly", "monthly", "all"):
        raise ValueError("invalid precomputed period kind")
    kinds: tuple[EdaPrecomputedPeriodKind, ...] = (
        ("daily", "weekly", "monthly")
        if kind == "all"
        else (kind,)
    )
    periods: list[tuple[datetime, datetime, EdaPrecomputedPeriodKind]] = []
    for period_kind in kinds:
        cursor = precomputed_period_start(period_kind, from_ts)
        while cursor < to_ts:
            end = precomputed_period_end(period_kind, cursor)
            periods.append((cursor, end, period_kind))
            cursor = end
    return periods


EDA_SECTION_NAMES: tuple[EdaSectionName, ...] = (
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
EDA_MANDATORY_SECTIONS: frozenset[EdaSectionName] = frozenset(
    {
        "quality_overview",
        "joint_density",
        "univariate",
        "quality_excerpt",
        "temporal_coverage",
        "temporal_distribution",
        "audit_metadata",
    }
)
EDA_OPTIONAL_STATISTICAL_SECTIONS: frozenset[EdaSectionName] = frozenset(
    {"relationships", "stationarity", "change_points", "uncertainty"}
)

EDA_ELIGIBILITY_REASONS: frozenset[EdaEligibilityReasonCode] = frozenset(
    {
        "no_exact_pairs",
        "no_selectable_excerpt",
        "no_positive_deltas",
        "insufficient_representative_cadence",
        "no_exposed_calendar_bins",
        "insufficient_nonconstant_pairs",
        "insufficient_rolling_windows",
        "insufficient_stationarity_sensitivity_tier",
        "insufficient_stationarity_primary_tier",
        "insufficient_daily_medians",
        "insufficient_dense_daily_pairs",
        "block_longer_than_run",
        "source_identity_unavailable",
    }
)
EDA_FAILURE_REASONS: frozenset[EdaFailureReasonCode] = frozenset(
    {"section_compute_failed", "dependency_unavailable", "resource_limit_exceeded"}
)
EDA_ELIGIBILITY_REASONS_BY_SECTION: dict[
    EdaSectionName, frozenset[EdaEligibilityReasonCode]
] = {
    "quality_overview": frozenset({"no_exact_pairs"}),
    "joint_density": frozenset({"no_exact_pairs"}),
    "univariate": frozenset({"no_exact_pairs"}),
    "quality_excerpt": frozenset({"no_exact_pairs", "no_selectable_excerpt"}),
    "temporal_coverage": frozenset(
        {"no_positive_deltas", "no_exposed_calendar_bins"}
    ),
    "temporal_distribution": frozenset(
        {"no_positive_deltas", "insufficient_representative_cadence"}
    ),
    "relationships": frozenset(
        {
            "no_exact_pairs",
            "insufficient_nonconstant_pairs",
            "insufficient_rolling_windows",
        }
    ),
    "stationarity": frozenset(
        {
            "insufficient_stationarity_sensitivity_tier",
            "insufficient_stationarity_primary_tier",
        }
    ),
    "change_points": frozenset({"insufficient_daily_medians"}),
    "uncertainty": frozenset(
        {"insufficient_dense_daily_pairs", "block_longer_than_run"}
    ),
    "audit_metadata": frozenset({"source_identity_unavailable"}),
}

NonEmptyString = Annotated[str, Field(min_length=1)]
NonNegativeInt = Annotated[int, Field(ge=0)]
Sha256Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
EdaPeriodCursor = Annotated[str, Field(pattern=r"^eda-periods:[0-9]+$")]
Fraction = Annotated[float, Field(ge=0, le=1)]

def _validate_payload_key(key: str, *, dependency: bool = False) -> None:
    if len(key) > 128 or any(category(character).startswith("C") for character in key):
        raise ValueError(f"invalid analytic payload field: {key!r}")
    canonical = "".join(character for character in key.casefold() if character.isalnum())
    forbidden = (
        "score" in canonical
        or "candidate" in canonical
        or "threshold" in canonical
        or canonical == "isanomaly"
        or (
            canonical.startswith("model")
            if dependency
            else "model" in canonical
        )
    )
    if forbidden:
        raise ValueError(f"forbidden analytic payload field: {key}")


def _validate_analytic_object_with_limit(
    value: dict[str, JsonValue], maximum_nodes: int
) -> dict[str, JsonValue]:
    node_count = 0

    def visit(item: JsonValue, depth: int = 0) -> None:
        nonlocal node_count
        node_count += 1
        if node_count > maximum_nodes:
            raise ValueError(
                f"analytic payloads must contain at most {maximum_nodes} values"
            )
        if depth > 20:
            raise ValueError("analytic payload nesting must not exceed 20 levels")
        if isinstance(item, dict):
            if len(item) > 500:
                raise ValueError("analytic payload mappings must contain at most 500 entries")
            for key, child in item.items():
                _validate_payload_key(key)
                visit(child, depth + 1)
        elif isinstance(item, list):
            if len(item) > 50_000:
                raise ValueError("analytic payload lists must contain at most 50000 entries")
            for child in item:
                visit(child, depth + 1)
        elif isinstance(item, str) and len(item) > 4_096:
            raise ValueError("analytic payload strings must contain at most 4096 characters")

    visit(value)
    return value


def _validate_analytic_object(value: dict[str, JsonValue]) -> dict[str, JsonValue]:
    return _validate_analytic_object_with_limit(value, 100_000)


def _validate_temporal_analytic_object(
    value: dict[str, JsonValue],
) -> dict[str, JsonValue]:
    return _validate_analytic_object_with_limit(value, 500_000)


EdaAnalyticObject = Annotated[
    dict[str, JsonValue], AfterValidator(_validate_analytic_object)
]
EdaTemporalAnalyticObject = Annotated[
    dict[str, JsonValue], AfterValidator(_validate_temporal_analytic_object)
]

_SectionNameT = TypeVar("_SectionNameT", bound=str)
_PayloadT = TypeVar("_PayloadT")


class EdaScope(StrictModel):
    device_id: Literal["b02f3872-39a2-4b6f-a4ec-045a287fde4b"]
    time_zone: Literal["Asia/Jakarta"]
    period_kind: EdaPeriodKind
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")

    @model_validator(mode="after")
    def validate_period(self) -> EdaScope:
        start = datetime.fromisoformat(self.from_ts)
        end = datetime.fromisoformat(self.to_ts)
        if start >= end:
            raise ValueError("from must be earlier than to")
        if self.from_ts < EDA_SOURCE_FROM or self.to_ts > EDA_SOURCE_TO:
            raise ValueError("range must be inside the canonical source bounds")

        at_midnight = start.hour == start.minute == start.second == 0
        if self.period_kind == "daily" and (
            not at_midnight
            or start != precomputed_period_start("daily", start)
            or end != precomputed_period_end("daily", start)
        ):
            raise ValueError("daily range must be Jakarta [00:00,next day 00:00)")
        if self.period_kind == "weekly" and (
            not at_midnight
            or start != precomputed_period_start("weekly", start)
            or end != precomputed_period_end("weekly", start)
        ):
            raise ValueError("weekly range must be Jakarta [Monday 00:00,next Monday)")
        if self.period_kind == "monthly":
            if (
                not at_midnight
                or start != precomputed_period_start("monthly", start)
                or end != precomputed_period_end("monthly", start)
            ):
                raise ValueError("monthly range must be Jakarta calendar-month aligned")
        if self.period_kind == "full_range" and (
            self.from_ts != EDA_SOURCE_FROM or self.to_ts != EDA_SOURCE_TO
        ):
            raise ValueError("full_range must equal the canonical half-open source range")
        return self


class EdaComputeRequest(EdaScope):
    @model_validator(mode="after")
    def validate_custom_period(self) -> EdaComputeRequest:
        if self.period_kind != "custom":
            raise ValueError("compute requests require period_kind=custom")
        return self


class EdaPeriodListQuery(StrictModel):
    period_kind: EdaPrecomputedPeriodKind
    limit: Annotated[int, Field(ge=1, le=100)] = 25
    cursor: EdaPeriodCursor | None = None


class EdaUnits(StrictModel):
    temperature: Literal["°C"] = "°C"
    relative_humidity: Literal["%"] = "%"
    time: Literal["second"] = "second"


class EdaSampleCounts(StrictModel):
    raw_rows: NonNegativeInt
    exact_pairs: NonNegativeInt
    screened_pairs: NonNegativeInt
    active_pairs: NonNegativeInt

    @model_validator(mode="after")
    def validate_counts(self) -> EdaSampleCounts:
        if self.raw_rows < 2 * self.exact_pairs:
            raise ValueError("raw_rows must contain both channels for every exact pair")
        if self.screened_pairs > self.exact_pairs:
            raise ValueError("screened_pairs must not exceed exact_pairs")
        return self


class EdaRangeBoundary(StrictModel):
    from_censored: bool = False
    to_censored: bool = False
    from_open_ended: bool = False
    to_open_ended: bool = False


class EdaSectionMetadata(StrictModel, Generic[_SectionNameT]):
    run_id: NonEmptyString
    section: _SectionNameT
    status: EdaPanelStatus
    reason_code: EdaReasonCode | None = None
    detail: NonEmptyString
    active_view: EdaActiveView
    units: EdaUnits
    sample_counts: EdaSampleCounts
    algorithm_version: NonEmptyString
    config_hash: Sha256Digest
    source_sha256: Sha256Digest
    range_boundary: EdaRangeBoundary
    payload_sha256: Sha256Digest | None = None
    created_at: OperationalInstant

    @model_validator(mode="after")
    def validate_status_reason(self) -> EdaSectionMetadata[_SectionNameT]:
        if self.section not in EDA_SECTION_NAMES:
            raise ValueError("unknown EDA section")
        section = cast(EdaSectionName, self.section)
        expected_active_pairs = (
            self.sample_counts.exact_pairs
            if self.active_view == "resolved_raw_pairs"
            else self.sample_counts.screened_pairs
        )
        if self.sample_counts.active_pairs != expected_active_pairs:
            raise ValueError("active_pairs must match the selected active_view")
        if self.status == "complete":
            if self.reason_code is not None or self.payload_sha256 is None:
                raise ValueError("complete sections require a payload hash and no reason")
            return self
        if self.payload_sha256 is not None or self.reason_code is None:
            raise ValueError("diagnostic sections require a reason and no payload hash")
        if self.status == "not_eligible":
            if self.reason_code not in EDA_ELIGIBILITY_REASONS_BY_SECTION[section]:
                raise ValueError("eligibility reason is invalid for this section")
        else:
            if section not in EDA_OPTIONAL_STATISTICAL_SECTIONS:
                raise ValueError("mandatory sections cannot publish failed status")
            if self.reason_code not in EDA_FAILURE_REASONS:
                raise ValueError("failed sections require a failure reason")
        return self


class QualityOverviewPayload(StrictModel):
    source_audit: EdaAnalyticObject
    count_conservation: EdaAnalyticObject
    quality_metrics: EdaAnalyticObject


class JointDensityEdges(StrictModel):
    temperature_c: list[float] = Field(min_length=2, max_length=1_000)
    relative_humidity_pct: list[float] = Field(min_length=2, max_length=1_000)

    @model_validator(mode="after")
    def validate_edges(self) -> JointDensityEdges:
        for values in (self.temperature_c, self.relative_humidity_pct):
            if any(left >= right for left, right in zip(values, values[1:])):
                raise ValueError("joint-density edges must be strictly increasing")
        return self


class JointDensityView(StrictModel):
    histogram: list[list[NonNegativeInt]] = Field(max_length=1_000)


class JointDensityPayload(StrictModel):
    edges: JointDensityEdges
    views: dict[EdaActiveView, JointDensityView] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_views(self) -> JointDensityPayload:
        if set(self.views) != {"resolved_raw_pairs", "rule_screened_pairs"}:
            raise ValueError("joint density must contain both canonical views")
        row_count = len(self.edges.temperature_c) - 1
        column_count = len(self.edges.relative_humidity_pct) - 1
        for view in self.views.values():
            if len(view.histogram) != row_count or any(
                len(row) != column_count for row in view.histogram
            ):
                raise ValueError("joint-density histogram dimensions must match edges")
        return self


class UnivariateView(StrictModel):
    histogram: list[NonNegativeInt] = Field(max_length=1_000)
    ecdf_count: list[NonNegativeInt] = Field(max_length=50_000)
    ecdf_fraction: list[Fraction] = Field(max_length=50_000)

    @model_validator(mode="after")
    def validate_ecdf(self) -> UnivariateView:
        if len(self.ecdf_count) != len(self.ecdf_fraction):
            raise ValueError("ECDF counts and fractions must have equal length")
        if any(left > right for left, right in zip(self.ecdf_count, self.ecdf_count[1:])):
            raise ValueError("ECDF counts must be monotone")
        if any(
            left > right
            for left, right in zip(self.ecdf_fraction, self.ecdf_fraction[1:])
        ):
            raise ValueError("ECDF fractions must be monotone")
        return self


class UnivariateChannel(StrictModel):
    unit: Literal["°C", "%"]
    edges: list[float] = Field(min_length=2, max_length=1_000)
    views: dict[EdaActiveView, UnivariateView] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_views(self) -> UnivariateChannel:
        if set(self.views) != {"resolved_raw_pairs", "rule_screened_pairs"}:
            raise ValueError("univariate channel must contain both canonical views")
        if any(left >= right for left, right in zip(self.edges, self.edges[1:])):
            raise ValueError("univariate edges must be strictly increasing")
        if any(len(view.histogram) != len(self.edges) - 1 for view in self.views.values()):
            raise ValueError("univariate histogram length must match edges")
        return self


class UnivariatePayload(StrictModel):
    channels: dict[Literal["Suhu", "RH"], UnivariateChannel] = Field(
        min_length=2, max_length=2
    )

    @model_validator(mode="after")
    def validate_channels(self) -> UnivariatePayload:
        if set(self.channels) != {"Suhu", "RH"}:
            raise ValueError("univariate payload must contain Suhu and RH")
        if self.channels["Suhu"].unit != "°C" or self.channels["RH"].unit != "%":
            raise ValueError("univariate channel units must match the canonical device")
        return self


class QualityExcerptPayload(StrictModel):
    selection_kind: NonEmptyString
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    records: list[EdaAnalyticObject] = Field(min_length=1, max_length=2_000)

    @model_validator(mode="after")
    def validate_range(self) -> QualityExcerptPayload:
        if self.from_ts > self.to_ts:
            raise ValueError("excerpt from must not be later than to")
        return self


class TemporalCoveragePayload(StrictModel):
    calendar_semantics: EdaAnalyticObject
    views: EdaTemporalAnalyticObject


class TemporalDistributionPayload(StrictModel):
    cadence: EdaAnalyticObject
    views: EdaTemporalAnalyticObject


CorrelationCoefficient = Annotated[float, Field(ge=-1, le=1)]


class RelationshipCorrelation(StrictModel):
    status: Literal["ok"]
    pair_count: Annotated[int, Field(ge=30)]
    pearson: CorrelationCoefficient
    spearman: CorrelationCoefficient


class RollingPearsonResult(StrictModel):
    status: Literal["complete", "not_eligible"]
    reason_code: Literal["insufficient_rolling_windows"] | None
    window_seconds: Literal[900, 1800, 3600, 10800]
    gap_boundary_seconds: Literal[15, 30, 60]
    eligible_window_count: NonNegativeInt
    total_endpoint_count: NonNegativeInt
    minimum: CorrelationCoefficient | None
    q05: CorrelationCoefficient | None
    q25: CorrelationCoefficient | None
    median: CorrelationCoefficient | None
    q75: CorrelationCoefficient | None
    q95: CorrelationCoefficient | None
    maximum: CorrelationCoefficient | None
    plotted_end_timestamps: list[int] = Field(max_length=2_000)
    plotted_correlations: list[CorrelationCoefficient] = Field(max_length=2_000)

    @model_validator(mode="after")
    def validate_result(self) -> RollingPearsonResult:
        summaries = (
            self.minimum,
            self.q05,
            self.q25,
            self.median,
            self.q75,
            self.q95,
            self.maximum,
        )
        if len(self.plotted_end_timestamps) != len(self.plotted_correlations):
            raise ValueError("rolling timestamps and correlations must align")
        if any(
            left >= right
            for left, right in zip(
                self.plotted_end_timestamps, self.plotted_end_timestamps[1:]
            )
        ):
            raise ValueError("rolling timestamps must be strictly increasing")
        if self.status == "complete":
            if (
                self.reason_code is not None
                or self.eligible_window_count == 0
                or any(value is None for value in summaries)
            ):
                raise ValueError("complete rolling results require finite summaries")
        elif (
            self.reason_code != "insufficient_rolling_windows"
            or self.eligible_window_count != 0
            or any(value is not None for value in summaries)
            or self.plotted_end_timestamps
            or self.plotted_correlations
        ):
            raise ValueError("ineligible rolling results must be empty")
        return self


class RelationshipsPayload(StrictModel):
    static: dict[EdaActiveView, RelationshipCorrelation] = Field(
        min_length=2, max_length=2
    )
    rolling_pearson: dict[EdaActiveView, dict[str, RollingPearsonResult]] = Field(
        min_length=2, max_length=2
    )

    @model_validator(mode="after")
    def validate_views_and_variants(self) -> RelationshipsPayload:
        views = {"resolved_raw_pairs", "rule_screened_pairs"}
        variants = {
            "window_15m_gap_30s",
            "window_30m_gap_15s",
            "window_30m_gap_30s",
            "window_30m_gap_60s",
            "window_60m_gap_30s",
            "window_180m_gap_30s",
        }
        if set(self.static) != views or set(self.rolling_pearson) != views:
            raise ValueError("relationships must contain both canonical views")
        if any(set(records) != variants for records in self.rolling_pearson.values()):
            raise ValueError("relationships must contain all canonical rolling variants")
        return self


class SequenceDiagnostic(StrictModel):
    status: Literal["ok", "short", "constant", "nonfinite", "error"]
    method: Literal["acf_fft", "pacf_ywm"]
    values: list[CorrelationCoefficient] = Field(max_length=73)
    maximum_lag: Annotated[int, Field(ge=0, le=72)]
    error: str | None = None

    @model_validator(mode="after")
    def validate_values(self) -> SequenceDiagnostic:
        if self.status == "ok" and len(self.values) != self.maximum_lag + 1:
            raise ValueError("successful correlation sequence must include lag zero")
        if self.status != "ok" and self.values:
            raise ValueError("unsuccessful correlation sequence must be empty")
        return self


class SpectrumDiagnostic(StrictModel):
    status: Literal["ok", "short", "constant", "nonfinite", "error"]
    frequencies: list[float] = Field(max_length=50_000)
    power: list[Annotated[float, Field(ge=0)]] = Field(max_length=50_000)
    error: str | None = None

    @model_validator(mode="after")
    def validate_arrays(self) -> SpectrumDiagnostic:
        if len(self.frequencies) != len(self.power):
            raise ValueError("spectrum frequency and power arrays must align")
        if self.status == "ok" and not self.frequencies:
            raise ValueError("successful spectrum must contain values")
        if self.status != "ok" and (self.frequencies or self.power):
            raise ValueError("unsuccessful spectrum must be empty")
        return self


class STLDiagnostic(StrictModel):
    status: Literal["ok", "short", "constant", "nonfinite", "error"]
    seasonal: list[float] = Field(max_length=50_000)
    trend: list[float] = Field(max_length=50_000)
    residual: list[float] = Field(max_length=50_000)
    error: str | None = None

    @model_validator(mode="after")
    def validate_arrays(self) -> STLDiagnostic:
        lengths = {len(self.seasonal), len(self.trend), len(self.residual)}
        if len(lengths) != 1:
            raise ValueError("STL arrays must align")
        if self.status == "ok" and not self.seasonal:
            raise ValueError("successful STL must contain values")
        if self.status != "ok" and self.seasonal:
            raise ValueError("unsuccessful STL must be empty")
        return self


class StationarityChannel(StrictModel):
    autocorrelation: SequenceDiagnostic
    partial_autocorrelation: SequenceDiagnostic
    spectrum: SpectrumDiagnostic
    stl: STLDiagnostic


class StationaritySegment(StrictModel):
    status: Literal["ok"]
    start: NonEmptyString
    end: NonEmptyString
    hours: Annotated[int, Field(ge=336)]
    channels: dict[Literal["suhu", "rh"], StationarityChannel] = Field(
        min_length=2, max_length=2
    )

    @model_validator(mode="after")
    def validate_segment(self) -> StationaritySegment:
        if set(self.channels) != {"suhu", "rh"}:
            raise ValueError("stationarity segment must contain both channels")
        for channel in self.channels.values():
            if channel.stl.status == "ok" and len(channel.stl.seasonal) != self.hours:
                raise ValueError("STL arrays must match segment hours")
        return self


class StationarityPayload(StrictModel):
    eligibility_tier: Literal["sensitivity", "primary"]
    primary: StationaritySegment | None
    sensitivity: list[StationaritySegment] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_tier(self) -> StationarityPayload:
        if self.eligibility_tier == "primary":
            if self.primary is None or self.primary.hours < 720:
                raise ValueError("primary eligibility tier requires 720 hourly medians")
        elif self.primary is not None:
            raise ValueError("sensitivity eligibility tier must not include primary results")
        return self


class StableChangePayload(StrictModel):
    representative_day: int
    representative_boundary_index: Annotated[int, Field(gt=0)]
    penalty_factors: list[Literal[1, 2, 4, 8]] = Field(min_length=3, max_length=4)
    observed_days: list[int] = Field(min_length=3, max_length=4)
    temperature_shift: float
    humidity_shift: float
    temperature_mad_effect: float | None
    humidity_mad_effect: float | None


class ChangeConfirmationPayload(StrictModel):
    minimum_segment_days: Literal[7, 14, 28]
    status: Literal["ok", "insufficient_data", "error"]
    requested_breakpoints: NonNegativeInt
    boundary_days: list[int] = Field(max_length=500)
    matched_stable_changes: NonNegativeInt
    error: str | None = None


class ChangePointBlockPayload(StrictModel):
    status: Literal["ok", "constant", "insufficient_data"]
    pair_count: NonNegativeInt
    start_day: int
    end_day: int
    scale_median: Annotated[list[float], Field(min_length=2, max_length=2)] | None
    scale_mad: Annotated[
        list[Annotated[float, Field(ge=0)]], Field(min_length=2, max_length=2)
    ] | None
    constant_channels: list[Literal[0, 1]] = Field(max_length=2)
    stable_changes: list[StableChangePayload] = Field(max_length=500)
    confirmations: list[ChangeConfirmationPayload] = Field(max_length=3)

    @model_validator(mode="after")
    def validate_block(self) -> ChangePointBlockPayload:
        if self.start_day > self.end_day:
            raise ValueError("change-point block range is invalid")
        if self.status == "insufficient_data" and self.pair_count >= 90:
            raise ValueError("ineligible change-point blocks must be shorter than 90 days")
        if self.status in {"ok", "constant"} and (
            self.pair_count < 90 or self.scale_median is None or self.scale_mad is None
        ):
            raise ValueError("eligible change-point blocks require robust scales")
        return self


class ChangePointsPayload(StrictModel):
    blocks: list[ChangePointBlockPayload] = Field(min_length=1, max_length=500)


class BootstrapIntervalPayload(StrictModel):
    statistic: Literal["pearson", "spearman"]
    block_days: Literal[7, 14, 28]
    status: Literal["ok", "insufficient_data", "constant"]
    pair_count: NonNegativeInt
    run_count: NonNegativeInt
    replicate_count: Literal[0, 2000]
    estimate: CorrelationCoefficient | None
    lower: CorrelationCoefficient | None
    upper: CorrelationCoefficient | None

    @model_validator(mode="after")
    def validate_interval(self) -> BootstrapIntervalPayload:
        estimates = (self.estimate, self.lower, self.upper)
        if self.status == "ok":
            if self.replicate_count != 2_000 or any(value is None for value in estimates):
                raise ValueError("complete bootstrap intervals require 2000 replicates")
        elif self.replicate_count != 0 or any(value is not None for value in estimates):
            raise ValueError("ineligible bootstrap intervals must not publish estimates")
        return self


class BootstrapBlockPayload(StrictModel):
    status: Literal["complete", "not_eligible"]
    reason_code: Literal["insufficient_dense_daily_pairs", "block_longer_than_run"] | None
    intervals: list[BootstrapIntervalPayload] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def validate_block(self) -> BootstrapBlockPayload:
        if {item.statistic for item in self.intervals} != {"pearson", "spearman"}:
            raise ValueError("bootstrap block must contain Pearson and Spearman intervals")
        if len({item.block_days for item in self.intervals}) != 1:
            raise ValueError("bootstrap intervals must use one block length")
        if self.status == "complete":
            if self.reason_code is not None or any(
                item.status != "ok" for item in self.intervals
            ):
                raise ValueError("complete bootstrap blocks require eligible intervals")
        elif self.reason_code is None or any(
            item.status == "ok" for item in self.intervals
        ):
            raise ValueError("ineligible bootstrap blocks require a reason")
        return self


class UncertaintyPayload(StrictModel):
    method: Literal["paired_moving_block_bootstrap"]
    confidence_level: Annotated[float, Field(ge=0.95, le=0.95)]
    seed: Literal[20260724]
    replicates: Literal[2000]
    blocks: dict[Literal["7", "14", "28"], BootstrapBlockPayload] = Field(
        min_length=3, max_length=3
    )
    sensitivity_status: Literal["robust", "not_robust", "insufficient_data"]

    @model_validator(mode="after")
    def validate_blocks(self) -> UncertaintyPayload:
        if set(self.blocks) != {"7", "14", "28"}:
            raise ValueError("bootstrap payload must contain 7, 14, and 28 day blocks")
        if any(
            interval.block_days != int(key)
            for key, block in self.blocks.items()
            for interval in block.intervals
        ):
            raise ValueError("bootstrap block keys must match interval lengths")
        if self.blocks["14"].status != "complete":
            raise ValueError("complete uncertainty payload requires the primary 14-day block")
        return self


class AuditMetadataPayload(StrictModel):
    dataset_id: Literal["bivariate_b02f3872_v1"]
    source_manifest_sha256: Sha256Digest
    release_id: Literal["bivariate_b02f3872_eda_v3"]
    seed: Literal[20260724]
    dependencies: dict[str, NonEmptyString] = Field(max_length=100)

    @field_validator("dependencies")
    @classmethod
    def validate_dependencies(
        cls, value: dict[str, str]
    ) -> dict[str, str]:
        for package, version in value.items():
            _validate_payload_key(package, dependency=True)
            if len(version) > 200:
                raise ValueError("dependency versions must contain at most 200 characters")
        return value


class _EdaSection(
    EdaSectionMetadata[_SectionNameT], Generic[_SectionNameT, _PayloadT]
):
    payload: _PayloadT | None

    @model_validator(mode="after")
    def validate_payload_state(self) -> _EdaSection[_SectionNameT, _PayloadT]:
        if self.status == "complete" and self.payload is None:
            raise ValueError("complete sections require analytic payload")
        if self.status != "complete" and self.payload is not None:
            raise ValueError("diagnostic sections must not include analytic payload")
        if isinstance(self.payload, JointDensityPayload):
            self._validate_joint_density_counts(self.payload)
        if isinstance(self.payload, UnivariatePayload):
            self._validate_univariate_counts(self.payload)
        return self

    def _expected_pairs(self, view: EdaActiveView) -> int:
        return (
            self.sample_counts.exact_pairs
            if view == "resolved_raw_pairs"
            else self.sample_counts.screened_pairs
        )

    def _validate_view_total(self, view: EdaActiveView, total: int) -> None:
        expected = self._expected_pairs(view)
        if total <= 0 or total > expected:
            raise ValueError("complete distribution counts must be within view sample counts")
        if view == "rule_screened_pairs" and total != expected:
            raise ValueError("screened distribution counts must equal screened_pairs")

    def _validate_joint_density_counts(self, payload: JointDensityPayload) -> None:
        for view_name, view in payload.views.items():
            self._validate_view_total(
                view_name,
                sum(count for row in view.histogram for count in row),
            )

    def _validate_univariate_counts(self, payload: UnivariatePayload) -> None:
        for channel in payload.channels.values():
            for view_name, view in channel.views.items():
                self._validate_view_total(view_name, sum(view.histogram))
                expected = self._expected_pairs(view_name)
                if not view.ecdf_count or view.ecdf_count[-1] > expected:
                    raise ValueError("ECDF terminal count must be within view sample counts")
                if view_name == "rule_screened_pairs" and view.ecdf_count[-1] != expected:
                    raise ValueError("screened ECDF terminal count must equal screened_pairs")
                if view.ecdf_fraction[-1] != 1.0:
                    raise ValueError("complete ECDF must terminate at fraction 1")


class QualityOverviewSection(
    _EdaSection[Literal["quality_overview"], QualityOverviewPayload]
):
    pass


class JointDensitySection(
    _EdaSection[Literal["joint_density"], JointDensityPayload]
):
    pass


class UnivariateSection(_EdaSection[Literal["univariate"], UnivariatePayload]):
    pass


class QualityExcerptSection(
    _EdaSection[Literal["quality_excerpt"], QualityExcerptPayload]
):
    pass


class TemporalCoverageSection(
    _EdaSection[Literal["temporal_coverage"], TemporalCoveragePayload]
):
    pass


class TemporalDistributionSection(
    _EdaSection[Literal["temporal_distribution"], TemporalDistributionPayload]
):
    pass


class RelationshipsSection(
    _EdaSection[Literal["relationships"], RelationshipsPayload]
):
    pass


class StationaritySection(
    _EdaSection[Literal["stationarity"], StationarityPayload]
):
    pass


class ChangePointsSection(
    _EdaSection[Literal["change_points"], ChangePointsPayload]
):
    pass


class UncertaintySection(
    _EdaSection[Literal["uncertainty"], UncertaintyPayload]
):
    pass


class AuditMetadataSection(
    _EdaSection[Literal["audit_metadata"], AuditMetadataPayload]
):
    pass


EdaSection: TypeAlias = Annotated[
    QualityOverviewSection
    | JointDensitySection
    | UnivariateSection
    | QualityExcerptSection
    | TemporalCoverageSection
    | TemporalDistributionSection
    | RelationshipsSection
    | StationaritySection
    | ChangePointsSection
    | UncertaintySection
    | AuditMetadataSection,
    Field(discriminator="section"),
]


class EdaJobSummary(StrictModel):
    job_id: NonEmptyString
    logical_key: Sha256Digest
    scope: EdaScope
    source_sha256: Sha256Digest
    algorithm_version: NonEmptyString
    config_hash: Sha256Digest
    status: EdaJobStatus
    trigger_kind: EdaTriggerKind
    attempt_count: NonNegativeInt
    max_attempts: Annotated[int, Field(gt=0)]
    terminal: bool
    created_at: OperationalInstant
    started_at: OperationalInstant | None
    completed_at: OperationalInstant | None
    run_id: NonEmptyString | None
    error_code: Annotated[str, Field(min_length=1, max_length=128)] | None
    error_detail: Annotated[str, Field(min_length=1, max_length=2_000)] | None

    @model_validator(mode="after")
    def validate_lifecycle(self) -> EdaJobSummary:
        if self.attempt_count > self.max_attempts:
            raise ValueError("attempt_count must not exceed max_attempts")
        if self.status != "queued" and self.attempt_count == 0:
            raise ValueError("started or terminal jobs require at least one attempt")
        if self.terminal != (self.status in {"succeeded", "failed"}):
            raise ValueError("terminal must match job status")
        created = datetime.fromisoformat(self.created_at.removesuffix("Z") + "+00:00")
        started = (
            datetime.fromisoformat(self.started_at.removesuffix("Z") + "+00:00")
            if self.started_at is not None
            else None
        )
        completed = (
            datetime.fromisoformat(self.completed_at.removesuffix("Z") + "+00:00")
            if self.completed_at is not None
            else None
        )
        if started is not None and started < created:
            raise ValueError("started_at must not precede created_at")
        if completed is not None and completed < (started or created):
            raise ValueError("completed_at must not precede job execution")
        if self.status == "queued" and any(
            value is not None
            for value in (self.started_at, self.completed_at, self.run_id)
        ):
            raise ValueError("queued jobs must not have execution or run timestamps")
        if self.status == "running" and (
            self.started_at is None
            or self.completed_at is not None
            or self.run_id is not None
        ):
            raise ValueError("running jobs require only started_at")
        if self.status == "succeeded" and (
            self.started_at is None
            or self.completed_at is None
            or self.run_id is None
            or self.error_code is not None
            or self.error_detail is not None
        ):
            raise ValueError("succeeded jobs require a run and no error")
        if self.status == "failed" and (
            self.started_at is None
            or self.completed_at is None
            or self.run_id is not None
            or not self.error_code
            or not self.error_detail
        ):
            raise ValueError("failed jobs require a terminal error and no run")
        if self.status in {"queued", "running"} and (
            self.error_code is not None or self.error_detail is not None
        ):
            raise ValueError("active jobs must not expose terminal errors")
        return self


class EdaRunSummary(StrictModel):
    run_id: NonEmptyString
    logical_key: Sha256Digest
    scope: EdaScope
    source_sha256: Sha256Digest
    algorithm_version: NonEmptyString
    config_hash: Sha256Digest
    provenance_label: EdaProvenanceLabel
    canonical_release: bool
    completed_at: OperationalInstant
    sections: list[EdaSectionMetadata[EdaSectionName]] = Field(
        min_length=11, max_length=11
    )

    @model_validator(mode="after")
    def validate_run(self) -> EdaRunSummary:
        expected_label: EdaProvenanceLabel = (
            "published v3 release"
            if self.canonical_release
            else "algorithm-equivalent range computation"
        )
        if self.provenance_label != expected_label:
            raise ValueError("provenance label must match canonical_release")
        if self.canonical_release and self.scope.period_kind != "full_range":
            raise ValueError("canonical_release requires full_range")
        names = [item.section for item in self.sections]
        if len(set(names)) != 11 or set(names) != set(EDA_SECTION_NAMES):
            raise ValueError("run must contain metadata for all eleven sections exactly once")
        if any(item.run_id != self.run_id for item in self.sections):
            raise ValueError("section metadata must belong to this run")
        if any(
            item.source_sha256 != self.source_sha256
            or item.config_hash != self.config_hash
            or item.algorithm_version != self.algorithm_version
            for item in self.sections
        ):
            raise ValueError("section identity must match the enclosing run")
        return self


class EdaPeriodListResponse(StrictModel):
    request_id: NonEmptyString
    period_kind: EdaPrecomputedPeriodKind
    items: list[EdaRunSummary] = Field(max_length=100)
    next_cursor: EdaPeriodCursor | None
    returned_count: NonNegativeInt

    @model_validator(mode="after")
    def validate_page(self) -> EdaPeriodListResponse:
        if self.returned_count != len(self.items):
            raise ValueError("returned_count must equal items length")
        if any(item.scope.period_kind != self.period_kind for item in self.items):
            raise ValueError("listed runs must match period_kind")
        return self


class EdaJobResponse(StrictModel):
    request_id: NonEmptyString
    job: EdaJobSummary


class EdaRunResponse(StrictModel):
    request_id: NonEmptyString
    run: EdaRunSummary


class EdaCacheHitResponse(StrictModel):
    request_id: NonEmptyString
    cache_hit: Literal[True]
    run: EdaRunSummary


class EdaQueuedComputeResponse(StrictModel):
    request_id: NonEmptyString
    cache_hit: Literal[False]
    job: EdaJobSummary


EdaComputeResponse: TypeAlias = Annotated[
    EdaCacheHitResponse | EdaQueuedComputeResponse,
    Field(discriminator="cache_hit"),
]
