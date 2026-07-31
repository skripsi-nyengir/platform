import asyncio
from datetime import datetime, timezone
import hashlib
from importlib import resources
import json
import math
import re
from typing import cast

from sqlalchemy import Table, delete, func, literal, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.pilot import (
    PILOT_DISCLAIMER,
    SOURCE_COMMIT,
    STEP10_SHA256,
    load_tracked_normalized_snapshot,
)


type JSONValue = (
    None | bool | int | float | str | list[JSONValue] | dict[str, JSONValue]
)
type JSONDict = dict[str, JSONValue]

_FIXTURE_PATH = "fixtures/talpha_seed.json"
_FIXTURE_HASH = "02e73176f7706e518b07716d0c66d68690731abccc1c6c65af02393d4554b0ad"
_LOCK_ID = 7_216_202_604
_TIMESTAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
_SENTINEL_ALERT_ID = "alert_talpha_1_active"
_PUBLIC_DEVICE_ID = "b02f3872-ruang-produksi"
_PREVIEW_CREATED_AT = datetime(2026, 7, 24, tzinfo=timezone.utc)
_EMPTY_FIELDS: frozenset[str] = frozenset()
_SOURCE_INDICES = {
    0,
    1,
    2,
    3,
    4,
    5,
    36030,
    36031,
    36032,
    36033,
    65144,
    65145,
    65146,
    65147,
    86103,
}
_WINDOWS = (
    (0, 29, "2025-12-11T23:50:35", "2025-12-11T23:53:36"),
    (30, 59, "2025-12-11T23:53:42", "2025-12-11T23:56:43"),
    (60, 89, "2025-12-11T23:56:48", "2025-12-11T23:59:51"),
    (90, 119, "2025-12-11T23:59:57", "2025-12-12T00:02:57"),
)
_INFERENCE_DEFINITIONS = {
    "talpha-1": (
        "conv1d-arm-b-talpha-1-validation-fixture",
        0.02707822278141974,
        (0.013, 0.019, 0.02707822278141974, 0.028),
    ),
    "talpha-2": (
        "conv1d-arm-b-talpha-2-validation-fixture",
        0.031537856459617604,
        (0.014, 0.022, 0.031537856459617604, 0.025),
    ),
}
_EVALUATIONS = {
    "ewma-canonical-4ch": ("ewma", "canonical_4ch", 0.047478773146867714),
    "pca-canonical-4ch": ("pca", "canonical_4ch", 0.057222952693700785),
    "conv1d-arm-a": (
        "conv1d_autoencoder",
        "arm_a",
        0.025718613043427447,
    ),
    "conv1d-arm-b-talpha1": (
        "conv1d_autoencoder",
        "arm_b_talpha1",
        0.02707822278141974,
    ),
    "conv1d-arm-b-talpha2": (
        "conv1d_autoencoder",
        "arm_b_talpha2",
        0.031537856459617604,
    ),
    "tranad-canonical-4ch": ("tranad", "canonical_4ch", 0.007528403326869005),
    "usad-canonical-4ch": ("usad", "canonical_4ch", 0.008044914752244947),
}
_PROVENANCE: JSONDict = {
    "metadata_sha256": "9d015808bd032747d7b48ffdadc7f7d98aa68efb81e8e5c0d9313fbd7c77a8bc",
    "validation_sha256": "56c43dfd7aeb4f79e533a67e373174a07c45c2a4b1ba3df14352309e6670f2b1",
    "comparison_sha256": "09e3afdb55930e4dfc26b6cae8af0cf55105d2f3a523b14e8ad83fecfe4df6b6",
    "validation_rows": 86_104,
    "seg_bounds": [0, 36032, 65146, 86104],
    "segment_count": 3,
    "gap_count": 2,
    "gap_threshold_seconds": 600,
    "source_timestamp_policy": "exact no-offset calendar values; timezone unspecified",
    "scaler": {
        "channels": ["suhu1", "rh1", "suhu2", "rh2"],
        "minimum": [
            20.859050750732422,
            29.2172908782959,
            17.866750717163086,
            32.085941314697266,
        ],
        "maximum": [
            49.910560607910156,
            85.91895294189453,
            27.658769607543945,
            81.82958984375,
        ],
        "inverse_formula": "physical = scaled * (maximum - minimum) + minimum",
    },
    "device_mapping": {
        "talpha-1": {
            "temperature_c": {"source_channel": "suhu1", "source_column": 0},
            "relative_humidity_pct": {
                "source_channel": "rh1",
                "source_column": 1,
            },
        },
        "talpha-2": {
            "temperature_c": {"source_channel": "suhu2", "source_column": 2},
            "relative_humidity_pct": {
                "source_channel": "rh2",
                "source_column": 3,
            },
        },
    },
}

_PREVIEW_MODELS = (
    ("ewma", "EWMA", "preview-ewma-v1", "context_end"),
    ("pca", "PCA", "preview-pca-v1", "context_end"),
    (
        "wsn-dense-ae",
        "WSN Dense AE",
        "preview-wsn-dense-ae-v1",
        "context_end",
    ),
    ("lstm-ae", "LSTM-AE", "preview-lstm-ae-v1", "context_end"),
    ("usad", "USAD", "preview-usad-v1", "context_end"),
    (
        "cfc-autoencoder",
        "CfC Autoencoder",
        "preview-cfc-autoencoder-v1",
        "context_end",
    ),
    ("mtad-gat", "MTAD-GAT", "preview-mtad-gat-v1", "next_target"),
)


class SeedIntegrityError(ValueError):
    pass


def _load_fixture() -> JSONDict:
    fixture_text = (
        resources.files("anomaly_backend")
        .joinpath(_FIXTURE_PATH)
        .read_text(encoding="utf-8")
    )
    return cast(JSONDict, json.loads(fixture_text))


def _as_dict(value: JSONValue, label: str) -> JSONDict:
    if not isinstance(value, dict):
        raise SeedIntegrityError(f"{label} must be an object")
    return value


def _rows(fixture: JSONDict, name: str) -> list[JSONDict]:
    value = fixture.get(name)
    if not isinstance(value, list):
        raise SeedIntegrityError(f"{name} must be an array")
    return [_as_dict(item, f"{name} row") for item in value]


def _string(row: JSONDict, name: str) -> str:
    value = row.get(name)
    if not isinstance(value, str):
        raise SeedIntegrityError(f"{name} must be a string")
    return value


def _integer(row: JSONDict, name: str) -> int:
    value = row.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SeedIntegrityError(f"{name} must be an integer")
    return value


def _number(row: JSONDict, name: str) -> float:
    value = row.get(name)
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SeedIntegrityError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise SeedIntegrityError(f"{name} must be finite")
    return number


def _timestamp(row: JSONDict, name: str) -> str:
    value = _string(row, name)
    if _TIMESTAMP_PATTERN.fullmatch(value) is None:
        raise SeedIntegrityError(f"{name} must be a no-offset second timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise SeedIntegrityError(f"{name} is invalid") from error
    if parsed.tzinfo is not None or parsed.strftime("%Y-%m-%dT%H:%M:%S") != value:
        raise SeedIntegrityError(f"{name} must preserve its source calendar value")
    return value


def _canonical_hash(fixture: JSONDict) -> str:
    encoded = json.dumps(
        fixture,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _telemetry_hash(row: JSONDict) -> str:
    payload = {
        name: row[name]
        for name in (
            "device_id",
            "ts",
            "temperature_c",
            "relative_humidity_pct",
            "source_index",
        )
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _validate_telemetry(fixture: JSONDict) -> None:
    rows = _rows(fixture, "telemetry")
    expected_keys = {
        "device_id",
        "ts",
        "temperature_c",
        "relative_humidity_pct",
        "payload_hash",
        "source_index",
        "gap_before",
    }
    identities: set[tuple[str, str]] = set()
    index_counts = {index: 0 for index in _SOURCE_INDICES}
    gap_indices: set[int] = set()

    if len(rows) != 30:
        raise SeedIntegrityError("telemetry must contain exactly 30 rows")
    for row in rows:
        if set(row) != expected_keys:
            raise SeedIntegrityError("telemetry row shape is invalid")
        device_id = _string(row, "device_id")
        timestamp = _timestamp(row, "ts")
        source_index = _integer(row, "source_index")
        _ = _number(row, "temperature_c")
        _ = _number(row, "relative_humidity_pct")
        if device_id not in _INFERENCE_DEFINITIONS:
            raise SeedIntegrityError("telemetry device_id is invalid")
        if source_index not in _SOURCE_INDICES:
            raise SeedIntegrityError("telemetry source_index is not authorized")
        gap_before = row.get("gap_before")
        if not isinstance(gap_before, bool):
            raise SeedIntegrityError("telemetry gap_before must be boolean")
        if gap_before:
            gap_indices.add(source_index)
        payload_hash = _string(row, "payload_hash")
        if payload_hash != _telemetry_hash(row):
            raise SeedIntegrityError("telemetry payload_hash does not match its payload")
        identity = (device_id, timestamp)
        if identity in identities:
            raise SeedIntegrityError("telemetry identity is duplicated")
        identities.add(identity)
        index_counts[source_index] += 1

    if any(count != 2 for count in index_counts.values()):
        raise SeedIntegrityError("each telemetry source_index must map to both devices")
    if gap_indices != {36032, 65146}:
        raise SeedIntegrityError("telemetry gap flags do not match segment boundaries")


def _validate_inferences(fixture: JSONDict) -> None:
    rows = _rows(fixture, "inference_results")
    expected_keys = {
        "device_id",
        "window_start_ts",
        "window_end_ts",
        "model_version",
        "score",
        "threshold",
        "is_anomaly",
        "score_provenance",
        "source_start_index",
        "source_end_index",
        "reading_count",
        "stride",
    }
    seen: set[tuple[str, int, int]] = set()

    if len(rows) != 8:
        raise SeedIntegrityError("inference_results must contain exactly eight rows")
    for row in rows:
        if set(row) != expected_keys:
            raise SeedIntegrityError("inference_results row shape is invalid")
        device_id = _string(row, "device_id")
        definition = _INFERENCE_DEFINITIONS.get(device_id)
        if definition is None:
            raise SeedIntegrityError("inference device_id is invalid")
        start_index = _integer(row, "source_start_index")
        end_index = _integer(row, "source_end_index")
        try:
            window_position = next(
                index
                for index, window in enumerate(_WINDOWS)
                if window[:2] == (start_index, end_index)
            )
        except StopIteration as error:
            raise SeedIntegrityError("inference source window is invalid") from error
        window = _WINDOWS[window_position]
        if _timestamp(row, "window_start_ts") != window[2]:
            raise SeedIntegrityError("inference window_start_ts is not canonical")
        if _timestamp(row, "window_end_ts") != window[3]:
            raise SeedIntegrityError("inference window_end_ts is not canonical")
        model_version, threshold, scores = definition
        score = _number(row, "score")
        if _string(row, "model_version") != model_version:
            raise SeedIntegrityError("inference model_version is invalid")
        if _number(row, "threshold") != threshold or score != scores[window_position]:
            raise SeedIntegrityError("inference score or threshold is invalid")
        if row.get("is_anomaly") is not (score > threshold):
            raise SeedIntegrityError("inference is_anomaly must use strict comparison")
        if _string(row, "score_provenance") != "deterministic_threshold_fixture":
            raise SeedIntegrityError("inference score_provenance is invalid")
        if _integer(row, "reading_count") != 30 or _integer(row, "stride") != 1:
            raise SeedIntegrityError("inference window shape is invalid")
        seen.add((device_id, start_index, end_index))

    if len(seen) != 8:
        raise SeedIntegrityError("inference windows must be unique per device")


def _validate_alerts(fixture: JSONDict) -> None:
    alerts = _rows(fixture, "alerts")
    events = _rows(fixture, "alert_events")
    commands = _rows(fixture, "alert_commands")
    if len(alerts) != 1 or len(events) != 1 or commands:
        raise SeedIntegrityError("fixture must contain one alert, one event, and no commands")

    alert = alerts[0]
    event = events[0]
    if _string(alert, "alert_id") != _SENTINEL_ALERT_ID:
        raise SeedIntegrityError("alert sentinel identity is invalid")
    if (
        _string(alert, "device_id") != "talpha-1"
        or _timestamp(alert, "detected_at") != _WINDOWS[3][3]
        or _number(alert, "score") != 0.028
        or _number(alert, "threshold") != _INFERENCE_DEFINITIONS["talpha-1"][1]
        or _string(alert, "model_version") != _INFERENCE_DEFINITIONS["talpha-1"][0]
        or _timestamp(alert, "inference_result_window_start_ts") != _WINDOWS[3][2]
        or _timestamp(alert, "inference_result_window_end_ts") != _WINDOWS[3][3]
        or _string(alert, "detection_basis") != "threshold_model_fixture"
    ):
        raise SeedIntegrityError("alert provenance is invalid")

    matching_inferences = [
        row
        for row in _rows(fixture, "inference_results")
        if _string(row, "device_id") == _string(alert, "device_id")
        and _string(row, "model_version") == _string(alert, "model_version")
        and _timestamp(row, "window_start_ts")
        == _timestamp(alert, "inference_result_window_start_ts")
        and _timestamp(row, "window_end_ts")
        == _timestamp(alert, "inference_result_window_end_ts")
        and _number(row, "score") == _number(alert, "score")
        and _number(row, "threshold") == _number(alert, "threshold")
        and row.get("is_anomaly") is True
    ]
    if len(matching_inferences) != 1:
        raise SeedIntegrityError("alert source inference tuple is invalid")

    nullable_note = event.get("note")
    if (
        _string(event, "event_id") != "event_talpha_1_detected"
        or _string(event, "alert_id") != _SENTINEL_ALERT_ID
        or _timestamp(event, "event_ts") != _timestamp(alert, "detected_at")
        or _string(event, "event_type") != "detected"
        or _string(event, "device_id") != "talpha-1"
        or _string(event, "actor") != "threshold-model-fixture"
        or nullable_note is not None
        or _timestamp(event, "inference_result_window_start_ts") != _WINDOWS[3][2]
        or _timestamp(event, "inference_result_window_end_ts") != _WINDOWS[3][3]
        or _string(event, "inference_model_version")
        != _INFERENCE_DEFINITIONS["talpha-1"][0]
        or _string(event, "detection_basis") != "threshold_model_fixture"
    ):
        raise SeedIntegrityError("detected alert event provenance is invalid")


def _validate_evaluations(fixture: JSONDict) -> None:
    rows = _rows(fixture, "model_evaluations")
    available_metrics: list[JSONValue] = [
        "threshold",
        "strict_exceedance_count",
        "strict_exceedance_fraction",
    ]
    threshold_policy: JSONDict = {
        "source_split": "val",
        "percentile": 99.5,
        "comparison": ">",
    }
    if len(rows) != 7 or {_string(row, "version") for row in rows} != set(
        _EVALUATIONS
    ):
        raise SeedIntegrityError("model_evaluations identities are invalid")

    for row in rows:
        version = _string(row, "version")
        model, track, threshold = _EVALUATIONS[version]
        metrics = _as_dict(row.get("metrics"), "metrics")
        if (
            _string(row, "model") != model
            or _string(row, "track") != track
            or _number(row, "threshold") != threshold
            or row.get("validation_only") is not True
            or row.get("test_evaluated") is not False
            or _integer(row, "n_val_windows") != 86_017
            or row.get("threshold_policy") != threshold_policy
            or row.get("has_labeled_ground_truth") is not False
            or row.get("available_metrics") != available_metrics
            or metrics
            != {
                "threshold": threshold,
                "strict_exceedance_count": 431,
                "strict_exceedance_fraction": 0.005010637432135508,
            }
        ):
            raise SeedIntegrityError(f"model_evaluations {version} is invalid")
        for nullable in (
            "model_hash",
            "preprocessing_hash",
            "threshold_hash",
            "notes",
        ):
            if row.get(nullable) is not None:
                raise SeedIntegrityError(f"model_evaluations {nullable} must be null")
        if not _string(row, "label") or not _string(row, "score_key"):
            raise SeedIntegrityError("model_evaluations labels must be nonempty")
        if not _string(row, "score_semantics") or not _string(row, "summary"):
            raise SeedIntegrityError("model_evaluations descriptions must be nonempty")
        if _string(row, "evaluation_period") != (
            "2025-12-11T23:50:35 – 2025-12-18T07:52:42"
        ):
            raise SeedIntegrityError("model_evaluations period is invalid")
        if {
            "created_at",
            "confusion_matrix",
            "roc",
            "precision_recall",
            "f1",
            "accuracy",
            "ranking",
        } & set(row):
            raise SeedIntegrityError("model_evaluations contains unsupported fields")


def _validate_fixture(fixture: JSONDict) -> None:
    expected_sections = {
        "schema_version",
        "fixture_note",
        "provenance",
        "telemetry",
        "inference_results",
        "alerts",
        "alert_events",
        "alert_commands",
        "model_evaluations",
    }
    if set(fixture) != expected_sections:
        raise SeedIntegrityError("fixture sections are invalid")
    if fixture.get("schema_version") != "talpha_seed_v1":
        raise SeedIntegrityError("schema_version is invalid")
    note = fixture.get("fixture_note")
    if not isinstance(note, str) or "not runtime inference or ground truth" not in note:
        raise SeedIntegrityError("fixture_note must disclaim runtime inference and ground truth")
    provenance = _as_dict(fixture.get("provenance"), "provenance")
    for name, expected in _PROVENANCE.items():
        if provenance.get(name) != expected:
            raise SeedIntegrityError(f"{name} provenance is invalid")
    if set(provenance) != set(_PROVENANCE):
        raise SeedIntegrityError("provenance shape is invalid")
    if _canonical_hash(fixture) != _FIXTURE_HASH:
        raise SeedIntegrityError("fixture content hash is invalid")

    _validate_telemetry(fixture)
    _validate_inferences(fixture)
    _validate_alerts(fixture)
    _validate_evaluations(fixture)


def _database_rows(
    fixture: JSONDict,
    name: str,
    timestamp_fields: frozenset[str] = _EMPTY_FIELDS,
    omitted_fields: frozenset[str] = _EMPTY_FIELDS,
) -> list[dict[str, object]]:
    return [
        {
            key: datetime.fromisoformat(cast(str, value))
            if key in timestamp_fields
            else value
            for key, value in row.items()
            if key not in omitted_fields
        }
        for row in _rows(fixture, name)
    ]


def _all_database_rows(fixture: JSONDict) -> dict[str, list[dict[str, object]]]:
    telemetry_rows = _database_rows(
        fixture,
        "telemetry",
        frozenset({"ts"}),
        frozenset({"gap_before"}),
    )
    for row in telemetry_rows:
        source_index = cast(int, row["source_index"])
        row.update(
            corpus_id=f"legacy-corpus-{row['device_id']}",
            corpus_index=source_index,
            segment_id=(
                0
                if source_index < 36_032
                else 1
                if source_index < 65_146
                else 2
            ),
            dataset_split="legacy",
        )

    inference_rows = _database_rows(
        fixture,
        "inference_results",
        frozenset({"window_start_ts", "window_end_ts"}),
    )
    for row in inference_rows:
        source_end_index = cast(int, row["source_end_index"])
        row.update(
            corpus_id=f"legacy-corpus-{row['device_id']}",
            score_ts=row["window_end_ts"],
            segment_id=(
                0
                if source_end_index < 36_032
                else 1
                if source_end_index < 65_146
                else 2
            ),
            replay_job_id=None,
            recon_temperature_c=None,
            recon_relative_humidity_pct=None,
            band_half_temperature_c=None,
            band_half_relative_humidity_pct=None,
        )

    alert_rows = _database_rows(
        fixture,
        "alerts",
        frozenset(
            {
                "detected_at",
                "inference_result_window_start_ts",
                "inference_result_window_end_ts",
            }
        ),
    )
    for row in alert_rows:
        row.update(
            corpus_id=f"legacy-corpus-{row['device_id']}",
            episode_start_ts=row["inference_result_window_start_ts"],
            episode_end_ts=row["inference_result_window_end_ts"],
            last_score_ts=row["inference_result_window_end_ts"],
            created_at=None,
            peak_score=row["score"],
            latest_score=row["score"],
            anomalous_window_count=1,
            replay_job_id=None,
            segment_id=0,
            closure_reason="legacy_m1_fixture",
            live_episode_id=None,
        )

    event_rows = _database_rows(
        fixture,
        "alert_events",
        frozenset(
            {
                "event_ts",
                "inference_result_window_start_ts",
                "inference_result_window_end_ts",
            }
        ),
    )
    for row in event_rows:
        row.update(event_at=None, time_domain="legacy_naive")

    command_rows = _database_rows(
        fixture,
        "alert_commands",
        frozenset({"event_ts"}),
    )
    for row in command_rows:
        row.update(
            accepted_at=None,
            time_domain="legacy_naive",
            payload_hash="legacy_m1_fixture",
        )

    evaluation_rows = _database_rows(fixture, "model_evaluations")
    for row in evaluation_rows:
        row.update(
            model_key=None,
            report_source="legacy_m1_fixture",
            label_source="none",
            evaluation_kind="validation_threshold",
            test_observed=False,
            independent_final=False,
            source_commit=None,
            source_path=None,
            source_sha256=None,
            is_public=False,
        )

    return {
        "telemetry": telemetry_rows,
        "inference_results": inference_rows,
        "alerts": alert_rows,
        "alert_events": event_rows,
        "alert_commands": command_rows,
        "model_evaluations": evaluation_rows,
    }


async def _seed_telemetry(
    connection: AsyncConnection,
    rows: list[dict[str, object]],
) -> None:
    for row in rows:
        device_id = cast(str, row["device_id"])
        timestamp = cast(datetime, row["ts"])
        payload_hash = cast(str, row["payload_hash"])
        identity = (
            tables.telemetry.c.device_id == device_id,
            tables.telemetry.c.ts == timestamp,
        )
        existing_hash = await connection.scalar(
            select(tables.telemetry.c.payload_hash).where(*identity)
        )
        if existing_hash is not None:
            if existing_hash != payload_hash:
                raise SeedIntegrityError(
                    f"telemetry identity {device_id}/{timestamp.isoformat()} conflicts"
                )
            continue

        statement = (
            insert(tables.telemetry)
            .values(row)
            .on_conflict_do_nothing(
                index_elements=[tables.telemetry.c.device_id, tables.telemetry.c.ts]
            )
            .returning(tables.telemetry.c.payload_hash)
        )
        inserted_hash = await connection.scalar(statement)
        if inserted_hash is None:
            existing_hash = await connection.scalar(
                select(tables.telemetry.c.payload_hash).where(*identity)
            )
            if existing_hash != payload_hash:
                raise SeedIntegrityError(
                    f"telemetry identity {device_id}/{timestamp.isoformat()} conflicts"
                )


async def _assert_identities_absent(
    connection: AsyncConnection,
    table: Table,
    rows: list[dict[str, object]],
) -> None:
    primary_keys = tuple(table.primary_key.columns)
    for row in rows:
        exists = await connection.scalar(
            select(literal(True)).where(
                *(column == row[column.name] for column in primary_keys)
            )
        )
        if exists:
            identity = "/".join(str(row[column.name]) for column in primary_keys)
            raise SeedIntegrityError(f"{table.name} identity {identity} conflicts")


async def _insert_rows(
    connection: AsyncConnection,
    table: Table,
    rows: list[dict[str, object]],
) -> None:
    if rows:
        _ = await connection.execute(table.insert(), rows)


async def _verify_alert_source_inference(
    connection: AsyncConnection,
    alert: dict[str, object],
) -> None:
    result = await connection.execute(
        select(
            tables.inference_results.c.score,
            tables.inference_results.c.threshold,
            tables.inference_results.c.is_anomaly,
        ).where(
            tables.inference_results.c.device_id == alert["device_id"],
            tables.inference_results.c.model_version == alert["model_version"],
            tables.inference_results.c.window_start_ts
            == alert["inference_result_window_start_ts"],
            tables.inference_results.c.window_end_ts
            == alert["inference_result_window_end_ts"],
        )
    )
    source = result.one_or_none()
    expected = (alert["score"], alert["threshold"], True)
    if source is None or tuple(source) != expected:
        raise SeedIntegrityError("alert source inference is missing or inconsistent")


async def _verify_seeded_rows(
    connection: AsyncConnection,
    database_rows: dict[str, list[dict[str, object]]],
) -> None:
    for table, lineage_filter, expected_count in (
        (
            tables.telemetry,
            tables.telemetry.c.device_id.in_(("talpha-1", "talpha-2")),
            30,
        ),
        (
            tables.inference_results,
            tables.inference_results.c.score_provenance
            == "deterministic_threshold_fixture",
            8,
        ),
        (
            tables.alerts,
            tables.alerts.c.detection_basis == "threshold_model_fixture",
            1,
        ),
        (
            tables.model_evaluations,
            tables.model_evaluations.c.report_source == "legacy_m1_fixture",
            7,
        ),
    ):
        actual_count = int(
            await connection.scalar(
                select(func.count()).select_from(table).where(lineage_filter)
            )
            or 0
        )
        if actual_count != expected_count:
            raise SeedIntegrityError(
                f"sentinel verification failed for {table.name} count: expected {expected_count}, found {actual_count}"
            )

    detected_event_count = int(
        await connection.scalar(
            select(func.count())
            .select_from(tables.alert_events)
            .where(
                tables.alert_events.c.event_type == "detected",
                tables.alert_events.c.actor == "threshold-model-fixture",
                tables.alert_events.c.detection_basis == "threshold_model_fixture",
            )
        )
        or 0
    )
    if detected_event_count != 1:
        raise SeedIntegrityError(
            f"sentinel verification failed for alert_events fixture count: expected 1, found {detected_event_count}"
        )

    for table in (
        tables.telemetry,
        tables.inference_results,
        tables.alerts,
        tables.alert_events,
        tables.model_evaluations,
    ):
        primary_keys = tuple(table.primary_key.columns)
        columns = tuple(table.columns)
        for expected in database_rows[table.name]:
            result = await connection.execute(
                select(*columns).where(
                    *(column == expected[column.name] for column in primary_keys)
                )
            )
            actual = result.one_or_none()
            expected_values = tuple(expected[column.name] for column in columns)
            if actual is None or tuple(actual) != expected_values:
                identity = "/".join(
                    str(expected[column.name]) for column in primary_keys
                )
                raise SeedIntegrityError(
                    f"sentinel verification failed for {table.name} {identity}"
                )


async def _seed_preview_catalog(connection: AsyncConnection) -> None:
    snapshot = load_tracked_normalized_snapshot()
    normalized_models = snapshot.get("models")
    if not isinstance(normalized_models, list) or len(normalized_models) != 7:
        raise SeedIntegrityError("normalized pilot snapshot must contain seven models")
    pilot_by_key = {
        cast(str, cast(JSONDict, row)["model_key"]): cast(JSONDict, row)
        for row in normalized_models
        if isinstance(row, dict)
    }
    if set(pilot_by_key) != {model[0] for model in _PREVIEW_MODELS}:
        raise SeedIntegrityError("pilot snapshot model keys do not match registry")

    preview_versions = [version for _, _, version, _ in _PREVIEW_MODELS]
    fabricated_versions = [f"{version}-live-10" for version in preview_versions]
    await connection.execute(
        delete(tables.active_model_selections).where(
            tables.active_model_selections.c.model_version.in_(
                preview_versions + fabricated_versions
            )
        )
    )
    await connection.execute(
        delete(tables.model_activations).where(
            tables.model_activations.c.model_version.in_(fabricated_versions)
        )
    )
    await connection.execute(
        delete(tables.model_versions).where(
            tables.model_versions.c.version.in_(fabricated_versions)
        )
    )

    await connection.execute(
        insert(tables.model_families)
        .values(
            [
                {
                    "model_key": model_key,
                    "display_name": display_name,
                    "is_public": True,
                }
                for model_key, display_name, _, _ in _PREVIEW_MODELS
            ]
        )
        .on_conflict_do_nothing(index_elements=[tables.model_families.c.model_key])
    )
    version_payloads = [
        {
            "version": version,
            "model_key": model_key,
            "runtime_kind": "preview_simulator",
            "is_selectable": False,
            "adapter_key": "preview_sha256_v1",
            "schema_version": "b02f3872_preview_v1",
            "channels": ["suhu", "rh"],
            "window_size": 30,
            "stride": 1,
            "contract_status": "legacy_30",
            "score_key": "preview_ratio",
            "score_semantics": (
                "deterministic simulated preview ratio; not a Dandy model score"
            ),
            "threshold": 1.0,
            "threshold_policy": {
                "comparator": ">",
                "source": "preview_contract",
            },
            "temporal_semantics": temporal_semantics,
            "source_commit": None,
            "source_config": "b02f3872_ruang_produksi_v2",
            "manifest_sha256": None,
            "model_manifest_sha256": None,
            "checkpoint_sha256": None,
            "scaler_manifest_sha256": None,
            "scaler_sha256": None,
            "created_at": _PREVIEW_CREATED_AT,
        }
        for model_key, _, version, temporal_semantics in _PREVIEW_MODELS
    ]
    version_insert = insert(tables.model_versions).values(version_payloads)
    await connection.execute(
        version_insert.on_conflict_do_update(
            index_elements=[tables.model_versions.c.version],
            set_={
                column: getattr(version_insert.excluded, column)
                for column in version_payloads[0]
                if column not in {"version", "created_at"}
            },
            where=tables.model_versions.c.contract_status == "live_10",
        )
    )
    evaluation_rows: list[dict[str, object]] = []
    for model_key, display_name, _, _ in _PREVIEW_MODELS:
        pilot = pilot_by_key[model_key]
        threshold = pilot["reported_threshold"]
        predicted_windows = pilot["n_predicted_windows"]
        if not isinstance(predicted_windows, int) or predicted_windows <= 0:
            raise SeedIntegrityError(f"pilot window count is invalid for {model_key}")
        evaluation_rows.append(
            {
                "version": f"reported-dandy-pilot-{model_key}",
                "model": display_name,
                "track": "reported_dandy_pilot",
                "label": "Pilot Dandy (satu run; bukan hasil platform)",
                "score_key": str(pilot["score_key"]),
                "score_semantics": (
                    "reported Dandy pilot metric; separate from preview replay"
                ),
                "evaluation_period": "single observed synthetic test run",
                "validation_only": False,
                "test_evaluated": True,
                "n_val_windows": predicted_windows,
                "threshold": threshold,
                "threshold_policy": {
                    "source": "reported_dandy_pilot",
                    "comparator": ">",
                },
                "has_labeled_ground_truth": True,
                "available_metrics": [
                    "composite_primary",
                    "window_f1",
                    "window_precision",
                    "window_recall",
                    "event_hit_rate",
                    "clean_test_fpr",
                    "alert_rate",
                    "stuck_event_hit_rate",
                ],
                "summary": PILOT_DISCLAIMER,
                "model_hash": None,
                "preprocessing_hash": None,
                "threshold_hash": None,
                "metrics": pilot,
                "notes": "Seluruh model memiliki stuck_event_hit_rate=0.0.",
                "model_key": model_key,
                "report_source": "reported_dandy_pilot",
                "label_source": "synthetic_injection",
                "evaluation_kind": "comparison_snapshot",
                "test_observed": True,
                "independent_final": False,
                "source_commit": SOURCE_COMMIT,
                "source_path": (
                    "notebooks/step10/summaries/"
                    "step10_comparison_summary.json"
                ),
                "source_sha256": STEP10_SHA256,
                "is_public": True,
            }
        )
    await connection.execute(
        insert(tables.model_evaluations)
        .values(evaluation_rows)
        .on_conflict_do_nothing(index_elements=[tables.model_evaluations.c.version])
    )

    public_family_count = int(
        await connection.scalar(
            select(func.count())
            .select_from(tables.model_families)
            .where(tables.model_families.c.is_public)
        )
        or 0
    )
    public_version_count = int(
        await connection.scalar(
            select(func.count())
            .select_from(tables.model_versions)
            .join(
                tables.model_families,
                tables.model_families.c.model_key
                == tables.model_versions.c.model_key,
            )
            .where(
                tables.model_families.c.is_public,
                tables.model_versions.c.version.in_(preview_versions),
                tables.model_versions.c.contract_status == "legacy_30",
                ~tables.model_versions.c.is_selectable,
            )
        )
        or 0
    )
    public_pilot_count = int(
        await connection.scalar(
            select(func.count())
            .select_from(tables.model_evaluations)
            .where(
                tables.model_evaluations.c.report_source
                == "reported_dandy_pilot",
                tables.model_evaluations.c.is_public,
            )
        )
        or 0
    )
    active_selection_count = int(
        await connection.scalar(
            select(func.count())
            .select_from(tables.active_model_selections)
            .where(
                tables.active_model_selections.c.device_id == _PUBLIC_DEVICE_ID
            )
        )
        or 0
    )
    if (
        public_family_count != 7
        or public_version_count != 7
        or public_pilot_count != 7
        or active_selection_count != 0
    ):
        raise SeedIntegrityError(
            "preview registry must have seven families, legacy versions, "
            "pilot rows, and no active selection"
        )


async def seed_database(connection: AsyncConnection) -> None:
    fixture = _load_fixture()
    _validate_fixture(fixture)
    database_rows = _all_database_rows(fixture)

    async with connection.begin():
        _ = await connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": _LOCK_ID},
        )
        sentinel_exists = await connection.scalar(
            select(literal(True)).where(
                tables.alerts.c.alert_id == _SENTINEL_ALERT_ID
            )
        )
        if sentinel_exists:
            await _verify_seeded_rows(connection, database_rows)
            await _seed_preview_catalog(connection)
            return

        await _seed_telemetry(connection, database_rows["telemetry"])
        await _assert_identities_absent(
            connection,
            tables.inference_results,
            database_rows["inference_results"],
        )
        await _insert_rows(
            connection,
            tables.inference_results,
            database_rows["inference_results"],
        )
        await _assert_identities_absent(connection, tables.alerts, database_rows["alerts"])
        await _verify_alert_source_inference(connection, database_rows["alerts"][0])
        await _insert_rows(connection, tables.alerts, database_rows["alerts"])
        await _assert_identities_absent(
            connection,
            tables.alert_events,
            database_rows["alert_events"],
        )
        await _insert_rows(
            connection,
            tables.alert_events,
            database_rows["alert_events"],
        )
        await _assert_identities_absent(
            connection,
            tables.model_evaluations,
            database_rows["model_evaluations"],
        )
        await _insert_rows(
            connection,
            tables.model_evaluations,
            database_rows["model_evaluations"],
        )
        await _seed_preview_catalog(connection)


async def _run() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            await seed_database(connection)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
