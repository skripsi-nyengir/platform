import asyncio
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from importlib import import_module
from pathlib import Path
import time
from typing import Any, cast

from fastapi import APIRouter
from httpx import Response
import psycopg
from psycopg.rows import dict_row
import pytest
from sqlalchemy import func, insert, select, text

from anomaly_backend import tables
from anomaly_backend import importer
from anomaly_backend.config import Settings
from anomaly_backend.contracts import (
    AcknowledgeAlertResponse,
    CurrentAlertsResponse,
    InferenceResponse,
    ModelActivationResponse,
    ModelsResponse,
    ProblemDetails,
    ReplayJobResponse,
    ResolveAlertResponse,
)
from anomaly_backend.db import create_database_engine
from anomaly_backend.seed import seed_database
from anomaly_backend.sql.preview import estimated_replay_results
from anomaly_worker.service import (
    ReplayWorkerError,
    _lock_owned_job,
    claim_job,
    fail_or_release_job,
    process_chunk,
    run_once,
)

from conftest import ClientFactory


PUBLIC_DEVICE_ID = "b02f3872-ruang-produksi"
PUBLIC_ARCHIVE_SHA = (
    "6c5a7ee8c248931bcc490cc114a3af55add8af82f976f58015ff7225dccce01a"
)
PUBLIC_MODEL_KEYS = [
    "ewma",
    "pca",
    "wsn-dense-ae",
    "lstm-ae",
    "usad",
    "cfc-autoencoder",
    "mtad-gat",
]
CORPUS_ID = "test-public-corpus"
CORPUS_START = datetime(2026, 2, 1, 0, 0, 0)
CORPUS_END = datetime(2026, 2, 1, 0, 2, 0)


def _router(module: str) -> APIRouter:
    value = getattr(import_module(module), "router", None)
    assert isinstance(value, APIRouter)
    return value


async def _reset_preview_fixture() -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.begin() as connection:
            cleanup_statements = (
                """
                    DELETE FROM alert_commands
                    WHERE alert_id IN (
                        SELECT alert_id FROM alerts WHERE device_id = :device_id
                    )
                """,
                """
                    DELETE FROM alert_events
                    WHERE alert_id IN (
                        SELECT alert_id FROM alerts WHERE device_id = :device_id
                    )
                """,
                "DELETE FROM alerts WHERE device_id = :device_id",
                "DELETE FROM inference_results WHERE device_id = :device_id",
                "DELETE FROM replay_episode_checkpoints",
                "DELETE FROM replay_episode_staging",
                "DELETE FROM replay_result_staging",
                "DELETE FROM replay_commands",
                "DELETE FROM replay_jobs WHERE device_id = :device_id",
                "DELETE FROM telemetry WHERE device_id = :device_id",
                "DELETE FROM published_corpora WHERE device_id = :device_id",
                """
                    DELETE FROM preprocessing_snapshots
                    WHERE corpus_id IN (
                        SELECT corpus_id FROM corpora WHERE device_id = :device_id
                    )
                """,
                "DELETE FROM corpora WHERE device_id = :device_id",
                """
                    UPDATE active_model_selections
                    SET activation_id = 'activation-preview-lstm-ae-v1',
                        model_version = 'preview-lstm-ae-v1'
                    WHERE device_id = :device_id
                """,
                """
                    DELETE FROM model_activations
                    WHERE device_id = :device_id
                      AND activation_id <> 'activation-preview-lstm-ae-v1'
                """,
            )
            for statement in cleanup_statements:
                await connection.execute(
                    text(statement), {"device_id": PUBLIC_DEVICE_ID}
                )
            now = datetime.now(timezone.utc)
            await connection.execute(
                insert(tables.corpora).values(
                    corpus_id=CORPUS_ID,
                    device_id=PUBLIC_DEVICE_ID,
                    status="published",
                    archive_sha256=PUBLIC_ARCHIVE_SHA,
                    member_sha256="a" * 64,
                    preprocessing_contract_version=(
                        "b02f3872_ruang_produksi_v2"
                    ),
                    source_device_uuid=(
                        "b02f3872-39a2-4b6f-a4ec-045a287fde4b"
                    ),
                    time_zone="Asia/Jakarta",
                    interval_start=CORPUS_START,
                    interval_end=CORPUS_END,
                    filter_config={},
                    started_at=now,
                    completed_at=now,
                    accepted_count=120,
                    ignored_index_count=0,
                    rejection_counts={},
                )
            )
            await connection.execute(
                insert(tables.preprocessing_snapshots).values(
                    corpus_id=CORPUS_ID,
                    channels=["suhu", "rh"],
                    window_size=30,
                    stride=1,
                    segment_metadata={"segments": 1},
                    split_boundaries={},
                    split_counts={"train": 120},
                    scaler={
                        "channels": ["suhu", "rh"],
                        "minimum": [20.0, 40.0],
                        "maximum": [30.0, 70.0],
                    },
                )
            )
            await connection.execute(
                insert(tables.published_corpora).values(
                    device_id=PUBLIC_DEVICE_ID,
                    corpus_id=CORPUS_ID,
                    published_at=now,
                )
            )
            await connection.execute(
                insert(tables.telemetry),
                [
                    {
                        "device_id": PUBLIC_DEVICE_ID,
                        "ts": CORPUS_START + timedelta(seconds=index),
                        "temperature_c": 25.0 + index / 100,
                        "relative_humidity_pct": 55.0 + index / 100,
                        "payload_hash": f"payload-{index}",
                        "source_index": index,
                        "corpus_id": CORPUS_ID,
                        "corpus_index": index,
                        "segment_id": 0,
                        "dataset_split": "train",
                    }
                    for index in range(120)
                ],
            )
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def preview_database() -> Iterator[None]:
    async def prepare() -> None:
        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.connect() as connection:
                await seed_database(connection)
        finally:
            await engine.dispose()
        await _reset_preview_fixture()

    asyncio.run(prepare())
    yield
    asyncio.run(_reset_preview_fixture())


def _payload(response: Response) -> dict[str, object]:
    return cast(dict[str, object], response.json())


def _problem(response: Response, status: int) -> ProblemDetails:
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    return ProblemDetails.model_validate(_payload(response), strict=True)


def _sync_connection() -> psycopg.Connection[dict[str, Any]]:
    settings = Settings.from_environ()
    raw_connection = psycopg.connect(
        (
            f"host={settings.postgres_host} port={settings.postgres_port} "
            f"dbname={settings.postgres_db} user={settings.postgres_user} "
            f"password={settings.postgres_password}"
        ),
        row_factory=dict_row,  # pyright: ignore[reportArgumentType]
        autocommit=True,
    )
    return cast(psycopg.Connection[dict[str, Any]], raw_connection)


@pytest.mark.anyio
async def test_devices_returns_only_the_published_b02_device(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.get("/api/devices")

    assert response.status_code == 200
    assert _payload(response)["items"] == [
        {
            "device_id": PUBLIC_DEVICE_ID,
            "display_name": "TALPHA Ruang Produksi",
            "time_zone": "Asia/Jakarta",
            "channels": ["suhu", "rh"],
            "corpus_from": "2026-02-01T00:00:00",
            "corpus_to": "2026-02-01T00:02:00",
            "import_readiness": "ready",
        }
    ]


@pytest.mark.anyio
async def test_models_returns_seven_pending_families_and_one_selection(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.get(
            "/api/models", params={"device_id": PUBLIC_DEVICE_ID}
        )

    models = ModelsResponse.model_validate(_payload(response), strict=True)
    assert response.status_code == 200
    assert [family.model_key for family in models.families] == PUBLIC_MODEL_KEYS
    assert models.active_model_version == "preview-lstm-ae-v1"
    assert all(family.artifact_status == "pending" for family in models.families)
    assert sum(
        version.version == models.active_model_version
        for family in models.families
        for version in family.versions
    ) == 1


@pytest.mark.anyio
async def test_activation_is_idempotent_and_records_noop_history(
    client_factory: ClientFactory,
) -> None:
    body = {
        "command_id": "activate-lstm-noop",
        "device_id": PUBLIC_DEVICE_ID,
        "model_version": "preview-lstm-ae-v1",
    }
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        first = await client.post("/api/model-activations", json=body)
        replay = await client.post("/api/model-activations", json=body)

    first_result = ModelActivationResponse.model_validate(
        _payload(first), strict=True
    )
    replay_result = ModelActivationResponse.model_validate(
        _payload(replay), strict=True
    )
    assert first.status_code == replay.status_code == 200
    assert first_result.activation.changed is False
    assert replay_result.activation.activation_id == (
        first_result.activation.activation_id
    )
    assert replay_result.idempotent_request_replay is True


@pytest.mark.anyio
async def test_activation_command_conflicts_when_payload_changes(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        first = await client.post(
            "/api/model-activations",
            json={
                "command_id": "activation-conflict",
                "device_id": PUBLIC_DEVICE_ID,
                "model_version": "preview-usad-v1",
            },
        )
        conflict = await client.post(
            "/api/model-activations",
            json={
                "command_id": "activation-conflict",
                "device_id": PUBLIC_DEVICE_ID,
                "model_version": "preview-pca-v1",
            },
        )

    assert first.status_code == 200
    assert "different payload" in _problem(conflict, 409).detail


@pytest.mark.anyio
async def test_replay_snapshots_model_before_future_activation(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        replay = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "replay-before-switch",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:01:00",
            },
        )
        activation = await client.post(
            "/api/model-activations",
            json={
                "command_id": "switch-after-submit",
                "device_id": PUBLIC_DEVICE_ID,
                "model_version": "preview-usad-v1",
            },
        )
        replay_payload = cast(dict[str, object], _payload(replay)["job"])
        status = await client.get(
            f"/api/replay-jobs/{replay_payload['job_id']}"
        )

    job = ReplayJobResponse.model_validate(_payload(replay), strict=True).job
    active = ModelActivationResponse.model_validate(
        _payload(activation), strict=True
    )
    persisted = cast(dict[str, object], _payload(status)["job"])
    assert replay.status_code == 202
    assert job.model_version == "preview-lstm-ae-v1"
    assert active.active_model_version == "preview-usad-v1"
    assert persisted["model_version"] == "preview-lstm-ae-v1"
    assert persisted["activation_id"] == job.activation_id


@pytest.mark.anyio
async def test_logically_identical_replays_share_one_job_across_commands(
    client_factory: ClientFactory,
) -> None:
    base = {
        "device_id": PUBLIC_DEVICE_ID,
        "from": "2026-02-01T00:00:00",
        "to": "2026-02-01T00:01:00",
    }
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        first = await client.post(
            "/api/replay-jobs",
            json={"command_id": "replay-command-a", **base},
        )
        second = await client.post(
            "/api/replay-jobs",
            json={"command_id": "replay-command-b", **base},
        )

    first_job = ReplayJobResponse.model_validate(
        _payload(first), strict=True
    )
    second_job = ReplayJobResponse.model_validate(
        _payload(second), strict=True
    )
    assert first.status_code == 202
    assert second.status_code == 200
    assert second_job.idempotent_request_replay is True
    assert second_job.job.job_id == first_job.job.job_id

    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            commands = list(
                await connection.scalars(
                    select(tables.replay_commands.c.command_id).where(
                        tables.replay_commands.c.job_id
                        == first_job.job.job_id
                    )
                )
            )
    finally:
        await engine.dispose()
    assert sorted(commands) == ["replay-command-a", "replay-command-b"]


@pytest.mark.anyio
async def test_overlapping_replay_for_same_selection_returns_conflict(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        first = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "replay-overlap-a",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:01:00",
            },
        )
        conflict = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "replay-overlap-b",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:30",
                "to": "2026-02-01T00:01:30",
            },
        )

    assert first.status_code == 202
    assert "overlaps existing job" in _problem(conflict, 409).detail


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("from_ts", "to_ts"),
    [
        ("2026-02-01T00:01:00", "2026-02-01T00:01:00"),
        ("2026-01-31T23:59:59", "2026-02-01T00:00:30"),
        ("2026-02-01T00:01:30", "2026-02-01T00:02:01"),
        ("2026-02-01T00:00:00", "2026-03-04T00:00:01"),
    ],
)
async def test_replay_rejects_invalid_or_out_of_corpus_intervals(
    client_factory: ClientFactory,
    from_ts: str,
    to_ts: str,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": f"invalid-{from_ts}-{to_ts}",
                "device_id": PUBLIC_DEVICE_ID,
                "from": from_ts,
                "to": to_ts,
            },
        )

    expected = 422
    assert response.status_code == expected


@pytest.mark.anyio
async def test_inference_default_resolves_active_selection_not_lexical_version(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(
        _router("anomaly_backend.routes.preview"),
        _router("anomaly_backend.routes.inference"),
    ) as (_, client):
        activation = await client.post(
            "/api/model-activations",
            json={
                "command_id": "activate-usad-for-resolver",
                "device_id": PUBLIC_DEVICE_ID,
                "model_version": "preview-usad-v1",
            },
        )
        assert activation.status_code == 200

        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    insert(tables.inference_results),
                    [
                        {
                            "device_id": PUBLIC_DEVICE_ID,
                            "corpus_id": CORPUS_ID,
                            "window_start_ts": CORPUS_START,
                            "window_end_ts": CORPUS_START
                            + timedelta(seconds=29),
                            "score_ts": CORPUS_START
                            + timedelta(seconds=29),
                            "model_version": version,
                            "score": score,
                            "threshold": 1.0,
                            "is_anomaly": False,
                            "score_provenance": "simulated_preview",
                            "source_start_index": 0,
                            "source_end_index": 29,
                            "reading_count": 30,
                            "stride": 1,
                            "segment_id": 0,
                            "replay_job_id": None,
                        }
                        for version, score in (
                            ("preview-ewma-v1", 0.2),
                            ("preview-usad-v1", 0.7),
                        )
                    ],
                )
        finally:
            await engine.dispose()

        default = await client.get(
            "/api/inference-results",
            params={
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:01:00",
            },
        )
        historical = await client.get(
            "/api/inference-results",
            params={
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:01:00",
                "model_version": "preview-ewma-v1",
            },
        )

    default_result = InferenceResponse.model_validate(
        _payload(default), strict=True
    )
    historical_result = InferenceResponse.model_validate(
        _payload(historical), strict=True
    )
    assert default_result.model_version == "preview-usad-v1"
    assert [point.score for point in default_result.points] == [0.7]
    assert historical_result.model_version == "preview-ewma-v1"
    assert [point.score for point in historical_result.points] == [0.2]
    assert default_result.points[0].score_ts == "2026-02-01T00:00:29"
    assert default_result.points[0].score_provenance == "simulated_preview"


@pytest.mark.anyio
async def test_worker_keeps_results_private_until_atomic_success_publication(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        submission = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "atomic-worker-replay",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:02:00",
            },
        )
    job_id = cast(dict[str, object], _payload(submission)["job"])["job_id"]
    assert submission.status_code == 202

    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            before = await connection.scalar(
                select(func.count())
                .select_from(tables.inference_results)
                .where(tables.inference_results.c.replay_job_id == job_id)
            )
    finally:
        await engine.dispose()
    assert before == 0

    settings = Settings.from_environ()
    raw_connection = psycopg.connect(
        (
            f"host={settings.postgres_host} port={settings.postgres_port} "
            f"dbname={settings.postgres_db} user={settings.postgres_user} "
            f"password={settings.postgres_password}"
        ),
        row_factory=dict_row,  # pyright: ignore[reportArgumentType]
        autocommit=True,
    )
    connection = cast(
        psycopg.Connection[dict[str, Any]], raw_connection
    )
    with connection:
        assert run_once(connection, "test-worker-atomic") is True

    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            job = (
                await connection.execute(
                    select(tables.replay_jobs).where(
                        tables.replay_jobs.c.job_id == job_id
                    )
                )
            ).mappings().one()
            final_count = await connection.scalar(
                select(func.count())
                .select_from(tables.inference_results)
                .where(tables.inference_results.c.replay_job_id == job_id)
            )
            staging_count = await connection.scalar(
                select(func.count())
                .select_from(tables.replay_result_staging)
                .where(tables.replay_result_staging.c.job_id == job_id)
            )
    finally:
        await engine.dispose()

    assert job["status"] == "succeeded"
    assert final_count == job["result_count"] == 91
    assert staging_count == 0


@pytest.mark.anyio
async def test_episode_lifecycle_keeps_corpus_time_separate_from_utc_audit_time(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(
        _router("anomaly_backend.routes.preview"),
        _router("anomaly_backend.routes.alerts"),
    ) as (_, client):
        submission = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "episode-lifecycle-replay",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:01:00",
            },
        )
        job = ReplayJobResponse.model_validate(
            _payload(submission), strict=True
        ).job
        created_at = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)
        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    insert(tables.alerts).values(
                        alert_id="alert-episode-lifecycle",
                        device_id=PUBLIC_DEVICE_ID,
                        detected_at=None,
                        score=1.4,
                        threshold=1.0,
                        model_version=job.model_version,
                        inference_result_window_start_ts=CORPUS_START,
                        inference_result_window_end_ts=CORPUS_START
                        + timedelta(seconds=29),
                        detection_basis="simulated_preview",
                        corpus_id=CORPUS_ID,
                        episode_start_ts=CORPUS_START
                        + timedelta(seconds=29),
                        episode_end_ts=CORPUS_START
                        + timedelta(seconds=31),
                        last_score_ts=CORPUS_START
                        + timedelta(seconds=31),
                        created_at=created_at,
                        peak_score=1.4,
                        latest_score=1.2,
                        anomalous_window_count=3,
                        replay_job_id=job.job_id,
                        segment_id=0,
                        closure_reason="replay_end",
                    )
                )
                await connection.execute(
                    insert(tables.alert_events).values(
                        event_id="event-episode-detected",
                        alert_id="alert-episode-lifecycle",
                        event_ts=None,
                        event_at=created_at,
                        time_domain="utc",
                        event_type="detected",
                        device_id=PUBLIC_DEVICE_ID,
                        actor="preview-worker",
                        note=None,
                        inference_result_window_start_ts=CORPUS_START,
                        inference_result_window_end_ts=CORPUS_START
                        + timedelta(seconds=29),
                        inference_model_version=job.model_version,
                        detection_basis="simulated_preview",
                    )
                )
        finally:
            await engine.dispose()

        current = await client.get(
            "/api/alerts/current",
            params={"device_id": PUBLIC_DEVICE_ID},
        )
        first_ack = await client.post(
            "/api/alerts/alert-episode-lifecycle/acknowledge",
            json={"command_id": "ack-episode-lifecycle"},
        )
        replay_ack = await client.post(
            "/api/alerts/alert-episode-lifecycle/acknowledge",
            json={"command_id": "ack-episode-lifecycle"},
        )
        resolved = await client.post(
            "/api/alerts/alert-episode-lifecycle/resolve",
            json={"command_id": "resolve-episode-lifecycle"},
        )

    listing = CurrentAlertsResponse.model_validate(
        _payload(current), strict=True
    )
    episode = listing.items[0]
    acknowledged = AcknowledgeAlertResponse.model_validate(
        _payload(first_ack), strict=True
    )
    replayed = AcknowledgeAlertResponse.model_validate(
        _payload(replay_ack), strict=True
    )
    resolution = ResolveAlertResponse.model_validate(
        _payload(resolved), strict=True
    )

    assert episode.episode_start_ts == "2026-02-01T00:00:29"
    assert episode.episode_end_ts == "2026-02-01T00:00:31"
    assert episode.created_at == "2026-07-24T12:00:00Z"
    assert "detected_at" not in episode.model_dump()
    assert acknowledged.event.event_at.endswith("Z")
    assert acknowledged.event.accepted_at is not None
    assert acknowledged.event.accepted_at.endswith("Z")
    assert replayed.event.event_id == acknowledged.event.event_id
    assert replayed.idempotent_replay is True
    assert resolution.event.event_at.endswith("Z")


@pytest.mark.anyio
async def test_two_workers_cannot_claim_the_same_job(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "claim-exclusive",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:01:00",
            },
        )
    assert response.status_code == 202

    with _sync_connection() as first, _sync_connection() as second:
        claimed = claim_job(first, "worker-exclusive-a")
        competing = claim_job(second, "worker-exclusive-b")

    assert claimed is not None
    assert competing is None


@pytest.mark.anyio
async def test_expired_lease_reclaim_fences_stale_generation_for_same_worker_id(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "same-worker-generation-fence",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:01:00",
            },
        )
    assert response.status_code == 202

    with _sync_connection() as connection:
        stale = claim_job(connection, "worker-generation")
        assert stale is not None
        connection.execute(
            """
            UPDATE replay_jobs
            SET lease_expires_at = now() - interval '1 second'
            WHERE job_id = %s
            """,
            (stale["job_id"],),
        )
        reclaimed = claim_job(connection, "worker-generation")
        assert reclaimed is not None

        assert reclaimed["job_id"] == stale["job_id"]
        assert reclaimed["attempt_count"] == stale["attempt_count"] + 1
        with pytest.raises(
            ReplayWorkerError, match="lease ownership was lost"
        ):
            _lock_owned_job(
                connection,
                str(stale["job_id"]),
                "worker-generation",
                int(stale["attempt_count"]),
            )


@pytest.mark.anyio
async def test_checkpoint_restart_publishes_without_duplicate_rows(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "checkpoint-restart",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:02:00",
            },
        )
    job_id = ReplayJobResponse.model_validate(
        _payload(response), strict=True
    ).job.job_id

    with _sync_connection() as first:
        initial = claim_job(first, "worker-before-restart")
        assert initial is not None
        assert process_chunk(
            first, "worker-before-restart", initial
        ) is False
        staged_before = first.execute(
            """
            SELECT count(*) AS count
            FROM replay_result_staging WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()
        assert staged_before is not None
        assert staged_before["count"] == 91
        first.execute(
            """
            UPDATE replay_jobs
            SET lease_expires_at = now() - interval '1 second'
            WHERE job_id = %s
            """,
            (job_id,),
        )

    with _sync_connection() as restarted:
        resumed = claim_job(restarted, "worker-after-restart")
        assert resumed is not None
        while not process_chunk(
            restarted, "worker-after-restart", resumed
        ):
            pass
        state = restarted.execute(
            """
            SELECT status, result_count, episode_count
            FROM replay_jobs WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()
        final_count = restarted.execute(
            """
            SELECT count(*) AS count
            FROM inference_results WHERE replay_job_id = %s
            """,
            (job_id,),
        ).fetchone()
        staging_count = restarted.execute(
            """
            SELECT count(*) AS count
            FROM replay_result_staging WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()

    assert state is not None
    assert final_count is not None
    assert staging_count is not None
    assert state["status"] == "succeeded"
    assert state["result_count"] == final_count["count"] == 91
    assert staging_count["count"] == 0


@pytest.mark.anyio
async def test_terminal_worker_failure_cleans_staging_and_leaves_no_final_output(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "terminal-worker-failure",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:02:00",
            },
        )
    job_id = ReplayJobResponse.model_validate(
        _payload(response), strict=True
    ).job.job_id

    with _sync_connection() as connection:
        claimed = claim_job(connection, "worker-terminal-failure")
        assert claimed is not None
        assert process_chunk(
            connection, "worker-terminal-failure", claimed
        ) is False
        connection.execute(
            "UPDATE replay_jobs SET max_attempts = 1 WHERE job_id = %s",
            (job_id,),
        )
        claimed["max_attempts"] = 1
        fail_or_release_job(
            connection,
            "worker-terminal-failure",
            claimed,
            ReplayWorkerError("synthetic fatal validation"),
        )
        state = connection.execute(
            """
            SELECT status, error_code FROM replay_jobs WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()
        staging_count = connection.execute(
            """
            SELECT count(*) AS count
            FROM replay_result_staging WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()
        final_count = connection.execute(
            """
            SELECT count(*) AS count
            FROM inference_results WHERE replay_job_id = %s
            """,
            (job_id,),
        ).fetchone()
        alert_count = connection.execute(
            "SELECT count(*) AS count FROM alerts WHERE replay_job_id = %s",
            (job_id,),
        ).fetchone()

    assert state == {
        "status": "failed",
        "error_code": "worker_validation_failed",
    }
    assert staging_count is not None and staging_count["count"] == 0
    assert final_count is not None and final_count["count"] == 0
    assert alert_count is not None and alert_count["count"] == 0


@pytest.mark.anyio
async def test_expired_max_attempt_job_is_cleaned_before_next_claim(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "expired-max-attempt",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:02:00",
            },
        )
    job_id = ReplayJobResponse.model_validate(
        _payload(response), strict=True
    ).job.job_id

    with _sync_connection() as connection:
        claimed = claim_job(connection, "worker-expired-terminal")
        assert claimed is not None
        assert process_chunk(
            connection, "worker-expired-terminal", claimed
        ) is False
        connection.execute(
            """
            UPDATE replay_jobs
            SET max_attempts = attempt_count,
                lease_expires_at = now() - interval '1 second'
            WHERE job_id = %s
            """,
            (job_id,),
        )
        assert claim_job(connection, "worker-cleaner") is None
        state = connection.execute(
            """
            SELECT status, error_code FROM replay_jobs WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()
        staging_count = connection.execute(
            """
            SELECT count(*) AS count
            FROM replay_result_staging WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()

    assert state == {
        "status": "failed",
        "error_code": "max_attempts_exhausted",
    }
    assert staging_count is not None and staging_count["count"] == 0


@pytest.mark.anyio
async def test_progress_estimate_counts_outputs_enabled_by_segment_preroll(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "progress-preroll",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:30",
                "to": "2026-02-01T00:01:00",
            },
        )
    job_id = ReplayJobResponse.model_validate(
        _payload(response), strict=True
    ).job.job_id

    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            row = (
                await connection.execute(
                    select(tables.replay_jobs).where(
                        tables.replay_jobs.c.job_id == job_id
                    )
                )
            ).mappings().one()
            estimate = await estimated_replay_results(connection, row)
    finally:
        await engine.dispose()

    assert estimate == 30


@pytest.mark.anyio
async def test_publication_collision_rolls_back_without_marking_job_succeeded(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router("anomaly_backend.routes.preview")) as (
        _,
        client,
    ):
        response = await client.post(
            "/api/replay-jobs",
            json={
                "command_id": "strict-publication-collision",
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T00:02:00",
            },
        )
    job_id = ReplayJobResponse.model_validate(
        _payload(response), strict=True
    ).job.job_id

    with _sync_connection() as connection:
        claimed = claim_job(connection, "worker-collision")
        assert claimed is not None
        assert process_chunk(connection, "worker-collision", claimed) is False
        staged = connection.execute(
            """
            SELECT * FROM replay_result_staging
            WHERE job_id = %s ORDER BY score_ts LIMIT 1
            """,
            (job_id,),
        ).fetchone()
        assert staged is not None
        connection.execute(
            """
            INSERT INTO inference_results (
                device_id, corpus_id, window_start_ts, window_end_ts,
                score_ts, model_version, score, threshold, is_anomaly,
                score_provenance, source_start_index, source_end_index,
                reading_count, stride, segment_id, replay_job_id
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, NULL
            )
            """,
            (
                PUBLIC_DEVICE_ID,
                CORPUS_ID,
                staged["window_start_ts"],
                staged["window_end_ts"],
                staged["score_ts"],
                staged["model_version"],
                staged["score"],
                staged["threshold"],
                staged["is_anomaly"],
                staged["score_provenance"],
                staged["source_start_index"],
                staged["source_end_index"],
                staged["reading_count"],
                staged["stride"],
                staged["segment_id"],
            ),
        )

        with pytest.raises(psycopg.errors.UniqueViolation):
            process_chunk(connection, "worker-collision", claimed)
        connection.rollback()
        state = connection.execute(
            "SELECT status FROM replay_jobs WHERE job_id = %s",
            (job_id,),
        ).fetchone()
        staging_count = connection.execute(
            """
            SELECT count(*) AS count
            FROM replay_result_staging WHERE job_id = %s
            """,
            (job_id,),
        ).fetchone()
        final_count = connection.execute(
            """
            SELECT count(*) AS count
            FROM inference_results
            WHERE device_id = %s AND model_version = %s
            """,
            (PUBLIC_DEVICE_ID, claimed["model_version"]),
        ).fetchone()

    assert state == {"status": "running"}
    assert staging_count is not None and staging_count["count"] == 91
    assert final_count is not None and final_count["count"] == 1


def test_importer_session_lock_serializes_invocations_and_recovers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(importer, "_validate_archive", lambda _: None)

    def invoke_import() -> dict[str, Any]:
        return importer.import_corpus(Path("/synthetic/tiny-b02.tar.gz"))

    with _sync_connection() as lock_holder:
        lock_holder.execute(
            "SELECT pg_advisory_lock(%s)", (importer.IMPORT_LOCK_ID,)
        )
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(invoke_import)
                deadline = time.monotonic() + 2.0
                waiting = False
                while time.monotonic() < deadline:
                    row = lock_holder.execute(
                        """
                        SELECT count(*) AS count
                        FROM pg_locks
                        WHERE locktype = 'advisory'
                          AND NOT granted
                        """
                    ).fetchone()
                    waiting = row is not None and int(row["count"]) >= 1
                    if waiting:
                        break
                    time.sleep(0.01)
                assert waiting
                assert future.done() is False
                lock_holder.execute(
                    "SELECT pg_advisory_unlock(%s)",
                    (importer.IMPORT_LOCK_ID,),
                )
                with pytest.raises(
                    importer.CorpusImportError,
                    match=(
                        "different corpus is already published|"
                        "published corpus identity has inconsistent metadata"
                    ),
                ):
                    _ = future.result(timeout=2.0)
        finally:
            lock_holder.execute(
                "SELECT pg_advisory_unlock(%s)",
                (importer.IMPORT_LOCK_ID,),
            )

    with pytest.raises(
        importer.CorpusImportError,
        match=(
            "different corpus is already published|"
            "published corpus identity has inconsistent metadata"
        ),
    ):
        _ = invoke_import()
