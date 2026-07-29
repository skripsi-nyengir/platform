from typing import Any, cast
from importlib import import_module

from fastapi import APIRouter
from httpx import Response
import pytest

from conftest import ClientFactory


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
