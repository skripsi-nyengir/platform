from __future__ import annotations

import asyncio
from collections.abc import Callable, Generator, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from importlib.metadata import version
import json
import os
import resource
import signal
import socket
import threading
import time
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

import psycopg
from psycopg.rows import dict_row
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.eda_contracts import (
    EDA_MANDATORY_SECTIONS,
    EDA_OPTIONAL_STATISTICAL_SECTIONS,
    EDA_SECTION_NAMES,
    EdaSection,
    EdaSectionName,
)
from anomaly_backend.sql.eda_runs import (
    claim_job,
    complete_job,
    fail_job,
    release_job,
    renew_lease,
)
from anomaly_eda.change_points import compute_change_points
from anomaly_eda.config import (
    ALGORITHM_VERSION,
    CONFIG_HASH,
    DATASET_ID,
    DEFAULT_CONFIG,
    MAXIMUM_CHUNK_PAIRS,
    MAXIMUM_PEAK_RSS_BYTES,
    SEED,
    SOURCE_RELEASE_ID,
    TIME_ZONE,
)
from anomaly_eda.input_adapter import RawInputAdapter, RawSourceMetadata
from anomaly_eda.pair_product import VIEW_RAW, VIEW_SCREENED
from anomaly_eda.quality import QualityComputeResult, compute_quality
from anomaly_eda.relationships import compute_relationships
from anomaly_eda.stationarity import compute_stationarity
from anomaly_eda.temporal import PeriodKind, build_temporal_sections
from anomaly_eda.uncertainty import compute_uncertainty


POLL_SECONDS = 1.0
_SECTION_ADAPTER: TypeAdapter[EdaSection] = TypeAdapter(EdaSection)
_DEPENDENCIES = (
    "numpy",
    "pandas",
    "matplotlib",
    "scipy",
    "statsmodels",
    "ruptures",
    "scikit-learn",
    "seaborn",
)


class EdaWorkerError(RuntimeError):
    pass


class LeaseLostError(EdaWorkerError):
    pass


class TerminalEdaError(EdaWorkerError):
    code: str
    detail: str

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code[:128]
        self.detail = detail[:2_000]


class EdaComputeTimeout(TerminalEdaError):
    def __init__(self) -> None:
        super().__init__(
            "compute_timeout", "Komputasi EDA melampaui batas waktu yang diizinkan."
        )


_TERMINAL_ERROR_DETAILS = {
    "compute_timeout": "Komputasi EDA melampaui batas waktu yang diizinkan.",
    "resource_limit_exceeded": "Komputasi EDA melampaui batas memori.",
    "serialization_failed": "Payload EDA tidak dapat diserialisasi dengan aman.",
    "invalid_source_identity": "Identitas sumber, konfigurasi, atau rentang EDA tidak cocok.",
    "compute_identity_drift": "Identitas algoritme EDA berubah saat komputasi.",
    "section_policy_violation": "Status bagian EDA melanggar kebijakan publikasi.",
    "section_contract_violation": "Bagian EDA gagal memenuhi kontrak publikasi.",
    "mandatory_section_missing": "Bagian wajib EDA belum lengkap.",
    "invariant_violation": "Komputasi EDA gagal pada pemeriksaan deterministik.",
}
_HEARTBEAT_SHUTDOWN_SECONDS = 5.0


@dataclass(frozen=True, slots=True)
class WorkerComputation:
    sections: tuple[dict[str, object], ...]
    provenance: dict[str, object]
    canonical_release: bool


class LeaseHeartbeat:
    _renew: Callable[[], bool]
    _interval_seconds: float
    _stop: threading.Event
    _wait: Callable[[float], bool]
    _thread: threading.Thread

    def __init__(
        self,
        renew: Callable[[], bool],
        *,
        interval_seconds: float,
        wait: Callable[[float], bool] | None = None,
    ) -> None:
        self._renew = renew
        self._interval_seconds = interval_seconds
        self._stop = threading.Event()
        self._wait = wait or self._stop.wait
        self._error: BaseException | None = None
        self._thread = threading.Thread(
            target=self._run, name="eda-lease-heartbeat", daemon=True
        )

    def _run(self) -> None:
        try:
            while not self._wait(self._interval_seconds):
                if self._stop.is_set():
                    return
                if not self._renew():
                    raise LeaseLostError("EDA lease ownership was lost")
        except BaseException as error:
            self._error = error

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def ensure_owned(self) -> None:
        if self._error is not None:
            raise self._error

    def __enter__(self) -> LeaseHeartbeat:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()
        self.join(timeout=_HEARTBEAT_SHUTDOWN_SECONDS)
        if self._thread.is_alive():
            self._error = LeaseLostError("EDA lease renewal did not stop")


def _worker_id() -> str:
    return os.environ.get("EDA_WORKER_ID") or f"{socket.gethostname()}-{os.getpid()}"


def _peak_rss_bytes() -> int:
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1_024


def _canonical_json(payload: object) -> bytes:
    try:
        return json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as error:
        raise TerminalEdaError(
            "serialization_failed", "Payload EDA tidak dapat diserialisasi dengan aman."
        ) from error


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _local_timestamp(epoch_seconds: int) -> str:
    return (
        datetime.fromtimestamp(epoch_seconds, ZoneInfo(TIME_ZONE))
        .replace(tzinfo=None)
        .isoformat(timespec="seconds")
    )


@contextmanager
def _compute_timeout(seconds: int) -> Generator[None, None, None]:
    if threading.current_thread() is not threading.main_thread():
        started = time.monotonic()
        yield
        if time.monotonic() - started > seconds:
            raise EdaComputeTimeout
        return

    previous_handler = signal.getsignal(signal.SIGALRM)

    def expired(_signum: int, _frame: object) -> None:
        raise EdaComputeTimeout

    _ = signal.signal(signal.SIGALRM, expired)
    _ = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        _ = signal.setitimer(signal.ITIMER_REAL, 0)
        _ = signal.signal(signal.SIGALRM, previous_handler)


def _validate_identity(snapshot: Mapping[str, object], job: Mapping[str, object]) -> None:
    try:
        source_from = cast(datetime, snapshot["source_from_ts"])
        source_to = cast(datetime, snapshot["source_to_ts"])
        range_from = cast(datetime, job["from_ts"])
        range_to = cast(datetime, job["to_ts"])
        valid = (
            snapshot["status"] == "complete"
            and snapshot["dataset_id"] == DATASET_ID
            and snapshot["source_sha256"] == job["source_sha256"]
            and snapshot["config_hash"] == CONFIG_HASH == job["config_hash"]
            and job["algorithm_version"] == ALGORITHM_VERSION
            and cast(int, snapshot["expected_channel_count"]) == 2
            and source_from <= range_from < range_to <= _source_to_exclusive(source_to)
            and range_from.tzinfo is None
            and range_to.tzinfo is None
        )
    except (KeyError, TypeError, ValueError) as error:
        raise TerminalEdaError(
            "invalid_source_identity", "Identitas sumber EDA tidak lengkap atau tidak valid."
        ) from error
    if not valid:
        raise TerminalEdaError(
            "invalid_source_identity",
            "Identitas sumber, konfigurasi, atau rentang EDA tidak cocok.",
        )


def _source_to_exclusive(source_to: datetime) -> datetime:
    return source_to + timedelta(seconds=1)


def _sample_counts(quality: QualityComputeResult) -> dict[str, int]:
    product = quality.pair_product
    return {
        "raw_rows": int(product.audit["row_count"]),
        "exact_pairs": product.raw_view.pair_count,
        "screened_pairs": product.rule_screened_view.pair_count,
        "active_pairs": product.rule_screened_view.pair_count,
    }


def _range_boundary(job: Mapping[str, object]) -> dict[str, bool]:
    open_ended = job["period_kind"] != "full_range"
    censored = job["period_kind"] == "custom"
    return {
        "from_censored": censored,
        "to_censored": censored,
        "from_open_ended": open_ended,
        "to_open_ended": open_ended,
    }


def _stage_section(
    job: Mapping[str, object],
    counts: Mapping[str, int],
    section: EdaSectionName,
    *,
    status: str,
    payload: dict[str, object] | None = None,
    reason_code: str | None = None,
) -> dict[str, object]:
    known = EDA_MANDATORY_SECTIONS | EDA_OPTIONAL_STATISTICAL_SECTIONS
    if section not in known or (status == "failed" and section not in EDA_OPTIONAL_STATISTICAL_SECTIONS):
        raise TerminalEdaError(
            "section_policy_violation", "Status bagian EDA melanggar kebijakan publikasi."
        )
    payload_sha256 = (
        hashlib.sha256(_canonical_json(payload)).hexdigest()
        if status == "complete" and payload is not None
        else None
    )
    detail = (
        f"Bagian EDA {section} berhasil dihitung."
        if status == "complete"
        else f"Bagian statistik {section} gagal dihitung."
        if status == "failed"
        else f"Bagian EDA {section} belum memenuhi syarat statistik."
    )
    candidate = {
        "run_id": str(job["id"]),
        "section": section,
        "status": status,
        "reason_code": reason_code,
        "detail": detail,
        "active_view": VIEW_SCREENED,
        "units": {
            "temperature": "°C",
            "relative_humidity": "%",
            "time": "second",
        },
        "sample_counts": dict(counts),
        "algorithm_version": str(job["algorithm_version"]),
        "config_hash": str(job["config_hash"]),
        "source_sha256": str(job["source_sha256"]),
        "range_boundary": _range_boundary(job),
        "payload_sha256": payload_sha256,
        "created_at": _utc_timestamp(),
        "payload": payload,
    }
    try:
        validated = _SECTION_ADAPTER.validate_python(candidate, strict=True)
    except ValidationError as error:
        raise TerminalEdaError(
            "section_contract_violation", "Bagian EDA gagal memenuhi kontrak publikasi."
        ) from error
    dumped = validated.model_dump(mode="json", by_alias=True)
    persisted: dict[str, object] = {
        "section": section,
        "status": status,
    }
    if status == "complete":
        persisted.update(
            payload=cast(dict[str, object], dumped["payload"]),
            payload_sha256=cast(str, dumped["payload_sha256"]),
        )
    else:
        persisted.update(reason_code=reason_code, reason_detail=detail)
    return persisted


def _quality_payloads(quality: QualityComputeResult) -> dict[str, dict[str, object]]:
    diagnostics = quality.diagnostics
    product = quality.pair_product
    joint = diagnostics.joint_density
    univariate = diagnostics.univariate

    joint_payload = {
        "edges": {
            "temperature_c": joint["edges"]["suhu"],
            "relative_humidity_pct": joint["edges"]["rh"],
        },
        "views": {
            view: {"histogram": joint["views"][view]["histogram"]}
            for view in (VIEW_RAW, VIEW_SCREENED)
        },
    }
    channels: dict[str, object] = {}
    for channel in ("Suhu", "RH"):
        record = univariate["channels"][channel]
        views: dict[str, object] = {}
        for view in (VIEW_RAW, VIEW_SCREENED):
            view_record = record["views"][view]
            cumulative = cast(list[int], view_record["ecdf_count"])
            denominator = cumulative[-1] if cumulative else 0
            views[view] = {
                "histogram": view_record["histogram"],
                "ecdf_count": cumulative,
                "ecdf_fraction": (
                    [count / denominator for count in cumulative] if denominator else []
                ),
            }
        channels[channel] = {
            "unit": record["unit"],
            "edges": record["edges"],
            "views": views,
        }

    excerpt = diagnostics.quality_excerpt
    excerpt_payload: dict[str, object] = {}
    if (
        excerpt["records"]
        and isinstance(excerpt["window_start_epoch_s"], int)
        and isinstance(excerpt["window_end_epoch_s"], int)
    ):
        excerpt_payload = {
            "selection_kind": excerpt["selection_kind"],
            "from": _local_timestamp(excerpt["window_start_epoch_s"]),
            "to": _local_timestamp(excerpt["window_end_epoch_s"]),
            "records": excerpt["records"],
        }
    return cast(dict[str, dict[str, object]], {
        "quality_overview": {
            "source_audit": quality.source_audit,
            "count_conservation": quality.count_conservation,
            "quality_metrics": {
                "reason_counts": product.audit["reason_counts"],
                "reason_mask_sha256": product.audit["reason_mask_sha256"],
                "reason_overlap": product.audit["reason_overlap"],
                "instrumentation": diagnostics.instrumentation,
            },
        },
        "joint_density": joint_payload,
        "univariate": {"channels": channels},
        "quality_excerpt": excerpt_payload,
    })


def _audit_payload(snapshot: Mapping[str, object]) -> dict[str, object]:
    return {
        "dataset_id": DATASET_ID,
        "source_manifest_sha256": str(snapshot["manifest_sha256"]),
        "release_id": SOURCE_RELEASE_ID,
        "seed": SEED,
        "dependencies": {package: version(package) for package in _DEPENDENCIES},
    }


def _optional_section(
    job: Mapping[str, object],
    counts: Mapping[str, int],
    section: EdaSectionName,
    compute: Callable[[], object],
) -> dict[str, object]:
    try:
        result = compute()
    except (TerminalEdaError, MemoryError, ValueError, AssertionError):
        raise
    except ImportError:
        return _stage_section(
            job,
            counts,
            section,
            status="failed",
            reason_code="dependency_unavailable",
        )
    except Exception:
        return _stage_section(
            job,
            counts,
            section,
            status="failed",
            reason_code="section_compute_failed",
        )

    status = getattr(result, "status", None)
    reason_code = getattr(result, "reason_code", None)
    payload = getattr(result, "payload", None)
    audit = getattr(result, "audit_metadata", {})
    if (
        status == "complete"
        and isinstance(audit, Mapping)
        and audit.get("status") == "failed"
    ):
        status, reason_code, payload = "failed", "section_compute_failed", None
    if status not in {"complete", "not_eligible", "failed"}:
        raise ValueError("optional compute returned an invalid section status")
    return _stage_section(
        job,
        counts,
        section,
        status=status,
        payload=cast(dict[str, object] | None, payload),
        reason_code=cast(str | None, reason_code),
    )


def compute_sections(
    adapter: RawInputAdapter,
    snapshot: Mapping[str, object],
    job: Mapping[str, object],
) -> WorkerComputation:
    _validate_identity(snapshot, job)
    quality = compute_quality(adapter, DEFAULT_CONFIG, enforce_cadence_gate=False)
    if quality.algorithm_version != job["algorithm_version"] or quality.config_hash != job["config_hash"]:
        raise TerminalEdaError(
            "compute_identity_drift", "Identitas algoritme EDA berubah saat komputasi."
        )
    temporal = build_temporal_sections(
        quality.pair_product,
        DEFAULT_CONFIG,
        period_kind=cast(PeriodKind, job["period_kind"]),
        range_start=cast(datetime, job["from_ts"]),
        range_end=cast(datetime, job["to_ts"]),
        enforce_cadence_gate=False,
    )
    counts = _sample_counts(quality)
    exact_pairs = counts["exact_pairs"]
    positive_deltas = cast(
        int, quality.pair_product.audit["positive_delta_at_most_gap_count"]
    )
    cadence_passed = cast(str, quality.pair_product.audit["cadence_gate"]) == "pass"
    payloads = _quality_payloads(quality) if exact_pairs else {}

    staged: dict[EdaSectionName, dict[str, object]] = {}
    for section in (
        "quality_overview",
        "joint_density",
        "univariate",
    ):
        staged[section] = _stage_section(
            job,
            counts,
            section,
            status="complete" if exact_pairs else "not_eligible",
            payload=payloads.get(section),
            reason_code=None if exact_pairs else "no_exact_pairs",
        )

    excerpt_payload = payloads.get("quality_excerpt", {})
    excerpt_records = cast(list[object], excerpt_payload.get("records", []))
    staged["quality_excerpt"] = _stage_section(
        job,
        counts,
        "quality_excerpt",
        status="complete" if excerpt_records else "not_eligible",
        payload=excerpt_payload if excerpt_records else None,
        reason_code=(
            None
            if excerpt_records
            else "no_exact_pairs"
            if not exact_pairs
            else "no_selectable_excerpt"
        ),
    )

    coverage_views = cast(dict[str, object], temporal.temporal_coverage["views"])
    exposed_bins = any(
        cast(dict[str, object], view).get("hourly")
        for view in coverage_views.values()
    )
    coverage_reason = (
        "no_positive_deltas"
        if not positive_deltas
        else "no_exposed_calendar_bins"
        if not exposed_bins
        else None
    )
    staged["temporal_coverage"] = _stage_section(
        job,
        counts,
        "temporal_coverage",
        status="not_eligible" if coverage_reason else "complete",
        payload=None if coverage_reason else temporal.temporal_coverage,
        reason_code=coverage_reason,
    )
    distribution_reason = (
        "no_positive_deltas"
        if not positive_deltas
        else "insufficient_representative_cadence"
        if not cadence_passed
        else None
    )
    staged["temporal_distribution"] = _stage_section(
        job,
        counts,
        "temporal_distribution",
        status="not_eligible" if distribution_reason else "complete",
        payload=None if distribution_reason else temporal.temporal_distribution,
        reason_code=distribution_reason,
    )
    staged["audit_metadata"] = _stage_section(
        job,
        counts,
        "audit_metadata",
        status="complete",
        payload=_audit_payload(snapshot),
    )

    if frozenset(staged) != EDA_MANDATORY_SECTIONS:
        raise TerminalEdaError(
            "mandatory_section_missing", "Bagian wajib EDA belum lengkap."
        )
    staged["relationships"] = _optional_section(
        job,
        counts,
        "relationships",
        lambda: compute_relationships(quality.pair_product, DEFAULT_CONFIG),
    )
    staged["stationarity"] = _optional_section(
        job,
        counts,
        "stationarity",
        lambda: compute_stationarity(temporal, DEFAULT_CONFIG),
    )
    staged["change_points"] = _optional_section(
        job,
        counts,
        "change_points",
        lambda: compute_change_points(temporal, DEFAULT_CONFIG),
    )
    staged["uncertainty"] = _optional_section(
        job,
        counts,
        "uncertainty",
        lambda: compute_uncertainty(temporal, DEFAULT_CONFIG),
    )

    peak_rss = _peak_rss_bytes()
    if peak_rss >= MAXIMUM_PEAK_RSS_BYTES:
        raise TerminalEdaError(
            "resource_limit_exceeded", "Komputasi EDA melampaui batas memori."
        )
    ordered = tuple(staged[section] for section in EDA_SECTION_NAMES)
    canonical_release = (
        job["period_kind"] == "full_range"
        and job["from_ts"] == snapshot["source_from_ts"]
        and job["to_ts"]
        == _source_to_exclusive(cast(datetime, snapshot["source_to_ts"]))
    )
    label = (
        "published v3 release"
        if canonical_release
        else "algorithm-equivalent range computation"
    )
    return WorkerComputation(
        sections=ordered,
        provenance={
            "label": label,
            "source_manifest_sha256": str(snapshot["manifest_sha256"]),
            "algorithm_version": ALGORITHM_VERSION,
            "config_hash": CONFIG_HASH,
            "peak_rss_bytes": peak_rss,
            "section_order": list(EDA_SECTION_NAMES),
        },
        canonical_release=canonical_release,
    )


@contextmanager
def _database_adapter(
    settings: Settings, job: Mapping[str, object]
) -> Generator[tuple[RawInputAdapter, Mapping[str, object]], None, None]:
    connect = cast(Any, psycopg.connect)
    raw_connection = connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname=settings.postgres_db,
        user=settings.postgres_user,
        password=settings.postgres_password,
        row_factory=dict_row,
    )
    connection = cast(psycopg.Connection[dict[str, Any]], raw_connection)
    with connection:
        snapshot = connection.execute(
            """
            SELECT dataset_id, source_sha256, manifest_sha256, config_hash,
                   source_from_ts, source_to_ts, expected_channel_count, status
            FROM eda_source_snapshots
            WHERE id = %s
            """,
            (job["snapshot_id"],),
        ).fetchone()
        if snapshot is None:
            raise TerminalEdaError(
                "invalid_source_identity", "Snapshot sumber EDA tidak ditemukan."
            )
        snapshot_mapping = cast(Mapping[str, object], cast(object, snapshot))
        _validate_identity(snapshot_mapping, job)
        cursor_name = f"eda_raw_{str(job['id']).replace('-', '')}"
        with connection.cursor(name=cursor_name, row_factory=dict_row) as cursor:
            cursor.itersize = MAXIMUM_CHUNK_PAIRS
            _ = cursor.execute(
                """
                SELECT source_row_number, device_id, data_index, value, ts,
                       is_connected
                FROM eda_raw_readings
                WHERE snapshot_id = %s AND ts >= %s AND ts < %s
                ORDER BY ts, data_index, source_row_number
                """,
                (job["snapshot_id"], job["from_ts"], job["to_ts"]),
            )
            range_end = cast(datetime, job["to_ts"]) - timedelta(seconds=1)
            adapter = RawInputAdapter.from_database_rows(
                cast(Iterator[Mapping[str, object]], cursor),
                metadata=RawSourceMetadata(
                    sha256=str(job["source_sha256"]),
                    start=cast(datetime, job["from_ts"]).strftime("%Y-%m-%d %H:%M:%S"),
                    cutoff_inclusive=range_end.strftime("%Y-%m-%d %H:%M:%S"),
                ),
                chunk_rows=MAXIMUM_CHUNK_PAIRS,
            )
            yield adapter, snapshot_mapping


def compute_job(settings: Settings, job: Mapping[str, object]) -> WorkerComputation:
    with _database_adapter(settings, job) as (adapter, snapshot):
        return compute_sections(adapter, snapshot, job)


def _renew_once(settings: Settings, job: Mapping[str, object], worker_id: str) -> bool:
    async def renew() -> bool:
        engine = create_database_engine(settings)
        try:
            async with engine.connect() as connection:
                row = await renew_lease(
                    connection,
                    job_id=cast(UUID, job["id"]),
                    lease_owner=worker_id,
                    attempt_count=int(cast(int, job["attempt_count"])),
                    lease_seconds=settings.eda_worker_lease_seconds,
                )
                return row is not None
        finally:
            await engine.dispose()

    return asyncio.run(renew())


def _heartbeat_factory(
    settings: Settings, job: Mapping[str, object], worker_id: str
) -> LeaseHeartbeat:
    return LeaseHeartbeat(
        lambda: _renew_once(settings, job, worker_id),
        interval_seconds=settings.eda_worker_heartbeat_seconds,
    )


def _terminal_failure(error: Exception) -> tuple[str, str] | None:
    if isinstance(error, TerminalEdaError):
        return error.code, _TERMINAL_ERROR_DETAILS.get(
            error.code, "Komputasi EDA dihentikan karena kesalahan deterministik."
        )
    if isinstance(error, MemoryError):
        return "resource_limit_exceeded", "Komputasi EDA melampaui batas memori."
    if isinstance(error, (ValidationError, ValueError, TypeError, AssertionError, IntegrityError)):
        return (
            "invariant_violation",
            "Komputasi EDA gagal pada pemeriksaan deterministik.",
        )
    if isinstance(error, (psycopg.DataError, psycopg.IntegrityError, psycopg.ProgrammingError)):
        return "invariant_violation", "Penyimpanan EDA gagal pada pemeriksaan deterministik."
    if isinstance(error, OSError) and not isinstance(
        error, (ConnectionError, InterruptedError)
    ):
        return "resource_limit_exceeded", "Sumber daya komputasi EDA tidak tersedia."
    return None


async def _mutate_failure(
    engine: AsyncEngine,
    settings: Settings,
    job: Mapping[str, object],
    worker_id: str,
    error: Exception,
) -> None:
    terminal = _terminal_failure(error)
    exhausted = int(cast(int, job["attempt_count"])) >= min(
        int(cast(int, job["max_attempts"])), settings.eda_worker_max_attempts
    )
    async with engine.connect() as connection:
        if terminal is not None or exhausted:
            error_code, error_detail = terminal or (
                "max_attempts_exhausted",
                "Komputasi EDA menghabiskan batas percobaan sementara.",
            )
            _ = await fail_job(
                connection,
                job_id=cast(UUID, job["id"]),
                lease_owner=worker_id,
                attempt_count=int(cast(int, job["attempt_count"])),
                error_code=error_code,
                error_detail=error_detail,
            )
        else:
            _ = await release_job(
                connection,
                job_id=cast(UUID, job["id"]),
                lease_owner=worker_id,
                attempt_count=int(cast(int, job["attempt_count"])),
            )


async def run_once(
    engine: AsyncEngine,
    settings: Settings,
    *,
    worker_id: str,
    compute: Callable[[Settings, Mapping[str, object]], WorkerComputation] | None = None,
    heartbeat_factory: Callable[
        [Settings, Mapping[str, object], str], LeaseHeartbeat
    ]
    | None = None,
) -> bool:
    async with engine.connect() as connection:
        claimed = await claim_job(
            connection,
            lease_owner=worker_id,
            lease_seconds=settings.eda_worker_lease_seconds,
        )
    if claimed is None:
        return False
    job = cast(Mapping[str, object], claimed)
    compute_function = compute or compute_job
    make_heartbeat = heartbeat_factory or _heartbeat_factory
    try:
        heartbeat = make_heartbeat(settings, job, worker_id)
        with heartbeat:
            with _compute_timeout(settings.eda_worker_compute_timeout_seconds):
                computation = compute_function(settings, job)
            heartbeat.ensure_owned()
        if _peak_rss_bytes() >= MAXIMUM_PEAK_RSS_BYTES:
            raise TerminalEdaError(
                "resource_limit_exceeded", "Komputasi EDA melampaui batas memori."
            )
        async with engine.connect() as connection:
            completed = await complete_job(
                connection,
                job_id=cast(UUID, job["id"]),
                lease_owner=worker_id,
                attempt_count=int(cast(int, job["attempt_count"])),
                provenance=computation.provenance,
                canonical_release=computation.canonical_release,
                sections=computation.sections,
            )
        if completed is None:
            raise LeaseLostError("EDA lease ownership was lost before publication")
    except LeaseLostError:
        return True
    except Exception as error:
        try:
            await _mutate_failure(engine, settings, job, worker_id, error)
        except (LeaseLostError, SQLAlchemyError, psycopg.Error):
            pass
    return True


async def _serve(settings: Settings) -> None:
    engine = create_database_engine(settings)
    worker_id = _worker_id()
    try:
        while True:
            try:
                worked = await run_once(
                    engine, settings, worker_id=worker_id
                )
            except (SQLAlchemyError, psycopg.Error, OSError):
                worked = False
            if os.environ.get("EDA_WORKER_RUN_ONCE") == "1":
                return
            if not worked:
                await asyncio.sleep(POLL_SECONDS)
    finally:
        await engine.dispose()


def run_forever() -> None:
    asyncio.run(_serve(Settings.from_environ()))


def main() -> None:
    run_forever()


if __name__ == "__main__":
    main()
