from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
import csv
import hashlib
import io
import math
from pathlib import Path
from typing import Any, BinaryIO, cast
from zoneinfo import ZoneInfo

import numpy as np  # pyright: ignore[reportMissingImports]

from .config import BUFFER_BYTES, DEVICE_ID, MAXIMUM_CHUNK_PAIRS, TIME_ZONE


CSV_HEADER = ("device_id", "data_index", "value", "timestamp", "is_connected")


@dataclass(frozen=True, slots=True)
class RawSourceMetadata:
    sha256: str | None = None
    size_bytes: int | None = None
    row_count: int | None = None
    start: str | None = None
    cutoff_inclusive: str | None = None


@dataclass(frozen=True, slots=True)
class RawInputAudit:
    sha256: str | None
    size_bytes: int | None
    row_count: int
    start: str | None
    cutoff_inclusive: str | None
    raw_open_count: int
    buffer_bytes: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "bytes_consumed": self.size_bytes,
            "row_count": self.row_count,
            "start": self.start,
            "cutoff_inclusive": self.cutoff_inclusive,
            "raw_open_count": self.raw_open_count,
            "buffer_bytes": self.buffer_bytes,
        }


@dataclass(frozen=True, slots=True)
class RawInputChunk:
    source_row_numbers: np.ndarray
    timestamps_epoch_s: np.ndarray
    data_indices: np.ndarray
    values: np.ndarray
    is_connected: np.ndarray

    def __post_init__(self) -> None:
        size = int(self.timestamps_epoch_s.size)
        for name in ("source_row_numbers", "data_indices", "values", "is_connected"):
            if cast(np.ndarray, getattr(self, name)).shape != (size,):
                raise ValueError(f"RawInputChunk.{name} must have shape (n,)")


@dataclass(frozen=True, slots=True)
class _RawRow:
    source_row_number: int
    device_id: str
    data_index: int
    value: float
    timestamp_epoch_s: int
    is_connected: bool


class _HashingReader(io.RawIOBase):
    def __init__(self, raw: BinaryIO) -> None:
        self.raw = raw
        self.digest = hashlib.sha256()
        self.bytes_consumed = 0

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        count = cast(Any, self.raw).readinto(buffer)
        if count is None:
            return 0
        if count:
            chunk = memoryview(buffer)[:count]
            self.digest.update(chunk)
            self.bytes_consumed += count
        return count


class RawInputAdapter:
    """One-shot source adapter for canonical CSV bytes or source-ordered DB rows.

    ``iter_chunks`` always emits the same compact NumPy shape, so duplicate
    resolution and screening never depend on whether evidence came from a file
    or ``eda_raw_readings``.
    """

    def __init__(
        self,
        *,
        csv_path: Path | None = None,
        database_rows: Iterable[Mapping[str, object]] | None = None,
        metadata: RawSourceMetadata | None = None,
        chunk_rows: int = MAXIMUM_CHUNK_PAIRS,
    ) -> None:
        if (csv_path is None) == (database_rows is None):
            raise ValueError("exactly one raw input source is required")
        if not 0 < chunk_rows <= MAXIMUM_CHUNK_PAIRS:
            raise ValueError("chunk_rows must be in [1, 250000]")
        self._csv_path = csv_path
        self._database_rows = database_rows
        self._metadata = metadata or RawSourceMetadata()
        self._chunk_rows = chunk_rows
        self._consumed = False
        self.audit: RawInputAudit | None = None

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        *,
        expected_sha256: str | None = None,
        expected_size_bytes: int | None = None,
        expected_row_count: int | None = None,
        source_start: str | None = None,
        source_cutoff_inclusive: str | None = None,
        chunk_rows: int = MAXIMUM_CHUNK_PAIRS,
    ) -> RawInputAdapter:
        return cls(
            csv_path=Path(path),
            metadata=RawSourceMetadata(
                sha256=expected_sha256,
                size_bytes=expected_size_bytes,
                row_count=expected_row_count,
                start=source_start,
                cutoff_inclusive=source_cutoff_inclusive,
            ),
            chunk_rows=chunk_rows,
        )

    @classmethod
    def from_database_rows(
        cls,
        rows: Iterable[Mapping[str, object]],
        *,
        metadata: RawSourceMetadata | None = None,
        chunk_rows: int = MAXIMUM_CHUNK_PAIRS,
    ) -> RawInputAdapter:
        return cls(database_rows=rows, metadata=metadata, chunk_rows=chunk_rows)

    def iter_chunks(self) -> Iterator[RawInputChunk]:
        if self._consumed:
            raise RuntimeError("RawInputAdapter is one-shot")
        self._consumed = True
        rows = self._csv_rows() if self._csv_path is not None else self._database_input_rows()
        yield from self._validated_chunks(rows)

    def _csv_rows(self) -> Iterator[_RawRow]:
        path = cast(Path, self._csv_path)
        with path.open("rb", buffering=BUFFER_BYTES) as raw:
            hashing = _HashingReader(raw)
            with io.TextIOWrapper(
                io.BufferedReader(hashing, buffer_size=BUFFER_BYTES),
                encoding="utf-8",
                newline="",
            ) as text:
                reader = csv.DictReader(text)
                if tuple(reader.fieldnames or ()) != CSV_HEADER:
                    raise ValueError("raw source header mismatch")
                for row_number, row in enumerate(reader, start=1):
                    yield _RawRow(
                        source_row_number=row_number,
                        device_id=str(row["device_id"]),
                        data_index=_channel(row["data_index"]),
                        value=_value(row["value"]),
                        timestamp_epoch_s=_epoch(row["timestamp"]),
                        is_connected=_connected(row["is_connected"]),
                    )
            actual_sha256 = hashing.digest.hexdigest()
            actual_size = hashing.bytes_consumed
        expected = self._metadata
        if expected.sha256 is not None and actual_sha256 != expected.sha256:
            raise ValueError("raw source SHA-256 mismatch")
        if expected.size_bytes is not None and actual_size != expected.size_bytes:
            raise ValueError("raw source size mismatch")
        self._metadata = RawSourceMetadata(
            sha256=actual_sha256,
            size_bytes=actual_size,
            row_count=expected.row_count,
            start=expected.start,
            cutoff_inclusive=expected.cutoff_inclusive,
        )

    def _database_input_rows(self) -> Iterator[_RawRow]:
        for row in cast(Iterable[Mapping[str, object]], self._database_rows):
            yield _RawRow(
                source_row_number=_source_row_number(row.get("source_row_number")),
                device_id=str(row.get("device_id", "")),
                data_index=_channel(row.get("data_index")),
                value=_value(row.get("value")),
                timestamp_epoch_s=_epoch(row.get("ts", row.get("timestamp"))),
                is_connected=_connected(row.get("is_connected")),
            )

    def _validated_chunks(self, rows: Iterable[_RawRow]) -> Iterator[RawInputChunk]:
        columns: dict[str, list[Any]] = {
            "source_row_numbers": [],
            "timestamps_epoch_s": [],
            "data_indices": [],
            "values": [],
            "is_connected": [],
        }
        previous_source_row = 0
        previous_sort_key: tuple[int, int, tuple[int, float], bool, str] | None = None
        row_count = 0
        first_timestamp: int | None = None
        last_timestamp: int | None = None
        expected = self._metadata
        if (expected.start is None) != (expected.cutoff_inclusive is None):
            raise ValueError("source bounds must include both start and cutoff")
        source_bounds = (
            (_epoch(expected.start), _epoch(expected.cutoff_inclusive))
            if expected.start is not None and expected.cutoff_inclusive is not None
            else None
        )
        if source_bounds is not None and source_bounds[0] > source_bounds[1]:
            raise ValueError("source start must not exceed cutoff")

        for row in rows:
            row_count += 1
            if row.device_id != DEVICE_ID:
                raise ValueError(f"wrong device_id at source row {row.source_row_number}")
            if row.source_row_number <= previous_source_row:
                raise ValueError("database rows must be ordered by source_row_number")
            if source_bounds is not None and not (
                source_bounds[0] <= row.timestamp_epoch_s <= source_bounds[1]
            ):
                raise ValueError(
                    f"timestamp outside source bounds at source row {row.source_row_number}"
                )
            sort_key = (
                row.timestamp_epoch_s,
                row.data_index,
                _sort_value(row.value),
                row.is_connected,
                row.device_id,
            )
            if previous_sort_key is not None and sort_key < previous_sort_key:
                raise ValueError(f"raw source is not sorted at source row {row.source_row_number}")
            previous_source_row = row.source_row_number
            previous_sort_key = sort_key
            first_timestamp = row.timestamp_epoch_s if first_timestamp is None else first_timestamp
            last_timestamp = row.timestamp_epoch_s
            for name, value in (
                ("source_row_numbers", row.source_row_number),
                ("timestamps_epoch_s", row.timestamp_epoch_s),
                ("data_indices", row.data_index),
                ("values", row.value),
                ("is_connected", row.is_connected),
            ):
                columns[name].append(value)
            if len(columns["timestamps_epoch_s"]) == self._chunk_rows:
                yield _raw_chunk(columns)
                for values in columns.values():
                    values.clear()
        if columns["timestamps_epoch_s"]:
            yield _raw_chunk(columns)

        if expected.row_count is not None and row_count != expected.row_count:
            raise ValueError("raw source row count mismatch")
        start = expected.start or _local_timestamp(first_timestamp)
        cutoff = expected.cutoff_inclusive or _local_timestamp(last_timestamp)
        self.audit = RawInputAudit(
            sha256=expected.sha256,
            size_bytes=expected.size_bytes,
            row_count=row_count,
            start=start,
            cutoff_inclusive=cutoff,
            raw_open_count=int(self._csv_path is not None),
            buffer_bytes=BUFFER_BYTES,
        )


def _raw_chunk(columns: Mapping[str, list[Any]]) -> RawInputChunk:
    return RawInputChunk(
        source_row_numbers=np.asarray(columns["source_row_numbers"], dtype=np.int64),
        timestamps_epoch_s=np.asarray(columns["timestamps_epoch_s"], dtype=np.int64),
        data_indices=np.asarray(columns["data_indices"], dtype=np.int8),
        values=np.asarray(columns["values"], dtype=np.float64),
        is_connected=np.asarray(columns["is_connected"], dtype=bool),
    )


def _source_row_number(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("source_row_number must be a positive integer")
    try:
        result = int(cast(Any, value))
    except (TypeError, ValueError) as error:
        raise ValueError("source_row_number must be a positive integer") from error
    if result <= 0:
        raise ValueError("source_row_number must be a positive integer")
    return result


def _channel(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("invalid data_index")
    try:
        result = int(cast(Any, value))
    except (TypeError, ValueError) as error:
        raise ValueError("invalid data_index") from error
    if result not in (0, 1):
        raise ValueError("unexpected data_index")
    return result


def _value(value: object) -> float:
    try:
        return float(cast(Any, value))
    except (TypeError, ValueError) as error:
        raise ValueError("invalid value") from error


def _epoch(value: object) -> int:
    if isinstance(value, datetime):
        parsed = value
        if parsed.tzinfo is not None:
            raise ValueError("database timestamps must not contain an offset")
    elif isinstance(value, str):
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError as error:
            raise ValueError(f"invalid timestamp: {value!r}") from error
    else:
        raise ValueError("timestamp must be a datetime or source-format string")
    return int(parsed.replace(tzinfo=ZoneInfo(TIME_ZONE)).timestamp())


def _connected(value: object) -> bool:
    if value is True or value in {1, "1", "true", "True"}:
        return True
    if value is False or value in {0, "0", "false", "False"}:
        return False
    raise ValueError(f"invalid is_connected value: {value!r}")


def _sort_value(value: float) -> tuple[int, float]:
    if math.isnan(value):
        return (3, 0.0)
    if value == -math.inf:
        return (0, 0.0)
    if value == math.inf:
        return (2, 0.0)
    return (1, value)


def _local_timestamp(epoch: int | None) -> str | None:
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, tz=ZoneInfo(TIME_ZONE)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )


__all__ = [
    "CSV_HEADER",
    "RawInputAdapter",
    "RawInputAudit",
    "RawInputChunk",
    "RawSourceMetadata",
]
