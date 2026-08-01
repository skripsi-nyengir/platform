from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from importlib import import_module
from typing import Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from httpx import Response
from sqlalchemy import func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
import pytest

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.sql.live import LIVE_DEVICE_ID

from tests.conftest import ClientFactory


_JAKARTA = ZoneInfo("Asia/Jakarta")


def _router(module: str) -> APIRouter:
    value = getattr(import_module(module), "router", None)
    assert isinstance(value, APIRouter)
    return value


def _payload(response: Response) -> dict[str, Any]:
    return cast(dict[str, Any], response.json())


@pytest.fixture(scope="module")
def live_api_fixture() -> Iterator[dict[str, object]]:
    async def create() -> dict[str, object]:
        suffix = uuid4().hex
        offset_minutes = int(suffix[:8], 16) % (300 * 24 * 60)
        base = datetime(2024, 1, 1) + timedelta(minutes=offset_minutes)
        base = base.replace(second=0, microsecond=0)
        corpus_id = f"live-api-corpus-{suffix}"
        model_key = f"live-api-model-{suffix}"
        model_version = f"{model_key}-v1"
        alert_id = f"live-api-alert-{suffix}"
        live_episode_id = uuid4()
        hashes = {
            "model_manifest_sha256": "a" * 64,
            "checkpoint_sha256": "b" * 64,
            "scaler_manifest_sha256": "c" * 64,
            "scaler_sha256": "d" * 64,
        }
        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    insert(tables.corpora).values(
                        corpus_id=corpus_id,
                        device_id=LIVE_DEVICE_ID,
                        status="published",
                        archive_sha256=suffix * 2,
                        member_sha256=None,
                        preprocessing_contract_version="live-api-v1",
                        source_device_uuid=None,
                        time_zone="Asia/Jakarta",
                        interval_start=base,
                        interval_end=base + timedelta(hours=12),
                        filter_config={},
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        accepted_count=20,
                        ignored_index_count=0,
                        rejection_counts={},
                    )
                )
                await connection.execute(
                    insert(tables.preprocessing_snapshots).values(
                        corpus_id=corpus_id,
                        channels=["temperature_c", "relative_humidity_pct"],
                        window_size=10,
                        stride=1,
                        contract_status="live_10",
                        segment_metadata={"source": "live-api-test"},
                        split_boundaries={"fit_split": "live"},
                        split_counts={},
                        scaler={
                            "channels": [
                                "temperature_c",
                                "relative_humidity_pct",
                            ],
                            "minimum": [0.0, 0.0],
                            "maximum": [100.0, 100.0],
                        },
                    )
                )
                await connection.execute(
                    insert(tables.model_families).values(
                        model_key=model_key,
                        display_name="Live API test model",
                        is_public=False,
                    )
                )
                await connection.execute(
                    insert(tables.model_versions).values(
                        version=model_version,
                        model_key=model_key,
                        runtime_kind="artifact",
                        is_selectable=True,
                        adapter_key="live-api-test",
                        schema_version="live-api-v1",
                        channels=["temperature_c", "relative_humidity_pct"],
                        window_size=10,
                        stride=1,
                        contract_status="live_10",
                        score_key="score",
                        score_semantics="higher-is-more-anomalous",
                        threshold=1.0,
                        threshold_policy={"comparator": ">"},
                        temporal_semantics="context_end",
                        source_commit=None,
                        source_config=None,
                        manifest_sha256=None,
                        created_at=datetime.now(timezone.utc),
                        **hashes,
                    )
                )
                model_pair_id = cast(
                    UUID,
                    await connection.scalar(
                        insert(tables.live_model_pairs)
                        .values(
                            model_version=model_version,
                            checkpoint_identity=f"checkpoint-{suffix}",
                            scaler_snapshot_corpus_id=corpus_id,
                            threshold=1.0,
                            contract_status="live_10",
                            **hashes,
                        )
                        .returning(tables.live_model_pairs.c.model_pair_id)
                    ),
                )
                request_id = cast(
                    UUID,
                    await connection.scalar(
                        insert(tables.live_model_activation_requests)
                        .values(
                            device_id=LIVE_DEVICE_ID,
                            model_pair_id=model_pair_id,
                            request_hash=f"request-{suffix}",
                            requested_by="live-api-test",
                        )
                        .returning(tables.live_model_activation_requests.c.request_id)
                    ),
                )
                activation = (
                    await connection.execute(
                        insert(tables.live_model_activations)
                        .values(
                            device_id=LIVE_DEVICE_ID,
                            request_id=request_id,
                            model_pair_id=model_pair_id,
                            fencing_token=1,
                        )
                        .returning(
                            tables.live_model_activations.c.activation_event_id,
                            tables.live_model_activations.c.activation_id,
                        )
                    )
                ).mappings().one()
                selection = pg_insert(tables.live_model_selections).values(
                    device_id=LIVE_DEVICE_ID,
                    activation_event_id=activation["activation_event_id"],
                    model_pair_id=model_pair_id,
                    activation_id=activation["activation_id"],
                )
                await connection.execute(
                    selection.on_conflict_do_update(
                        index_elements=["device_id"],
                        set_={
                            "activation_event_id": selection.excluded.activation_event_id,
                            "model_pair_id": selection.excluded.model_pair_id,
                            "activation_id": selection.excluded.activation_id,
                            "selected_at_utc": func.clock_timestamp(),
                        },
                        where=(
                            tables.live_model_selections.c.activation_id
                            < selection.excluded.activation_id
                        ),
                    )
                )

                telemetry_ids = [uuid4() for _ in range(14)]
                source_rows = [
                    {
                        "received_ts": base + timedelta(seconds=index),
                        "telemetry_id": telemetry_ids[index],
                        "device_id": LIVE_DEVICE_ID,
                        "received_at_utc": (
                            base.replace(tzinfo=_JAKARTA).astimezone(timezone.utc)
                            + timedelta(seconds=index)
                        ),
                        "temperature_c": 20.0 + index,
                        "relative_humidity_pct": 50.0 + index,
                        "ingress_generation": 1,
                        "activation_id": activation["activation_id"],
                        "continuity_epoch": 1,
                        "segment_start_reason": "startup" if index == 0 else None,
                        "fencing_token": 1,
                        "processing_status": "processed",
                    }
                    for index in range(14)
                ]
                equal_second_ids = sorted((uuid4(), uuid4()))
                source_rows.extend(
                    [
                        {
                            "received_ts": base + timedelta(seconds=30),
                            "telemetry_id": telemetry_id,
                            "device_id": LIVE_DEVICE_ID,
                            "received_at_utc": datetime.now(timezone.utc),
                            "temperature_c": 70.0 + index,
                            "relative_humidity_pct": 80.0 + index,
                            "ingress_generation": 1,
                            "activation_id": activation["activation_id"],
                            "continuity_epoch": 1,
                            "segment_start_reason": None,
                            "fencing_token": 1,
                            "processing_status": "processed",
                        }
                        for index, telemetry_id in enumerate(equal_second_ids)
                    ]
                )
                source_rows.extend(
                    [
                        {
                            "received_ts": base + timedelta(hours=1),
                            "telemetry_id": uuid4(),
                            "device_id": LIVE_DEVICE_ID,
                            "received_at_utc": datetime.now(timezone.utc),
                            "temperature_c": 40.0,
                            "relative_humidity_pct": 60.0,
                            "ingress_generation": 1,
                            "activation_id": activation["activation_id"],
                            "continuity_epoch": 1,
                            "segment_start_reason": None,
                            "fencing_token": 1,
                            "processing_status": "processed",
                        },
                        {
                            "received_ts": base + timedelta(hours=8, seconds=1),
                            "telemetry_id": uuid4(),
                            "device_id": LIVE_DEVICE_ID,
                            "received_at_utc": datetime.now(timezone.utc),
                            "temperature_c": 44.0,
                            "relative_humidity_pct": 64.0,
                            "ingress_generation": 1,
                            "activation_id": activation["activation_id"],
                            "continuity_epoch": 1,
                            "segment_start_reason": None,
                            "fencing_token": 1,
                            "processing_status": "processed",
                        },
                    ]
                )
                fresh_ts = datetime.now(_JAKARTA).replace(tzinfo=None, microsecond=0)
                fresh_id = uuid4()
                source_rows.append(
                    {
                        "received_ts": fresh_ts,
                        "telemetry_id": fresh_id,
                        "device_id": LIVE_DEVICE_ID,
                        "received_at_utc": datetime.now(timezone.utc),
                        "temperature_c": 26.5,
                        "relative_humidity_pct": 61.5,
                        "ingress_generation": 2,
                        "activation_id": activation["activation_id"],
                        "continuity_epoch": 2,
                        "segment_start_reason": "data_gap",
                        "fencing_token": 1,
                        "processing_status": "processed",
                    }
                )
                await connection.execute(insert(tables.live_telemetry), source_rows)

                inference_ids = [uuid4() for _ in range(5)]
                scores = (1.5, 2.5, 0.5, 0.4, 0.3)
                for index, (inference_id, score) in enumerate(
                    zip(inference_ids, scores, strict=True)
                ):
                    score_ts = base + timedelta(seconds=index + 9)
                    await connection.execute(
                        insert(tables.live_inference).values(
                            score_ts=score_ts,
                            inference_id=inference_id,
                            device_id=LIVE_DEVICE_ID,
                            window_start_ts=base + timedelta(seconds=index),
                            window_end_ts=score_ts,
                            score=score,
                            threshold=1.0,
                            is_anomaly=score > 1.0,
                            severity_at_score=(
                                "critical"
                                if score > 2.0
                                else "warning"
                                if score > 1.0
                                else "info"
                            ),
                            model_pair_id=model_pair_id,
                            activation_id=activation["activation_id"],
                            continuity_epoch=1,
                            model_version=model_version,
                            snapshot_corpus_id=corpus_id,
                            ordered_source_fingerprint=f"source-{suffix}-{index}",
                        )
                    )
                    await connection.execute(
                        insert(tables.live_inference_sources),
                        [
                            {
                                "score_ts": score_ts,
                                "inference_id": inference_id,
                                "ordinal": ordinal,
                                "received_ts": base
                                + timedelta(seconds=index + ordinal),
                                "telemetry_id": telemetry_ids[index + ordinal],
                                "device_id": LIVE_DEVICE_ID,
                            }
                            for ordinal in range(10)
                        ],
                    )

                created_at = datetime.now(timezone.utc)
                await connection.execute(
                    insert(tables.alerts).values(
                        alert_id=alert_id,
                        device_id=LIVE_DEVICE_ID,
                        detected_at=None,
                        score=scores[0],
                        threshold=1.0,
                        model_version=model_version,
                        inference_result_window_start_ts=base,
                        inference_result_window_end_ts=base
                        + timedelta(seconds=9),
                        detection_basis="artifact_backed",
                        corpus_id=corpus_id,
                        episode_start_ts=base + timedelta(seconds=9),
                        episode_end_ts=base + timedelta(seconds=13),
                        last_score_ts=base + timedelta(seconds=13),
                        created_at=created_at,
                        peak_score=2.5,
                        latest_score=0.3,
                        anomalous_window_count=2,
                        replay_job_id=None,
                        segment_id=1,
                        closure_reason="normal",
                        live_episode_id=live_episode_id,
                    )
                )
                await connection.execute(
                    insert(tables.live_alert_episodes).values(
                        live_episode_id=live_episode_id,
                        alert_id=alert_id,
                        device_id=LIVE_DEVICE_ID,
                        model_pair_id=model_pair_id,
                        activation_id=activation["activation_id"],
                        continuity_epoch=1,
                        model_version=model_version,
                        snapshot_corpus_id=corpus_id,
                        started_score_ts=base + timedelta(seconds=9),
                        ended_score_ts=None,
                        status="open",
                        close_reason=None,
                    )
                )
                await connection.execute(
                    insert(tables.live_alert_episode_points),
                    [
                        {
                            "live_episode_id": live_episode_id,
                            "score_ts": base + timedelta(seconds=index + 9),
                            "inference_id": inference_ids[index],
                            "ordinal": index,
                            "device_id": LIVE_DEVICE_ID,
                            "model_pair_id": model_pair_id,
                            "activation_id": activation["activation_id"],
                            "continuity_epoch": 1,
                            "model_version": model_version,
                            "snapshot_corpus_id": corpus_id,
                        }
                        for index in range(5)
                    ],
                )
                detected_event_id = f"event-{suffix}-detected"
                await connection.execute(
                    insert(tables.alert_events).values(
                        event_id=detected_event_id,
                        alert_id=alert_id,
                        event_ts=None,
                        event_at=created_at,
                        time_domain="utc",
                        event_type="detected",
                        device_id=LIVE_DEVICE_ID,
                        actor="live-worker",
                        note=None,
                        inference_result_window_start_ts=base,
                        inference_result_window_end_ts=base
                        + timedelta(seconds=9),
                        inference_model_version=model_version,
                        detection_basis="artifact_backed",
                    )
                )

                current_token = cast(
                    int,
                    await connection.scalar(
                        select(
                            func.coalesce(
                                func.max(tables.live_writer_leases.c.fencing_token), 0
                            )
                        )
                    ),
                )
                fencing_token = current_token + 1
                lease = pg_insert(tables.live_writer_leases).values(
                    device_id=LIVE_DEVICE_ID,
                    lease_owner=f"secret-client-{suffix}",
                    lease_expires_at_utc=datetime.now(timezone.utc)
                    + timedelta(minutes=5),
                    fencing_token=fencing_token,
                    updated_at_utc=datetime.now(timezone.utc),
                )
                await connection.execute(
                    lease.on_conflict_do_update(
                        index_elements=["device_id"],
                        set_={
                            "lease_owner": lease.excluded.lease_owner,
                            "lease_expires_at_utc": lease.excluded.lease_expires_at_utc,
                            "fencing_token": lease.excluded.fencing_token,
                            "updated_at_utc": lease.excluded.updated_at_utc,
                        },
                    )
                )
                health = pg_insert(tables.live_health).values(
                    device_id=LIVE_DEVICE_ID,
                    status="healthy",
                    detail_code=None,
                    fencing_token=fencing_token,
                    observed_at_utc=datetime.now(timezone.utc),
                )
                await connection.execute(
                    health.on_conflict_do_update(
                        index_elements=["device_id"],
                        set_={
                            "status": health.excluded.status,
                            "detail_code": health.excluded.detail_code,
                            "fencing_token": health.excluded.fencing_token,
                            "observed_at_utc": health.excluded.observed_at_utc,
                        },
                    )
                )
            return {
                "activation_id": cast(int, activation["activation_id"]),
                "alert_id": alert_id,
                "base": base,
                "corpus_id": corpus_id,
                "equal_second_values": [70.0, 71.0],
                "fresh_ts": fresh_ts,
                "hashes": hashes,
                "live_episode_id": live_episode_id,
                "model_pair_id": model_pair_id,
                "model_version": model_version,
                "secret": f"secret-client-{suffix}",
            }
        finally:
            await engine.dispose()

    state = asyncio.run(create())
    yield state


@pytest.mark.anyio
async def test_latest_telemetry_uses_server_wall_clock_freshness(
    client_factory: ClientFactory,
    live_api_fixture: dict[str, object],
) -> None:
    async with client_factory(_router("anomaly_backend.routes.telemetry")) as (
        _,
        client,
    ):
        response = await client.get(
            "/api/telemetry/latest", params={"device_id": LIVE_DEVICE_ID}
        )

    assert response.status_code == 200
    sensor = _payload(response)["sensors"][0]
    assert sensor["ts"] == cast(datetime, live_api_fixture["fresh_ts"]).isoformat()
    assert sensor["temperature_c"] == 26.5
    assert sensor["freshness"] == "fresh"
    assert 0 <= sensor["age_seconds"] < 30


@pytest.mark.anyio
async def test_raw_history_is_half_open_and_omits_empty_buckets(
    client_factory: ClientFactory,
    live_api_fixture: dict[str, object],
) -> None:
    base = cast(datetime, live_api_fixture["base"])
    params = {
        "device_id": LIVE_DEVICE_ID,
        "from": base.isoformat(),
        "to": (base + timedelta(hours=1)).isoformat(),
        "bucket": "raw",
        "limit": 100,
    }
    async with client_factory(_router("anomaly_backend.routes.telemetry")) as (
        _,
        client,
    ):
        response = await client.get("/api/telemetry/history", params=params)
        empty = await client.get(
            "/api/telemetry/history",
            params={
                **params,
                "from": (base + timedelta(hours=2)).isoformat(),
                "to": (base + timedelta(hours=3)).isoformat(),
            },
        )

    body = _payload(response)
    assert response.status_code == 200
    assert body["bucket"] == "raw"
    assert body["bucket_seconds"] is None
    assert body["from"] == base.isoformat()
    assert body["to"] == (base + timedelta(hours=1)).isoformat()
    assert all(point["ts"] < body["to"] for point in body["points"])
    assert not any(point["temperature_c"] == 40.0 for point in body["points"])
    assert _payload(empty)["points"] == []


@pytest.mark.anyio
async def test_one_minute_and_adaptive_history_return_effective_aggregates(
    client_factory: ClientFactory,
    live_api_fixture: dict[str, object],
) -> None:
    base = cast(datetime, live_api_fixture["base"])
    async with client_factory(_router("anomaly_backend.routes.telemetry")) as (
        _,
        client,
    ):
        preset = await client.get(
            "/api/telemetry/history",
            params={
                "device_id": LIVE_DEVICE_ID,
                "from": base.isoformat(),
                "to": (base + timedelta(hours=6)).isoformat(),
                "bucket": "one_minute",
            },
        )
        custom = await client.get(
            "/api/telemetry/history",
            params={
                "device_id": LIVE_DEVICE_ID,
                "from": base.isoformat(),
                "to": (base + timedelta(hours=11)).isoformat(),
                "bucket": "adaptive",
            },
        )

    minute = _payload(preset)
    assert preset.status_code == 200
    assert minute["bucket_seconds"] == 60
    first = minute["points"][0]
    assert first["sample_count"] >= 14
    assert first["temperature_c_min"] == 20.0
    assert first["temperature_c_max"] == 71.0
    assert first["temperature_c"] == pytest.approx(32.0)

    adaptive = _payload(custom)
    assert custom.status_code == 200
    assert adaptive["bucket"] == "adaptive"
    assert adaptive["bucket_seconds"] == 120
    assert len(adaptive["points"]) <= 600


@pytest.mark.anyio
async def test_equal_second_keyset_cursor_is_stable_and_filter_bound(
    client_factory: ClientFactory,
    live_api_fixture: dict[str, object],
) -> None:
    base = cast(datetime, live_api_fixture["base"]) + timedelta(seconds=30)
    params = {
        "device_id": LIVE_DEVICE_ID,
        "from": base.isoformat(),
        "to": (base + timedelta(seconds=1)).isoformat(),
        "bucket": "raw",
        "limit": 1,
    }
    async with client_factory(_router("anomaly_backend.routes.telemetry")) as (
        _,
        client,
    ):
        first = await client.get("/api/telemetry/history", params=params)
        cursor = _payload(first)["next_cursor"]
        assert isinstance(cursor, str) and not cursor.startswith("telemetry:")

        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    insert(tables.live_telemetry).values(
                        received_ts=base + timedelta(seconds=1),
                        telemetry_id=uuid4(),
                        device_id=LIVE_DEVICE_ID,
                        received_at_utc=datetime.now(timezone.utc),
                        temperature_c=99.0,
                        relative_humidity_pct=99.0,
                        ingress_generation=1,
                        activation_id=live_api_fixture["activation_id"],
                        continuity_epoch=1,
                        segment_start_reason=None,
                        fencing_token=1,
                        processing_status="processed",
                    )
                )
        finally:
            await engine.dispose()

        second = await client.get(
            "/api/telemetry/history", params={**params, "cursor": cursor}
        )
        mismatch = await client.get(
            "/api/telemetry/history",
            params={
                **params,
                "to": (base + timedelta(seconds=2)).isoformat(),
                "cursor": cursor,
            },
        )

    values = [
        _payload(first)["points"][0]["temperature_c"],
        _payload(second)["points"][0]["temperature_c"],
    ]
    assert values == live_api_fixture["equal_second_values"]
    assert 99.0 not in values
    assert mismatch.status_code == 422


@pytest.mark.anyio
async def test_inference_bucket_preserves_peak_anomaly_and_latest_value(
    client_factory: ClientFactory,
    live_api_fixture: dict[str, object],
) -> None:
    base = cast(datetime, live_api_fixture["base"])
    async with client_factory(_router("anomaly_backend.routes.inference")) as (
        _,
        client,
    ):
        response = await client.get(
            "/api/inference-results",
            params={
                "device_id": LIVE_DEVICE_ID,
                "from": base.isoformat(),
                "to": (base + timedelta(hours=6)).isoformat(),
                "bucket": "one_minute",
                "model_version": cast(str, live_api_fixture["model_version"]),
            },
        )

    body = _payload(response)
    assert response.status_code == 200
    assert body["bucket_seconds"] == 60
    point = body["points"][0]
    assert point["score"] == 2.5
    assert point["threshold"] == 1.0
    assert point["is_anomaly"] is True
    assert point["severity"] == "critical"
    assert point["latest_score"] == 0.3
    assert point["sample_count"] == 5


@pytest.mark.anyio
async def test_live_alert_detail_events_and_manual_lifecycle_race(
    client_factory: ClientFactory,
    live_api_fixture: dict[str, object],
) -> None:
    alert_id = cast(str, live_api_fixture["alert_id"])
    async with client_factory(_router("anomaly_backend.routes.alerts")) as (
        _,
        client,
    ):
        current = await client.get(
            "/api/alerts/current", params={"device_id": LIVE_DEVICE_ID}
        )
        detail = await client.get(f"/api/alerts/{alert_id}")
        acknowledged = await client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"command_id": f"ack-{alert_id}"},
        )
        replayed_ack = await client.post(
            f"/api/alerts/{alert_id}/acknowledge",
            json={"command_id": f"ack-{alert_id}"},
        )
        detected_events = await client.get(
            "/api/alert-events", params={"alert_id": alert_id, "limit": 1}
        )
        blocked = await client.post(
            f"/api/alerts/{alert_id}/resolve",
            json={"command_id": f"resolve-open-{alert_id}"},
        )

        engine = create_database_engine(Settings.from_environ())
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    tables.live_alert_episodes.update()
                    .where(
                        tables.live_alert_episodes.c.live_episode_id
                        == live_api_fixture["live_episode_id"]
                    )
                    .values(
                        status="resolved",
                        ended_score_ts=cast(datetime, live_api_fixture["base"])
                        + timedelta(seconds=13),
                        close_reason="normal_recovery",
                    )
                )
        finally:
            await engine.dispose()

        resolved = await client.post(
            f"/api/alerts/{alert_id}/resolve",
            json={"command_id": f"resolve-{alert_id}"},
        )
        replayed_resolve = await client.post(
            f"/api/alerts/{alert_id}/resolve",
            json={"command_id": f"resolve-{alert_id}"},
        )

    current_item = next(
        item for item in _payload(current)["items"] if item["alert_id"] == alert_id
    )
    assert current_item["status"] == "detected"
    assert current_item["replay_job_id"] is None

    context = _payload(detail)
    assert detail.status_code == 200
    assert len(context["context_before"]) == 10
    assert len(context["episode_points"]) == 2
    assert len(context["recovery_points"]) == 3
    assert all(
        len(point["source_readings"]) == 10
        for point in context["episode_points"] + context["recovery_points"]
    )

    events = _payload(detected_events)
    assert detected_events.status_code == 200
    assert events["events"][0]["event_type"] == "detected"
    assert isinstance(events["next_cursor"], str)
    assert acknowledged.status_code == 200
    assert _payload(acknowledged)["event"]["event_at"].endswith("Z")
    assert _payload(replayed_ack)["idempotent_replay"] is True
    assert blocked.status_code == 409
    assert resolved.status_code == 200
    assert _payload(replayed_resolve)["idempotent_replay"] is True


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("bucket", "hours"),
    [
        ("raw", 2),
        ("one_minute", 2),
        ("adaptive", 0.5),
        ("adaptive", 25),
    ],
)
async def test_history_rejects_invalid_bucket_ranges(
    client_factory: ClientFactory,
    live_api_fixture: dict[str, object],
    bucket: str,
    hours: float,
) -> None:
    base = cast(datetime, live_api_fixture["base"])
    async with client_factory(
        _router("anomaly_backend.routes.telemetry"),
        _router("anomaly_backend.routes.inference"),
    ) as (_, client):
        params = {
            "device_id": LIVE_DEVICE_ID,
            "from": base.isoformat(),
            "to": (base + timedelta(hours=hours)).isoformat(),
            "bucket": bucket,
        }
        telemetry = await client.get("/api/telemetry/history", params=params)
        inference = await client.get("/api/inference-results", params=params)

    assert telemetry.status_code == 422
    assert inference.status_code == 422


@pytest.mark.anyio
async def test_system_status_is_actionable_fresh_and_redacted(
    client_factory: ClientFactory,
    live_api_fixture: dict[str, object],
) -> None:
    async with client_factory(_router("anomaly_backend.routes.system")) as (
        _,
        client,
    ):
        response = await client.get("/api/system/status")

    body = _payload(response)
    assert response.status_code == 200
    telemetry = body["telemetry"]
    assert telemetry["classification"] in {"healthy", "degraded", "failed"}
    assert telemetry["configuration_valid"] is True
    assert telemetry["last_valid_reading_ts"] is not None
    assert telemetry["last_valid_reading_at"].endswith("Z")
    assert 0 <= telemetry["age_seconds"] < 30
    assert telemetry["active_model_version"] == live_api_fixture["model_version"]
    assert telemetry["artifact_hashes"] == live_api_fixture["hashes"]
    assert "live-subscriber" in {service["name"] for service in body["services"]}
    rendered = response.text
    assert cast(str, live_api_fixture["secret"]) not in rendered
    for forbidden in ("broker_host", "password", "username", "ca_file"):
        assert forbidden not in rendered
