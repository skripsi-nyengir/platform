from collections.abc import Callable
from math import inf, nan

from pydantic import TypeAdapter, ValidationError

from anomaly_backend.contracts import (
    AlertCommandRequest,
    CurrentAlert,
    HistoricalDateTime,
    InferencePoint,
    OperationalInstant,
    ReplayJobRequest,
    SensorId,
    compare_historical_datetimes,
    is_finite_number,
    make_cursor,
    parse_cursor,
)


PUBLIC_DEVICE_ID = "b02f3872-ruang-produksi"


def assert_validation_error(call: Callable[[], object]) -> None:
    try:
        _ = call()
    except ValidationError:
        return
    raise AssertionError("expected a validation error")


def test_public_sensor_id_accepts_only_b02f3872() -> None:
    adapter: TypeAdapter[SensorId] = TypeAdapter(SensorId)

    assert adapter.validate_python(PUBLIC_DEVICE_ID, strict=True) == PUBLIC_DEVICE_ID
    for archived_or_unknown in ("talpha-1", "talpha-2", "n1"):
        assert_validation_error(
            lambda value=archived_or_unknown: adapter.validate_python(
                value, strict=True
            )
        )


def test_corpus_datetime_accepts_local_seconds_without_offset() -> None:
    adapter: TypeAdapter[HistoricalDateTime] = TypeAdapter(HistoricalDateTime)

    assert adapter.validate_python(
        "2026-02-01T00:00:00", strict=True
    ) == "2026-02-01T00:00:00"
    for invalid in (
        "2026-02-01T00:00:00Z",
        "2026-02-01T00:00:00+07:00",
        "2026-02-01T00:00:00.000",
        "2026-02-30T00:00:00",
    ):
        assert_validation_error(
            lambda value=invalid: adapter.validate_python(value, strict=True)
        )

    assert compare_historical_datetimes(
        "2026-02-01T00:00:00", "2026-02-01T00:00:01"
    ) < 0


def test_operational_instant_requires_utc_rfc3339_z() -> None:
    adapter: TypeAdapter[OperationalInstant] = TypeAdapter(OperationalInstant)

    assert adapter.validate_python(
        "2026-07-24T12:00:00Z", strict=True
    ) == "2026-07-24T12:00:00Z"
    for invalid in (
        "2026-07-24T12:00:00",
        "2026-07-24T19:00:00+07:00",
        "2026-07-24 12:00:00Z",
    ):
        assert_validation_error(
            lambda value=invalid: adapter.validate_python(value, strict=True)
        )


def test_cursor_round_trip_is_scoped() -> None:
    cursor = make_cursor("inference", 12)

    assert cursor == "inference:12"
    assert parse_cursor(cursor, "inference") == 12


def test_cursor_rejects_wrong_scope() -> None:
    try:
        _ = parse_cursor("telemetry:1", "inference")
    except ValueError:
        return
    raise AssertionError("expected wrong cursor scope to fail")


def test_numeric_contracts_reject_non_finite_scores() -> None:
    assert is_finite_number(0.25)
    assert not is_finite_number(True)
    assert not is_finite_number(nan)
    assert not is_finite_number(inf)

    base = {
        "window_start_ts": "2026-02-01T00:00:00",
        "window_end_ts": "2026-02-01T00:00:29",
        "score_ts": "2026-02-01T00:00:29",
        "score": 0.5,
        "threshold": 1.0,
        "is_anomaly": False,
        "model_version": "preview-lstm-ae-v1",
        "score_provenance": "simulated_preview",
    }
    for field in ("score", "threshold"):
        assert_validation_error(
            lambda key=field: InferencePoint.model_validate(
                {**base, key: nan}, strict=True
            )
        )


def test_inference_point_requires_explicit_score_timestamp_and_preview_provenance() -> None:
    point = InferencePoint.model_validate(
        {
            "window_start_ts": "2026-02-01T00:00:00",
            "window_end_ts": "2026-02-01T00:00:29",
            "score_ts": "2026-02-01T00:00:30",
            "score": 1.1,
            "threshold": 1.0,
            "is_anomaly": True,
            "model_version": "preview-mtad-gat-v1",
            "score_provenance": "simulated_preview",
        },
        strict=True,
    )

    assert point.score_ts == "2026-02-01T00:00:30"
    assert_validation_error(
        lambda: InferencePoint.model_validate(
            {
                **point.model_dump(),
                "score_provenance": "deterministic_threshold_fixture",
            },
            strict=True,
        )
    )


def test_current_alert_exposes_episode_and_utc_lifecycle_domains() -> None:
    alert = CurrentAlert(
        alert_id="alert-preview",
        device_id=PUBLIC_DEVICE_ID,
        status="detected",
        episode_start_ts="2026-02-01T00:00:29",
        episode_end_ts="2026-02-01T00:00:31",
        last_score_ts="2026-02-01T00:00:31",
        created_at="2026-07-24T12:00:00Z",
        latest_event_at="2026-07-24T12:00:00Z",
        latest_event_id="event-preview",
        peak_score=1.4,
        latest_score=1.2,
        anomalous_window_count=3,
        replay_job_id="job-preview",
        threshold=1.0,
        model_version="preview-lstm-ae-v1",
        detection_basis="simulated_preview",
        can_acknowledge=True,
        can_resolve=False,
    )

    assert "detected_at" not in alert.model_dump()
    assert alert.created_at.endswith("Z")


def test_current_alert_permissions_must_match_status() -> None:
    payload = {
        "alert_id": "alert-preview",
        "device_id": PUBLIC_DEVICE_ID,
        "status": "detected",
        "episode_start_ts": "2026-02-01T00:00:29",
        "episode_end_ts": "2026-02-01T00:00:31",
        "last_score_ts": "2026-02-01T00:00:31",
        "created_at": "2026-07-24T12:00:00Z",
        "latest_event_at": "2026-07-24T12:00:00Z",
        "latest_event_id": "event-preview",
        "peak_score": 1.4,
        "latest_score": 1.2,
        "anomalous_window_count": 3,
        "replay_job_id": "job-preview",
        "threshold": 1.0,
        "model_version": "preview-lstm-ae-v1",
        "detection_basis": "simulated_preview",
        "can_acknowledge": True,
        "can_resolve": True,
    }

    assert_validation_error(
        lambda: CurrentAlert.model_validate(payload, strict=True)
    )


def test_alert_command_uses_server_owned_operational_time() -> None:
    command = AlertCommandRequest.model_validate(
        {"command_id": "command-1"}, strict=True
    )

    assert command.model_dump() == {"command_id": "command-1"}
    assert_validation_error(
        lambda: AlertCommandRequest.model_validate(
            {
                "command_id": "command-1",
                "event_ts": "2026-07-24T12:00:00",
            },
            strict=True,
        )
    )


def test_replay_request_preserves_corpus_datetime_fields() -> None:
    request = ReplayJobRequest.model_validate(
        {
            "command_id": "replay-request",
            "device_id": PUBLIC_DEVICE_ID,
            "from": "2026-02-01T00:00:00",
            "to": "2026-02-02T00:00:00",
        },
        strict=True,
    )

    assert request.from_ts == "2026-02-01T00:00:00"
    assert request.to_ts == "2026-02-02T00:00:00"
