from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import tarfile
from typing import Any, cast
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from anomaly_backend.config import Settings


PUBLIC_DEVICE_ID = "b02f3872-ruang-produksi"
SOURCE_DEVICE_UUID = "b02f3872-39a2-4b6f-a4ec-045a287fde4b"
TIME_ZONE = "Asia/Jakarta"
CHANNELS = ("temperature_c", "relative_humidity_pct")
MEMBER_NAME = "b02f3872.csv"
EXPECTED_ARCHIVE_SHA256 = (
    "6c5a7ee8c248931bcc490cc114a3af55add8af82f976f58015ff7225dccce01a"
)
EXPECTED_MEMBER_SHA256 = (
    "849c694616f6e2b463d0ff46731b73a9ee865c03ab0dbc375eb634218c40c9c0"
)
EXPECTED_PUBLISHED_METADATA_SHA256 = (
    "51c324eaccf12449777e872c30eb52e3be91f33265dc441c4f3d04390b6e4a76"
)
CONTRACT_VERSION = "b02f3872_ruang_produksi_v2"
CROP_START = datetime(2026, 2, 1)
CROP_END = datetime(2026, 6, 1)
VALIDATION_START = datetime(2026, 5, 10)
TEST_START = datetime(2026, 5, 20)
EXPECTED_HEADER = ("device_id", "data_index", "value", "timestamp")
IMPORT_LOCK_ID = 20_260_724_3872


class CorpusImportError(RuntimeError):
    pass


def _archive_sha256(archive_path: Path) -> str:
    digest = hashlib.sha256()
    with archive_path.open("rb") as archive:
        for chunk in iter(lambda: archive.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_archive(archive_path: Path) -> tarfile.TarInfo:
    if not archive_path.is_file():
        raise CorpusImportError("configured archive is not a regular file")
    archive_sha256 = _archive_sha256(archive_path)
    if archive_sha256 != EXPECTED_ARCHIVE_SHA256:
        raise CorpusImportError("archive SHA-256 does not match the locked corpus")
    with tarfile.open(archive_path, "r:gz") as archive:
        members = archive.getmembers()
    if len(members) != 1:
        raise CorpusImportError("archive must contain exactly one member")
    member = members[0]
    member_path = PurePosixPath(member.name)
    if (
        member.name != MEMBER_NAME
        or member_path.is_absolute()
        or ".." in member_path.parts
        or not member.isfile()
        or member.issym()
        or member.islnk()
    ):
        raise CorpusImportError("archive member is not the approved regular CSV")
    return member


def _connection_string(settings: Settings) -> str:
    return (
        f"host={settings.postgres_host} port={settings.postgres_port} "
        f"dbname={settings.postgres_db} user={settings.postgres_user} "
        f"password={settings.postgres_password}"
    )


def _published_metadata_fingerprint(
    connection: psycopg.Connection[dict[str, Any]], corpus_id: str
) -> str | None:
    row = connection.execute(
        """
        SELECT encode(
            digest(
                jsonb_build_object(
                    'archive_sha256', corpora.archive_sha256,
                    'member_sha256', corpora.member_sha256,
                    'contract', corpora.preprocessing_contract_version,
                    'source_device_uuid', corpora.source_device_uuid,
                    'time_zone', corpora.time_zone,
                    'interval_start', corpora.interval_start,
                    'interval_end', corpora.interval_end,
                    'filter_config', corpora.filter_config,
                    'accepted_count', corpora.accepted_count,
                    'ignored_index_count', corpora.ignored_index_count,
                    'rejection_counts', corpora.rejection_counts,
                    'channels', preprocessing_snapshots.channels,
                    'window_size', preprocessing_snapshots.window_size,
                    'stride', preprocessing_snapshots.stride,
                    'segment_metadata',
                        preprocessing_snapshots.segment_metadata,
                    'split_boundaries',
                        preprocessing_snapshots.split_boundaries,
                    'split_counts', preprocessing_snapshots.split_counts,
                    'scaler', preprocessing_snapshots.scaler
                )::text,
                'sha256'
            ),
            'hex'
        ) AS fingerprint
        FROM corpora
        JOIN preprocessing_snapshots USING (corpus_id)
        WHERE corpora.corpus_id = %s
        """,
        (corpus_id,),
    ).fetchone()
    return str(row["fingerprint"]) if row is not None else None


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CorpusImportError("CSV contains a malformed timestamp") from error
    if parsed.tzinfo is not None:
        raise CorpusImportError("CSV timestamps must not contain an offset")
    return parsed


def _stream_to_staging(
    connection: psycopg.Connection[dict[str, Any]],
    archive_path: Path,
    stage_name: str,
) -> tuple[str, dict[str, int], int]:
    counts = {
        "wrong_device": 0,
        "outside_crop": 0,
        "unsupported_index": 0,
    }
    ignored_index_count = 0
    member_digest = hashlib.sha256()
    copy_statement = sql.SQL(
        "COPY {} (raw_ordinal, data_index, value, ts) FROM STDIN"
    ).format(sql.Identifier(stage_name))
    with archive_path.open("rb") as archive_file:
        archive_digest = hashlib.sha256()
        for archive_chunk in iter(
            lambda: archive_file.read(1024 * 1024), b""
        ):
            archive_digest.update(archive_chunk)
        if archive_digest.hexdigest() != EXPECTED_ARCHIVE_SHA256:
            raise CorpusImportError(
                "streamed archive descriptor does not match the locked SHA-256"
            )
        archive_file.seek(0)
        archive = tarfile.open(fileobj=archive_file, mode="r:gz")
        member = archive.getmember(MEMBER_NAME)
        binary = archive.extractfile(member)
        if binary is None:
            raise CorpusImportError("approved CSV member could not be opened")

        def decoded_lines() -> Any:
            for raw_line in binary:
                member_digest.update(raw_line)
                try:
                    yield raw_line.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise CorpusImportError(
                        "CSV member is not valid UTF-8"
                    ) from error

        reader = csv.reader(decoded_lines())
        try:
            header = tuple(next(reader))
        except StopIteration as error:
            raise CorpusImportError("CSV member is empty") from error
        if header != EXPECTED_HEADER:
            raise CorpusImportError("CSV header does not match the contract")

        try:
            with connection.cursor().copy(copy_statement) as copy:
                for raw_ordinal, row in enumerate(reader):
                    if len(row) != 4:
                        raise CorpusImportError("CSV row shape is invalid")
                    (
                        source_device_uuid,
                        index_text,
                        value_text,
                        timestamp_text,
                    ) = row
                    try:
                        data_index = int(index_text)
                        value = float(value_text)
                    except ValueError as error:
                        raise CorpusImportError(
                            "CSV contains malformed numeric data"
                        ) from error
                    if not math.isfinite(value):
                        raise CorpusImportError(
                            "CSV contains a nonfinite value"
                        )
                    timestamp = _parse_timestamp(timestamp_text)
                    if source_device_uuid != SOURCE_DEVICE_UUID:
                        raise CorpusImportError(
                            "CSV contains a source device UUID outside the "
                            "approved B02F3872 corpus"
                        )
                    if not CROP_START <= timestamp < CROP_END:
                        counts["outside_crop"] += 1
                        continue
                    if 2 <= data_index <= 7:
                        ignored_index_count += 1
                        continue
                    if data_index not in (0, 1):
                        counts["unsupported_index"] += 1
                        continue
                    copy.write_row(
                        (raw_ordinal, data_index, value, timestamp)
                    )
        finally:
            archive.close()
    return member_digest.hexdigest(), counts, ignored_index_count


def _create_clean_relation(
    connection: psycopg.Connection[dict[str, Any]],
    stage_name: str,
    clean_name: str,
) -> None:
    statement = sql.SQL(
        """
        CREATE UNLOGGED TABLE {} AS
        WITH duplicate_conflicts AS (
            SELECT DISTINCT ts
            FROM (
                SELECT ts, data_index
                FROM {}
                GROUP BY ts, data_index
                HAVING min(value) <> max(value)
            ) AS conflicts
        ), deduplicated AS (
            SELECT staged.ts, staged.data_index, min(staged.value) AS value
            FROM {} AS staged
            WHERE NOT EXISTS (
                SELECT 1
                FROM duplicate_conflicts
                WHERE duplicate_conflicts.ts = staged.ts
            )
            GROUP BY staged.ts, staged.data_index
        ), paired AS (
            SELECT
                ts,
                max(value) FILTER (WHERE data_index = 0) AS suhu,
                max(value) FILTER (WHERE data_index = 1) AS rh,
                count(*) AS channel_count
            FROM deduplicated
            GROUP BY ts
        ), valid_pairs AS (
            SELECT ts, suhu, rh
            FROM paired
            WHERE channel_count = 2
              AND suhu > 0 AND rh > 0
              AND suhu < 200 AND rh < 200
              AND rh <= 100
        ), suspect_points AS (
            SELECT
                ts,
                CASE
                    WHEN lag(ts) OVER (ORDER BY ts) IS NULL THEN 1
                    WHEN ts - lag(ts) OVER (ORDER BY ts) > interval '600 seconds'
                        THEN 1
                    ELSE 0
                END AS episode_start
            FROM valid_pairs
            WHERE suhu > 35 OR rh > 80
        ), suspect_grouped AS (
            SELECT
                ts,
                sum(episode_start) OVER (ORDER BY ts) AS episode_id
            FROM suspect_points
        ), suspect_intervals AS (
            SELECT
                min(ts) - interval '600 seconds' AS start_ts,
                max(ts) + interval '600 seconds' AS end_ts
            FROM suspect_grouped
            GROUP BY episode_id
        ), clean_pairs AS (
            SELECT valid_pairs.*
            FROM valid_pairs
            WHERE NOT EXISTS (
                SELECT 1
                FROM suspect_intervals
                WHERE valid_pairs.ts BETWEEN start_ts AND end_ts
            )
        ), boundaries AS (
            SELECT
                *,
                CASE
                    WHEN lag(ts) OVER (ORDER BY ts) IS NULL THEN 1
                    WHEN ts - lag(ts) OVER (ORDER BY ts) > interval '600 seconds'
                        THEN 1
                    ELSE 0
                END AS segment_start
            FROM clean_pairs
        ), indexed AS (
            SELECT
                ts,
                suhu,
                rh,
                row_number() OVER (ORDER BY ts) - 1 AS corpus_index,
                sum(segment_start) OVER (ORDER BY ts) - 1 AS segment_id
            FROM boundaries
        )
        SELECT
            ts,
            suhu::double precision,
            rh::double precision,
            corpus_index::bigint,
            segment_id::integer,
            CASE
                WHEN ts < TIMESTAMP '2026-05-10 00:00:00' THEN 'train'
                WHEN ts < TIMESTAMP '2026-05-20 00:00:00' THEN 'validation'
                ELSE 'test'
            END::text AS dataset_split
        FROM indexed
        ORDER BY ts
        """
    ).format(
        sql.Identifier(clean_name),
        sql.Identifier(stage_name),
        sql.Identifier(stage_name),
    )
    connection.execute(statement)


def _audit_transform(
    connection: psycopg.Connection[dict[str, Any]],
    stage_name: str,
    clean_name: str,
    stream_counts: dict[str, int],
) -> tuple[dict[str, int], dict[str, Any], dict[str, int], list[dict[str, Any]]]:
    names = {
        "stage": sql.Identifier(stage_name),
        "clean": sql.Identifier(clean_name),
    }
    query = sql.SQL(
        """
        WITH duplicate_conflicts AS (
            SELECT DISTINCT ts
            FROM (
                SELECT ts, data_index
                FROM {stage}
                GROUP BY ts, data_index
                HAVING min(value) <> max(value)
            ) AS conflicts
        ), deduplicated AS (
            SELECT staged.ts, staged.data_index, min(staged.value) AS value
            FROM {stage} AS staged
            WHERE NOT EXISTS (
                SELECT 1 FROM duplicate_conflicts
                WHERE duplicate_conflicts.ts = staged.ts
            )
            GROUP BY staged.ts, staged.data_index
        ), paired AS (
            SELECT
                ts,
                max(value) FILTER (WHERE data_index = 0) AS suhu,
                max(value) FILTER (WHERE data_index = 1) AS rh,
                count(*) AS channel_count
            FROM deduplicated
            GROUP BY ts
        ), valid_pairs AS (
            SELECT ts, suhu, rh
            FROM paired
            WHERE channel_count = 2
              AND suhu > 0 AND rh > 0
              AND suhu < 200 AND rh < 200
              AND rh <= 100
        )
        SELECT
            (
                SELECT coalesce(sum(row_count - distinct_count), 0)
                FROM (
                    SELECT
                        count(*) AS row_count,
                        count(DISTINCT value) AS distinct_count
                    FROM {stage}
                    GROUP BY ts, data_index
                ) AS duplicate_counts
            )::bigint AS duplicate_identical,
            (SELECT count(*) FROM duplicate_conflicts)::bigint
                AS duplicate_conflict,
            (
                SELECT count(*) FROM paired
                WHERE channel_count <> 2
            )::bigint AS incomplete_pair,
            (
                SELECT count(*) FROM paired
                WHERE channel_count = 2
                  AND NOT (
                      suhu > 0 AND rh > 0
                      AND suhu < 200 AND rh < 200
                      AND rh <= 100
                  )
            )::bigint AS invalid_or_sentinel,
            (
                SELECT count(*) FROM valid_pairs
            )::bigint - (
                SELECT count(*) FROM {clean}
            )::bigint AS suspect_buffer
        """
    ).format(**names)
    row = connection.execute(query).fetchone()
    if row is None:
        raise CorpusImportError("transform audit could not be computed")
    rejection_counts = {
        **stream_counts,
        **{key: int(value) for key, value in row.items()},
    }
    scaler_row = connection.execute(
        sql.SQL(
            """
            SELECT
                min(suhu) AS suhu_min,
                max(suhu) AS suhu_max,
                min(rh) AS rh_min,
                max(rh) AS rh_max
            FROM {}
            WHERE dataset_split = 'train'
            """
        ).format(sql.Identifier(clean_name))
    ).fetchone()
    if (
        scaler_row is None
        or scaler_row["suhu_min"] is None
        or scaler_row["rh_min"] is None
    ):
        raise CorpusImportError("clean corpus does not contain a train split")
    scaler = {
        "channels": ["suhu", "rh"],
        "minimum": [
            float(scaler_row["suhu_min"]),
            float(scaler_row["rh_min"]),
        ],
        "maximum": [
            float(scaler_row["suhu_max"]),
            float(scaler_row["rh_max"]),
        ],
        "fit_split": "train",
    }
    split_rows = connection.execute(
        sql.SQL(
            "SELECT dataset_split, count(*)::bigint AS count "
            "FROM {} GROUP BY dataset_split"
        ).format(sql.Identifier(clean_name))
    ).fetchall()
    split_counts = {
        str(item["dataset_split"]): int(item["count"])
        for item in split_rows
    }
    segments = connection.execute(
        sql.SQL(
            """
            SELECT
                segment_id,
                min(ts) AS first_ts,
                max(ts) AS last_ts,
                min(corpus_index)::bigint AS first_corpus_index,
                max(corpus_index)::bigint AS last_corpus_index,
                count(*)::bigint AS row_count
            FROM {}
            GROUP BY segment_id
            ORDER BY segment_id
            """
        ).format(sql.Identifier(clean_name))
    ).fetchall()
    return rejection_counts, scaler, split_counts, list(segments)


def import_corpus(
    archive_path: Path,
    *,
    expected_archive_sha256: str = EXPECTED_ARCHIVE_SHA256,
) -> dict[str, Any]:
    if expected_archive_sha256 != EXPECTED_ARCHIVE_SHA256:
        raise CorpusImportError("expected archive hash cannot be overridden")
    _validate_archive(archive_path)
    settings = Settings.from_environ()
    corpus_id = f"corpus_b02_{EXPECTED_ARCHIVE_SHA256[:24]}"
    stage_name = f"import_stage_{uuid4().hex}"
    clean_name = f"import_clean_{uuid4().hex}"
    started_at = datetime.now(timezone.utc)
    created_corpus_record = False
    lock_acquired = False
    connection = cast(
        psycopg.Connection[dict[str, Any]],
        psycopg.connect(
            _connection_string(settings),
            row_factory=dict_row,  # pyright: ignore[reportArgumentType]
            autocommit=False,
        ),
    )
    try:
        connection.execute("SELECT pg_advisory_lock(%s)", (IMPORT_LOCK_ID,))
        lock_acquired = True
        with connection.transaction():
            orphan_rows = connection.execute(
                """
                SELECT relname
                FROM pg_class
                JOIN pg_namespace
                  ON pg_namespace.oid = pg_class.relnamespace
                WHERE pg_namespace.nspname = current_schema()
                  AND pg_class.relkind IN ('r', 'p')
                  AND (
                    relname LIKE 'import_stage_%'
                    OR relname LIKE 'import_clean_%'
                  )
                """
            ).fetchall()
            for orphan in orphan_rows:
                connection.execute(
                    sql.SQL("DROP TABLE {}").format(
                        sql.Identifier(str(orphan["relname"]))
                    )
                )
            existing = connection.execute(
                """
                SELECT *
                FROM corpora
                WHERE device_id = %s
                  AND archive_sha256 = %s
                  AND preprocessing_contract_version = %s
                """,
                (
                    PUBLIC_DEVICE_ID,
                    EXPECTED_ARCHIVE_SHA256,
                    CONTRACT_VERSION,
                ),
            ).fetchone()
            if existing is not None and existing["status"] == "published":
                consistency = connection.execute(
                    """
                    SELECT
                        published_corpora.corpus_id AS pointer_corpus_id,
                        preprocessing_snapshots.channels,
                        preprocessing_snapshots.window_size,
                        preprocessing_snapshots.stride,
                        (
                            SELECT count(*)::bigint
                            FROM telemetry
                            WHERE telemetry.corpus_id = corpora.corpus_id
                        ) AS telemetry_count
                    FROM corpora
                    LEFT JOIN published_corpora
                      ON published_corpora.device_id = corpora.device_id
                    LEFT JOIN preprocessing_snapshots
                      ON preprocessing_snapshots.corpus_id = corpora.corpus_id
                    WHERE corpora.corpus_id = %s
                    """,
                    (corpus_id,),
                ).fetchone()
                consistent = (
                    consistency is not None
                    and consistency["pointer_corpus_id"] == corpus_id
                    and tuple(consistency["channels"] or ()) == CHANNELS
                    and consistency["window_size"] == 10
                    and consistency["stride"] == 1
                    and int(consistency["telemetry_count"])
                    == int(existing["accepted_count"])
                    and existing["source_device_uuid"] == SOURCE_DEVICE_UUID
                    and existing["time_zone"] == TIME_ZONE
                    and existing["interval_start"] == CROP_START
                    and existing["interval_end"] == CROP_END
                    and existing["member_sha256"] == EXPECTED_MEMBER_SHA256
                    and _published_metadata_fingerprint(
                        connection, corpus_id
                    )
                    == EXPECTED_PUBLISHED_METADATA_SHA256
                )
                if not consistent:
                    raise CorpusImportError(
                        "published corpus identity has inconsistent metadata"
                    )
                return {
                    "corpus_id": existing["corpus_id"],
                    "status": "published",
                    "accepted_count": int(existing["accepted_count"]),
                    "idempotent_noop": True,
                }
            published = connection.execute(
                """
                SELECT published_corpora.corpus_id
                FROM published_corpora
                WHERE device_id = %s
                """,
                (PUBLIC_DEVICE_ID,),
            ).fetchone()
            if published is not None:
                raise CorpusImportError(
                    "a different corpus is already published for this device: "
                    f"{published['corpus_id']}"
                )
            if existing is not None:
                dependencies = connection.execute(
                    """
                    SELECT
                        EXISTS (
                            SELECT 1 FROM telemetry WHERE corpus_id = %s
                        ) AS has_telemetry,
                        EXISTS (
                            SELECT 1 FROM preprocessing_snapshots
                            WHERE corpus_id = %s
                        ) AS has_snapshot,
                        EXISTS (
                            SELECT 1 FROM published_corpora
                            WHERE corpus_id = %s
                        ) AS has_pointer
                    """,
                    (corpus_id, corpus_id, corpus_id),
                ).fetchone()
                if dependencies is None or any(dependencies.values()):
                    raise CorpusImportError(
                        "non-published corpus has unsafe dependent data"
                    )
                connection.execute(
                    "DELETE FROM corpora WHERE corpus_id = %s",
                    (corpus_id,),
                )
            connection.execute(
                """
                INSERT INTO corpora (
                    corpus_id, device_id, status, archive_sha256,
                    member_sha256, preprocessing_contract_version,
                    source_device_uuid, time_zone, interval_start, interval_end,
                    filter_config, started_at, completed_at, accepted_count,
                    ignored_index_count, rejection_counts
                ) VALUES (
                    %s, %s, 'staging', %s, NULL, %s, %s, %s, %s, %s,
                    %s::jsonb, %s, NULL, 0, 0, '{}'::jsonb
                )
                """,
                (
                    corpus_id,
                    PUBLIC_DEVICE_ID,
                    EXPECTED_ARCHIVE_SHA256,
                    CONTRACT_VERSION,
                    SOURCE_DEVICE_UUID,
                    TIME_ZONE,
                    CROP_START,
                    CROP_END,
                    json.dumps(
                        {
                            "crop": {
                                "from": CROP_START.isoformat(),
                                "to": CROP_END.isoformat(),
                                "bounds": "[)",
                            },
                            "channels": {"0": "suhu", "1": "rh"},
                            "suspect": {
                                "suhu_gt": 35,
                                "rh_gt": 80,
                                "merge_seconds": 600,
                                "buffer_seconds": 600,
                            },
                            "gap_seconds_gt": 600,
                        }
                    ),
                    started_at,
                ),
            )
            created_corpus_record = True

        connection.execute(
            sql.SQL(
                "CREATE UNLOGGED TABLE {} ("
                "raw_ordinal bigint NOT NULL, "
                "data_index integer NOT NULL, "
                "value double precision NOT NULL, "
                "ts timestamp without time zone NOT NULL)"
            ).format(sql.Identifier(stage_name))
        )
        connection.commit()
        member_sha256, stream_counts, ignored_index_count = _stream_to_staging(
            connection, archive_path, stage_name
        )
        if member_sha256 != EXPECTED_MEMBER_SHA256:
            raise CorpusImportError(
                "CSV member SHA-256 does not match the locked corpus"
            )
        connection.commit()
        _create_clean_relation(connection, stage_name, clean_name)
        connection.commit()
        (
            rejection_counts,
            scaler,
            split_counts,
            segments,
        ) = _audit_transform(connection, stage_name, clean_name, stream_counts)
        accepted_row = connection.execute(
                sql.SQL("SELECT count(*)::bigint AS count FROM {}").format(
                    sql.Identifier(clean_name)
                )
            ).fetchone()
        if accepted_row is None:
            raise CorpusImportError("clean corpus count could not be read")
        accepted_count = int(accepted_row["count"])
        if accepted_count <= 0:
            raise CorpusImportError("preprocessing produced an empty corpus")

        completed_at = datetime.now(timezone.utc)
        with connection.transaction():
            connection.execute(
                sql.SQL(
                    """
                    INSERT INTO telemetry (
                        device_id, ts, temperature_c,
                        relative_humidity_pct, payload_hash, source_index,
                        corpus_id, corpus_index, segment_id, dataset_split
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
                        dataset_split
                    FROM {}
                    ORDER BY corpus_index
                    """
                ).format(sql.Identifier(clean_name)),
                (PUBLIC_DEVICE_ID, PUBLIC_DEVICE_ID, corpus_id),
            )
            connection.execute(
                """
                INSERT INTO preprocessing_snapshots (
                    corpus_id, channels, window_size, stride,
                    contract_status, segment_metadata, split_boundaries,
                    split_counts, scaler
                ) VALUES (
                    %s, %s::jsonb, 10, 1, 'live_10', %s::jsonb, %s::jsonb,
                    %s::jsonb, %s::jsonb
                )
                """,
                (
                    corpus_id,
                    json.dumps(list(CHANNELS)),
                    json.dumps(
                        [
                            {
                                **segment,
                                "first_ts": segment["first_ts"].isoformat(),
                                "last_ts": segment["last_ts"].isoformat(),
                            }
                            for segment in segments
                        ]
                    ),
                    json.dumps(
                        {
                            "validation_start": VALIDATION_START.isoformat(),
                            "test_start": TEST_START.isoformat(),
                        }
                    ),
                    json.dumps(split_counts),
                    json.dumps(scaler),
                ),
            )
            published_row = connection.execute(
                """
                UPDATE corpora
                SET
                    status = 'published',
                    member_sha256 = %s,
                    completed_at = %s,
                    accepted_count = %s,
                    ignored_index_count = %s,
                    rejection_counts = %s::jsonb
                WHERE corpus_id = %s AND status = 'staging'
                RETURNING corpus_id
                """,
                (
                    member_sha256,
                    completed_at,
                    accepted_count,
                    ignored_index_count,
                    json.dumps(rejection_counts),
                    corpus_id,
                ),
            ).fetchone()
            if published_row is None:
                raise CorpusImportError(
                    "corpus staging ownership was lost before publication"
                )
            connection.execute(
                """
                INSERT INTO published_corpora (
                    device_id, corpus_id, published_at
                ) VALUES (%s, %s, %s)
                """,
                (PUBLIC_DEVICE_ID, corpus_id, completed_at),
            )
            if (
                _published_metadata_fingerprint(connection, corpus_id)
                != EXPECTED_PUBLISHED_METADATA_SHA256
            ):
                raise CorpusImportError(
                    "published preprocessing metadata does not match the "
                    "locked deterministic corpus"
                )
        return {
            "corpus_id": corpus_id,
            "status": "published",
            "accepted_count": accepted_count,
            "ignored_index_count": ignored_index_count,
            "rejection_counts": rejection_counts,
            "member_sha256": member_sha256,
            "idempotent_noop": False,
        }
    except Exception:
        connection.rollback()
        if created_corpus_record:
            try:
                with connection.transaction():
                    connection.execute(
                        """
                        UPDATE corpora
                        SET status = 'failed', completed_at = %s
                        WHERE corpus_id = %s AND status = 'staging'
                        """,
                        (datetime.now(timezone.utc), corpus_id),
                    )
            except Exception:
                connection.rollback()
        raise
    finally:
        for relation_name in (clean_name, stage_name):
            try:
                connection.execute(
                    sql.SQL("DROP TABLE IF EXISTS {}").format(
                        sql.Identifier(relation_name)
                    )
                )
                connection.commit()
            except Exception:
                connection.rollback()
        if lock_acquired:
            try:
                connection.execute(
                    "SELECT pg_advisory_unlock(%s)", (IMPORT_LOCK_ID,)
                )
                connection.commit()
            except Exception:
                connection.rollback()
        connection.close()


def _run() -> None:
    configured = os.environ.get("B02_RAW_ARCHIVE_PATH")
    if not configured:
        raise CorpusImportError("B02_RAW_ARCHIVE_PATH is required")
    result = import_corpus(Path(configured))
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    _run()
