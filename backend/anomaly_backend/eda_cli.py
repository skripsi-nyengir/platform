from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence
from datetime import datetime, timedelta
import json
import sys
from typing import Literal, cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.eda_contracts import (
    EDA_ALGORITHM_VERSION,
    EDA_CONFIG_HASH,
    EDA_DATASET_ID,
    EDA_DEVICE_ID,
    EDA_SOURCE_SHA256,
    EDA_SOURCE_FROM,
    EDA_SOURCE_TO,
    EDA_TIME_ZONE,
    EdaPrecomputedPeriodKind,
    EdaScope,
    enumerate_precomputed_periods,
)
from anomaly_backend.sql.eda_runs import enqueue_job


BackfillKind = Literal["daily", "weekly", "monthly", "all"]
COUNTER_NAMES = (
    "cache_hits",
    "active_jobs",
    "enqueued",
    "skipped_open",
    "skipped_outside_source",
    "errors",
)
EXACT_COMMAND = (
    "docker compose --profile ops run --rm eda-cli backfill --kind all "
    "--from 2025-06-23T00:00:00 --to 2026-07-24T09:02:05 --json"
)


class EdaCliError(RuntimeError):
    pass


def enumerate_periods(
    kind: str, from_ts: datetime, to_ts: datetime
) -> list[tuple[datetime, datetime, EdaPrecomputedPeriodKind]]:
    return enumerate_precomputed_periods(kind, from_ts, to_ts)


async def _canonical_snapshot(engine: AsyncEngine) -> dict[str, object]:
    source_from = datetime.fromisoformat(EDA_SOURCE_FROM)
    source_to_inclusive = datetime.fromisoformat(EDA_SOURCE_TO) - timedelta(seconds=1)
    async with engine.connect() as connection:
        row = (
            await connection.execute(
                select(*tables.eda_source_snapshots.c).where(
                    tables.eda_source_snapshots.c.dataset_id == EDA_DATASET_ID,
                    tables.eda_source_snapshots.c.source_sha256
                    == EDA_SOURCE_SHA256,
                    tables.eda_source_snapshots.c.source_from_ts == source_from,
                    tables.eda_source_snapshots.c.source_to_ts == source_to_inclusive,
                    tables.eda_source_snapshots.c.expected_channel_count == 2,
                    tables.eda_source_snapshots.c.status == "complete",
                )
            )
        ).mappings().one_or_none()
    if row is None:
        raise EdaCliError("no complete canonical EDA source snapshot is available")
    return dict(row)


async def backfill(
    engine: AsyncEngine,
    *,
    kind: str,
    from_ts: datetime,
    to_ts: datetime,
) -> dict[str, int]:
    if from_ts >= to_ts:
        raise EdaCliError("--from must be earlier than --to")
    snapshot = await _canonical_snapshot(engine)
    source_from = cast(datetime, snapshot["source_from_ts"])
    source_to = cast(datetime, snapshot["source_to_ts"]) + timedelta(seconds=1)
    counters = {name: 0 for name in COUNTER_NAMES}
    logical_periods: set[tuple[datetime, datetime, str]] = set()

    async with engine.connect() as connection:
        for period_from, period_to, period_kind in enumerate_periods(
            kind, from_ts, to_ts
        ):
            logical_period = (period_from, period_to, period_kind)
            if logical_period in logical_periods:
                continue
            logical_periods.add(logical_period)
            if period_from < source_from or period_from >= source_to:
                counters["skipped_outside_source"] += 1
                continue
            if period_from < from_ts or period_to > to_ts:
                counters["skipped_open"] += 1
                continue
            if period_to > source_to:
                counters["skipped_outside_source"] += 1
                continue

            _ = EdaScope.model_validate(
                {
                    "device_id": EDA_DEVICE_ID,
                    "time_zone": EDA_TIME_ZONE,
                    "period_kind": period_kind,
                    "from": period_from.isoformat(timespec="seconds"),
                    "to": period_to.isoformat(timespec="seconds"),
                }
            )
            try:
                disposition, _ = await enqueue_job(
                    connection,
                    snapshot_id=cast(UUID, snapshot["id"]),
                    source_sha256=cast(str, snapshot["source_sha256"]),
                    from_ts=period_from,
                    to_ts=period_to,
                    period_kind=period_kind,
                    algorithm_version=EDA_ALGORITHM_VERSION,
                    config_hash=EDA_CONFIG_HASH,
                    trigger_kind="backfill",
                )
            except SQLAlchemyError:
                counters["errors"] += 1
                continue
            counters[
                {
                    "cache_hit": "cache_hits",
                    "active_job": "active_jobs",
                    "enqueued": "enqueued",
                }[disposition]
            ] += 1
    return counters


def _historical_datetime(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "expected naive second-precision YYYY-MM-DDTHH:MM:SS"
        ) from error
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eda-cli",
        description="Enqueue closed Asia/Jakarta EDA precompute periods.",
        epilog=f"Exact full backfill command:\n  {EXACT_COMMAND}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "backfill",
        help="enqueue closed daily, ISO-weekly, or monthly periods",
        description="Enqueue closed Asia/Jakarta EDA precompute periods.",
        epilog=f"Exact full backfill command:\n  {EXACT_COMMAND}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _ = command.add_argument(
        "--kind",
        choices=("daily", "weekly", "monthly", "all"),
        required=True,
    )
    _ = command.add_argument("--from", dest="from_ts", type=_historical_datetime, required=True)
    _ = command.add_argument("--to", dest="to_ts", type=_historical_datetime, required=True)
    _ = command.add_argument("--json", action="store_true", dest="as_json")
    return parser


async def _run(arguments: argparse.Namespace) -> dict[str, int]:
    kind = cast(str, arguments.kind)
    from_ts = cast(datetime, arguments.from_ts)
    to_ts = cast(datetime, arguments.to_ts)
    engine = create_database_engine(Settings.from_environ())
    try:
        return await backfill(
            engine,
            kind=kind,
            from_ts=from_ts,
            to_ts=to_ts,
        )
    finally:
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    from_ts = cast(datetime, arguments.from_ts)
    to_ts = cast(datetime, arguments.to_ts)
    if from_ts >= to_ts:
        print("eda-cli: --from must be earlier than --to", file=sys.stderr)
        return 2
    try:
        counters = asyncio.run(_run(arguments))
    except (EdaCliError, KeyError, ValueError, SQLAlchemyError) as error:
        print(f"eda-cli: {error}", file=sys.stderr)
        return 2
    if cast(bool, arguments.as_json):
        print(json.dumps(counters, separators=(",", ":")))
    else:
        for name in COUNTER_NAMES:
            print(f"{name}: {counters[name]}")
    return 1 if counters["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
