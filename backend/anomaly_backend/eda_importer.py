from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from anomaly_backend.config import Settings
from anomaly_eda.config import CONFIG_HASH


DATASET_ID = "bivariate_b02f3872_v1"
DEVICE_ID = "b02f3872-39a2-4b6f-a4ec-045a287fde4b"
EXPECTED_HEADER = (
    "device_id",
    "data_index",
    "value",
    "timestamp",
    "is_connected",
)
EXPECTED_ORDER = (
    "timestamp",
    "data_index",
    "value",
    "is_connected",
    "device_id",
)
SOURCE_FROM = datetime(2025, 6, 23)
SOURCE_TO = datetime(2026, 7, 24, 9, 2, 4)
CANONICAL_SOURCE_SHA256 = (
    "b8ae739a427681735792f02eea14dd8b7fc53f5265630a7e9a62b846f7b8040f"
)
CANONICAL_MANIFEST_SHA256 = (
    "196178e7424bd2e92268606f0ef33237d2329bdfefd9dce592283c07a697d486"
)
CANONICAL_SIZE_BYTES = 532_396_136
CANONICAL_ROW_COUNT = 6_931_792
CANONICAL_ROWS_PER_CHANNEL = 3_465_896
IMPORTER_VERSION = "eda-raw-import-v1"
IMPORT_LOCK_ID = 20_260_726_6006
DEFAULT_BATCH_SIZE = 10_000
MAX_MANIFEST_BYTES = 1024 * 1024
MAX_CSV_LINE_BYTES = 1024 * 1024
MAX_SOURCE_BYTES = 1024 * 1024 * 1024
_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
class EdaImportError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SourceContract:
    dataset_id: str
    source_sha256: str
    manifest_sha256: str
    size_bytes: int
    row_count: int
    rows_per_channel: dict[int, int]
    source_from: datetime
    source_to: datetime
    manifest: dict[str, Any]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _manifest_timestamp(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not _TIMESTAMP.fullmatch(value):
        raise EdaImportError(f"manifest {field} must be a naive second-precision timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise EdaImportError(f"manifest {field} is invalid") from error
    if parsed.tzinfo is not None or parsed.microsecond:
        raise EdaImportError(f"manifest {field} must be a naive second-precision timestamp")
    return parsed


def _load_contract(
    manifest_path: Path,
    expected_manifest_sha256: str,
) -> SourceContract:
    if not _SHA256.fullmatch(expected_manifest_sha256):
        raise EdaImportError("expected manifest SHA-256 is invalid")
    try:
        descriptor = os.open(
            manifest_path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as error:
        raise EdaImportError("source manifest could not be opened") from error
    try:
        with os.fdopen(descriptor, "rb") as handle:
            metadata = os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode):
                raise EdaImportError("source manifest is not a regular file")
            if metadata.st_size > MAX_MANIFEST_BYTES:
                raise EdaImportError("source manifest exceeds the size limit")
            encoded = handle.read(MAX_MANIFEST_BYTES + 1)
    except OSError as error:
        raise EdaImportError("source manifest could not be read") from error
    if len(encoded) > MAX_MANIFEST_BYTES:
        raise EdaImportError("source manifest exceeds the size limit")
    manifest_sha256 = _sha256_bytes(encoded)
    if manifest_sha256 != expected_manifest_sha256:
        raise EdaImportError(
            "manifest SHA-256 mismatch: "
            f"expected={expected_manifest_sha256} actual={manifest_sha256}"
        )
    try:
        loaded = json.loads(encoded)
        if not isinstance(loaded, dict):
            raise TypeError
        manifest = cast(dict[str, Any], loaded)
        artifact = manifest["artifact"]
        source = manifest["source"]
        device = manifest["device"]
        if not all(isinstance(item, dict) for item in (artifact, source, device)):
            raise TypeError
        artifact = cast(dict[str, Any], artifact)
        source = cast(dict[str, Any], source)
        device = cast(dict[str, Any], device)
        artifact_bounds = artifact["bounds"]
        cutoff = source["cutoff"]
        per_index = artifact["per_index"]
        indices = device["indices"]
        if not all(
            isinstance(item, dict)
            for item in (artifact_bounds, cutoff, per_index, indices)
        ):
            raise TypeError
        artifact_bounds = cast(dict[str, Any], artifact_bounds)
        cutoff = cast(dict[str, Any], cutoff)
        per_index = cast(dict[str, Any], per_index)
        indices = cast(dict[str, Any], indices)
        dataset_id = manifest["dataset_id"]
        source_sha256 = artifact["sha256"]
        size_bytes = artifact["size_bytes"]
        row_count = artifact["row_count"]
        index_payloads = tuple(per_index[str(index)] for index in (0, 1))
        if not all(isinstance(item, dict) for item in index_payloads):
            raise TypeError
        row_values = tuple(
            cast(dict[str, Any], item)["rows"] for item in index_payloads
        )
        if not all(type(value) is int for value in row_values):
            raise TypeError
        header = source["header"]
        order_by = source["order_by"]
        if not all(
            isinstance(item, list)
            and all(isinstance(value, str) for value in item)
            for item in (header, order_by)
        ):
            raise TypeError
        rows_per_channel: dict[int, int] = dict(
            zip((0, 1), cast(tuple[int, int], row_values))
        )
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        raise EdaImportError("source manifest structure is invalid") from error
    source_from = _manifest_timestamp(artifact_bounds.get("start"), "start")
    source_to = _manifest_timestamp(artifact_bounds.get("cutoff"), "cutoff")
    try:
        index_maxima = tuple(
            _manifest_timestamp(cutoff["per_index_max"][str(index)], "index cutoff")
            for index in (0, 1)
        )
        literal_cutoff = _manifest_timestamp(
            cutoff["literal_inclusive"], "literal cutoff"
        )
    except (KeyError, TypeError) as error:
        raise EdaImportError("source manifest cutoff is invalid") from error
    valid = (
        manifest.get("schema_version") == "bivariate_b02f3872_source_v1"
        and isinstance(dataset_id, str)
        and bool(dataset_id)
        and device.get("id") == DEVICE_ID
        and set(indices) == {"0", "1"}
        and tuple(header) == EXPECTED_HEADER
        and tuple(order_by) == EXPECTED_ORDER
        and source.get("timezone") == "Asia/Jakarta"
        and source.get("table") == "default.sensor_data"
        and source.get("start_inclusive") == SOURCE_FROM.isoformat(sep=" ")
        and cutoff.get("method") == "min_of_two_per_index_maxima"
        and literal_cutoff == min(index_maxima)
        and artifact_bounds.get("inclusive") is True
        and artifact_bounds.get("timezone") == "Asia/Jakarta"
        and source_from == SOURCE_FROM
        and source_to == SOURCE_TO
        and literal_cutoff == SOURCE_TO
        and isinstance(source_sha256, str)
        and _SHA256.fullmatch(source_sha256) is not None
        and type(size_bytes) is int
        and 0 < size_bytes <= MAX_SOURCE_BYTES
        and type(row_count) is int
        and row_count > 0
        and set(per_index) == {"0", "1"}
        and all(rows_per_channel[index] > 0 for index in (0, 1))
        and sum(rows_per_channel.values()) == row_count
        and (
            expected_manifest_sha256 != CANONICAL_MANIFEST_SHA256
            or (
                dataset_id == DATASET_ID
                and source_sha256 == CANONICAL_SOURCE_SHA256
                and size_bytes == CANONICAL_SIZE_BYTES
                and row_count == CANONICAL_ROW_COUNT
                and rows_per_channel
                == {0: CANONICAL_ROWS_PER_CHANNEL, 1: CANONICAL_ROWS_PER_CHANNEL}
            )
        )
    )
    if not valid:
        raise EdaImportError("source manifest contract is invalid or divergent")
    return SourceContract(
        dataset_id=dataset_id,
        source_sha256=source_sha256,
        manifest_sha256=manifest_sha256,
        size_bytes=size_bytes,
        row_count=row_count,
        rows_per_channel=rows_per_channel,
        source_from=source_from,
        source_to=source_to,
        manifest=manifest,
    )


def _connection_string(settings: Settings) -> str:
    return (
        f"host={settings.postgres_host} port={settings.postgres_port} "
        f"dbname={settings.postgres_db} user={settings.postgres_user} "
        f"password={settings.postgres_password}"
    )


def _rollback_preserving(
    connection: psycopg.Connection[dict[str, Any]],
    error: Exception,
    context: str,
) -> None:
    try:
        connection.rollback()
    except Exception as rollback_error:
        error.add_note(f"{context}: {rollback_error}")


def _parse_timestamp(value: str, line_number: int) -> datetime:
    if not _TIMESTAMP.fullmatch(value):
        raise EdaImportError(
            f"timestamp must be naive and second-precision at line {line_number}"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise EdaImportError(f"invalid timestamp at line {line_number}") from error
    if parsed.tzinfo is not None or parsed.microsecond:
        raise EdaImportError(
            f"timestamp must be naive and second-precision at line {line_number}"
        )
    return parsed


def _parse_connected(value: str, line_number: int) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true"}:
        return True
    if normalized in {"0", "false"}:
        return False
    raise EdaImportError(f"invalid is_connected value at line {line_number}")


def _numeric_order(value: Decimal) -> tuple[int, Decimal]:
    if value.is_nan():
        return 3, Decimal(0)
    if value == Decimal("-Infinity"):
        return 0, Decimal(0)
    if value == Decimal("Infinity"):
        return 2, Decimal(0)
    return 1, value


def _insert_batch(
    connection: psycopg.Connection[dict[str, Any]],
    rows: list[tuple[Any, ...]],
) -> None:
    with connection.cursor().copy(
        """
        COPY eda_raw_readings (
            snapshot_id, source_row_number, device_id, data_index,
            value, ts, is_connected
        ) FROM STDIN
        """
    ) as copy:
        for row in rows:
            copy.write_row(row)
    connection.commit()


def _stream_source(
    connection: psycopg.Connection[dict[str, Any]],
    source_path: Path,
    snapshot_id: str,
    contract: SourceContract,
    batch_size: int,
) -> tuple[int, str, int]:
    if source_path.name != contract.manifest["artifact"].get("path"):
        raise EdaImportError("source filename does not match the manifest")
    digest = hashlib.sha256()
    bytes_read = 0
    row_count = 0
    channel_counts = {0: 0, 1: 0}
    previous_key: tuple[Any, ...] | None = None
    batch: list[tuple[Any, ...]] = []

    try:
        descriptor = os.open(
            source_path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as error:
        raise EdaImportError("source CSV could not be opened") from error
    try:
        binary = os.fdopen(descriptor, "rb")
    except Exception:
        os.close(descriptor)
        raise
    with binary:
        metadata = os.fstat(binary.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise EdaImportError("source CSV is not a regular file")
        actual_size = metadata.st_size
        if actual_size != contract.size_bytes:
            raise EdaImportError(
                f"source size mismatch: expected={contract.size_bytes} actual={actual_size}"
            )

        def decoded_lines() -> Any:
            nonlocal bytes_read
            while raw_line := binary.readline(MAX_CSV_LINE_BYTES + 1):
                if len(raw_line) > MAX_CSV_LINE_BYTES:
                    raise EdaImportError("source CSV row exceeds the size limit")
                digest.update(raw_line)
                bytes_read += len(raw_line)
                if bytes_read > contract.size_bytes:
                    raise EdaImportError("streamed source exceeds the manifest size")
                try:
                    yield raw_line.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise EdaImportError("source CSV is not valid UTF-8") from error

        reader = csv.reader(decoded_lines())
        try:
            header = tuple(next(reader))
        except StopIteration as error:
            raise EdaImportError("source CSV is empty") from error
        if header != EXPECTED_HEADER:
            raise EdaImportError(
                f"source header mismatch: expected={EXPECTED_HEADER} actual={header}"
            )
        for source_row_number, row in enumerate(reader, start=1):
            line_number = source_row_number + 1
            if len(row) != len(EXPECTED_HEADER):
                raise EdaImportError(f"malformed CSV row at line {line_number}")
            device_id, index_text, value_text, timestamp_text, connected_text = row
            if device_id != DEVICE_ID:
                raise EdaImportError(f"wrong device_id at line {line_number}")
            try:
                data_index = int(index_text)
            except ValueError as error:
                raise EdaImportError(
                    f"invalid data_index at line {line_number}"
                ) from error
            if data_index not in (0, 1):
                raise EdaImportError(
                    f"unexpected data_index at line {line_number}: {data_index}"
                )
            timestamp = _parse_timestamp(timestamp_text, line_number)
            if not contract.source_from <= timestamp <= contract.source_to:
                raise EdaImportError(
                    f"timestamp outside inclusive bounds at line {line_number}"
                )
            try:
                decimal_value = Decimal(value_text.strip())
                value = float(decimal_value)
            except (InvalidOperation, ValueError) as error:
                raise EdaImportError(f"invalid value at line {line_number}") from error
            connected = _parse_connected(connected_text, line_number)
            order_key = (
                timestamp,
                data_index,
                _numeric_order(decimal_value),
                connected,
                device_id,
            )
            if previous_key is not None and order_key < previous_key:
                raise EdaImportError(
                    f"source is not sorted by {EXPECTED_ORDER} at line {line_number}"
                )
            previous_key = order_key
            row_count += 1
            channel_counts[data_index] += 1
            batch.append(
                (
                    snapshot_id,
                    source_row_number,
                    device_id,
                    data_index,
                    value,
                    timestamp,
                    connected,
                )
            )
            if len(batch) == batch_size:
                _insert_batch(connection, batch)
                batch.clear()
        if batch:
            _insert_batch(connection, batch)

    actual_sha256 = digest.hexdigest()
    if bytes_read != contract.size_bytes:
        raise EdaImportError(
            f"streamed source size mismatch: expected={contract.size_bytes} actual={bytes_read}"
        )
    if actual_sha256 != contract.source_sha256:
        raise EdaImportError(
            "source SHA-256 mismatch: "
            f"expected={contract.source_sha256} actual={actual_sha256}"
        )
    if row_count != contract.row_count:
        raise EdaImportError(
            f"source row count mismatch: expected={contract.row_count} actual={row_count}"
        )
    if channel_counts != contract.rows_per_channel:
        raise EdaImportError(
            "source per-channel row counts mismatch: "
            f"expected={contract.rows_per_channel} actual={channel_counts}"
        )
    return row_count, actual_sha256, bytes_read


def _result(
    snapshot_id: str,
    contract: SourceContract,
    *,
    idempotent_noop: bool,
) -> dict[str, Any]:
    return {
        "snapshot_id": str(snapshot_id),
        "dataset_id": contract.dataset_id,
        "source_sha256": contract.source_sha256,
        "status": "complete",
        "row_count": contract.row_count,
        "idempotent_noop": idempotent_noop,
    }


def import_eda_source(
    source_path: Path,
    manifest_path: Path,
    *,
    expected_manifest_sha256: str = CANONICAL_MANIFEST_SHA256,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> dict[str, Any]:
    if batch_size <= 0:
        raise EdaImportError("batch_size must be positive")
    source_path = Path(source_path)
    contract = _load_contract(Path(manifest_path), expected_manifest_sha256)
    settings = Settings.from_environ()
    connection = cast(
        psycopg.Connection[dict[str, Any]],
        psycopg.connect(
            _connection_string(settings),
            row_factory=dict_row,  # pyright: ignore[reportArgumentType]
            autocommit=False,
        ),
    )
    snapshot_id: str | None = None
    owns_staging_snapshot = False
    lock_acquired = False
    try:
        connection.execute("SELECT pg_advisory_lock(%s)", (IMPORT_LOCK_ID,))
        connection.commit()
        lock_acquired = True
        idempotent_result: dict[str, Any] | None = None
        with connection.transaction():
            existing = connection.execute(
                """
                SELECT id, status, manifest_sha256, config_hash,
                       source_from_ts, source_to_ts, expected_row_count,
                       expected_channel_count, importer_version
                FROM eda_source_snapshots
                WHERE dataset_id = %s AND source_sha256 = %s
                """,
                (contract.dataset_id, contract.source_sha256),
            ).fetchone()
            if existing is not None:
                snapshot_id = str(existing["id"])
                identity_matches = (
                    existing["manifest_sha256"] == contract.manifest_sha256
                    and existing["config_hash"] == CONFIG_HASH
                    and existing["source_from_ts"] == contract.source_from
                    and existing["source_to_ts"] == contract.source_to
                    and int(existing["expected_row_count"]) == contract.row_count
                    and int(existing["expected_channel_count"]) == 2
                    and existing["importer_version"] == IMPORTER_VERSION
                )
                if not identity_matches:
                    raise EdaImportError(
                        "existing snapshot identity has divergent immutable metadata"
                    )
                if existing["status"] == "complete":
                    stored = connection.execute(
                        "SELECT count(*) AS count FROM eda_raw_readings "
                        "WHERE snapshot_id = %s",
                        (snapshot_id,),
                    ).fetchone()
                    if stored is None or int(stored["count"]) != contract.row_count:
                        raise EdaImportError(
                            "complete snapshot raw row count is inconsistent"
                        )
                    idempotent_result = _result(
                        snapshot_id, contract, idempotent_noop=True
                    )
                else:
                    owns_staging_snapshot = True
                    connection.execute(
                        "DELETE FROM eda_raw_readings WHERE snapshot_id = %s",
                        (snapshot_id,),
                    )
                    connection.execute(
                        """
                        UPDATE eda_source_snapshots
                        SET status = 'staging', completed_at = NULL
                        WHERE id = %s AND status IN ('staging', 'failed')
                        """,
                        (snapshot_id,),
                    )
            else:
                created = connection.execute(
                    """
                    INSERT INTO eda_source_snapshots (
                        dataset_id, source_sha256, manifest_sha256, config_hash,
                        source_from_ts, source_to_ts, expected_row_count,
                        expected_channel_count, importer_version, status, manifest
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, 2, %s, 'staging', %s::jsonb
                    )
                    RETURNING id
                    """,
                    (
                        contract.dataset_id,
                        contract.source_sha256,
                        contract.manifest_sha256,
                        CONFIG_HASH,
                        contract.source_from,
                        contract.source_to,
                        contract.row_count,
                        IMPORTER_VERSION,
                        json.dumps(contract.manifest, allow_nan=False),
                    ),
                ).fetchone()
                if created is None:
                    raise EdaImportError("snapshot staging row could not be created")
                snapshot_id = str(created["id"])
                owns_staging_snapshot = True

        if idempotent_result is not None:
            return idempotent_result

        _stream_source(
            connection,
            source_path,
            snapshot_id,
            contract,
            batch_size,
        )
        with connection.transaction():
            stored = connection.execute(
                "SELECT count(*) AS count FROM eda_raw_readings WHERE snapshot_id = %s",
                (snapshot_id,),
            ).fetchone()
            if stored is None or int(stored["count"]) != contract.row_count:
                raise EdaImportError(
                    "staged raw row count does not match the validated source"
                )
            completed = connection.execute(
                """
                UPDATE eda_source_snapshots
                SET status = 'complete', completed_at = %s
                WHERE id = %s AND status = 'staging'
                RETURNING id
                """,
                (datetime.now(timezone.utc), snapshot_id),
            ).fetchone()
            if completed is None:
                raise EdaImportError(
                    "snapshot staging ownership was lost before publication"
                )
        owns_staging_snapshot = False
        return _result(snapshot_id, contract, idempotent_noop=False)
    except Exception as error:
        _rollback_preserving(connection, error, "failed to roll back EDA import")
        if snapshot_id is not None and owns_staging_snapshot:
            try:
                with connection.transaction():
                    connection.execute(
                        "DELETE FROM eda_raw_readings WHERE snapshot_id = %s",
                        (snapshot_id,),
                    )
                    connection.execute(
                        """
                        UPDATE eda_source_snapshots
                        SET status = 'failed', completed_at = %s
                        WHERE id = %s AND status IN ('staging', 'failed')
                        """,
                        (datetime.now(timezone.utc), snapshot_id),
                    )
            except Exception as cleanup_error:
                _rollback_preserving(
                    connection,
                    error,
                    "failed to roll back EDA cleanup",
                )
                error.add_note(f"failed to clean staged EDA rows: {cleanup_error}")
        raise
    finally:
        if lock_acquired:
            try:
                connection.execute(
                    "SELECT pg_advisory_unlock(%s)", (IMPORT_LOCK_ID,)
                )
                connection.commit()
            except Exception as unlock_error:
                _rollback_preserving(
                    connection,
                    unlock_error,
                    "failed to roll back EDA advisory unlock",
                )
        connection.close()


def main() -> int:
    source = os.environ.get("EDA_RAW_SOURCE_PATH")
    manifest = os.environ.get("EDA_SOURCE_MANIFEST_PATH")
    if not source or not manifest:
        print(
            "eda-import: EDA_RAW_SOURCE_PATH and EDA_SOURCE_MANIFEST_PATH are required",
            file=sys.stderr,
        )
        return 2
    try:
        result = import_eda_source(
            Path(source),
            Path(manifest),
            expected_manifest_sha256=os.environ.get(
                "EDA_SOURCE_MANIFEST_SHA256", CANONICAL_MANIFEST_SHA256
            ),
        )
    except EdaImportError as error:
        print(f"eda-import: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
