from datetime import datetime, timezone
from typing import Any, cast
from importlib import import_module

from fastapi import APIRouter
from httpx import Response
import pytest

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine

from tests.conftest import ClientFactory


SIM_DEVICE_ID = "b02f3872-simulasi-injeksi"
_SIMULATION_ROUTER = "anomaly_backend.routes.simulation"


def _router(module: str) -> APIRouter:
    value = getattr(import_module(module), "router", None)
    assert isinstance(value, APIRouter)
    return value


def _payload(response: Response) -> dict[str, Any]:
    return cast(dict[str, Any], response.json())


@pytest.mark.anyio
async def test_simulation_models_returns_envelope(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router(_SIMULATION_ROUTER)) as (_, client):
        response = await client.get("/api/simulation/models")

    assert response.status_code == 200
    body = _payload(response)
    assert body["device_id"] == SIM_DEVICE_ID
    assert isinstance(body["models"], list)
    assert isinstance(body["request_id"], str) and body["request_id"]


@pytest.mark.anyio
async def test_set_active_model_unknown_version_returns_404(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router(_SIMULATION_ROUTER)) as (_, client):
        response = await client.post(
            "/api/simulation/active-model",
            json={"model_version": "artifact-does-not-exist"},
        )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.anyio
async def test_set_active_model_rejects_incompatible_runtime_metadata(
    client_factory: ClientFactory,
) -> None:
    version = "test-simulation-artifact-window-30"
    activation_id = "activation-test-simulation-window-30"
    engine = create_database_engine(Settings.from_environ())
    prior_selection: dict[str, object] | None = None
    created_device = False
    try:
        async with engine.begin() as connection:
            prior = (
                await connection.execute(
                    tables.active_model_selections.select().where(
                        tables.active_model_selections.c.device_id
                        == SIM_DEVICE_ID
                    )
                )
            ).mappings().one_or_none()
            prior_selection = dict(prior) if prior is not None else None
            await connection.execute(
                tables.active_model_selections.delete().where(
                    tables.active_model_selections.c.device_id == SIM_DEVICE_ID
                )
            )
            device_exists = (
                await connection.execute(
                    tables.devices.select().where(
                        tables.devices.c.device_id == SIM_DEVICE_ID
                    )
                )
            ).first()
            if device_exists is None:
                await connection.execute(
                    tables.devices.insert().values(
                        device_id=SIM_DEVICE_ID,
                        display_name="Test simulation device",
                        source_device_uuid=None,
                        time_zone="Asia/Jakarta",
                        telemetry_kind="anomaly_injected",
                        is_active=True,
                        archived_at=None,
                    )
                )
                created_device = True
            await connection.execute(
                tables.model_versions.insert().values(
                    version=version,
                    model_key="lstm-ae",
                    runtime_kind="artifact",
                    is_selectable=True,
                    adapter_key="test-artifact-v1",
                    schema_version="b02f3872_preview_v1",
                        channels=["suhu", "rh"],
                        window_size=30,
                        stride=1,
                        contract_status="legacy_30",
                    score_key="test_score",
                    score_semantics="execution-boundary fixture",
                    threshold=1.0,
                    threshold_policy={"comparator": ">"},
                    temporal_semantics="context_end",
                    source_commit=None,
                    source_config="test-simulation-window-30",
                    manifest_sha256="a" * 64,
                    created_at=datetime.now(timezone.utc),
                )
            )
            await connection.execute(
                tables.model_activations.insert().values(
                    activation_id=activation_id,
                    command_id="command-test-simulation-window-30",
                    payload_hash="b" * 64,
                    device_id=SIM_DEVICE_ID,
                    prior_model_version=None,
                    model_version=version,
                    changed=True,
                    activated_at=datetime.now(timezone.utc),
                    actor="test",
                )
            )
            await connection.execute(
                tables.active_model_selections.insert().values(
                    device_id=SIM_DEVICE_ID,
                    activation_id=activation_id,
                    model_version=version,
                )
            )

        async with client_factory(_router(_SIMULATION_ROUTER)) as (_, client):
            response = await client.post(
                "/api/simulation/active-model",
                json={"model_version": version},
            )

        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                tables.active_model_selections.delete().where(
                    tables.active_model_selections.c.device_id == SIM_DEVICE_ID
                )
            )
            await connection.execute(
                tables.model_activations.delete().where(
                    tables.model_activations.c.activation_id == activation_id
                )
            )
            await connection.execute(
                tables.model_versions.delete().where(
                    tables.model_versions.c.version == version
                )
            )
            if prior_selection is not None:
                await connection.execute(
                    tables.active_model_selections.insert().values(
                        **prior_selection
                    )
                )
            if created_device:
                await connection.execute(
                    tables.devices.delete().where(
                        tables.devices.c.device_id == SIM_DEVICE_ID
                    )
                )
        await engine.dispose()


@pytest.mark.anyio
async def test_set_active_model_rejects_empty_version(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(_router(_SIMULATION_ROUTER)) as (_, client):
        response = await client.post(
            "/api/simulation/active-model",
            json={"model_version": ""},
        )

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
