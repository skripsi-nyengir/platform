from __future__ import annotations

import base64
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Annotated, ClassVar, Literal, cast
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

SensorId = Literal["b02f3872-ruang-produksi"]
CorpusDeviceId = Literal["b02f3872-ruang-produksi", "b02f3872-simulasi-injeksi"]
Bucket = Literal["raw", "one_minute", "adaptive"]
Freshness = Literal["fresh", "stale", "unknown"]
Availability = Literal["online", "offline", "unknown"]
AlertStatus = Literal["detected", "acknowledged", "resolved"]
Severity = Literal["info", "warning", "critical"]
ScoreProvenance = Literal["simulated_preview", "artifact_backed"]
DetectionBasis = Literal["simulated_preview", "artifact_backed"]
InjectionFamily = Literal[
    "spike", "drift", "stuck", "erratic", "bias", "data_loss", "garbage"
]
InjectionSeverity = Literal["low", "medium", "high"]
LivenessState = Literal["alive", "not_alive", "unknown"]
ReadinessState = Literal["ready", "not_ready", "unknown"]
CursorScope = Literal["telemetry", "inference", "alert-events", "post_inference_bins"]

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


def make_keyset_cursor(
    scope: CursorScope,
    *,
    timestamp: str,
    row_id: str,
    snapshot_to: str,
    filters: dict[str, object],
) -> str:
    payload = json.dumps(
        {
            "v": 1,
            "scope": scope,
            "timestamp": timestamp,
            "row_id": row_id,
            "snapshot_to": snapshot_to,
            "filters": filters,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    checksum = hashlib.sha256(payload).hexdigest()[:16].encode()
    return base64.urlsafe_b64encode(checksum + b"." + payload).decode().rstrip("=")


def parse_keyset_cursor(
    cursor: str,
    expected_scope: CursorScope,
    *,
    snapshot_to: str,
    filters: dict[str, object],
) -> tuple[str, str]:
    if not cursor or len(cursor) > 4_096:
        raise ValueError("invalid cursor")
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode(cursor + padding)
        checksum, separator, payload = decoded.partition(b".")
        document = json.loads(payload)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise ValueError("invalid cursor") from None
    if (
        separator != b"."
        or checksum != hashlib.sha256(payload).hexdigest()[:16].encode()
        or not isinstance(document, dict)
        or document.get("v") != 1
        or document.get("scope") != expected_scope
        or document.get("snapshot_to") != snapshot_to
        or document.get("filters") != filters
        or not isinstance(document.get("timestamp"), str)
        or not isinstance(document.get("row_id"), str)
        or not document["row_id"]
    ):
        raise ValueError("invalid cursor")
    return document["timestamp"], document["row_id"]


def effective_bucket_seconds(
    bucket: Bucket,
    from_ts: HistoricalDateTime,
    to_ts: HistoricalDateTime,
) -> int | None:
    duration_seconds = int(
        (
            datetime.fromisoformat(to_ts) - datetime.fromisoformat(from_ts)
        ).total_seconds()
    )
    if duration_seconds <= 0:
        raise ValueError("from must be earlier than to")
    if bucket == "raw":
        if duration_seconds > 3_600:
            raise ValueError("raw history is limited to one hour")
        return None
    if bucket == "one_minute":
        if duration_seconds not in (6 * 3_600, 12 * 3_600, 24 * 3_600):
            raise ValueError("one_minute is limited to 6, 12, or 24 hour presets")
        return 60
    if not 3_600 <= duration_seconds <= 24 * 3_600:
        raise ValueError("adaptive history must span between 1 and 24 hours")
    return max(60, 60 * math.ceil(duration_seconds / (600 * 60)))


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
    temperature_c_min: float | None = None
    temperature_c_max: float | None = None
    relative_humidity_pct_min: float | None = None
    relative_humidity_pct_max: float | None = None
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


class ScopeMetricsModel(StrictModel):
    scope: str
    precision: float
    recall: float
    f1: float
    accuracy: float
    tn: int
    fp: int
    fn: int
    tp: int
    n_evaluated: int
    n_anomalous: int


class SimAlertEventModel(StrictModel):
    segment_id: int
    start_idx: int
    end_idx: int
    n_candidates: int
    peak_score: float


class OperationalBucketModel(StrictModel):
    bucket_start: HistoricalDateTime
    bucket_end: HistoricalDateTime
    event_count: int


class SimMetricsResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    model_version: str
    threshold: float
    window_size: int
    frame_count: int
    event_count: int
    scored_windows: int
    timestamp_scope: ScopeMetricsModel
    overlapping_scope: ScopeMetricsModel
    bins_scope: ScopeMetricsModel
    operational_event_count: int
    operational_events: list[SimAlertEventModel]
    bucket_hours: int | None = None
    operational_buckets: list[OperationalBucketModel] = []


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
        _ = effective_bucket_seconds(self.bucket, self.from_ts, self.to_ts)
        if self.bucket != "raw" and self.limit > 2_000:
            raise ValueError("bucketed limit must be at most 2000")
        return self


class TelemetryHistoryResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    bucket: Bucket
    bucket_seconds: Annotated[int, Field(ge=60)] | None
    time_zone: Literal["Asia/Jakarta"]
    points: list[TelemetryPoint] = Field(max_length=5_000)
    next_cursor: str | None
    returned_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_response(self) -> TelemetryHistoryResponse:
        expected_seconds = effective_bucket_seconds(
            self.bucket, self.from_ts, self.to_ts
        )
        if self.bucket_seconds != expected_seconds:
            raise ValueError("bucket_seconds must match the effective bucket")
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
    severity: Severity | None = None
    latest_score: float | None = None
    sample_count: Annotated[int, Field(ge=1)] = 1
    recon_temperature_c: float | None = None
    recon_relative_humidity_pct: float | None = None
    band_half_temperature_c: float | None = None
    band_half_relative_humidity_pct: float | None = None

    @model_validator(mode="after")
    def validate_window(self) -> InferencePoint:
        if compare_historical_datetimes(self.window_start_ts, self.window_end_ts) > 0:
            raise ValueError("window_start_ts must not be later than window_end_ts")
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
        _ = effective_bucket_seconds(self.bucket, self.from_ts, self.to_ts)
        if self.bucket != "raw" and self.limit > 2_000:
            raise ValueError("bucketed limit must be at most 2000")
        return self


InferenceResultsQuery = InferenceQuery


class InferenceResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    bucket: Bucket
    bucket_seconds: Annotated[int, Field(ge=60)] | None
    time_zone: Literal["Asia/Jakarta"]
    model_version: str
    points: list[InferencePoint] = Field(max_length=5_000)
    next_cursor: str | None
    returned_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_count(self) -> InferenceResponse:
        if self.bucket_seconds != effective_bucket_seconds(
            self.bucket, self.from_ts, self.to_ts
        ):
            raise ValueError("bucket_seconds must match the effective bucket")
        if self.returned_count != len(self.points):
            raise ValueError("returned_count must equal points length")
        return self


InferenceResultsResponse = InferenceResponse


PostInferenceBinSource = Literal["replay", "live"]


class PostInferenceBin(StrictModel):
    segment_id: int
    bin_ordinal: int
    start_score_ts: HistoricalDateTime
    end_score_ts: HistoricalDateTime
    scored_timestamp_count: int
    is_alert: bool
    candidate_alert_count: Annotated[int, Field(ge=0)]
    first_alert_ts: HistoricalDateTime | None = None
    last_alert_ts: HistoricalDateTime | None = None
    peak_score: float
    latest_score: float
    threshold: float
    schema_version: str

    @model_validator(mode="after")
    def validate_window(self) -> PostInferenceBin:
        if compare_historical_datetimes(self.start_score_ts, self.end_score_ts) > 0:
            raise ValueError("start_score_ts must not be later than end_score_ts")
        return self


class PostInferenceBinsQuery(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset(
        {"cursor", "model_version"}
    )

    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    source: PostInferenceBinSource = "replay"
    limit: Annotated[int, Field(ge=1, le=5_000)] = 500
    cursor: str | None = Field(default=None, exclude_if=_is_none)
    model_version: str | None = Field(default=None, exclude_if=_is_none)

    @model_validator(mode="after")
    def validate_range(self) -> PostInferenceBinsQuery:
        if compare_historical_datetimes(self.from_ts, self.to_ts) >= 0:
            raise ValueError("from must be earlier than to")
        return self


class PostInferenceBinsResponse(StrictModel):
    request_id: str
    device_id: CorpusDeviceId
    from_ts: HistoricalDateTime = Field(alias="from")
    to_ts: HistoricalDateTime = Field(alias="to")
    time_zone: Literal["Asia/Jakarta"]
    source: PostInferenceBinSource
    model_version: str
    bins: list[PostInferenceBin] = Field(max_length=5_000)
    next_cursor: str | None
    returned_count: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_count(self) -> PostInferenceBinsResponse:
        if self.returned_count != len(self.bins):
            raise ValueError("returned_count must equal bins length")
        return self


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
    from_ts: OperationalInstant | None = Field(alias="from")
    to_ts: OperationalInstant = Field(alias="to")
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
    replay_job_id: str | None
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


class AlertContextPoint(StrictModel):
    inference: InferencePoint
    source_readings: list[TelemetryPoint] = Field(min_length=10, max_length=10)


class AlertDetailResponse(StrictModel):
    request_id: str
    time_zone: Literal["Asia/Jakarta"]
    alert: CurrentAlert
    context_before: list[TelemetryPoint] = Field(max_length=10)
    episode_points: list[AlertContextPoint]
    recovery_points: list[AlertContextPoint] = Field(max_length=3)


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
    id: Literal[
        "conv1d_step5", "gru_step5", "lstm_step5", "rnn_step5", "transformer_step5"
    ]
    family: Literal["conv1d", "gru", "lstm", "rnn", "transformer"]
    display_name: NonEmptyString
    architecture: dict[str, int | float] = Field(min_length=1, max_length=16)
    param_count: Annotated[int, Field(gt=0)]
    best_val_mse: Annotated[float, Field(gt=0)]
    best_epoch: Annotated[int, Field(gt=0)]
    model_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    dataset_reference: Literal["b02f3872_ruang_produksi_v3_march07"]
    window_size: Literal[10]
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
    items: list[ModelRegistryItem] = Field(min_length=5, max_length=5)


class OfflineEvaluationThreshold(StrictModel):
    value: Annotated[float, Field(ge=0)]
    method: Literal["clean_percentile_99_5"]
    percentile: Annotated[float, Field(ge=99.5, le=99.5)]
    calibration_split: Literal["clean_validation"]
    comparison: Literal["strict_gt"]
    score_unit: Literal["timestamp"]
    uses_anomaly_labels: Literal[False]
    clean_alert_rate: Annotated[float, Field(ge=0, le=1)]


class OfflineEvaluationScopeMetrics(StrictModel):
    accuracy: Annotated[float, Field(ge=0, le=1)]
    precision: Annotated[float, Field(ge=0, le=1)]
    recall: Annotated[float, Field(ge=0, le=1)]
    f1: Annotated[float, Field(ge=0, le=1)]
    tn: Annotated[int, Field(ge=0)]
    fp: Annotated[int, Field(ge=0)]
    fn: Annotated[int, Field(ge=0)]
    tp: Annotated[int, Field(ge=0)]
    n_evaluated: Annotated[int, Field(gt=0)]

    @model_validator(mode="after")
    def validate_confusion_metrics(self) -> OfflineEvaluationScopeMetrics:
        if self.tn + self.fp + self.fn + self.tp != self.n_evaluated:
            raise ValueError("scope confusion counts must sum to n_evaluated")

        accuracy = (self.tn + self.tp) / self.n_evaluated
        precision = self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0
        recall = self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0
        f1 = (
            (2 * self.tp) / (2 * self.tp + self.fp + self.fn)
            if 2 * self.tp + self.fp + self.fn
            else 0.0
        )
        for name, expected in (
            ("accuracy", accuracy),
            ("precision", precision),
            ("recall", recall),
            ("f1", f1),
        ):
            if abs(getattr(self, name) - expected) > 1e-12:
                raise ValueError(f"scope {name} must match confusion counts")
        return self


class OfflineEvaluationScopes(StrictModel):
    timestamp: OfflineEvaluationScopeMetrics
    overlapping_model_windows: OfflineEvaluationScopeMetrics
    non_overlapping_evaluation_bins: OfflineEvaluationScopeMetrics


class OfflineEvaluationPointAuc(StrictModel):
    roc: Annotated[float, Field(ge=0, le=1)]
    pr_trapezoidal: Annotated[float, Field(ge=0, le=1)]
    pr_definition: Literal["trapezoidal_precision_recall_auc"]
    score_unit: Literal["timestamp"]


class OfflineEvaluationSourceFile(StrictModel):
    filename: NonEmptyString
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class OfflineEvaluationArtifactCheck(OfflineEvaluationSourceFile):
    role: Literal["step5_model_identity", "step7_metric_cross_check"]
    consistency: Literal["matched", "conflict"]
    note: NonEmptyString


class OfflineEvaluationProvenance(StrictModel):
    metric_authority: Literal["executed_step7_notebook_output"]
    step5_notebook: OfflineEvaluationSourceFile
    step7_notebook: OfflineEvaluationSourceFile
    artifact_checks: list[OfflineEvaluationArtifactCheck] = Field(max_length=3)


class OfflineEvaluationContext(StrictModel):
    dataset_reference: Literal["b02f3872_ruang_produksi_v3_march07"]
    evaluation_split: Literal["val_injected"]
    test_consumed: Literal[False]
    primary_scope: Literal["non_overlapping_evaluation_bins"]
    primary_metric: Literal["f1"]
    n_points_total: Annotated[int, Field(gt=0)]
    n_points_evaluated: Annotated[int, Field(gt=0)]
    n_model_windows: Annotated[int, Field(gt=0)]
    n_positive_windows: Annotated[int, Field(gt=0)]
    n_events: Annotated[int, Field(gt=0)]
    evaluation_bin_size_points: Annotated[int, Field(gt=0)]
    n_evaluation_bins: Annotated[int, Field(gt=0)]
    n_skipped_bins: Annotated[int, Field(ge=0)]

    @model_validator(mode="after")
    def validate_counts(self) -> OfflineEvaluationContext:
        if self.n_points_evaluated > self.n_points_total:
            raise ValueError("evaluated points cannot exceed total points")
        if self.n_positive_windows > self.n_model_windows:
            raise ValueError("positive windows cannot exceed model windows")
        return self


class OfflineEvaluationItem(StrictModel):
    model_family: Literal["conv1d", "gru", "lstm", "rnn", "transformer"]
    model_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    threshold: OfflineEvaluationThreshold
    scopes: OfflineEvaluationScopes
    point_auc: OfflineEvaluationPointAuc
    provenance: OfflineEvaluationProvenance


class OfflineEvaluationsResponse(StrictModel):
    evaluation: OfflineEvaluationContext
    items: list[OfflineEvaluationItem] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def validate_model_order(self) -> OfflineEvaluationsResponse:
        expected = ["conv1d", "gru", "lstm", "rnn", "transformer"]
        if [item.model_family for item in self.items] != expected:
            raise ValueError("offline evaluations must contain the five models in order")
        return self


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
    classification: Literal["healthy", "degraded", "failed"]
    reasons: list[str] = Field(max_length=20)
    configuration_valid: bool
    lease_active: bool
    fencing_token: Annotated[int, Field(gt=0)] | None
    database_heartbeat: OperationalInstant | None
    connection_state: Literal["connected", "subscribed", "disconnected", "unknown"]
    connack_received: bool | None
    suback_received: bool | None
    latest_ts: HistoricalDateTime | None
    last_valid_reading_ts: HistoricalDateTime | None
    last_valid_reading_at: OperationalInstant | None
    age_seconds: Annotated[float, Field(ge=0)] | None
    last_gap_at: OperationalInstant | None
    invalid_message_count: Annotated[int, Field(ge=0)] | None
    retained_message_count: Annotated[int, Field(ge=0)] | None
    last_persistence_failure_at: OperationalInstant | None
    ingress_queue_depth: Annotated[int, Field(ge=0)] | None
    dropped_newest_count: Annotated[int, Field(ge=0)] | None
    pending_boundary_count: Annotated[int, Field(ge=0)]
    durable_backlog_count: Annotated[int, Field(ge=0)]
    cursor_ts: HistoricalDateTime | None
    cursor_id: str | None
    recovery_ready: bool
    active_model_version: str | None
    active_scaler_corpus_id: str | None
    artifact_hashes: dict[str, str]
    retry_state: Literal["idle", "retrying", "unknown"]
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
    database_revision: str
    minimum_database_revision: str
    dependencies: list[ReadinessDependency] = Field(max_length=500)


class LoginRequest(StrictModel):
    username: Annotated[str, Field(min_length=1, max_length=200)]
    password: Annotated[str, Field(min_length=1, max_length=1024)]


class SessionResponse(StrictModel):
    request_id: str
    username: str
    display_name: str
    expires_at: OperationalInstant


class LogoutResponse(StrictModel):
    request_id: str


class SlackSettingsResponse(StrictModel):
    request_id: str
    enabled: bool
    bot_token_configured: bool
    channel_id: str | None
    updated_at: OperationalInstant
    updated_by_username: str | None


class SlackSettingsUpdateRequest(StrictModel):
    enabled: bool
    channel_id: Annotated[str, Field(min_length=1, max_length=255)] | None
    bot_token: Annotated[str, Field(min_length=1, max_length=4096)] | None = None


class SlackTestRequest(StrictModel):
    _optional_non_nullable_fields: ClassVar[frozenset[str]] = frozenset({"bot_token"})

    channel_id: Annotated[str, Field(min_length=1, max_length=255)]
    bot_token: Annotated[str, Field(min_length=1, max_length=4096)] | None = None


class SlackTestResponse(StrictModel):
    request_id: str
    status: Literal["sent"]
    sent_at: OperationalInstant


class DeviceItem(StrictModel):
    device_id: SensorId
    display_name: Literal["TALPHA Ruang Produksi"]
    time_zone: Literal["Asia/Jakarta"]
    channels: tuple[
        Literal["temperature_c"], Literal["relative_humidity_pct"]
    ]
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
    channels: tuple[str, ...]
    window_size: Annotated[int, Field(gt=0)]
    stride: Annotated[int, Field(gt=0)]
    artifact_status: Literal["pending", "ready"]
    score_provenance: ScoreProvenance

    @field_validator("channels", mode="before")
    @classmethod
    def restore_json_channels(cls, value: object) -> object:
        return tuple(value) if isinstance(value, list) else value


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
