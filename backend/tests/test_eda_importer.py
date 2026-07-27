from collections.abc import Iterator
import csv
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row
import pytest

from anomaly_backend.config import Settings
import anomaly_backend.eda_importer as eda_importer  # pyright: ignore[reportMissingImports]
from anomaly_eda.config import CONFIG_HASH


DEVICE_ID = "b02f3872-39a2-4b6f-a4ec-045a287fde4b"
HEADER = ("device_id", "data_index", "value", "timestamp", "is_connected")
ORDER = ("timestamp", "data_index", "value", "is_connected", "device_id")
START = "2025-06-23 00:00:00"
CUTOFF = "2026-07-24 09:02:04"
Row = tuple[str, str, str, str, str]


def _run_alembic(*arguments: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=Path(__file__).parents[1],
        check=True,
        capture_output=True,
        text=True,
    )


def _connect() -> psycopg.Connection[dict[str, Any]]:
    settings = Settings.from_environ()
    return cast(
        psycopg.Connection[dict[str, Any]],
        psycopg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            row_factory=dict_row,  # pyright: ignore[reportArgumentType]
            autocommit=True,
        ),
    )


@pytest.fixture(scope="module", autouse=True)
def eda_schema_head() -> Iterator[None]:
    _run_alembic("upgrade", "head")
    yield


@pytest.fixture(autouse=True)
def clean_eda_tables(eda_schema_head: None) -> Iterator[None]:
    del eda_schema_head
    with _connect() as connection:
        connection.execute(
            "TRUNCATE eda_result_sections, eda_runs, eda_jobs, "
            "eda_raw_readings, eda_source_snapshots"
        )
    yield
    with _connect() as connection:
        connection.execute(
            "TRUNCATE eda_result_sections, eda_runs, eda_jobs, "
            "eda_raw_readings, eda_source_snapshots"
        )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> str:
    path.write_text(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    return _sha256(path)


def _write_source(
    directory: Path,
    rows: list[Row],
    *,
    header: tuple[str, ...] = HEADER,
    name: str = "sensor_data_long.csv",
) -> Path:
    path = directory / name
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)
    return path


def _write_manifest(
    directory: Path,
    source: Path,
    rows: list[Row],
    *,
    artifact_sha256: str | None = None,
    row_count: int | None = None,
    name: str = "manifest.json",
) -> tuple[Path, str]:
    expected_row_count = len(rows) if row_count is None else row_count
    counts = {
        str(index): {"rows": sum(int(row[1]) == index for row in rows)}
        for index in (0, 1)
    }
    counts["0"]["rows"] += expected_row_count - len(rows)
    payload = {
        "artifact": {
            "bounds": {
                "cutoff": CUTOFF,
                "inclusive": True,
                "start": START,
                "timezone": "Asia/Jakarta",
            },
            "path": source.name,
            "per_index": counts,
            "row_count": expected_row_count,
            "sha256": artifact_sha256 or _sha256(source),
            "size_bytes": source.stat().st_size,
        },
        "dataset_id": "synthetic_b02_v1",
        "device": {
            "id": DEVICE_ID,
            "indices": {
                "0": {"name": "Suhu", "unit": "°C"},
                "1": {"name": "RH", "unit": "%"},
            },
        },
        "schema_version": "bivariate_b02f3872_source_v1",
        "source": {
            "cutoff": {
                "literal_inclusive": CUTOFF,
                "method": "min_of_two_per_index_maxima",
                "per_index_max": {"0": CUTOFF, "1": CUTOFF},
            },
            "header": list(HEADER),
            "order_by": list(ORDER),
            "start_inclusive": START,
            "table": "default.sensor_data",
            "timezone": "Asia/Jakarta",
        },
    }
    path = directory / name
    return path, _write_json(path, payload)


def _valid_rows() -> list[Row]:
    timestamp = START
    return [
        (DEVICE_ID, "0", "-Infinity", timestamp, "true"),
        (DEVICE_ID, "0", "0", timestamp, "false"),
        (DEVICE_ID, "0", "0", timestamp, "true"),
        (DEVICE_ID, "0", "0", timestamp, "true"),
        (DEVICE_ID, "0", "Infinity", timestamp, "true"),
        (DEVICE_ID, "0", "NaN", timestamp, "true"),
        (DEVICE_ID, "1", "50", timestamp, "false"),
        (DEVICE_ID, "0", "25", "2025-06-23 00:00:06", "true"),
        (DEVICE_ID, "1", "51", "2025-06-23 00:00:06", "true"),
    ]


def _import(directory: Path, rows: list[Row], **source_options: Any) -> dict[str, Any]:
    source = _write_source(directory, rows, **source_options)
    manifest, manifest_sha256 = _write_manifest(directory, source, rows)
    return eda_importer.import_eda_source(
        source,
        manifest,
        expected_manifest_sha256=manifest_sha256,
        batch_size=2,
    )


def test_import_preserves_duplicate_disconnect_and_nonfinite_rows(
    tmp_path: Path,
) -> None:
    rows = _valid_rows()
    result = _import(tmp_path, rows)

    assert result == {
        "snapshot_id": result["snapshot_id"],
        "dataset_id": "synthetic_b02_v1",
        "source_sha256": _sha256(tmp_path / "sensor_data_long.csv"),
        "status": "complete",
        "row_count": len(rows),
        "idempotent_noop": False,
    }
    with _connect() as connection:
        stored = connection.execute(
            """
            SELECT source_row_number, device_id, data_index, value, ts, is_connected
            FROM eda_raw_readings
            WHERE snapshot_id = %s
            ORDER BY source_row_number
            """,
            (result["snapshot_id"],),
        ).fetchall()
        snapshot = connection.execute(
            "SELECT status, expected_row_count, config_hash "
            "FROM eda_source_snapshots WHERE id = %s",
            (result["snapshot_id"],),
        ).fetchone()

    assert snapshot == {
        "status": "complete",
        "expected_row_count": len(rows),
        "config_hash": CONFIG_HASH,
    }
    assert [row["source_row_number"] for row in stored] == list(
        range(1, len(rows) + 1)
    )
    assert [row["is_connected"] for row in stored] == [
        True,
        False,
        True,
        True,
        True,
        True,
        False,
        True,
        True,
    ]
    assert stored[1]["value"] == stored[2]["value"] == stored[3]["value"] == 0.0
    assert math.isinf(stored[0]["value"]) and stored[0]["value"] < 0
    assert math.isinf(stored[4]["value"]) and stored[4]["value"] > 0
    assert math.isnan(stored[5]["value"])


def test_complete_snapshot_reimport_does_not_read_or_insert_source(
    tmp_path: Path,
) -> None:
    rows = _valid_rows()
    source = _write_source(tmp_path, rows)
    manifest, manifest_sha256 = _write_manifest(tmp_path, source, rows)
    first = eda_importer.import_eda_source(
        source, manifest, expected_manifest_sha256=manifest_sha256, batch_size=2
    )
    source.unlink()

    second = eda_importer.import_eda_source(
        source, manifest, expected_manifest_sha256=manifest_sha256, batch_size=2
    )

    assert second == {**first, "idempotent_noop": True}
    with _connect() as connection:
        assert connection.execute(
            "SELECT count(*) AS count FROM eda_raw_readings"
        ).fetchone() == {"count": len(rows)}


def test_changed_source_hash_creates_a_distinct_valid_snapshot(tmp_path: Path) -> None:
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    first_directory.mkdir()
    second_directory.mkdir()
    first = _import(first_directory, _valid_rows())
    changed_rows = _valid_rows() + [
        (DEVICE_ID, "0", "26", "2025-06-23 00:00:12", "true"),
        (DEVICE_ID, "1", "52", "2025-06-23 00:00:12", "true"),
    ]
    second = _import(second_directory, changed_rows)

    assert first["snapshot_id"] != second["snapshot_id"]
    assert first["source_sha256"] != second["source_sha256"]
    with _connect() as connection:
        assert connection.execute(
            "SELECT count(*) AS count FROM eda_source_snapshots WHERE status = 'complete'"
        ).fetchone() == {"count": 2}


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("header", "source header mismatch"),
        ("device", "wrong device_id"),
        ("order", "source is not sorted"),
        ("bounds", "timestamp outside inclusive bounds"),
        ("calendar", "invalid timestamp"),
        ("hash", "source SHA-256 mismatch"),
        ("count", "source row count mismatch"),
    ],
)
def test_invalid_source_fails_without_publishing_or_leaking_rows(
    tmp_path: Path,
    case: str,
    message: str,
) -> None:
    rows = [
        (DEVICE_ID, "0", "25", START, "true"),
        (DEVICE_ID, "1", "50", START, "true"),
    ]
    header = HEADER
    if case == "header":
        header = HEADER[:-1]
    elif case == "device":
        rows[0] = ("wrong-device", "0", "25", START, "true")
    elif case == "order":
        rows.reverse()
    elif case == "bounds":
        rows[-1] = (DEVICE_ID, "1", "50", "2026-07-24 09:02:05", "true")
    elif case == "calendar":
        rows[-1] = (DEVICE_ID, "1", "50", "2026-02-30 00:00:00", "true")

    source = _write_source(tmp_path, rows, header=header)
    manifest, manifest_sha256 = _write_manifest(
        tmp_path,
        source,
        rows,
        artifact_sha256="0" * 64 if case == "hash" else None,
        row_count=len(rows) + 1 if case == "count" else None,
    )

    with pytest.raises(eda_importer.EdaImportError, match=message):
        eda_importer.import_eda_source(
            source,
            manifest,
            expected_manifest_sha256=manifest_sha256,
            batch_size=1,
        )

    with _connect() as connection:
        assert connection.execute(
            "SELECT count(*) AS count FROM eda_raw_readings"
        ).fetchone() == {"count": 0}
        assert connection.execute(
            "SELECT status FROM eda_source_snapshots"
        ).fetchall() == [{"status": "failed"}]


def test_manifest_hash_is_rejected_before_snapshot_creation(tmp_path: Path) -> None:
    rows = _valid_rows()
    source = _write_source(tmp_path, rows)
    manifest, _ = _write_manifest(tmp_path, source, rows)

    with pytest.raises(eda_importer.EdaImportError, match="manifest SHA-256 mismatch"):
        eda_importer.import_eda_source(
            source,
            manifest,
            expected_manifest_sha256="0" * 64,
        )

    with _connect() as connection:
        assert connection.execute(
            "SELECT count(*) AS count FROM eda_source_snapshots"
        ).fetchone() == {"count": 0}


@pytest.mark.parametrize(
    ("field", "value"),
    [("device", []), ("header", None), ("order_by", 1)],
)
def test_malformed_manifest_uses_stable_cli_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    field: str,
    value: Any,
) -> None:
    rows = _valid_rows()
    source = _write_source(tmp_path, rows)
    manifest, _ = _write_manifest(tmp_path, source, rows)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if field == "device":
        payload[field] = value
    else:
        payload["source"][field] = value
    manifest_sha256 = _write_json(manifest, payload)
    monkeypatch.setenv("EDA_RAW_SOURCE_PATH", str(source))
    monkeypatch.setenv("EDA_SOURCE_MANIFEST_PATH", str(manifest))
    monkeypatch.setenv("EDA_SOURCE_MANIFEST_SHA256", manifest_sha256)

    assert eda_importer.main() == 2
    assert "eda-import: source manifest structure is invalid" in capsys.readouterr().err
    with _connect() as connection:
        assert connection.execute(
            "SELECT count(*) AS count FROM eda_source_snapshots"
        ).fetchone() == {"count": 0}


def test_inconsistent_complete_snapshot_preserves_original_error(
    tmp_path: Path,
) -> None:
    rows = _valid_rows()
    source = _write_source(tmp_path, rows)
    manifest, manifest_sha256 = _write_manifest(tmp_path, source, rows)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    with _connect() as connection:
        snapshot = connection.execute(
            """
            INSERT INTO eda_source_snapshots (
                dataset_id, source_sha256, manifest_sha256, config_hash,
                source_from_ts, source_to_ts, expected_row_count,
                expected_channel_count, importer_version, status,
                completed_at, manifest
            ) VALUES (
                'synthetic_b02_v1', %s, %s, %s, %s, %s, %s, 2, %s,
                'complete', now(), %s::jsonb
            )
            RETURNING id
            """,
            (
                _sha256(source),
                manifest_sha256,
                eda_importer.CONFIG_HASH,
                START,
                CUTOFF,
                len(rows),
                eda_importer.IMPORTER_VERSION,
                json.dumps(payload),
            ),
        ).fetchone()
    assert snapshot is not None

    with pytest.raises(
        eda_importer.EdaImportError,
        match="complete snapshot raw row count is inconsistent",
    ):
        eda_importer.import_eda_source(
            source,
            manifest,
            expected_manifest_sha256=manifest_sha256,
        )

    with _connect() as connection:
        assert connection.execute(
            "SELECT status FROM eda_source_snapshots WHERE id = %s",
            (snapshot["id"],),
        ).fetchone() == {"status": "complete"}


def test_oversized_manifest_is_rejected_before_snapshot_creation(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_bytes(b" " * (eda_importer.MAX_MANIFEST_BYTES + 1))

    with pytest.raises(
        eda_importer.EdaImportError,
        match="source manifest exceeds the size limit",
    ):
        eda_importer.import_eda_source(
            tmp_path / "missing.csv",
            manifest,
            expected_manifest_sha256=_sha256(manifest),
        )

    with _connect() as connection:
        assert connection.execute(
            "SELECT count(*) AS count FROM eda_source_snapshots"
        ).fetchone() == {"count": 0}


def test_oversized_csv_row_fails_and_cleans_staging(tmp_path: Path) -> None:
    rows = [
        (DEVICE_ID, "0", "1" * eda_importer.MAX_CSV_LINE_BYTES, START, "true"),
        (DEVICE_ID, "1", "50", START, "true"),
    ]
    source = _write_source(tmp_path, rows)
    manifest, manifest_sha256 = _write_manifest(tmp_path, source, rows)

    with pytest.raises(
        eda_importer.EdaImportError,
        match="source CSV row exceeds the size limit",
    ):
        eda_importer.import_eda_source(
            source,
            manifest,
            expected_manifest_sha256=manifest_sha256,
        )

    with _connect() as connection:
        assert connection.execute(
            "SELECT count(*) AS count FROM eda_raw_readings"
        ).fetchone() == {"count": 0}
        assert connection.execute(
            "SELECT status FROM eda_source_snapshots"
        ).fetchall() == [{"status": "failed"}]


def test_rollback_failure_does_not_replace_original_error() -> None:
    class BrokenConnection:
        def rollback(self) -> None:
            raise RuntimeError("connection lost")

    error = eda_importer.EdaImportError("source rejected")
    eda_importer._rollback_preserving(
        cast(
            psycopg.Connection[dict[str, Any]],
            cast(object, BrokenConnection()),
        ),
        error,
        "rollback failed",
    )

    assert str(error) == "source rejected"
    assert error.__notes__ == ["rollback failed: connection lost"]
