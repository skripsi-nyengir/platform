from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Annotated, ClassVar, Literal, cast
from urllib.parse import urlsplit

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

SensorId = Literal["b02f3872-ruang-produksi"]
CorpusDeviceId = Literal["b02f3872-ruang-produksi", "b02f3872-simulasi-injeksi"]
Bucket = Literal["raw", "1m", "5m", "15m", "1h", "1d"]
Freshness = Literal["fresh", "stale", "unknown"]
Availability = Literal["online", "offline", "unknown"]
AlertStatus = Literal["detected", "acknowledged", "resolved"]
ScoreProvenance = Literal["simulated_preview", "artifact_backed"]
DetectionBasis = Literal["simulated_preview", "artifact_backed"]
InjectionFamily = Literal[
    "spike", "drift", "stuck", "erratic", "bias", "data_loss", "garbage"
]
InjectionSeverity = Literal["low", "medium", "high"]
LivenessState = Literal["alive", "not_alive", "unknown"]
ReadinessState = Literal["ready", "not_ready", "unknown"]
CursorScope = Literal["telemetry", "inference", "alert-events"]

_HISTORICAL_DATETIME = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}$")
_OPERATIONAL_INSTANT = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
_CURSOR_OFFSET = re.compile(r"^[0-9]+$")
_CURSOR_SCOPES = {"telemetry", "inference", "alert-events"}


def _validate_historical_datetime(value: str) -> str:
    if not _HISTORICAL_DATETIME.fullmatch(value):
        raise ValueError("historical timestamps must not contain a timezone offset")
    try:
        _ = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as error:
        raise ValueError("invalid historical timestamp") from error
    return value


HistoricalDateTime = Annotated[str, AfterValidator(_validate_historical_datetime)]
CorpusDateTime = HistoricalDateTime


def _validate_operational_instant(value: str) -> str:
    if not _OPERATIONAL_INSTANT.fullmatch(value):
        raise ValueError("operational timestamps must be UTC RFC3339 instants")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as error:
        raise ValueError("invalid operational timestamp") from error
    offset = parsed.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise ValueError("operational timestamps must be UTC")
    return value


OperationalInstant = Annotated[str, AfterValidator(_validate_operational_instant)]


def format_historical_datetime(value: datetime) -> HistoricalDateTime:
    rendered = value.replace(tzinfo=None, microsecond=0).isoformat(timespec="seconds")
    return cast(HistoricalDateTime, _validate_historical_datetime(rendered))


def current_historical_datetime() -> HistoricalDateTime:
    return format_historical_datetime(datetime.now())


def format_operational_instant(value: datetime) -> OperationalInstant:
    if value.tzinfo is None:
        raise ValueError("operational timestamp must be timezone-aware")
    rendered = (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )
    return cast(OperationalInstant, _validate_operational_instant(rendered))


def current_operational_instant() -> OperationalInstant:
    return format_operational_instant(datetime.now(timezone.utc))


def compare_historical_datetimes(left: HistoricalDateTime, right: HistoricalDateTime) -> int:
    return (left > right) - (left < right)


def is_finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def make_cursor(scope: str, offset: int) -> str:
    if scope not in _CURSOR_SCOPES or type(offset) is not int or offset < 0:
        raise ValueError("invalid cursor scope or offset")
    return f"{scope}:{offset}"


def parse_cursor(cursor: str, expected_scope: str) -> int:
    if expected_scope not in _CURSOR_SCOPES:
        raise ValueError("invalid cursor scope")
    scope, separator, offset = cursor.partition(":")
    if separator != ":" or scope != expected_scope or not _CURSOR_OFFSET.fullmatch(offset):
        raise ValueError("invalid cursor")
    return int(offset)


def _validate_url(value: str) -> str:
    if not urlsplit(value).scheme:
        raise ValueError("value must be an absolute URL")
    return value


ProblemType = Annotated[str, AfterValidator(_validate_url)]


def _is_none(value: object) -> bool:
    return value is None


class StrictModel(BaseModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset()
    model_config: ClassVar[ConfigDict] = ConfigDict(
        strict=True,
        extra="forbid",
        allow_inf_nan=False,
        validate_by_name=True,
        serialize_by_alias=True,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_explicit_null_for_optional_fields(
        cls, value: dict[str, object]
    ) -> dict[str, object]:
        for field in cls._optional_non_nullable_fields:
            if field in value and value[field] is None:
                raise ValueError(f"{field} may be omitted but not null")
        return value


class ProblemDetails(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"errors"})

    type: ProblemType
    title: str
    status: int
    detail: str
    instance: str
    request_id: str
    errors: dict[str, list[str]] | None = Field(default=None, exclude_if=_is_none)


class AlertCommandRequest(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"note"})

    command_id: str
    note: str | None = Field(default=None, exclude_if=_is_none)


class LatestTelemetrySensor(StrictModel):
    device_id: SensorId
    ts: HistoricalDateTime | None
    temperature_c: float | None
    relative_humidity_pct: float | None
    freshness: Freshness
    age_seconds: Annotated[float, Field(ge=0)] | None
    availability: Availability


class LatestTelemetryResponse(StrictModel):
    request_id: str
    generated_at: OperationalInstant
    time_zone: Literal["Asia/Jakarta"]
    sensors: list[LatestTelemetrySensor] = Field(max_length=1)


class TelemetryPoint(StrictModel):
    ts: HistoricalDateTime
    temperature_c: float | None
    relative_humidity_pct: float | None
    sample_count: Annotated[int, Field(ge=0)]
    gap_before: bool


class SimInjectionEvent(StrictModel):
    event_id: str
    family: InjectionFamily
    severity: InjectionSeverity
    channel: str
    channel_index: Annotated[int, Field(ge=0)]
    start_ts: HistoricalDateTime
    end_ts: HistoricalDateTime
    start_idx: Annotated[int, Field(ge=0)]
    end_idx_exclusive: Annotated[int, Field(ge=0)]
    segment_index: Annotated[int, Field(ge=0)]


class InjectionEventsResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    time_zone: Literal["Asia/Jakarta"]
    events: list[SimInjectionEvent]
    returned_count: Annotated[int, Field(ge=0)]


class SimModel(StrictModel):
    version: str
    model_key: str
    display_name: str
    score_key: str
    threshold: float
    manifest_sha256: str
    is_active: bool


class SimModelsResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    models: list[SimModel]


class SetSimActiveModelRequest(StrictModel):
    model_version: str = Field(min_length=1)


class SetSimActiveModelResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    active_model_version: str


class TelemetryHistoryQuery(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"cursor"})

    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    bucket: Bucket = "raw"
    limit: Annotated[int, Field(ge=1, le=5_000)] = 500
    cursor: str | None = Field(default=None, exclude_if=_is_none)

    @model_validator(mode="after")
    def validate_range(self) -> TelemetryHistoryQuery:
        if compare_historical_datetimes(self.from_ts, self.to_ts) >= 0:
            raise ValueError("from must be earlier than to")
        if self.bucket != "raw" and self.limit > 2_000:
            raise ValueError("bucketed limit must be at most 2000")
        return self


class TelemetryHistoryResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    bucket: Bucket
    time_zone: Literal["Asia/Jakarta"]
    points: list[TelemetryPoint] = Field(max_length=5_000)
    next_cursor: str | None
    returned_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_response(self) -> TelemetryHistoryResponse:
        if compare_historical_datetimes(self.from_ts, self.to_ts) >= 0:
            raise ValueError("from must be earlier than to")
        if self.bucket != "raw" and len(self.points) > 2_000:
            raise ValueError("bucketed responses contain at most 2000 points")
        if self.returned_count != len(self.points):
            raise ValueError("returned_count must equal points length")
        return self


class InferencePoint(StrictModel):
    window_start_ts: HistoricalDateTime
    window_end_ts: HistoricalDateTime
    score_ts: HistoricalDateTime
    score: float
    threshold: float
    is_anomaly: bool
    model_version: str
    score_provenance: ScoreProvenance

    @model_validator(mode="after")
    def validate_window(self) -> InferencePoint:
        if compare_historical_datetimes(self.window_start_ts, self.window_end_ts) >= 0:
            raise ValueError("window_start_ts must be earlier than window_end_ts")
        if compare_historical_datetimes(self.window_end_ts, self.score_ts) > 0:
            raise ValueError("score_ts must not be earlier than window_end_ts")
        return self


class InferenceQuery(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"cursor", "model_version"}
    )

    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    bucket: Bucket = "raw"
    limit: Annotated[int, Field(ge=1, le=5_000)] = 500
    cursor: str | None = Field(default=None, exclude_if=_is_none)
    model_version: str | None = Field(default=None, exclude_if=_is_none)

    @model_validator(mode="after")
    def validate_range(self) -> InferenceQuery:
        if compare_historical_datetimes(self.from_ts, self.to_ts) >= 0:
            raise ValueError("from must be earlier than to")
        if self.bucket != "raw" and self.limit > 2_000:
            raise ValueError("bucketed limit must be at most 2000")
        return self


InferenceResultsQuery = InferenceQuery


class InferenceResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    time_zone: Literal["Asia/Jakarta"]
    model_version: str
    points: list[InferencePoint] = Field(max_length=5_000)
    next_cursor: str | None
    returned_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_count(self) -> InferenceResponse:
        if self.returned_count != len(self.points):
            raise ValueError("returned_count must equal points length")
        return self


InferenceResultsResponse = InferenceResponse


class AlertEvent(StrictModel):
    event_id: str
    alert_id: str
    event_at: OperationalInstant
    event_type: AlertStatus
    device_id: SensorId
    actor: str
    note: str | None
    accepted_at: OperationalInstant | None
    inference_model_version: str | None
    detection_basis: DetectionBasis


class AlertEventsQuery(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"alert_id", "device_id", "from", "from_ts", "to", "to_ts", "cursor"}
    )

    alert_id: Annotated[str, Field(min_length=1)] | None = Field(
        default=None, exclude_if=_is_none
    )
    device_id: SensorId | None = Field(default=None, exclude_if=_is_none)
    from_ts: OperationalInstant | None = Field(
        default=None, alias="from", exclude_if=_is_none
    )
    to_ts: OperationalInstant | None = Field(
        default=None, alias="to", exclude_if=_is_none
    )
    limit: Annotated[int, Field(ge=1, le=200)] = 200
    cursor: str | None = Field(default=None, exclude_if=_is_none)

    @model_validator(mode="after")
    def validate_range(self) -> AlertEventsQuery:
        if self.from_ts is not None and self.to_ts is not None:
            if self.from_ts >= self.to_ts:
                raise ValueError("from must be earlier than to")
        return self


class AlertEventsResponse(StrictModel):
    request_id: str
    time_zone: Literal["Asia/Jakarta"]
    events: list[AlertEvent] = Field(max_length=200)
    next_cursor: str | None
    returned_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_count(self) -> AlertEventsResponse:
        if self.returned_count != len(self.events):
            raise ValueError("returned_count must equal events length")
        return self


_ALERT_PERMISSIONS = {
    "detected": (True, False),
    "acknowledged": (False, True),
    "resolved": (False, False),
}


class CurrentAlert(StrictModel):
    alert_id: str
    device_id: SensorId
    status: AlertStatus
    episode_start_ts: HistoricalDateTime
    episode_end_ts: HistoricalDateTime
    last_score_ts: HistoricalDateTime
    created_at: OperationalInstant
    latest_event_at: OperationalInstant
    latest_event_id: str
    peak_score: float
    latest_score: float
    anomalous_window_count: Annotated[int, Field(gt=0)]
    replay_job_id: str
    threshold: float
    model_version: str
    detection_basis: DetectionBasis
    can_acknowledge: bool
    can_resolve: bool

    @model_validator(mode="after")
    def validate_permissions(self) -> CurrentAlert:
        if (self.can_acknowledge, self.can_resolve) != _ALERT_PERMISSIONS[self.status]:
            raise ValueError(f"permissions are invalid for {self.status}")
        return self


class CurrentAlertsQuery(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"device_id", "status"}
    )

    device_id: SensorId | None = Field(default=None, exclude_if=_is_none)
    status: AlertStatus | None = Field(default=None, exclude_if=_is_none)
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=100)] = 25


class CurrentAlertsResponse(StrictModel):
    request_id: str
    time_zone: Literal["Asia/Jakarta"]
    generated_at: OperationalInstant
    items: list[CurrentAlert] = Field(max_length=100)
    page: Annotated[int, Field(ge=1)]
    page_size: Annotated[int, Field(ge=1, le=100)]
    total: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_page(self) -> CurrentAlertsResponse:
        if self.total < len(self.items) or len(self.items) > self.page_size:
            raise ValueError("invalid current-alert page counts")
        return self


class _AlertMutationResponseFields(StrictModel):
    request_id: str
    alert_id: str
    event: AlertEvent
    idempotent_replay: bool


class AcknowledgeAlertResponse(_AlertMutationResponseFields):
    status: Literal["acknowledged"]

    @model_validator(mode="after")
    def validate_event(self) -> AcknowledgeAlertResponse:
        if self.event.alert_id != self.alert_id or self.event.event_type != "acknowledged":
            raise ValueError("event must match mutation response")
        return self


class ResolveAlertResponse(_AlertMutationResponseFields):
    status: Literal["resolved"]

    @model_validator(mode="after")
    def validate_event(self) -> ResolveAlertResponse:
        if self.event.alert_id != self.alert_id or self.event.event_type != "resolved":
            raise ValueError("event must match mutation response")
        return self


AlertMutationResponse = AcknowledgeAlertResponse | ResolveAlertResponse


NonEmptyString = Annotated[str, Field(min_length=1)]


class ModelRegistryItem(StrictModel):
    id: Literal["transformer_step5", "conv1d_step5", "lstm_step5"]
    family: Literal["transformer", "conv1d", "lstm"]
    display_name: NonEmptyString
    architecture: dict[str, int | float] = Field(min_length=1, max_length=16)
    param_count: Annotated[int, Field(gt=0)]
    best_val_mse: Annotated[float, Field(gt=0)]
    best_epoch: Annotated[int, Field(gt=0)]
    model_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    dataset_reference: Literal["b02f3872_ruang_produksi_v3_march07"]
    window_size: Literal[30]
    features: list[Literal["suhu", "rh"]] = Field(min_length=2, max_length=2)
    score_semantics: Literal["window_mean_squared_reconstruction_error"]
    report_source: Literal["reported_model_registry"]
    summary: NonEmptyString

    @model_validator(mode="after")
    def validate_features(self) -> ModelRegistryItem:
        if self.features != ["suhu", "rh"]:
            raise ValueError("model registry features must be suhu then rh")
        return self


class ModelRegistryResponse(StrictModel):
    items: list[ModelRegistryItem] = Field(min_length=3, max_length=3)


class OfflineEvaluationForwardValidation(StrictModel):
    recon_max_abs_diff: float
    score_rel_error: float
    passed: bool


class OfflineEvaluationThreshold(StrictModel):
    value: float
    policy: Literal["clean_val_quantile"]
    alpha: float
    comparison: Literal["strict_gt"]


class OfflineEvaluationMetrics(StrictModel):
    window_precision: float
    window_recall: float
    window_f1: float
    event_hit_rate: float
    event_hit_by_family: dict[str, float] = Field(min_length=1)
    clean_test_fpr: float
    composite_fc1: float
    alert_rate: float


class OfflineEvaluationProvenance(StrictModel):
    forward: NonEmptyString
    torch_version: NonEmptyString
    computed_at: NonEmptyString


class OfflineEvaluationItem(StrictModel):
    model_family: Literal["lstm"]
    model_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    dataset_reference: Literal["b02f3872_ruang_produksi_v3_march07"]
    forward_validation: OfflineEvaluationForwardValidation
    threshold: OfflineEvaluationThreshold
    n_val_windows: Annotated[int, Field(ge=0)]
    n_test_windows: Annotated[int, Field(ge=0)]
    n_events: Annotated[int, Field(ge=0)]
    n_positive_windows: Annotated[int, Field(ge=0)]
    metrics: OfflineEvaluationMetrics
    provenance: OfflineEvaluationProvenance


class OfflineEvaluationsResponse(StrictModel):
    items: list[OfflineEvaluationItem] = Field(min_length=1, max_length=1)


class ValidationTrackFields(StrictModel):
    version: NonEmptyString
    model: NonEmptyString
    track: NonEmptyString
    label: NonEmptyString
    score_key: NonEmptyString
    score_semantics: NonEmptyString
    evaluation_period: NonEmptyString
    validation_only: bool
    test_evaluated: bool
    n_val_windows: Annotated[int, Field(gt=0)]
    threshold: float
    threshold_policy: dict[str, object]
    has_labeled_ground_truth: bool
    available_metrics: list[NonEmptyString] = Field(max_length=500)
    summary: NonEmptyString
    model_key: str | None
    report_source: Literal[
        "legacy_m1_fixture", "platform_computed", "reported_dandy_pilot"
    ]
    label_source: Literal["none", "synthetic_injection", "expert", "natural"]
    evaluation_kind: Literal[
        "validation_threshold",
        "synthetic_test",
        "clean_test",
        "comparison_snapshot",
    ]
    test_observed: bool
    independent_final: bool
    source_commit: str | None
    source_path: str | None
    source_sha256: str | None


ModelEvaluationSummary = ValidationTrackFields


class ModelEvaluationsQuery(StrictModel):
    page: Annotated[int, Field(ge=1)] = 1
    page_size: Annotated[int, Field(ge=1, le=50)] = 25


class ModelEvaluationsResponse(StrictModel):
    request_id: str
    items: list[ValidationTrackFields] = Field(max_length=50)
    page: Annotated[int, Field(ge=1)]
    page_size: Annotated[int, Field(ge=1, le=50)]
    total: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_page(self) -> ModelEvaluationsResponse:
        if self.total < len(self.items) or len(self.items) > self.page_size:
            raise ValueError("invalid model-evaluation page counts")
        return self


class ConfusionMatrix(StrictModel):
    labels: list[str] = Field(min_length=2, max_length=500)
    matrix: list[list[Annotated[int, Field(ge=0)]]] = Field(min_length=2, max_length=500)

    @model_validator(mode="after")
    def validate_dimensions(self) -> ConfusionMatrix:
        if len(self.matrix) != len(self.labels):
            raise ValueError("matrix dimensions must match labels")
        if any(len(row) != len(self.labels) or len(row) > 500 for row in self.matrix):
            raise ValueError("matrix dimensions must match labels")
        return self


class RocPoint(StrictModel):
    fpr: Annotated[float, Field(ge=0, le=1)]
    tpr: Annotated[float, Field(ge=0, le=1)]


class RocCurve(StrictModel):
    auc: Annotated[float, Field(ge=0, le=1)]
    points: list[RocPoint] = Field(max_length=5_000)


class PrecisionRecallPoint(StrictModel):
    recall: Annotated[float, Field(ge=0, le=1)]
    precision: Annotated[float, Field(ge=0, le=1)]


class PrecisionRecallCurve(StrictModel):
    average_precision: Annotated[float, Field(ge=0, le=1)]
    points: list[PrecisionRecallPoint] = Field(max_length=5_000)


class ModelEvaluationDetail(ValidationTrackFields):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"confusion_matrix", "roc", "precision_recall"}
    )

    request_id: str
    model_hash: str | None
    preprocessing_hash: str | None
    threshold_hash: str | None
    metrics: dict[str, object]
    confusion_matrix: ConfusionMatrix | None = Field(default=None, exclude_if=_is_none)
    roc: RocCurve | None = Field(default=None, exclude_if=_is_none)
    precision_recall: PrecisionRecallCurve | None = Field(
        default=None, exclude_if=_is_none
    )
    notes: str | None

    @model_validator(mode="after")
    def validate_metrics(self) -> ModelEvaluationDetail:
        if len(self.metrics) > 500:
            raise ValueError("metrics must be bounded")
        return self


class SystemServiceStatus(StrictModel):
    name: str
    liveness: LivenessState
    readiness: ReadinessState
    checked_at: OperationalInstant
    detail: str


class SystemTelemetryStatus(StrictModel):
    latest_ts: HistoricalDateTime | None
    age_seconds: Annotated[float, Field(ge=0)] | None
    fresh_sensor_count: Annotated[int, Field(ge=0, le=1)]
    stale_sensor_count: Annotated[int, Field(ge=0, le=1)]
    offline_sensor_count: Annotated[int, Field(ge=0, le=1)]

    @model_validator(mode="after")
    def validate_total(self) -> SystemTelemetryStatus:
        if self.fresh_sensor_count + self.stale_sensor_count + self.offline_sensor_count > 1:
            raise ValueError("telemetry sensor counts must not exceed one public device")
        return self


class SystemStatusResponse(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"diagnostics"}
    )

    request_id: str
    checked_at: OperationalInstant
    overall_observation: str
    services: list[SystemServiceStatus] = Field(max_length=500)
    telemetry: SystemTelemetryStatus
    diagnostics: dict[str, object] | None = Field(default=None, exclude_if=_is_none)

    @model_validator(mode="after")
    def validate_diagnostics(self) -> SystemStatusResponse:
        if self.diagnostics is not None and len(self.diagnostics) > 500:
            raise ValueError("diagnostics must contain at most 500 entries")
        return self


class LivenessResponse(StrictModel):
    status: Literal["alive"]
    request_id: str
    checked_at: OperationalInstant


class ReadinessDependency(StrictModel):
    name: str
    status: ReadinessState
    detail: str


class ReadinessResponse(StrictModel):
    status: Literal["ready", "not_ready"]
    request_id: str
    checked_at: OperationalInstant
    dependencies: list[ReadinessDependency] = Field(max_length=500)


class DeviceItem(StrictModel):
    device_id: SensorId
    display_name: Literal["TALPHA Ruang Produksi"]
    time_zone: Literal["Asia/Jakarta"]
    channels: tuple[Literal["suhu"], Literal["rh"]]
    corpus_from: HistoricalDateTime | None
    corpus_to: HistoricalDateTime | None
    import_readiness: Literal["pending", "importing", "ready", "failed"]


class DevicesResponse(StrictModel):
    request_id: str
    items: list[DeviceItem] = Field(min_length=1, max_length=1)


class PublicModelVersion(StrictModel):
    version: str
    runtime_kind: Literal["preview_simulator", "artifact"]
    selectable: bool
    compatible: bool
    artifact_status: Literal["pending", "ready"]
    score_provenance: ScoreProvenance


class PublicModelFamily(StrictModel):
    model_key: Literal[
        "ewma",
        "pca",
        "wsn-dense-ae",
        "lstm-ae",
        "usad",
        "cfc-autoencoder",
        "mtad-gat",
    ]
    display_name: str
    artifact_status: Literal["pending", "ready"]
    versions: list[PublicModelVersion] = Field(min_length=1)


class ModelsResponse(StrictModel):
    request_id: str
    device_id: SensorId
    active_activation_id: str
    active_model_version: str
    families: list[PublicModelFamily] = Field(min_length=7, max_length=7)


class ModelActivationRequest(StrictModel):
    command_id: Annotated[str, Field(min_length=1, max_length=128)]
    device_id: SensorId
    model_version: Annotated[str, Field(min_length=1, max_length=200)]


class ModelActivation(StrictModel):
    activation_id: str
    command_id: str
    device_id: SensorId
    prior_model_version: str | None
    model_version: str
    changed: bool
    activated_at: OperationalInstant
    actor: str


class ModelActivationResponse(StrictModel):
    request_id: str
    activation: ModelActivation
    active_model_version: str
    idempotent_request_replay: bool


class ReplayJobRequest(StrictModel):
    command_id: Annotated[str, Field(min_length=1, max_length=128)]
    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")

    @model_validator(mode="after")
    def validate_replay_interval(self) -> ReplayJobRequest:
        start = datetime.fromisoformat(self.from_ts)
        end = datetime.fromisoformat(self.to_ts)
        if start >= end:
            raise ValueError("from must be earlier than to")
        if (end - start).total_seconds() > 31 * 86_400:
            raise ValueError("replay interval must not exceed 31 days")
        return self


class ReplayJobItem(StrictModel):
    job_id: str
    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    time_zone: Literal["Asia/Jakarta"]
    model_version: str
    activation_id: str
    score_provenance: ScoreProvenance
    status: Literal["queued", "running", "succeeded", "failed"]
    progress: Annotated[float, Field(ge=0, le=1)]
    processed_count: Annotated[int, Field(ge=0)]
    result_count: Annotated[int, Field(ge=0)]
    episode_count: Annotated[int, Field(ge=0)]
    submitted_at: OperationalInstant
    started_at: OperationalInstant | None
    completed_at: OperationalInstant | None
    error_code: str | None
    error_detail: str | None


class ReplayJobResponse(StrictModel):
    request_id: str
    job: ReplayJobItem
    idempotent_request_replay: bool


class ReplayJobStatusResponse(StrictModel):
    request_id: str
    job: ReplayJobItem
