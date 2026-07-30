from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from collections.abc import Iterator
from typing import Any, cast

import numpy as np
import psycopg
from psycopg.rows import dict_row

from anomaly_backend.config import Settings


SIM_DEVICE_ID = "b02f3872-simulasi-injeksi"
SIM_DISPLAY_NAME = "B02 Simulasi Injeksi"
SOURCE_DEVICE_UUID = "b02f3872-39a2-4b6f-a4ec-045a287fde4b"
TIME_ZONE = "Asia/Jakarta"
SIM_CORPUS_ID = "sim_b02_march07_v5_test_injected"
CONTRACT_VERSION = "b02f3872_march07_v5_injected"
CHANNELS = ["suhu", "rh"]
SCALER_MINIMUM = [24.36616, 18.1394]
SCALER_MAXIMUM = [30.32931, 68.02039]
EXPECTED_ROW_COUNT = 105_767
EXPECTED_EVENT_COUNT = 210
EXPECTED_FIRST_TS = datetime(2026, 4, 19, 0, 49, 45)
EXPECTED_LAST_TS = datetime(2026, 4, 26, 13, 51, 22)
BATCH_SIZE = 20_000


class SimImportError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _naive_wib(epoch_seconds: int) -> datetime:
    return (
        datetime.fromtimestamp(int(epoch_seconds), tz=timezone.utc) + timedelta(hours=7)
    ).replace(tzinfo=None)


def _connect() -> psycopg.Connection[dict[str, Any]]:
    settings = Settings.from_environ()
    return cast(
        "psycopg.Connection[dict[str, Any]]",
        psycopg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            row_factory=dict_row,  # pyright: ignore[reportArgumentType]
        ),
    )


def _load_source(
    npz_path: Path, events_path: Path
) -> tuple[np.ndarray, list[datetime], np.ndarray, list[dict[str, Any]], int]:
    if not npz_path.is_file() or not events_path.is_file():
        raise SimImportError("both injected NPZ and event JSON files are required")

    with np.load(npz_path, allow_pickle=False) as archive:
        required = {"values", "timestamps", "seg_bounds", "frame_labels"}
        missing = required.difference(archive.files)
        if missing:
            raise SimImportError(f"injected NPZ is missing keys: {sorted(missing)}")
        values = archive["values"]
        epoch_seconds = archive["timestamps"]
        segment_bounds = archive["seg_bounds"]
        frame_labels = archive["frame_labels"]

    if values.shape != (EXPECTED_ROW_COUNT, 2):
        raise SimImportError(f"unexpected values shape: {values.shape}")
    if epoch_seconds.shape != (EXPECTED_ROW_COUNT,):
        raise SimImportError(f"unexpected timestamps shape: {epoch_seconds.shape}")
    if frame_labels.shape != (EXPECTED_ROW_COUNT,) or frame_labels.dtype != np.bool_:
        raise SimImportError("frame_labels must be a boolean row-aligned vector")
    if (
        segment_bounds.shape != (20,)
        or int(segment_bounds[0]) != 0
        or int(segment_bounds[-1]) != EXPECTED_ROW_COUNT
        or not bool(np.all(np.diff(segment_bounds) > 0))
    ):
        raise SimImportError("seg_bounds must contain 19 ordered full-coverage segments")

    timestamps = [_naive_wib(value) for value in epoch_seconds.tolist()]
    if min(timestamps) != EXPECTED_FIRST_TS or max(timestamps) != EXPECTED_LAST_TS:
        raise SimImportError(
            f"unexpected WIB range: {min(timestamps)}..{max(timestamps)}"
        )

    try:
        events = json.loads(events_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise SimImportError("injected event file is not valid JSON") from error
    if not isinstance(events, list) or len(events) != EXPECTED_EVENT_COUNT:
        raise SimImportError(f"expected {EXPECTED_EVENT_COUNT} injected events")
    if not all(isinstance(event, dict) for event in events):
        raise SimImportError("injected event file must contain objects")

    physical = np.asarray(SCALER_MINIMUM) + values.astype(np.float64) * (
        np.asarray(SCALER_MAXIMUM) - np.asarray(SCALER_MINIMUM)
    )
    if not bool(np.isfinite(physical).all()):
        raise SimImportError("denormalized telemetry contains non-finite values")
    frame_indexes = np.arange(EXPECTED_ROW_COUNT)
    segment_ids = np.searchsorted(segment_bounds[1:], frame_indexes, side="right")
    return physical, timestamps, segment_ids, events, int(frame_labels.sum())


def _segment_metadata(
    timestamps: list[datetime], segment_ids: np.ndarray
) -> list[dict[str, Any]]:
    metadata: list[dict[str, Any]] = []
    for segment_id in range(19):
        indexes = np.flatnonzero(segment_ids == segment_id)
        if indexes.size == 0:
            raise SimImportError(f"segment {segment_id} is empty")
        first = int(indexes[0])
        last = int(indexes[-1])
        metadata.append(
            {
                "segment_id": segment_id,
                "first_corpus_index": first,
                "last_corpus_index": last,
                "first_ts": timestamps[first].isoformat(),
                "last_ts": timestamps[last].isoformat(),
                "row_count": int(indexes.size),
            }
        )
    return metadata


def _upsert_device(connection: psycopg.Connection[dict[str, Any]]) -> None:
    connection.execute(
        """
        INSERT INTO devices (
            device_id, display_name, telemetry_kind, is_active, archived_at,
            time_zone, source_device_uuid
        ) VALUES (%s, %s, 'anomaly_injected', TRUE, NULL, %s, %s)
        ON CONFLICT (device_id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            telemetry_kind = EXCLUDED.telemetry_kind,
            is_active = EXCLUDED.is_active,
            archived_at = EXCLUDED.archived_at,
            time_zone = EXCLUDED.time_zone,
            source_device_uuid = EXCLUDED.source_device_uuid
        """,
        (SIM_DEVICE_ID, SIM_DISPLAY_NAME, TIME_ZONE, SOURCE_DEVICE_UUID),
    )


def _upsert_corpus(
    connection: psycopg.Connection[dict[str, Any]],
    archive_sha256: str,
    timestamps: list[datetime],
    frame_label_count: int,
) -> str:
    connection.execute(
        """
        INSERT INTO corpora (
            corpus_id, device_id, status, archive_sha256, member_sha256,
            preprocessing_contract_version, source_device_uuid, time_zone,
            interval_start, interval_end, filter_config, started_at, completed_at,
            accepted_count, ignored_index_count, rejection_counts
        ) VALUES (
            %s, %s, 'published', %s, %s, %s, %s, %s, %s, %s, %s::jsonb,
            now(), now(), %s, 0, '{}'::jsonb
        )
        ON CONFLICT (device_id, archive_sha256, preprocessing_contract_version)
        DO NOTHING
        """,
        (
            SIM_CORPUS_ID,
            SIM_DEVICE_ID,
            archive_sha256,
            archive_sha256,
            CONTRACT_VERSION,
            SOURCE_DEVICE_UUID,
            TIME_ZONE,
            min(timestamps),
            max(timestamps),
            json.dumps(
                {
                    "provenance": "injected anomaly simulation",
                    "source_split": "test",
                    "frame_label_count": frame_label_count,
                    "source_format": "npz with event JSON annotations",
                }
            ),
            EXPECTED_ROW_COUNT,
        ),
    )
    corpus_row = connection.execute(
        """
        SELECT corpus_id FROM corpora
        WHERE device_id = %s
          AND archive_sha256 = %s
          AND preprocessing_contract_version = %s
        """,
        (SIM_DEVICE_ID, archive_sha256, CONTRACT_VERSION),
    ).fetchone()
    if corpus_row is None or corpus_row["corpus_id"] != SIM_CORPUS_ID:
        raise SimImportError("simulation corpus identity resolves to an unexpected corpus")
    connection.execute(
        """
        INSERT INTO published_corpora (device_id, corpus_id, published_at)
        VALUES (%s, %s, now())
        ON CONFLICT (device_id) DO UPDATE SET
            corpus_id = EXCLUDED.corpus_id,
            published_at = EXCLUDED.published_at
        """,
        (SIM_DEVICE_ID, SIM_CORPUS_ID),
    )
    return str(corpus_row["corpus_id"])


def _upsert_snapshot(
    connection: psycopg.Connection[dict[str, Any]],
    corpus_id: str,
    segment_metadata: list[dict[str, Any]],
) -> None:
    connection.execute(
        """
        INSERT INTO preprocessing_snapshots (
            corpus_id, channels, window_size, stride, segment_metadata,
            split_boundaries, split_counts, scaler
        ) VALUES (%s, %s::jsonb, 30, 1, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb)
        ON CONFLICT (corpus_id) DO UPDATE SET
            channels = EXCLUDED.channels,
            window_size = EXCLUDED.window_size,
            stride = EXCLUDED.stride,
            segment_metadata = EXCLUDED.segment_metadata,
            split_boundaries = EXCLUDED.split_boundaries,
            split_counts = EXCLUDED.split_counts,
            scaler = EXCLUDED.scaler
        """,
        (
            corpus_id,
            json.dumps(CHANNELS),
            json.dumps(segment_metadata),
            json.dumps({"test_start": EXPECTED_FIRST_TS.isoformat()}),
            json.dumps({"test": EXPECTED_ROW_COUNT}),
            json.dumps(
                {
                    "channels": CHANNELS,
                    "minimum": SCALER_MINIMUM,
                    "maximum": SCALER_MAXIMUM,
                    "fit_split": "train",
                }
            ),
        ),
    )


def _telemetry_rows(
    timestamps: list[datetime], physical: np.ndarray, segment_ids: np.ndarray
) -> Iterator[tuple[datetime, float, float, int, int]]:
    for corpus_index, timestamp in enumerate(timestamps):
        yield (
            timestamp,
            float(physical[corpus_index, 0]),
            float(physical[corpus_index, 1]),
            corpus_index,
            int(segment_ids[corpus_index]),
        )


def _insert_telemetry(
    connection: psycopg.Connection[dict[str, Any]],
    corpus_id: str,
    timestamps: list[datetime],
    physical: np.ndarray,
    segment_ids: np.ndarray,
) -> int:
    count_row = connection.execute(
        "SELECT count(*) AS count FROM telemetry WHERE corpus_id = %s", (corpus_id,)
    ).fetchone()
    if count_row is None:
        raise SimImportError("simulation telemetry count could not be read")
    existing_count = int(count_row["count"])
    if existing_count == EXPECTED_ROW_COUNT:
        return 0
    if existing_count:
        raise SimImportError("simulation telemetry is partially loaded")

    connection.execute(
        """
        CREATE TEMP TABLE sim_telemetry_staging (
            ts timestamp without time zone NOT NULL,
            suhu double precision NOT NULL,
            rh double precision NOT NULL,
            corpus_index bigint NOT NULL,
            segment_id integer NOT NULL
        ) ON COMMIT DROP
        """
    )
    inserted = 0
    rows = _telemetry_rows(timestamps, physical, segment_ids)
    with connection.cursor() as cursor:
        while batch := list(_take(rows, BATCH_SIZE)):
            with cursor.copy(
                "COPY sim_telemetry_staging (ts, suhu, rh, corpus_index, segment_id) FROM STDIN"
            ) as copy:
                for row in batch:
                    copy.write_row(row)
            cursor.execute(
                """
                INSERT INTO telemetry (
                    device_id, ts, temperature_c, relative_humidity_pct, payload_hash,
                    source_index, corpus_id, corpus_index, segment_id, dataset_split
                )
                SELECT
                    %s,
                    ts,
                    suhu,
                    rh,
                    encode(
                        digest(
                            concat_ws(
                                '|', %s::text, ts::text, suhu::text, rh::text,
                                corpus_index::text
                            ),
                            'sha256'
                        ),
                        'hex'
                    ),
                    corpus_index,
                    %s,
                    corpus_index,
                    segment_id,
                    'test'
                FROM sim_telemetry_staging
                ORDER BY corpus_index
                ON CONFLICT (device_id, ts) DO NOTHING
                """,
                (SIM_DEVICE_ID, SIM_DEVICE_ID, corpus_id),
            )
            inserted += cursor.rowcount
            cursor.execute("TRUNCATE sim_telemetry_staging")
    return inserted


def _take(
    rows: Iterator[tuple[datetime, float, float, int, int]], size: int
) -> Iterator[tuple[datetime, float, float, int, int]]:
    for _ in range(size):
        try:
            yield next(rows)
        except StopIteration:
            return


def _upsert_events(
    connection: psycopg.Connection[dict[str, Any]],
    corpus_id: str,
    events: list[dict[str, Any]],
) -> None:
    rows = [
        (
            event["event_id"],
            corpus_id,
            SIM_DEVICE_ID,
            event["family"],
            event["severity"],
            event["channel"],
            event["channel_index"],
            event["start_idx"],
            event["end_idx_exclusive"],
            _naive_wib(event["start_ts"]),
            _naive_wib(event["end_ts_inclusive"]),
            event["segment_index"],
        )
        for event in events
    ]
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO injection_events (
                event_id, corpus_id, device_id, family, severity, channel,
                channel_index, start_idx, end_idx_exclusive, start_ts, end_ts,
                segment_index
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (event_id) DO UPDATE SET
                corpus_id = EXCLUDED.corpus_id,
                device_id = EXCLUDED.device_id,
                family = EXCLUDED.family,
                severity = EXCLUDED.severity,
                channel = EXCLUDED.channel,
                channel_index = EXCLUDED.channel_index,
                start_idx = EXCLUDED.start_idx,
                end_idx_exclusive = EXCLUDED.end_idx_exclusive,
                start_ts = EXCLUDED.start_ts,
                end_ts = EXCLUDED.end_ts,
                segment_index = EXCLUDED.segment_index
            """,
            rows,
        )


def _upsert_models(connection: psycopg.Connection[dict[str, Any]]) -> None:
    # is_public MUST stay FALSE: seed asserts exactly seven public preview
    # families/versions, so a public artifact family breaks seed and blocks
    # every service. The demo surfaces these via runtime_kind='artifact'.
    with connection.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO model_families (model_key, display_name, is_public)
            VALUES (%s, %s, FALSE)
            ON CONFLICT (model_key) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                is_public = EXCLUDED.is_public
            """,
            [
                ("artifact-lstm-ae", "LSTM-AE"),
                ("artifact-conv1d", "Conv1D Autoencoder"),
                ("artifact-transformer", "Transformer Autoencoder"),
                ("artifact-gru", "GRU-AE"),
                ("artifact-rnn", "RNN-AE"),
            ],
        )
        cursor.executemany(
            """
            INSERT INTO model_versions (
                version, model_key, runtime_kind, is_selectable, adapter_key,
                schema_version, channels, window_size, stride, score_key,
                score_semantics, threshold, threshold_policy, temporal_semantics,
                source_commit, source_config, manifest_sha256, created_at
            ) VALUES (
                %s, %s, 'artifact', TRUE, 'artifact_reconstruction_v1',
                %s, %s::jsonb, %s, 1, 'global_mse', %s, %s, %s::jsonb,
                'context_end', NULL, %s, %s, now()
            )
            ON CONFLICT (version) DO UPDATE SET
                model_key = EXCLUDED.model_key,
                runtime_kind = EXCLUDED.runtime_kind,
                is_selectable = EXCLUDED.is_selectable,
                adapter_key = EXCLUDED.adapter_key,
                schema_version = EXCLUDED.schema_version,
                channels = EXCLUDED.channels,
                window_size = EXCLUDED.window_size,
                stride = EXCLUDED.stride,
                score_key = EXCLUDED.score_key,
                score_semantics = EXCLUDED.score_semantics,
                threshold = EXCLUDED.threshold,
                threshold_policy = EXCLUDED.threshold_policy,
                temporal_semantics = EXCLUDED.temporal_semantics,
                source_commit = EXCLUDED.source_commit,
                source_config = EXCLUDED.source_config,
                manifest_sha256 = EXCLUDED.manifest_sha256
            """,
            [
                (
                    "artifact-lstm-ae-v3",
                    "artifact-lstm-ae",
                    CONTRACT_VERSION,
                    json.dumps(CHANNELS),
                    30,
                    "real reconstruction-error score from trained weights; unlike preview simulator rows, this is not synthesized",
                    0.0006799018211313575,
                    json.dumps(
                        {
                            "source": "artifact validation scores",
                            "percentile": 99.5,
                            "comparator": ">",
                        }
                    ),
                    "stored artifact validation percentile",
                    "f26a67d378c4b5a90e64f7dc3844d2971cb414d1bf60926fefa188b13df99212",
                ),
                (
                    "artifact-conv1d-v3",
                    "artifact-conv1d",
                    CONTRACT_VERSION,
                    json.dumps(CHANNELS),
                    30,
                    "real reconstruction-error score from trained weights; unlike preview simulator rows, this is not synthesized",
                    0.00033055954801966444,
                    json.dumps(
                        {
                            "source": "artifact validation scores",
                            "percentile": 99.5,
                            "comparator": ">",
                        }
                    ),
                    "stored artifact validation percentile",
                    "189a935b547163d00505deb4f654d59ca36d7077e54b87f4b5c472cf41c5fcc6",
                ),
                (
                    "artifact-transformer-v3",
                    "artifact-transformer",
                    CONTRACT_VERSION,
                    json.dumps(CHANNELS),
                    30,
                    "real reconstruction-error score from trained weights; unlike preview simulator rows, this is not synthesized",
                    0.0003650374799326533,
                    json.dumps(
                        {
                            "source": "artifact validation scores",
                            "percentile": 99.5,
                            "comparator": ">",
                        }
                    ),
                    "stored artifact validation percentile",
                    "21ec02b261b64f4491f0e5ecac1cbc41cba55fb7cb07d85b0596ca467e213b3b",
                ),
                (
                    "artifact-gru-v3",
                    "artifact-gru",
                    CONTRACT_VERSION,
                    json.dumps(CHANNELS),
                    10,
                    "real reconstruction-error score from trained weights; unlike preview simulator rows, this is not synthesized",
                    0.0005618056084495022,
                    json.dumps(
                        {
                            "source": "artifact validation scores",
                            "percentile": 99.5,
                            "comparator": ">",
                        }
                    ),
                    "stored artifact validation percentile",
                    "0506d1da27d92a259e62c32ce43db7fd19dfa8ad679c08c6d67bf727653a2caa",
                ),
                (
                    "artifact-rnn-v3",
                    "artifact-rnn",
                    CONTRACT_VERSION,
                    json.dumps(CHANNELS),
                    10,
                    "real reconstruction-error score from trained weights; unlike preview simulator rows, this is not synthesized",
                    0.0005023972923204374,
                    json.dumps(
                        {
                            "source": "artifact validation scores",
                            "percentile": 99.5,
                            "comparator": ">",
                        }
                    ),
                    "stored artifact validation percentile",
                    "c801a284c95c16ce9031a24f774d941c314bc0758e7b20d593af64fb630f0ebd",
                ),
            ],
        )
        # Seed one activation per artifact model so any of the three can be made
        # the sim device's active selection (replay resolves the model from
        # active_model_selections). Deterministic ids keep this idempotent.
        cursor.executemany(
            """
            INSERT INTO model_activations (
                activation_id, command_id, payload_hash, device_id,
                prior_model_version, model_version, changed, activated_at, actor
            ) VALUES (%s, %s, 'sim-seed', %s, NULL, %s, FALSE, now(), 'sim_importer')
            ON CONFLICT (activation_id) DO NOTHING
            """,
            [
                (
                    "activation-sim-artifact-lstm",
                    "activation-sim-artifact-lstm",
                    SIM_DEVICE_ID,
                    "artifact-lstm-ae-v3",
                ),
                (
                    "activation-sim-artifact-conv1d",
                    "activation-sim-artifact-conv1d",
                    SIM_DEVICE_ID,
                    "artifact-conv1d-v3",
                ),
                (
                    "activation-sim-artifact-transformer",
                    "activation-sim-artifact-transformer",
                    SIM_DEVICE_ID,
                    "artifact-transformer-v3",
                ),
                (
                    "activation-sim-artifact-gru",
                    "activation-sim-artifact-gru",
                    SIM_DEVICE_ID,
                    "artifact-gru-v3",
                ),
                (
                    "activation-sim-artifact-rnn",
                    "activation-sim-artifact-rnn",
                    SIM_DEVICE_ID,
                    "artifact-rnn-v3",
                ),
            ],
        )
        # Default the sim device to the LSTM artifact. DO NOTHING preserves a
        # later switch made through the simulation API across re-imports.
        cursor.execute(
            """
            INSERT INTO active_model_selections (device_id, activation_id, model_version)
            VALUES (%s, 'activation-sim-artifact-lstm', 'artifact-lstm-ae-v3')
            ON CONFLICT (device_id) DO NOTHING
            """,
            (SIM_DEVICE_ID,),
        )


def _assert_counts(connection: psycopg.Connection[dict[str, Any]], corpus_id: str) -> None:
    telemetry_row = connection.execute(
        "SELECT count(*) AS count FROM telemetry WHERE device_id = %s AND corpus_id = %s",
        (SIM_DEVICE_ID, corpus_id),
    ).fetchone()
    event_row = connection.execute(
        "SELECT count(*) AS count FROM injection_events WHERE corpus_id = %s",
        (corpus_id,),
    ).fetchone()
    model_row = connection.execute(
        """
        SELECT count(*) AS count FROM model_versions
        WHERE version IN ('artifact-lstm-ae-v3', 'artifact-conv1d-v3', 'artifact-transformer-v3', 'artifact-gru-v3', 'artifact-rnn-v3')
          AND runtime_kind = 'artifact'
        """
    ).fetchone()
    if (
        telemetry_row is None
        or event_row is None
        or model_row is None
        or int(telemetry_row["count"]) != EXPECTED_ROW_COUNT
        or int(event_row["count"]) != EXPECTED_EVENT_COUNT
        or int(model_row["count"]) != 5
    ):
        raise SimImportError("simulation import did not reach its expected counts")


def import_simulation_corpus(npz_path: Path, events_path: Path) -> dict[str, Any]:
    physical, timestamps, segment_ids, events, frame_label_count = _load_source(
        npz_path, events_path
    )
    archive_sha256 = _sha256_file(npz_path)
    connection = _connect()
    try:
        _upsert_device(connection)
        corpus_id = _upsert_corpus(
            connection,
            archive_sha256,
            timestamps,
            frame_label_count,
        )
        _upsert_snapshot(connection, corpus_id, _segment_metadata(timestamps, segment_ids))
        inserted = _insert_telemetry(
            connection, corpus_id, timestamps, physical, segment_ids
        )
        _upsert_events(connection, corpus_id, events)
        _upsert_models(connection)
        _assert_counts(connection, corpus_id)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return {
        "archive_sha256": archive_sha256,
        "corpus_id": corpus_id,
        "device_id": SIM_DEVICE_ID,
        "events": EXPECTED_EVENT_COUNT,
        "rows_inserted": inserted,
        "telemetry": EXPECTED_ROW_COUNT,
    }


def _run() -> None:
    npz_path = os.environ.get("SIM_INJECTED_NPZ_PATH")
    events_path = os.environ.get("SIM_INJECTED_EVENTS_PATH")
    if not npz_path or not events_path:
        raise SimImportError("SIM_INJECTED_NPZ_PATH and SIM_INJECTED_EVENTS_PATH are required")
    print(
        json.dumps(
            import_simulation_corpus(Path(npz_path), Path(events_path)), sort_keys=True
        )
    )


if __name__ == "__main__":
    _run()
