from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import socket
import time
from typing import Any, cast

import psycopg
from psycopg.rows import dict_row

from anomaly_backend.config import Settings
from anomaly_worker.scorer import (
    CHANNELS,
    PreviewSimulatorScorer,
    ScoreBatch,
    Scorer,
    TemporalSemantics,
)


CHUNK_SIZE = 512
LEASE_SECONDS = 60
POLL_SECONDS = 1.0


class ReplayWorkerError(RuntimeError):
    pass


def _connection_string(settings: Settings) -> str:
    return (
        f"host={settings.postgres_host} port={settings.postgres_port} "
        f"dbname={settings.postgres_db} user={settings.postgres_user} "
        f"password={settings.postgres_password}"
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _worker_id() -> str:
    configured = os.environ.get("PREVIEW_WORKER_ID")
    return configured or f"{socket.gethostname()}-{os.getpid()}"


def _heartbeat(
    connection: psycopg.Connection[dict[str, Any]], worker_id: str
) -> None:
    now = _utc_now()
    connection.execute(
        """
        INSERT INTO worker_heartbeats (worker_id, started_at, heartbeat_at)
        VALUES (%s, %s, %s)
        ON CONFLICT (worker_id) DO UPDATE
        SET heartbeat_at = EXCLUDED.heartbeat_at
        """,
        (worker_id, now, now),
    )


def _lock_owned_job(
    connection: psycopg.Connection[dict[str, Any]],
    job_id: str,
    worker_id: str,
    attempt_count: int,
) -> dict[str, Any]:
    owned = connection.execute(
        """
        SELECT *
        FROM replay_jobs
        WHERE job_id = %s
          AND status = 'running'
          AND lease_owner = %s
          AND attempt_count = %s
          AND lease_expires_at >= %s
        FOR UPDATE
        """,
        (job_id, worker_id, attempt_count, _utc_now()),
    ).fetchone()
    if owned is None:
        raise ReplayWorkerError("replay lease ownership was lost")
    return dict(owned)


def claim_job(
    connection: psycopg.Connection[dict[str, Any]], worker_id: str
) -> dict[str, Any] | None:
    with connection.transaction():
        _heartbeat(connection, worker_id)
        now = _utc_now()
        expired_terminal = connection.execute(
            """
            SELECT job_id
            FROM replay_jobs
            WHERE status = 'running'
              AND lease_expires_at < %s
              AND attempt_count >= max_attempts
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if expired_terminal is not None:
            job_id = expired_terminal["job_id"]
            connection.execute(
                "DELETE FROM replay_result_staging WHERE job_id = %s",
                (job_id,),
            )
            connection.execute(
                "DELETE FROM replay_episode_staging WHERE job_id = %s",
                (job_id,),
            )
            connection.execute(
                "DELETE FROM replay_episode_checkpoints WHERE job_id = %s",
                (job_id,),
            )
            connection.execute(
                """
                UPDATE replay_jobs
                SET status = 'failed',
                    completed_at = %s,
                    lease_owner = NULL,
                    lease_expires_at = NULL,
                    error_code = 'max_attempts_exhausted',
                    error_detail = 'Preview replay exhausted its retry budget'
                WHERE job_id = %s
                """,
                (now, job_id),
            )

        job = connection.execute(
            """
            SELECT *
            FROM replay_jobs
            WHERE (
                status = 'queued'
                OR (
                    status = 'running'
                    AND lease_expires_at < %s
                    AND attempt_count < max_attempts
                )
            )
            ORDER BY submitted_at, job_id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """,
            (now,),
        ).fetchone()
        if job is None:
            return None
        claimed = connection.execute(
            """
            UPDATE replay_jobs
            SET status = 'running',
                lease_owner = %s,
                lease_expires_at = %s,
                heartbeat_at = %s,
                attempt_count = attempt_count + 1,
                started_at = coalesce(started_at, %s),
                error_code = NULL,
                error_detail = NULL
            WHERE job_id = %s
            RETURNING *
            """,
            (
                worker_id,
                now + timedelta(seconds=LEASE_SECONDS),
                now,
                now,
                job["job_id"],
            ),
        ).fetchone()
        return dict(claimed) if claimed is not None else None


def _scaler(
    connection: psycopg.Connection[dict[str, Any]], corpus_id: str
) -> tuple[tuple[float, float], tuple[float, float]]:
    row = connection.execute(
        """
        SELECT scaler
        FROM preprocessing_snapshots
        WHERE corpus_id = %s
        """,
        (corpus_id,),
    ).fetchone()
    if row is None or not isinstance(row["scaler"], dict):
        raise ReplayWorkerError("preprocessing snapshot is missing")
    scaler = row["scaler"]
    minimum = scaler.get("minimum")
    maximum = scaler.get("maximum")
    if (
        not isinstance(minimum, list)
        or not isinstance(maximum, list)
        or len(minimum) != 2
        or len(maximum) != 2
    ):
        raise ReplayWorkerError("preprocessing scaler shape is invalid")
    return (
        (float(minimum[0]), float(minimum[1])),
        (float(maximum[0]), float(maximum[1])),
    )


def _scale_pair(
    value: tuple[float, float],
    minimum: tuple[float, float],
    maximum: tuple[float, float],
) -> tuple[float, float]:
    scaled: list[float] = []
    for position, raw in enumerate(value):
        width = maximum[position] - minimum[position]
        scaled.append(0.0 if width == 0 else (raw - minimum[position]) / width)
    return cast(tuple[float, float], tuple(scaled))


def _target_rows(
    connection: psycopg.Connection[dict[str, Any]],
    job: dict[str, Any],
) -> list[dict[str, Any]]:
    return list(
        connection.execute(
            """
            SELECT
                ts, temperature_c, relative_humidity_pct,
                corpus_index, segment_id
            FROM telemetry
            WHERE corpus_id = %s
              AND ts >= %s
              AND ts < %s
              AND corpus_index >= %s
            ORDER BY corpus_index
            LIMIT %s
            """,
            (
                job["corpus_id"],
                job["from_ts"],
                job["to_ts"],
                job["next_corpus_index"],
                CHUNK_SIZE,
            ),
        ).fetchall()
    )


def _context_rows(
    connection: psycopg.Connection[dict[str, Any]],
    job: dict[str, Any],
    targets: list[dict[str, Any]],
) -> dict[int, dict[str, Any]]:
    start = max(0, int(targets[0]["corpus_index"]) - 30)
    end = int(targets[-1]["corpus_index"])
    rows = connection.execute(
        """
        SELECT
            ts, temperature_c, relative_humidity_pct,
            corpus_index, segment_id
        FROM telemetry
        WHERE corpus_id = %s
          AND corpus_index BETWEEN %s AND %s
        ORDER BY corpus_index
        """,
        (job["corpus_id"], start, end),
    ).fetchall()
    return {int(row["corpus_index"]): dict(row) for row in rows}


def _segment_starts(
    connection: psycopg.Connection[dict[str, Any]],
    corpus_id: str,
    segment_ids: Iterable[int],
) -> dict[int, int]:
    identifiers = sorted(set(segment_ids))
    if not identifiers:
        return {}
    rows = connection.execute(
        """
        SELECT segment_id, min(corpus_index)::bigint AS first_index
        FROM telemetry
        WHERE corpus_id = %s AND segment_id = ANY(%s)
        GROUP BY segment_id
        """,
        (corpus_id, identifiers),
    ).fetchall()
    return {
        int(row["segment_id"]): int(row["first_index"])
        for row in rows
    }


def _score_batch(
    connection: psycopg.Connection[dict[str, Any]],
    job: dict[str, Any],
    targets: list[dict[str, Any]],
) -> tuple[
    ScoreBatch,
    list[dict[str, Any]],
    float,
    tuple[float, float],
    tuple[float, float],
]:
    version = connection.execute(
        """
        SELECT *
        FROM model_versions
        WHERE version = %s
        """,
        (job["model_version"],),
    ).fetchone()
    if version is None:
        raise ReplayWorkerError("job model snapshot no longer exists")
    temporal = TemporalSemantics(str(version["temporal_semantics"]))
    required_preceding = 30 if temporal is TemporalSemantics.NEXT_TARGET else 29
    contexts = _context_rows(connection, job, targets)
    segment_starts = _segment_starts(
        connection,
        str(job["corpus_id"]),
        (int(target["segment_id"]) for target in targets),
    )
    minimum, maximum = _scaler(connection, str(job["corpus_id"]))

    eligible: list[dict[str, Any]] = []
    raw_values = []
    model_values = []
    context_ts = []
    context_start_indices = []
    context_end_indices = []
    segment_ids = []
    ordinals = []
    target_ts = []
    target_raw_values = []
    target_model_values = []

    for target in targets:
        target_index = int(target["corpus_index"])
        segment_id = int(target["segment_id"])
        start_index = target_index - required_preceding
        end_index = (
            target_index - 1
            if temporal is TemporalSemantics.NEXT_TARGET
            else target_index
        )
        window = [
            contexts.get(index)
            for index in range(start_index, end_index + 1)
        ]
        if (
            len(window) != 30
            or any(row is None for row in window)
            or any(int(cast(dict[str, Any], row)["segment_id"]) != segment_id for row in window)
        ):
            continue
        typed_window = [cast(dict[str, Any], row) for row in window]
        raw_window = tuple(
            (
                float(row["temperature_c"]),
                float(row["relative_humidity_pct"]),
            )
            for row in typed_window
        )
        scaled_window = tuple(
            _scale_pair(pair, minimum, maximum) for pair in raw_window
        )
        raw_target = (
            float(target["temperature_c"]),
            float(target["relative_humidity_pct"]),
        )
        raw_values.append(raw_window)
        model_values.append(scaled_window)
        context_ts.append(tuple(cast(datetime, row["ts"]) for row in typed_window))
        context_start_indices.append(start_index)
        context_end_indices.append(end_index)
        segment_ids.append(segment_id)
        ordinal = (
            end_index - segment_starts[segment_id] - 29
        )
        if ordinal < 0:
            continue
        ordinals.append(ordinal)
        target_ts.append(cast(datetime, target["ts"]))
        target_raw_values.append(raw_target)
        target_model_values.append(_scale_pair(raw_target, minimum, maximum))
        eligible.append(
            {
                "target": target,
                "window_start_ts": typed_window[0]["ts"],
                "window_end_ts": typed_window[-1]["ts"],
                "source_start_index": start_index,
                "source_end_index": end_index,
                "eligible_window_ordinal": ordinal,
            }
        )

    if not eligible:
        raise ReplayWorkerError("batch contains no eligible windows")
    batch = ScoreBatch(
        model_version=str(job["model_version"]),
        schema_version=str(version["schema_version"]),
        channels=CHANNELS,
        raw_values=tuple(raw_values),
        model_values=tuple(model_values),
        context_ts=tuple(context_ts),
        context_start_indices=tuple(context_start_indices),
        context_end_indices=tuple(context_end_indices),
        segment_ids=tuple(segment_ids),
        eligible_window_ordinals=tuple(ordinals),
        target_ts=tuple(target_ts),
        target_raw_values=(
            tuple(target_raw_values)
            if temporal is TemporalSemantics.NEXT_TARGET
            else None
        ),
        target_model_values=(
            tuple(target_model_values)
            if temporal is TemporalSemantics.NEXT_TARGET
            else None
        ),
    )
    return batch, eligible, float(version["threshold"]), minimum, maximum


def _default_checkpoint() -> dict[str, Any]:
    return {
        "next_episode_ordinal": 0,
        "open_episode": None,
    }


def _load_checkpoint(
    connection: psycopg.Connection[dict[str, Any]], job_id: str
) -> dict[str, Any]:
    row = connection.execute(
        "SELECT state FROM replay_episode_checkpoints WHERE job_id = %s",
        (job_id,),
    ).fetchone()
    if row is None:
        return _default_checkpoint()
    state = row["state"]
    if not isinstance(state, dict):
        raise ReplayWorkerError("episode checkpoint is malformed")
    return state


def _close_episode(
    connection: psycopg.Connection[dict[str, Any]],
    job_id: str,
    state: dict[str, Any],
    reason: str,
) -> None:
    episode = state.get("open_episode")
    if not isinstance(episode, dict):
        return
    ordinal = int(state["next_episode_ordinal"])
    connection.execute(
        """
        INSERT INTO replay_episode_staging (
            job_id, episode_ordinal, segment_id,
            episode_start_ts, episode_end_ts, last_score_ts,
            first_window_start_ts, first_window_end_ts,
            peak_score, latest_score, anomalous_window_count,
            closure_reason
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
        """,
        (
            job_id,
            ordinal,
            episode["segment_id"],
            datetime.fromisoformat(episode["episode_start_ts"]),
            datetime.fromisoformat(episode["episode_end_ts"]),
            datetime.fromisoformat(episode["last_score_ts"]),
            datetime.fromisoformat(episode["first_window_start_ts"]),
            datetime.fromisoformat(episode["first_window_end_ts"]),
            episode["peak_score"],
            episode["latest_score"],
            episode["anomalous_window_count"],
            reason,
        ),
    )
    state["next_episode_ordinal"] = ordinal + 1
    state["open_episode"] = None


def _accumulate_episodes(
    connection: psycopg.Connection[dict[str, Any]],
    job: dict[str, Any],
    state: dict[str, Any],
    staged_rows: list[dict[str, Any]],
) -> None:
    for row in staged_rows:
        open_episode = state.get("open_episode")
        consecutive = (
            isinstance(open_episode, dict)
            and open_episode["segment_id"] == row["segment_id"]
            and open_episode["last_eligible_window_ordinal"] + 1
            == row["eligible_window_ordinal"]
        )
        if not row["is_anomaly"]:
            if isinstance(open_episode, dict):
                _close_episode(
                    connection,
                    str(job["job_id"]),
                    state,
                    "normal" if consecutive else "gap",
                )
            continue
        if isinstance(open_episode, dict) and not consecutive:
            _close_episode(connection, str(job["job_id"]), state, "gap")
            open_episode = None
        if not isinstance(open_episode, dict):
            state["open_episode"] = {
                "segment_id": row["segment_id"],
                "episode_start_ts": row["score_ts"].isoformat(),
                "episode_end_ts": row["score_ts"].isoformat(),
                "last_score_ts": row["score_ts"].isoformat(),
                "first_window_start_ts": row["window_start_ts"].isoformat(),
                "first_window_end_ts": row["window_end_ts"].isoformat(),
                "peak_score": row["score"],
                "latest_score": row["score"],
                "anomalous_window_count": 1,
                "last_eligible_window_ordinal": row[
                    "eligible_window_ordinal"
                ],
            }
            continue
        open_episode["episode_end_ts"] = row["score_ts"].isoformat()
        open_episode["last_score_ts"] = row["score_ts"].isoformat()
        open_episode["peak_score"] = max(
            float(open_episode["peak_score"]), row["score"]
        )
        open_episode["latest_score"] = row["score"]
        open_episode["anomalous_window_count"] += 1
        open_episode["last_eligible_window_ordinal"] = row[
            "eligible_window_ordinal"
        ]


def process_chunk(
    connection: psycopg.Connection[dict[str, Any]],
    worker_id: str,
    job: dict[str, Any],
) -> bool:
    targets = _target_rows(connection, job)
    if not targets:
        with connection.transaction():
            _lock_owned_job(
                connection,
                str(job["job_id"]),
                worker_id,
                int(job["attempt_count"]),
            )
            state = _load_checkpoint(connection, str(job["job_id"]))
            _close_episode(
                connection, str(job["job_id"]), state, "replay_end"
            )
            connection.execute(
                """
                INSERT INTO replay_episode_checkpoints (job_id, state, updated_at)
                VALUES (%s, %s::jsonb, %s)
                ON CONFLICT (job_id) DO UPDATE
                SET state = EXCLUDED.state, updated_at = EXCLUDED.updated_at
                """,
                (
                    job["job_id"],
                    json.dumps(state),
                    _utc_now(),
                ),
            )
        publish_job(connection, worker_id, job)
        return True

    last_target_index = int(targets[-1]["corpus_index"])
    try:
        batch, eligible, threshold, minimum, maximum = _score_batch(
            connection, job, targets
        )
    except ReplayWorkerError as error:
        if str(error) != "batch contains no eligible windows":
            raise
        with connection.transaction():
            _lock_owned_job(
                connection,
                str(job["job_id"]),
                worker_id,
                int(job["attempt_count"]),
            )
            state = _load_checkpoint(connection, str(job["job_id"]))
            open_episode = state.get("open_episode")
            if isinstance(open_episode, dict) and any(
                target["segment_id"] != open_episode["segment_id"]
                for target in targets
            ):
                _close_episode(
                    connection, str(job["job_id"]), state, "gap"
                )
                connection.execute(
                    """
                    INSERT INTO replay_episode_checkpoints (
                        job_id, state, updated_at
                    ) VALUES (%s, %s::jsonb, %s)
                    ON CONFLICT (job_id) DO UPDATE
                    SET state = EXCLUDED.state,
                        updated_at = EXCLUDED.updated_at
                    """,
                    (job["job_id"], json.dumps(state), _utc_now()),
                )
            advanced = connection.execute(
                """
                UPDATE replay_jobs
                SET next_corpus_index = %s,
                    processed_count = processed_count + %s,
                    heartbeat_at = %s,
                    lease_expires_at = %s
                WHERE job_id = %s AND lease_owner = %s AND status = 'running'
                RETURNING job_id
                """,
                (
                    last_target_index + 1,
                    len(targets),
                    _utc_now(),
                    _utc_now() + timedelta(seconds=LEASE_SECONDS),
                    job["job_id"],
                    worker_id,
                ),
            ).fetchone()
            if advanced is None:
                raise ReplayWorkerError("replay lease ownership was lost")
        job["next_corpus_index"] = last_target_index + 1
        return False

    temporal_row = connection.execute(
        """
        SELECT temporal_semantics, runtime_kind, manifest_sha256
        FROM model_versions
        WHERE version = %s
        """,
        (job["model_version"],),
    ).fetchone()
    if temporal_row is None:
        raise ReplayWorkerError("job model temporal semantics is missing")
    temporal = TemporalSemantics(str(temporal_row["temporal_semantics"]))
    runtime_kind = temporal_row["runtime_kind"]
    provenance = job["score_provenance"]
    if runtime_kind == "preview_simulator" and provenance == "simulated_preview":
        scorer: Scorer = PreviewSimulatorScorer(
            archive_sha256=str(job["archive_sha256"]),
            temporal_semantics=temporal,
        )
    elif runtime_kind == "artifact" and provenance == "artifact_backed":
        from anomaly_worker.artifact_scorer import ArtifactScorer

        scorer = ArtifactScorer(
            model_version=str(job["model_version"]),
            manifest_sha256=str(temporal_row["manifest_sha256"]),
            temporal_semantics=temporal,
        )
    else:
        raise ReplayWorkerError(
            "job scorer adapter and provenance are not supported"
        )
    results = scorer.score(batch)
    staged_rows = []
    band_half = tuple(
        (maximum[channel] - minimum[channel]) * (threshold ** 0.5)
        for channel in range(2)
    )
    for metadata, point in zip(eligible, results.points, strict=True):
        recon = point.reconstruction
        if recon is not None:
            recon_temperature_c: float | None = (
                recon[0] * (maximum[0] - minimum[0]) + minimum[0]
            )
            recon_relative_humidity_pct: float | None = (
                recon[1] * (maximum[1] - minimum[1]) + minimum[1]
            )
            band_half_temperature_c: float | None = band_half[0]
            band_half_relative_humidity_pct: float | None = band_half[1]
        else:
            recon_temperature_c = None
            recon_relative_humidity_pct = None
            band_half_temperature_c = None
            band_half_relative_humidity_pct = None
        staged_rows.append(
            {
                "job_id": job["job_id"],
                "score_ts": point.score_ts,
                "window_start_ts": metadata["window_start_ts"],
                "window_end_ts": metadata["window_end_ts"],
                "model_version": job["model_version"],
                "score": point.score,
                "threshold": threshold,
                "is_anomaly": point.score > threshold,
                "score_provenance": job["score_provenance"],
                "source_start_index": metadata["source_start_index"],
                "source_end_index": metadata["source_end_index"],
                "reading_count": 30,
                "stride": 1,
                "segment_id": metadata["target"]["segment_id"],
                "eligible_window_ordinal": metadata[
                    "eligible_window_ordinal"
                ],
                "recon_temperature_c": recon_temperature_c,
                "recon_relative_humidity_pct": recon_relative_humidity_pct,
                "band_half_temperature_c": band_half_temperature_c,
                "band_half_relative_humidity_pct": band_half_relative_humidity_pct,
            }
        )

    now = _utc_now()
    with connection.transaction():
        _lock_owned_job(
            connection,
            str(job["job_id"]),
            worker_id,
            int(job["attempt_count"]),
        )
        with connection.cursor() as cursor:
            cursor.executemany(
                """
            INSERT INTO replay_result_staging (
                job_id, score_ts, window_start_ts, window_end_ts,
                model_version, score, threshold, is_anomaly,
                score_provenance, source_start_index, source_end_index,
                reading_count, stride, segment_id, eligible_window_ordinal,
                recon_temperature_c, recon_relative_humidity_pct,
                band_half_temperature_c, band_half_relative_humidity_pct
            ) VALUES (
                %(job_id)s, %(score_ts)s, %(window_start_ts)s,
                %(window_end_ts)s, %(model_version)s, %(score)s,
                %(threshold)s, %(is_anomaly)s, %(score_provenance)s,
                %(source_start_index)s, %(source_end_index)s,
                %(reading_count)s, %(stride)s, %(segment_id)s,
                %(eligible_window_ordinal)s,
                %(recon_temperature_c)s, %(recon_relative_humidity_pct)s,
                %(band_half_temperature_c)s, %(band_half_relative_humidity_pct)s
            )
            """,
                staged_rows,
            )
        state = _load_checkpoint(connection, str(job["job_id"]))
        _accumulate_episodes(connection, job, state, staged_rows)
        connection.execute(
            """
            INSERT INTO replay_episode_checkpoints (job_id, state, updated_at)
            VALUES (%s, %s::jsonb, %s)
            ON CONFLICT (job_id) DO UPDATE
            SET state = EXCLUDED.state, updated_at = EXCLUDED.updated_at
            """,
            (job["job_id"], json.dumps(state), now),
        )
        advanced = connection.execute(
            """
            UPDATE replay_jobs
            SET next_corpus_index = %s,
                processed_count = processed_count + %s,
                result_count = (
                    SELECT count(*) FROM replay_result_staging
                    WHERE job_id = %s
                ),
                episode_count = (
                    SELECT count(*) FROM replay_episode_staging
                    WHERE job_id = %s
                ),
                heartbeat_at = %s,
                lease_expires_at = %s
            WHERE job_id = %s AND lease_owner = %s AND status = 'running'
            RETURNING job_id
            """,
            (
                last_target_index + 1,
                len(targets),
                job["job_id"],
                job["job_id"],
                now,
                now + timedelta(seconds=LEASE_SECONDS),
                job["job_id"],
                worker_id,
            ),
        ).fetchone()
        if advanced is None:
            raise ReplayWorkerError("replay lease ownership was lost")
        _heartbeat(connection, worker_id)
    job["next_corpus_index"] = last_target_index + 1
    return False


def _stable_id(prefix: str, *parts: object) -> str:
    encoded = "|".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(encoded).hexdigest()[:32]}"


def publish_job(
    connection: psycopg.Connection[dict[str, Any]],
    worker_id: str,
    job: dict[str, Any],
) -> None:
    created_at = _utc_now()
    with connection.transaction():
        _lock_owned_job(
            connection,
            str(job["job_id"]),
            worker_id,
            int(job["attempt_count"]),
        )
        episodes = connection.execute(
            """
            SELECT *
            FROM replay_episode_staging
            WHERE job_id = %s
            ORDER BY episode_ordinal
            """,
            (job["job_id"],),
        ).fetchall()
        connection.execute(
            """
            INSERT INTO inference_results (
                device_id, corpus_id, window_start_ts, window_end_ts,
                score_ts, model_version, score, threshold, is_anomaly,
                score_provenance, source_start_index, source_end_index,
                reading_count, stride, segment_id, replay_job_id,
                recon_temperature_c, recon_relative_humidity_pct,
                band_half_temperature_c, band_half_relative_humidity_pct
            )
            SELECT
                %s, %s, window_start_ts, window_end_ts, score_ts,
                model_version, score, threshold, is_anomaly,
                score_provenance, source_start_index, source_end_index,
                reading_count, stride, segment_id, job_id,
                recon_temperature_c, recon_relative_humidity_pct,
                band_half_temperature_c, band_half_relative_humidity_pct
            FROM replay_result_staging
            WHERE job_id = %s
            ORDER BY score_ts
            """,
            (job["device_id"], job["corpus_id"], job["job_id"]),
        )
        for episode in episodes:
            alert_id = _stable_id(
                "alert",
                job["logical_job_hash"],
                job["model_version"],
                episode["episode_start_ts"].isoformat(),
            )
            event_id = _stable_id("event_detected", alert_id)
            connection.execute(
                """
                INSERT INTO alerts (
                    alert_id, device_id, detected_at, score, threshold,
                    model_version, inference_result_window_start_ts,
                    inference_result_window_end_ts, detection_basis,
                    corpus_id, episode_start_ts, episode_end_ts,
                    last_score_ts, created_at, peak_score, latest_score,
                    anomalous_window_count, replay_job_id, segment_id,
                    closure_reason
                ) VALUES (
                    %s, %s, NULL, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    alert_id,
                    job["device_id"],
                    episode["peak_score"],
                    1.0,
                    job["model_version"],
                    episode["first_window_start_ts"],
                    episode["first_window_end_ts"],
                    job["score_provenance"],
                    job["corpus_id"],
                    episode["episode_start_ts"],
                    episode["episode_end_ts"],
                    episode["last_score_ts"],
                    created_at,
                    episode["peak_score"],
                    episode["latest_score"],
                    episode["anomalous_window_count"],
                    job["job_id"],
                    episode["segment_id"],
                    episode["closure_reason"],
                ),
            )
            connection.execute(
                """
                INSERT INTO alert_events (
                    event_id, alert_id, event_ts, event_at, time_domain,
                    event_type, device_id, actor, note,
                    inference_result_window_start_ts,
                    inference_result_window_end_ts,
                    inference_model_version, detection_basis
                ) VALUES (
                    %s, %s, NULL, %s, 'utc', 'detected', %s,
                    'preview-worker', NULL, %s, %s, %s, %s
                )
                """,
                (
                    event_id,
                    alert_id,
                    created_at,
                    job["device_id"],
                    episode["first_window_start_ts"],
                    episode["first_window_end_ts"],
                    job["model_version"],
                    job["score_provenance"],
                ),
            )
        final_count_row = connection.execute(
                "SELECT count(*) AS count FROM replay_result_staging WHERE job_id = %s",
                (job["job_id"],),
            ).fetchone()
        if final_count_row is None:
            raise ReplayWorkerError("final result count could not be read")
        final_result_count = int(final_count_row["count"])
        completed = connection.execute(
            """
            UPDATE replay_jobs
            SET status = 'succeeded',
                completed_at = %s,
                heartbeat_at = %s,
                lease_owner = NULL,
                lease_expires_at = NULL,
                result_count = %s,
                episode_count = %s,
                error_code = NULL,
                error_detail = NULL
            WHERE job_id = %s AND status = 'running' AND lease_owner = %s
            RETURNING job_id
            """,
            (
                created_at,
                created_at,
                final_result_count,
                len(episodes),
                job["job_id"],
                worker_id,
            ),
        ).fetchone()
        if completed is None:
            raise ReplayWorkerError("replay lease ownership was lost")
        connection.execute(
            "DELETE FROM replay_result_staging WHERE job_id = %s",
            (job["job_id"],),
        )
        connection.execute(
            "DELETE FROM replay_episode_staging WHERE job_id = %s",
            (job["job_id"],),
        )
        connection.execute(
            "DELETE FROM replay_episode_checkpoints WHERE job_id = %s",
            (job["job_id"],),
        )
        _heartbeat(connection, worker_id)


def fail_or_release_job(
    connection: psycopg.Connection[dict[str, Any]],
    worker_id: str,
    job: dict[str, Any],
    error: Exception,
) -> None:
    public_detail = "Preview replay failed validation"
    now = _utc_now()
    terminal = int(job["attempt_count"]) >= int(job["max_attempts"])
    with connection.transaction():
        _lock_owned_job(
            connection,
            str(job["job_id"]),
            worker_id,
            int(job["attempt_count"]),
        )
        if terminal:
            connection.execute(
                "DELETE FROM replay_result_staging WHERE job_id = %s",
                (job["job_id"],),
            )
            connection.execute(
                "DELETE FROM replay_episode_staging WHERE job_id = %s",
                (job["job_id"],),
            )
            connection.execute(
                "DELETE FROM replay_episode_checkpoints WHERE job_id = %s",
                (job["job_id"],),
            )
        updated = connection.execute(
            """
            UPDATE replay_jobs
            SET status = %s,
                completed_at = CASE WHEN %s THEN %s ELSE NULL END,
                lease_owner = CASE WHEN %s THEN NULL ELSE lease_owner END,
                lease_expires_at = CASE WHEN %s THEN NULL ELSE %s END,
                error_code = 'worker_validation_failed',
                error_detail = %s
            WHERE job_id = %s AND lease_owner = %s
            RETURNING job_id
            """,
            (
                "failed" if terminal else "running",
                terminal,
                now,
                terminal,
                terminal,
                now,
                public_detail,
                job["job_id"],
                worker_id,
            ),
        ).fetchone()
        if updated is None:
            raise ReplayWorkerError("replay lease ownership was lost")
        _heartbeat(connection, worker_id)
    _ = error


def run_once(
    connection: psycopg.Connection[dict[str, Any]], worker_id: str
) -> bool:
    job = claim_job(connection, worker_id)
    if job is None:
        return False
    try:
        while not process_chunk(connection, worker_id, job):
            pass
    except Exception as error:
        connection.rollback()
        try:
            fail_or_release_job(connection, worker_id, job, error)
        except ReplayWorkerError:
            connection.rollback()
    return True


def run_forever() -> None:
    settings = Settings.from_environ()
    worker_id = _worker_id()
    raw_connection = psycopg.connect(
        _connection_string(settings),
        row_factory=dict_row,  # pyright: ignore[reportArgumentType]
        autocommit=True,
    )
    connection = cast(
        psycopg.Connection[dict[str, Any]], raw_connection
    )
    with connection:
        while True:
            worked = run_once(connection, worker_id)
            if os.environ.get("PREVIEW_WORKER_RUN_ONCE") == "1":
                return
            if not worked:
                time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_forever()
