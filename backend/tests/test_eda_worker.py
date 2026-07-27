from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
import os
from typing import cast
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend.config import Settings
from anomaly_backend.eda_contracts import EDA_SECTION_NAMES
from anomaly_eda.config import ALGORITHM_VERSION, CONFIG_HASH
from anomaly_eda.input_adapter import RawInputAdapter, RawSourceMetadata
import anomaly_worker.eda_service as service


DATABASE_ENV = {
    "POSTGRES_HOST": "db",
    "POSTGRES_PORT": "5432",
    "POSTGRES_DB": "anomaly_detection",
    "POSTGRES_USER": "anomaly",
    "POSTGRES_PASSWORD": "anomaly-dev-only",
}
SOURCE_SHA = "a" * 64
MANIFEST_SHA = "b" * 64


def _settings(**overrides: int) -> Settings:
    return Settings(
        postgres_host="db",
        postgres_port=5432,
        postgres_db="anomaly_detection",
        postgres_user="anomaly",
        postgres_password="anomaly-dev-only",
        eda_worker_lease_seconds=overrides.get("eda_worker_lease_seconds", 900),
        eda_worker_heartbeat_seconds=overrides.get(
            "eda_worker_heartbeat_seconds", 30
        ),
        eda_worker_max_attempts=overrides.get("eda_worker_max_attempts", 3),
        eda_worker_compute_timeout_seconds=overrides.get(
            "eda_worker_compute_timeout_seconds", 1_800
        ),
    )


def _job(*, attempt_count: int = 1, max_attempts: int = 3) -> dict[str, object]:
    start = datetime(2025, 7, 1)
    return {
        "id": uuid4(),
        "snapshot_id": uuid4(),
        "logical_key": "c" * 64,
        "source_sha256": SOURCE_SHA,
        "from_ts": start,
        "to_ts": start + timedelta(minutes=20),
        "period_kind": "custom",
        "algorithm_version": ALGORITHM_VERSION,
        "config_hash": CONFIG_HASH,
        "attempt_count": attempt_count,
        "max_attempts": max_attempts,
    }


def _sections(
    *, not_eligible: str | None = None, failed: str | None = None
) -> tuple[dict[str, object], ...]:
    result: list[dict[str, object]] = []
    for name in EDA_SECTION_NAMES:
        if name == not_eligible:
            result.append(
                {
                    "section": name,
                    "status": "not_eligible",
                    "reason_code": "insufficient_rolling_windows",
                    "reason_detail": "Rentang belum memenuhi syarat statistik.",
                }
            )
        elif name == failed:
            result.append(
                {
                    "section": name,
                    "status": "failed",
                    "reason_code": "section_compute_failed",
                    "reason_detail": "Bagian statistik gagal dihitung.",
                }
            )
        else:
            result.append(
                {
                    "section": name,
                    "status": "complete",
                    "payload": {},
                    "payload_sha256": "d" * 64,
                }
            )
    return tuple(result)


class _ConnectionContext(AbstractAsyncContextManager[object]):
    async def __aenter__(self) -> object:
        return object()

    async def __aexit__(self, *args: object) -> None:
        return None


class _Engine:
    def connect(self) -> _ConnectionContext:
        return _ConnectionContext()


class _Heartbeat:
    error: Exception | None
    entered: bool

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.entered = False

    def __enter__(self) -> _Heartbeat:
        self.entered = True
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def ensure_owned(self) -> None:
        if self.error is not None:
            raise self.error


def _install_repository(
    monkeypatch: pytest.MonkeyPatch,
    job: dict[str, object],
    events: list[tuple[str, dict[str, object]]],
    *,
    complete_error: Exception | None = None,
) -> None:
    async def claim(connection: object, **kwargs: object) -> dict[str, object]:
        del connection
        events.append(("claim", dict(kwargs)))
        return job

    async def complete(connection: object, **kwargs: object) -> tuple[object, object]:
        del connection
        events.append(("complete", dict(kwargs)))
        if complete_error is not None:
            raise complete_error
        return object(), object()

    async def release(connection: object, **kwargs: object) -> object:
        del connection
        events.append(("release", dict(kwargs)))
        return object()

    async def fail(connection: object, **kwargs: object) -> object:
        del connection
        events.append(("fail", dict(kwargs)))
        return object()

    monkeypatch.setattr(service, "claim_job", claim)
    monkeypatch.setattr(service, "complete_job", complete)
    monkeypatch.setattr(service, "release_job", release)
    monkeypatch.setattr(service, "fail_job", fail)


def _computation(sections: tuple[dict[str, object], ...]) -> service.WorkerComputation:
    return service.WorkerComputation(
        sections=sections,
        provenance={"label": "algorithm-equivalent range computation"},
        canonical_release=False,
    )


def _run_once(
    monkeypatch: pytest.MonkeyPatch,
    *,
    compute: Callable[
        [Settings, Mapping[str, object]], service.WorkerComputation
    ],
    heartbeat: _Heartbeat | None = None,
    job: dict[str, object] | None = None,
    complete_error: Exception | None = None,
) -> list[tuple[str, dict[str, object]]]:
    events: list[tuple[str, dict[str, object]]] = []
    claimed = job or _job()
    _install_repository(
        monkeypatch, claimed, events, complete_error=complete_error
    )
    active_heartbeat = heartbeat or _Heartbeat()
    worked = asyncio.run(
        service.run_once(
            cast(AsyncEngine, cast(object, _Engine())),
            _settings(),
            worker_id="eda-worker-test",
            compute=compute,
            heartbeat_factory=lambda *_: cast(
                service.LeaseHeartbeat, cast(object, active_heartbeat)
            ),
        )
    )
    assert worked is True
    assert active_heartbeat.entered
    return events


def _synthetic_adapter(pair_count: int = 120) -> RawInputAdapter:
    start = datetime(2025, 7, 1)
    rows: list[dict[str, object]] = []
    source_row = 0
    for pair in range(pair_count):
        timestamp = start + timedelta(seconds=6 * pair)
        for data_index, value in ((0, 24.0 + pair / 100), (1, 55.0 + pair / 50)):
            source_row += 1
            rows.append(
                {
                    "source_row_number": source_row,
                    "device_id": "b02f3872-39a2-4b6f-a4ec-045a287fde4b",
                    "data_index": data_index,
                    "value": value,
                    "ts": timestamp,
                    "is_connected": True,
                }
            )
    return RawInputAdapter.from_database_rows(
        rows,
        metadata=RawSourceMetadata(
            sha256=SOURCE_SHA,
            row_count=len(rows),
            start="2025-07-01 00:00:00",
            cutoff_inclusive="2025-07-01 00:19:59",
        ),
    )


def _snapshot() -> dict[str, object]:
    return {
        "dataset_id": "bivariate_b02f3872_v1",
        "source_sha256": SOURCE_SHA,
        "manifest_sha256": MANIFEST_SHA,
        "config_hash": CONFIG_HASH,
        "source_from_ts": datetime(2025, 7, 1),
        "source_to_ts": datetime(2025, 7, 1, 0, 20),
        "expected_channel_count": 2,
        "status": "complete",
    }


def test_worker_settings_have_validated_environment_defaults() -> None:
    with patch.dict(os.environ, DATABASE_ENV, clear=True):
        settings = Settings.from_environ()
    assert settings.eda_worker_lease_seconds == 900
    assert settings.eda_worker_heartbeat_seconds == 30
    assert settings.eda_worker_max_attempts == 3
    assert settings.eda_worker_compute_timeout_seconds == 1800

    invalid = {**DATABASE_ENV, "EDA_WORKER_HEARTBEAT_SECONDS": "900"}
    with patch.dict(os.environ, invalid, clear=True), pytest.raises(
        ValueError, match="heartbeat.*lease"
    ):
        _ = Settings.from_environ()


def test_lease_heartbeat_renews_on_fake_clock_until_stopped() -> None:
    elapsed = 0
    renewals = 0

    def wait(seconds: float) -> bool:
        nonlocal elapsed
        elapsed += int(seconds)
        return elapsed > 90

    def renew() -> bool:
        nonlocal renewals
        renewals += 1
        return True

    heartbeat = service.LeaseHeartbeat(renew, interval_seconds=30, wait=wait)
    heartbeat.start()
    heartbeat.join(timeout=1)
    heartbeat.ensure_owned()
    assert renewals == 3
    assert elapsed == 120


def test_timeout_is_terminal_and_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def compute(*_: object) -> service.WorkerComputation:
        raise service.EdaComputeTimeout

    events = _run_once(monkeypatch, compute=compute)
    assert [name for name, _ in events] == ["claim", "fail"]
    assert events[-1][1]["error_code"] == "compute_timeout"


def test_transient_failure_releases_for_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def compute(*_: object) -> service.WorkerComputation:
        raise ConnectionError("database connection interrupted")

    events = _run_once(monkeypatch, compute=compute)
    assert [name for name, _ in events] == ["claim", "release"]


def test_last_transient_attempt_becomes_sanitized_terminal_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def compute(*_: object) -> service.WorkerComputation:
        raise ConnectionError("SELECT raw_secret FROM /private/source.csv")

    events = _run_once(
        monkeypatch,
        compute=compute,
        job=_job(attempt_count=3, max_attempts=3),
    )
    assert [name for name, _ in events] == ["claim", "fail"]
    failure = events[-1][1]
    assert failure["error_code"] == "max_attempts_exhausted"
    assert "SELECT" not in str(failure["error_detail"])
    assert "/private" not in str(failure["error_detail"])


def test_deterministic_invariant_failure_is_terminal_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def compute(*_: object) -> service.WorkerComputation:
        raise ValueError("raw row parity drift at /private/source.csv")

    events = _run_once(monkeypatch, compute=compute)
    assert [name for name, _ in events] == ["claim", "fail"]
    failure = events[-1][1]
    assert failure["error_code"] == "invariant_violation"
    assert "/private" not in str(failure["error_detail"])


def test_lease_loss_fences_publication_and_failure_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _run_once(
        monkeypatch,
        compute=lambda *_: _computation(_sections()),
        heartbeat=_Heartbeat(service.LeaseLostError()),
    )
    assert [name for name, _ in events] == ["claim"]


def test_publication_failure_uses_one_atomic_call_and_leaves_no_partial_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _run_once(
        monkeypatch,
        compute=lambda *_: _computation(_sections()),
        complete_error=ConnectionError("publication interrupted"),
    )
    assert [name for name, _ in events] == ["claim", "complete", "release"]
    sections = cast(tuple[dict[str, object], ...], events[1][1]["sections"])
    assert len(sections) == 11


def test_success_publishes_mixed_complete_and_not_eligible_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _run_once(
        monkeypatch,
        compute=lambda *_: _computation(_sections(not_eligible="relationships")),
    )
    assert [name for name, _ in events] == ["claim", "complete"]
    published = cast(tuple[dict[str, object], ...], events[-1][1]["sections"])
    assert [item["section"] for item in published] == list(EDA_SECTION_NAMES)
    assert any(item["status"] == "not_eligible" for item in published)


def test_optional_failed_section_still_completes_the_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events = _run_once(
        monkeypatch,
        compute=lambda *_: _computation(_sections(failed="stationarity")),
    )
    assert [name for name, _ in events] == ["claim", "complete"]
    published = cast(tuple[dict[str, object], ...], events[-1][1]["sections"])
    stationarity = next(
        item for item in published if item["section"] == "stationarity"
    )
    assert stationarity["status"] == "failed"


def test_real_section_assembly_reuses_one_product_and_preserves_order() -> None:
    computation = service.compute_sections(_synthetic_adapter(), _snapshot(), _job())
    assert [item["section"] for item in computation.sections] == list(EDA_SECTION_NAMES)
    statuses = {item["section"]: item["status"] for item in computation.sections}
    assert statuses["quality_overview"] == "complete"
    assert statuses["temporal_distribution"] == "complete"
    assert statuses["relationships"] == "not_eligible"
    assert statuses["stationarity"] == "not_eligible"
    assert statuses["change_points"] == "not_eligible"
    assert statuses["uncertainty"] == "not_eligible"
    assert statuses["audit_metadata"] == "complete"


def test_real_optional_compute_exception_is_published_as_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_relationships(*_: object) -> object:
        raise RuntimeError("isolated method failure")

    monkeypatch.setattr(service, "compute_relationships", fail_relationships)
    computation = service.compute_sections(_synthetic_adapter(), _snapshot(), _job())
    relationship = next(
        item for item in computation.sections if item["section"] == "relationships"
    )
    assert relationship == {
        "section": "relationships",
        "status": "failed",
        "reason_code": "section_compute_failed",
        "reason_detail": "Bagian statistik relationships gagal dihitung.",
    }


def test_single_pair_is_successfully_published_as_not_eligible() -> None:
    computation = service.compute_sections(
        _synthetic_adapter(pair_count=1), _snapshot(), _job()
    )
    statuses = {item["section"]: item["status"] for item in computation.sections}
    reasons = {
        item["section"]: item.get("reason_code") for item in computation.sections
    }
    assert statuses["quality_overview"] == "complete"
    assert statuses["quality_excerpt"] == "not_eligible"
    assert reasons["quality_excerpt"] == "no_selectable_excerpt"
    assert statuses["temporal_coverage"] == "not_eligible"
    assert reasons["temporal_coverage"] == "no_positive_deltas"
