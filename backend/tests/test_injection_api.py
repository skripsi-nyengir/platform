from typing import Any, cast
from importlib import import_module

from fastapi import APIRouter
from httpx import Response
import psycopg
from psycopg.rows import dict_row
import pytest

from anomaly_backend.config import Settings

from conftest import ClientFactory


PUBLIC_DEVICE_ID = "b02f3872-ruang-produksi"
SIM_DEVICE_ID = "b02f3872-simulasi-injeksi"
_INJECTION_ROUTER = "anomaly_backend.routes.injection"


def _router(module: str) -> APIRouter:
    value = getattr(import_module(module), "router", None)
    assert isinstance(value, APIRouter)
    return value


def _payload(response: Response) -> dict[str, Any]:
    return cast(dict[str, Any], response.json())


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
async def test_injection_events_empty_for_unseeded_sim_device(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router(_INJECTION_ROUTER)) as (_, client):
        response = await client.get("/api/injection-events")

    assert response.status_code == 200
    body = _payload(response)
    assert body["device_id"] == SIM_DEVICE_ID
    assert body["time_zone"] == "Asia/Jakarta"
    assert body["events"] == []
    assert body["returned_count"] == 0
    assert isinstance(body["request_id"], str) and body["request_id"]


@pytest.mark.anyio
async def test_injection_events_returns_rows_ordered_by_start_ts(
    client_factory: ClientFactory,
) -> None:
    connection = _sync_connection()
    corpus = connection.execute(
        "SELECT corpus_id FROM corpora WHERE device_id = %s LIMIT 1",
        (PUBLIC_DEVICE_ID,),
    ).fetchone()
    assert corpus is not None, "seed must provide a corpus for the public device"
    corpus_id = corpus["corpus_id"]
    event_ids = ("test_inj_evt_b", "test_inj_evt_a")
    try:
        # Insert later-timestamped row first so insertion order != start_ts order.
        connection.execute(
            """
            INSERT INTO injection_events (
                event_id, corpus_id, device_id, family, severity, channel,
                channel_index, start_idx, end_idx_exclusive, start_ts, end_ts,
                segment_index
            ) VALUES
                (%s, %s, %s, 'drift', 'medium', 'suhu', 0, 60, 90,
                 '2026-02-01 00:01:00', '2026-02-01 00:01:30', 1),
                (%s, %s, %s, 'spike', 'low', 'suhu', 0, 10, 20,
                 '2026-02-01 00:00:10', '2026-02-01 00:00:20', 0)
            """,
            (
                event_ids[0], corpus_id, PUBLIC_DEVICE_ID,
                event_ids[1], corpus_id, PUBLIC_DEVICE_ID,
            ),
        )
        async with client_factory(_router(_INJECTION_ROUTER)) as (_, client):
            response = await client.get(
                "/api/injection-events",
                params={"device_id": PUBLIC_DEVICE_ID},
            )
    finally:
        connection.execute(
            "DELETE FROM injection_events WHERE event_id = ANY(%s)",
            (list(event_ids),),
        )
        connection.close()

    assert response.status_code == 200
    body = _payload(response)
    assert body["device_id"] == PUBLIC_DEVICE_ID
    events = body["events"]
    assert [event["event_id"] for event in events] == ["test_inj_evt_a", "test_inj_evt_b"]
    first = events[0]
    assert first["family"] == "spike"
    assert first["severity"] == "low"
    assert first["channel"] == "suhu"
    assert first["channel_index"] == 0
    assert first["start_ts"] == "2026-02-01T00:00:10"
    assert first["end_ts"] == "2026-02-01T00:00:20"
    assert first["start_idx"] == 10
    assert first["end_idx_exclusive"] == 20
    assert first["segment_index"] == 0
    assert body["returned_count"] == 2
