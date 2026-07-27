from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from pydantic import TypeAdapter
from sqlalchemy import func, select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.contracts import (
    format_historical_datetime,
    format_operational_instant,
)
from anomaly_backend.db import get_connection
from anomaly_backend.eda_contracts import (
    EDA_ALGORITHM_VERSION,
    EDA_CONFIG_HASH,
    EDA_DATASET_ID,
    EDA_DEVICE_ID,
    EDA_SOURCE_FROM,
    EDA_SOURCE_SHA256,
    EDA_SOURCE_TO,
    EDA_TIME_ZONE,
    EdaCacheHitResponse,
    EdaComputeRequest,
    EdaComputeResponse,
    EdaJobResponse,
    EdaJobSummary,
    EdaPeriodListQuery,
    EdaPeriodListResponse,
    EdaPrecomputedPeriodKind,
    EdaQueuedComputeResponse,
    EdaRunResponse,
    EdaRunSummary,
    EdaSection,
    EdaSectionName,
)
from anomaly_backend.problems import (
    Conflict,
    InvalidQuery,
    NotFound,
    ProblemException,
    new_request_id,
)
from anomaly_backend.sql.eda_runs import (
    EnqueueDisposition,
    build_logical_key,
    cache_lookup,
    enqueue_job,
    get_job,
    get_run,
    get_sections,
    list_periods,
)


router = APIRouter()
_SECTION_ADAPTER: TypeAdapter[EdaSection] = TypeAdapter(EdaSection)
_SOURCE_FROM = datetime.fromisoformat(EDA_SOURCE_FROM)
_SOURCE_TO_INCLUSIVE = datetime.fromisoformat(EDA_SOURCE_TO) - timedelta(seconds=1)
_CUSTOM_JOB_LIMIT = 32
_CUSTOM_COMPUTE_LOCK_ID = 20_260_726_013


class EdaSourceUnavailable(ProblemException):
    status: int = 503
    title: str = "Service unavailable"
    slug: str = "eda-source-unavailable"


class EdaCapacityExceeded(ProblemException):
    status: int = 429
    title: str = "Too many requests"
    slug: str = "eda-capacity-exceeded"


async def _active_snapshot(connection: AsyncConnection) -> RowMapping:
    row = (
        await connection.execute(
            select(*tables.eda_source_snapshots.c)
            .where(
                tables.eda_source_snapshots.c.dataset_id == EDA_DATASET_ID,
                tables.eda_source_snapshots.c.source_sha256 == EDA_SOURCE_SHA256,
                tables.eda_source_snapshots.c.config_hash == EDA_CONFIG_HASH,
                tables.eda_source_snapshots.c.source_from_ts == _SOURCE_FROM,
                tables.eda_source_snapshots.c.source_to_ts == _SOURCE_TO_INCLUSIVE,
                tables.eda_source_snapshots.c.expected_channel_count == 2,
                tables.eda_source_snapshots.c.status == "complete",
            )
            .order_by(
                tables.eda_source_snapshots.c.completed_at.desc(),
                tables.eda_source_snapshots.c.id.desc(),
            )
            .limit(1)
        )
    ).mappings().one_or_none()
    if row is None:
        raise EdaSourceUnavailable(
            "No complete canonical B02 EDA source snapshot is available"
        )
    return row


def _scope(row: RowMapping) -> dict[str, object]:
    return {
        "device_id": EDA_DEVICE_ID,
        "time_zone": EDA_TIME_ZONE,
        "period_kind": row["period_kind"],
        "from": format_historical_datetime(cast(datetime, row["from_ts"])),
        "to": format_historical_datetime(cast(datetime, row["to_ts"])),
    }


def _optional_instant(value: object) -> str | None:
    return (
        format_operational_instant(cast(datetime, value))
        if value is not None
        else None
    )


def _job_summary(row: RowMapping) -> EdaJobSummary:
    run_id = row.get("run_id")
    if row["status"] == "succeeded" and run_id is None:
        raise Conflict("The completed EDA job has no published run")
    return EdaJobSummary.model_validate(
        {
            "job_id": str(row["id"]),
            "logical_key": row["logical_key"],
            "scope": _scope(row),
            "source_sha256": row["source_sha256"],
            "algorithm_version": row["algorithm_version"],
            "config_hash": row["config_hash"],
            "status": row["status"],
            "trigger_kind": row["trigger_kind"],
            "attempt_count": row["attempt_count"],
            "max_attempts": row["max_attempts"],
            "terminal": row["terminal"],
            "created_at": format_operational_instant(
                cast(datetime, row["created_at"])
            ),
            "started_at": _optional_instant(row["started_at"]),
            "completed_at": _optional_instant(row["completed_at"]),
            "run_id": str(run_id) if run_id is not None else None,
            "error_code": row["error_code"],
            "error_detail": row["error_detail"],
        },
        strict=True,
    )


def _sample_counts(sections: Sequence[RowMapping]) -> dict[str, int]:
    quality = next(
        (
            row
            for row in sections
            if row["section"] == "quality_overview" and row["status"] == "complete"
        ),
        None,
    )
    payload = quality["payload"] if quality is not None else None
    source_audit = payload.get("source_audit") if isinstance(payload, Mapping) else None

    def count(field: str) -> int:
        value = source_audit.get(field) if isinstance(source_audit, Mapping) else None
        return value if type(value) is int and value >= 0 else 0

    return {
        "raw_rows": count("row_count"),
        "exact_pairs": count("exact_pair_count"),
        "screened_pairs": count("rule_screened_pair_count"),
        "active_pairs": count("rule_screened_pair_count"),
    }


def _section_fields(
    run: RowMapping,
    section: RowMapping,
    sample_counts: Mapping[str, int],
) -> dict[str, object]:
    period_kind = str(run["period_kind"])
    status = str(section["status"])
    return {
        "run_id": str(run["id"]),
        "section": section["section"],
        "status": status,
        "reason_code": section["reason_code"],
        "detail": (
            section["reason_detail"]
            if status != "complete"
            else f"Bagian EDA {section['section']} berhasil dihitung."
        ),
        "active_view": "rule_screened_pairs",
        "units": {
            "temperature": "°C",
            "relative_humidity": "%",
            "time": "second",
        },
        "sample_counts": dict(sample_counts),
        "algorithm_version": run["algorithm_version"],
        "config_hash": run["config_hash"],
        "source_sha256": run["source_sha256"],
        "range_boundary": {
            "from_censored": period_kind == "custom",
            "to_censored": period_kind == "custom",
            "from_open_ended": period_kind != "full_range",
            "to_open_ended": period_kind != "full_range",
        },
        "payload_sha256": section["payload_sha256"],
        "created_at": format_operational_instant(
            cast(datetime, section["created_at"])
        ),
    }


async def _run_summary(
    connection: AsyncConnection, run: RowMapping
) -> EdaRunSummary:
    sections = await get_sections(connection, run_id=cast(UUID, run["id"]))
    counts = _sample_counts(sections)
    canonical_release = cast(bool, run["canonical_release"])
    return EdaRunSummary.model_validate(
        {
            "run_id": str(run["id"]),
            "logical_key": run["logical_key"],
            "scope": _scope(run),
            "source_sha256": run["source_sha256"],
            "algorithm_version": run["algorithm_version"],
            "config_hash": run["config_hash"],
            "provenance_label": (
                "published v3 release"
                if canonical_release
                else "algorithm-equivalent range computation"
            ),
            "canonical_release": canonical_release,
            "completed_at": format_operational_instant(
                cast(datetime, run["completed_at"])
            ),
            "sections": [
                _section_fields(run, section, counts) for section in sections
            ],
        },
        strict=True,
    )


async def _enqueue_custom_job(
    connection: AsyncConnection,
    *,
    snapshot: RowMapping,
    request: EdaComputeRequest,
) -> tuple[EnqueueDisposition, RowMapping]:
    _ = await connection.scalar(
        select(func.pg_advisory_lock(_CUSTOM_COMPUTE_LOCK_ID))
    )
    try:
        from_ts = datetime.fromisoformat(request.from_ts)
        to_ts = datetime.fromisoformat(request.to_ts)
        logical_key = build_logical_key(
            source_sha256=EDA_SOURCE_SHA256,
            from_ts=from_ts,
            to_ts=to_ts,
            period_kind="custom",
            algorithm_version=EDA_ALGORITHM_VERSION,
            config_hash=EDA_CONFIG_HASH,
        )
        cached = await cache_lookup(connection, logical_key=logical_key)
        if cached is not None:
            return "cache_hit", cached

        active = (
            await connection.execute(
                select(*tables.eda_jobs.c).where(
                    tables.eda_jobs.c.logical_key == logical_key,
                    tables.eda_jobs.c.status.in_(("queued", "running")),
                )
            )
        ).mappings().one_or_none()
        if active is not None:
            return "active_job", active

        active_count = await connection.scalar(
            select(func.count())
            .select_from(tables.eda_jobs)
            .where(
                tables.eda_jobs.c.period_kind == "custom",
                tables.eda_jobs.c.status.in_(("queued", "running")),
            )
        )
        if (active_count or 0) >= _CUSTOM_JOB_LIMIT:
            raise EdaCapacityExceeded(
                "EDA custom compute capacity is full; retry after an active job finishes"
            )

        await connection.commit()
        return await enqueue_job(
            connection,
            snapshot_id=cast(UUID, snapshot["id"]),
            source_sha256=EDA_SOURCE_SHA256,
            from_ts=from_ts,
            to_ts=to_ts,
            period_kind="custom",
            algorithm_version=EDA_ALGORITHM_VERSION,
            config_hash=EDA_CONFIG_HASH,
            trigger_kind="api",
        )
    finally:
        if connection.in_transaction():
            await connection.rollback()
        _ = await connection.scalar(
            select(func.pg_advisory_unlock(_CUSTOM_COMPUTE_LOCK_ID))
        )
        await connection.commit()


@router.get("/api/eda/periods", response_model=EdaPeriodListResponse)
async def eda_periods(
    period_kind: Annotated[EdaPrecomputedPeriodKind, Query()],
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    cursor: Annotated[str | None, Query()] = None,
) -> EdaPeriodListResponse:
    try:
        query = EdaPeriodListQuery.model_validate(
            {"period_kind": period_kind, "limit": limit, "cursor": cursor},
            strict=True,
        )
    except ValueError as error:
        raise InvalidQuery(
            "Query parameters failed validation", {"cursor": ["Invalid cursor"]}
        ) from error
    _ = await _active_snapshot(connection)
    rows, next_cursor = await list_periods(
        connection,
        period_kind=query.period_kind,
        source_sha256=EDA_SOURCE_SHA256,
        algorithm_version=EDA_ALGORITHM_VERSION,
        config_hash=EDA_CONFIG_HASH,
        limit=query.limit,
        cursor=query.cursor,
    )
    items = [await _run_summary(connection, row) for row in rows]
    return EdaPeriodListResponse(
        request_id=new_request_id(),
        period_kind=query.period_kind,
        items=items,
        next_cursor=next_cursor,
        returned_count=len(items),
    )


@router.post(
    "/api/eda/compute",
    response_model=EdaComputeResponse,
    status_code=202,
    responses={200: {"model": EdaCacheHitResponse}},
)
async def eda_compute(
    request: EdaComputeRequest,
    response: Response,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> EdaCacheHitResponse | EdaQueuedComputeResponse:
    snapshot = await _active_snapshot(connection)
    disposition, row = await _enqueue_custom_job(
        connection, snapshot=snapshot, request=request
    )
    if disposition == "cache_hit":
        response.status_code = 200
        return EdaCacheHitResponse(
            request_id=new_request_id(),
            cache_hit=True,
            run=await _run_summary(connection, row),
        )
    return EdaQueuedComputeResponse(
        request_id=new_request_id(),
        cache_hit=False,
        job=_job_summary(row),
    )


@router.get("/api/eda/jobs/{job_id}", response_model=EdaJobResponse)
async def eda_job(
    job_id: UUID,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> EdaJobResponse:
    row = await get_job(connection, job_id=job_id)
    if row is None:
        raise NotFound("EDA job was not found")
    return EdaJobResponse(request_id=new_request_id(), job=_job_summary(row))


@router.get("/api/eda/runs/{run_id}", response_model=EdaRunResponse)
async def eda_run(
    run_id: UUID,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> EdaRunResponse:
    row = await get_run(connection, run_id=run_id)
    if row is None:
        raise NotFound("Published EDA run was not found")
    return EdaRunResponse(
        request_id=new_request_id(), run=await _run_summary(connection, row)
    )


@router.get(
    "/api/eda/runs/{run_id}/sections/{section}",
    response_model=EdaSection,
)
async def eda_section(
    run_id: UUID,
    section: EdaSectionName,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> EdaSection:
    run = await get_run(connection, run_id=run_id)
    if run is None:
        raise NotFound("Published EDA run was not found")
    sections = await get_sections(connection, run_id=run_id)
    row = next((item for item in sections if item["section"] == section), None)
    if row is None:
        raise NotFound("EDA run section was not found")
    fields = _section_fields(run, row, _sample_counts(sections))
    return _SECTION_ADAPTER.validate_python(
        {**fields, "payload": row["payload"]}, strict=True
    )
