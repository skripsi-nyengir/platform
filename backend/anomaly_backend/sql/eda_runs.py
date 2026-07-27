from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import and_, case, func, insert, or_, select, update
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.selectable import Subquery

from anomaly_backend import tables
from anomaly_backend.eda_contracts import (
    EDA_SECTION_NAMES,
    EdaPeriodKind,
    EdaSectionName,
    EdaTriggerKind,
)


EnqueueDisposition = Literal["cache_hit", "active_job", "enqueued"]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_logical_key(
    *,
    source_sha256: str,
    from_ts: datetime,
    to_ts: datetime,
    period_kind: EdaPeriodKind,
    algorithm_version: str,
    config_hash: str,
) -> str:
    canonical = json.dumps(
        (
            source_sha256,
            from_ts.isoformat(timespec="microseconds"),
            to_ts.isoformat(timespec="microseconds"),
            period_kind,
            algorithm_version,
            config_hash,
        ),
        ensure_ascii=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _published_run_ids() -> Subquery:
    return (
        select(tables.eda_result_sections.c.run_id)
        .group_by(tables.eda_result_sections.c.run_id)
        .having(
            func.count(func.distinct(tables.eda_result_sections.c.section))
            == len(EDA_SECTION_NAMES)
        )
        .subquery()
    )


async def cache_lookup(
    connection: AsyncConnection, *, logical_key: str
) -> RowMapping | None:
    published = _published_run_ids()
    return (
        await connection.execute(
            select(*tables.eda_runs.c)
            .join(published, published.c.run_id == tables.eda_runs.c.id)
            .where(tables.eda_runs.c.logical_key == logical_key)
        )
    ).mappings().one_or_none()


async def list_periods(
    connection: AsyncConnection,
    *,
    period_kind: Literal["daily", "weekly", "monthly"],
    source_sha256: str,
    algorithm_version: str,
    config_hash: str,
    limit: int,
    cursor: str | None = None,
) -> tuple[list[RowMapping], str | None]:
    if limit < 1:
        raise ValueError("limit must be positive")
    offset = 0
    if cursor is not None:
        prefix, separator, raw_offset = cursor.partition(":")
        if prefix != "eda-periods" or separator != ":" or not raw_offset.isdigit():
            raise ValueError("invalid EDA period cursor")
        offset = int(raw_offset)

    published = _published_run_ids()
    statement = (
        select(*tables.eda_runs.c)
        .join(published, published.c.run_id == tables.eda_runs.c.id)
        .join(
            tables.eda_source_snapshots,
            tables.eda_source_snapshots.c.id == tables.eda_runs.c.snapshot_id,
        )
        .where(
            tables.eda_source_snapshots.c.status == "complete",
            tables.eda_runs.c.period_kind == period_kind,
            tables.eda_runs.c.source_sha256 == source_sha256,
            tables.eda_runs.c.algorithm_version == algorithm_version,
            tables.eda_runs.c.config_hash == config_hash,
        )
        .order_by(
            tables.eda_runs.c.from_ts.desc(),
            tables.eda_runs.c.to_ts.desc(),
            tables.eda_runs.c.id.desc(),
        )
        .limit(limit + 1)
        .offset(offset)
    )
    rows = list((await connection.execute(statement)).mappings())
    next_cursor = (
        f"eda-periods:{offset + limit}" if len(rows) > limit else None
    )
    return rows[:limit], next_cursor


async def _active_job(
    connection: AsyncConnection, logical_key: str
) -> RowMapping | None:
    return (
        await connection.execute(
            select(*tables.eda_jobs.c).where(
                tables.eda_jobs.c.logical_key == logical_key,
                tables.eda_jobs.c.status.in_(("queued", "running")),
            )
        )
    ).mappings().one_or_none()


async def enqueue_job(
    connection: AsyncConnection,
    *,
    snapshot_id: UUID,
    source_sha256: str,
    from_ts: datetime,
    to_ts: datetime,
    period_kind: EdaPeriodKind,
    algorithm_version: str,
    config_hash: str,
    trigger_kind: EdaTriggerKind,
    max_attempts: int = 3,
) -> tuple[EnqueueDisposition, RowMapping]:
    logical_key = build_logical_key(
        source_sha256=source_sha256,
        from_ts=from_ts,
        to_ts=to_ts,
        period_kind=period_kind,
        algorithm_version=algorithm_version,
        config_hash=config_hash,
    )
    values = {
        "logical_key": logical_key,
        "snapshot_id": snapshot_id,
        "source_sha256": source_sha256,
        "from_ts": from_ts,
        "to_ts": to_ts,
        "period_kind": period_kind,
        "algorithm_version": algorithm_version,
        "config_hash": config_hash,
        "trigger_kind": trigger_kind,
        "max_attempts": max_attempts,
    }

    async with connection.begin():
        cached = await cache_lookup(connection, logical_key=logical_key)
        if cached is not None:
            return "cache_hit", cached

        active = await _active_job(connection, logical_key)
        if active is not None:
            return "active_job", active

        try:
            async with connection.begin_nested():
                queued = (
                    await connection.execute(
                        insert(tables.eda_jobs)
                        .values(**values)
                        .returning(*tables.eda_jobs.c)
                    )
                ).mappings().one()
        except IntegrityError as error:
            constraint_name = getattr(
                getattr(error.orig, "diag", None), "constraint_name", None
            )
            if constraint_name != "uq_eda_jobs_active_logical_key":
                raise
            active = await _active_job(connection, logical_key)
            if active is not None:
                return "active_job", active
            cached = await cache_lookup(connection, logical_key=logical_key)
            if cached is not None:
                return "cache_hit", cached
            raise
        return "enqueued", queued


async def get_job(
    connection: AsyncConnection, *, job_id: UUID
) -> RowMapping | None:
    published_ids = _published_run_ids()
    published_runs = (
        select(
            tables.eda_runs.c.id.label("run_id"),
            tables.eda_runs.c.logical_key,
        )
        .join(published_ids, published_ids.c.run_id == tables.eda_runs.c.id)
        .subquery()
    )
    return (
        await connection.execute(
            select(*tables.eda_jobs.c, published_runs.c.run_id)
            .outerjoin(
                published_runs,
                and_(
                    published_runs.c.logical_key
                    == tables.eda_jobs.c.logical_key,
                    tables.eda_jobs.c.status == "succeeded",
                ),
            )
            .where(tables.eda_jobs.c.id == job_id)
        )
    ).mappings().one_or_none()


async def claim_job(
    connection: AsyncConnection,
    *,
    lease_owner: str,
    lease_seconds: int,
) -> RowMapping | None:
    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")
    now = _utc_now()
    jobs = tables.eda_jobs
    async with connection.begin():
        exhausted = cast(
            UUID | None,
            (
                await connection.execute(
                select(jobs.c.id)
                .where(
                    jobs.c.status == "running",
                    jobs.c.lease_until < now,
                    jobs.c.attempt_count >= jobs.c.max_attempts,
                )
                .order_by(jobs.c.created_at.asc(), jobs.c.id.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
                )
            ).scalar_one_or_none(),
        )
        if exhausted is not None:
            _ = await connection.execute(
                update(jobs)
                .where(jobs.c.id == exhausted)
                .values(
                    status="failed",
                    terminal=True,
                    completed_at=now,
                    lease_owner=None,
                    lease_until=None,
                    error_code="max_attempts_exhausted",
                    error_detail="EDA computation exhausted its retry budget",
                )
            )

        candidate = cast(
            UUID | None,
            (
                await connection.execute(
                select(jobs.c.id)
                .where(
                    or_(
                        jobs.c.status == "queued",
                        and_(
                            jobs.c.status == "running",
                            jobs.c.lease_until < now,
                            jobs.c.attempt_count < jobs.c.max_attempts,
                        ),
                    )
                )
                .order_by(jobs.c.created_at.asc(), jobs.c.id.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
                )
            ).scalar_one_or_none(),
        )
        if candidate is None:
            return None
        return (
            await connection.execute(
                update(jobs)
                .where(jobs.c.id == candidate)
                .values(
                    status="running",
                    attempt_count=jobs.c.attempt_count + 1,
                    lease_owner=lease_owner,
                    lease_until=now + timedelta(seconds=lease_seconds),
                    started_at=func.coalesce(jobs.c.started_at, now),
                    error_code=None,
                    error_detail=None,
                )
                .returning(*jobs.c)
            )
        ).mappings().one()


async def renew_lease(
    connection: AsyncConnection,
    *,
    job_id: UUID,
    lease_owner: str,
    attempt_count: int,
    lease_seconds: int,
) -> RowMapping | None:
    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")
    now = _utc_now()
    jobs = tables.eda_jobs
    async with connection.begin():
        return (
            await connection.execute(
                update(jobs)
                .where(
                    jobs.c.id == job_id,
                    jobs.c.status == "running",
                    jobs.c.lease_owner == lease_owner,
                    jobs.c.attempt_count == attempt_count,
                    jobs.c.lease_until >= now,
                )
                .values(lease_until=now + timedelta(seconds=lease_seconds))
                .returning(*jobs.c)
            )
        ).mappings().one_or_none()


async def release_job(
    connection: AsyncConnection,
    *,
    job_id: UUID,
    lease_owner: str,
    attempt_count: int,
) -> RowMapping | None:
    now = _utc_now()
    jobs = tables.eda_jobs
    async with connection.begin():
        return (
            await connection.execute(
                update(jobs)
                .where(
                    jobs.c.id == job_id,
                    jobs.c.status == "running",
                    jobs.c.lease_owner == lease_owner,
                    jobs.c.attempt_count == attempt_count,
                    jobs.c.lease_until >= now,
                )
                .values(
                    status="queued",
                    lease_owner=None,
                    lease_until=None,
                    error_code=None,
                    error_detail=None,
                )
                .returning(*jobs.c)
            )
        ).mappings().one_or_none()


async def complete_job(
    connection: AsyncConnection,
    *,
    job_id: UUID,
    lease_owner: str,
    attempt_count: int,
    provenance: Mapping[str, object],
    canonical_release: bool,
    sections: Sequence[Mapping[str, object]],
) -> tuple[RowMapping, RowMapping] | None:
    section_names = [item.get("section") for item in sections]
    if (
        len(section_names) != len(EDA_SECTION_NAMES)
        or len(set(section_names)) != len(EDA_SECTION_NAMES)
        or set(section_names) != set(EDA_SECTION_NAMES)
    ):
        raise ValueError("publication requires all eleven EDA sections exactly once")

    now = _utc_now()
    jobs = tables.eda_jobs
    async with connection.begin():
        owned = (
            await connection.execute(
                select(*jobs.c)
                .where(
                    jobs.c.id == job_id,
                    jobs.c.status == "running",
                    jobs.c.lease_owner == lease_owner,
                    jobs.c.attempt_count == attempt_count,
                    jobs.c.lease_until >= now,
                )
                .with_for_update()
            )
        ).mappings().one_or_none()
        if owned is None:
            return None

        run = (
            await connection.execute(
                insert(tables.eda_runs)
                .values(
                    logical_key=owned["logical_key"],
                    snapshot_id=owned["snapshot_id"],
                    source_sha256=owned["source_sha256"],
                    from_ts=owned["from_ts"],
                    to_ts=owned["to_ts"],
                    period_kind=owned["period_kind"],
                    algorithm_version=owned["algorithm_version"],
                    config_hash=owned["config_hash"],
                    provenance=dict(provenance),
                    canonical_release=canonical_release,
                    completed_at=now,
                )
                .returning(*tables.eda_runs.c)
            )
        ).mappings().one()
        complete_sections: list[dict[str, object]] = []
        diagnostic_sections: list[dict[str, object]] = []
        for item in sections:
            section_value: dict[str, object] = {
                "run_id": run["id"],
                "section": item["section"],
                "status": item["status"],
                "created_at": item.get("created_at", now),
            }
            if item["status"] == "complete":
                section_value.update(
                    payload=item.get("payload"),
                    payload_sha256=item.get("payload_sha256"),
                )
                complete_sections.append(section_value)
            else:
                section_value.update(
                    reason_code=item.get("reason_code"),
                    reason_detail=item.get(
                        "reason_detail", item.get("detail")
                    ),
                )
                diagnostic_sections.append(section_value)
        for section_values in (complete_sections, diagnostic_sections):
            if section_values:
                _ = await connection.execute(
                    insert(tables.eda_result_sections), section_values
                )
        completed = (
            await connection.execute(
                update(jobs)
                .where(
                    jobs.c.id == job_id,
                    jobs.c.status == "running",
                    jobs.c.lease_owner == lease_owner,
                    jobs.c.attempt_count == attempt_count,
                    jobs.c.lease_until >= now,
                )
                .values(
                    status="succeeded",
                    terminal=True,
                    completed_at=now,
                    lease_owner=None,
                    lease_until=None,
                    error_code=None,
                    error_detail=None,
                )
                .returning(*jobs.c)
            )
        ).mappings().one_or_none()
        if completed is None:
            raise RuntimeError("EDA lease ownership was lost during publication")
        return run, completed


async def fail_job(
    connection: AsyncConnection,
    *,
    job_id: UUID,
    lease_owner: str,
    attempt_count: int,
    error_code: str,
    error_detail: str,
) -> RowMapping | None:
    if not error_code or not error_detail:
        raise ValueError("terminal EDA failures require an error code and detail")
    now = _utc_now()
    jobs = tables.eda_jobs
    async with connection.begin():
        return (
            await connection.execute(
                update(jobs)
                .where(
                    jobs.c.id == job_id,
                    jobs.c.status == "running",
                    jobs.c.lease_owner == lease_owner,
                    jobs.c.attempt_count == attempt_count,
                    jobs.c.lease_until >= now,
                )
                .values(
                    status="failed",
                    terminal=True,
                    completed_at=now,
                    lease_owner=None,
                    lease_until=None,
                    error_code=error_code,
                    error_detail=error_detail,
                )
                .returning(*jobs.c)
            )
        ).mappings().one_or_none()


async def get_run(
    connection: AsyncConnection, *, run_id: UUID
) -> RowMapping | None:
    published = _published_run_ids()
    return (
        await connection.execute(
            select(*tables.eda_runs.c)
            .join(published, published.c.run_id == tables.eda_runs.c.id)
            .where(tables.eda_runs.c.id == run_id)
        )
    ).mappings().one_or_none()


async def get_sections(
    connection: AsyncConnection,
    *,
    run_id: UUID,
    section: EdaSectionName | None = None,
) -> list[RowMapping]:
    published = _published_run_ids()
    section_order = case(
        {name: position for position, name in enumerate(EDA_SECTION_NAMES)},
        value=tables.eda_result_sections.c.section,
        else_=len(EDA_SECTION_NAMES),
    )
    statement = (
        select(*tables.eda_result_sections.c)
        .join(
            tables.eda_runs,
            tables.eda_runs.c.id == tables.eda_result_sections.c.run_id,
        )
        .join(published, published.c.run_id == tables.eda_runs.c.id)
        .where(tables.eda_runs.c.id == run_id)
        .order_by(section_order)
    )
    if section is not None:
        statement = statement.where(
            tables.eda_result_sections.c.section == section
        )
    return list((await connection.execute(statement)).mappings())
