from importlib import import_module

from fastapi import APIRouter
import pytest

from anomaly_backend.contracts import PostInferenceBinsResponse

from tests.conftest import ClientFactory

PUBLIC_DEVICE_ID = "b02f3872-ruang-produksi"


def _router(module: str) -> APIRouter:
    value = getattr(import_module(module), "router", None)
    assert isinstance(value, APIRouter)
    return value


@pytest.mark.anyio
async def test_post_inference_bins_empty_range_returns_valid_response(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(
        _router("anomaly_backend.routes.post_inference_bins"),
    ) as (_, client):
        response = await client.get(
            "/api/post-inference-bins",
            params={
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T02:00:00",
            },
        )
    assert response.status_code == 200
    result = PostInferenceBinsResponse.model_validate(
        response.json(), strict=True
    )
    assert result.time_zone == "Asia/Jakarta"
    assert result.device_id == PUBLIC_DEVICE_ID
    assert result.returned_count == 0
    assert result.bins == []
    assert result.next_cursor is None


@pytest.mark.anyio
async def test_post_inference_bins_rejects_reversed_range(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(
        _router("anomaly_backend.routes.post_inference_bins"),
    ) as (_, client):
        response = await client.get(
            "/api/post-inference-bins",
            params={
                "device_id": PUBLIC_DEVICE_ID,
                "from": "2026-02-01T02:00:00",
                "to": "2026-02-01T00:00:00",
            },
        )
    assert response.status_code == 422


@pytest.mark.anyio
async def test_post_inference_bins_rejects_unknown_device(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(
        _router("anomaly_backend.routes.post_inference_bins"),
    ) as (_, client):
        response = await client.get(
            "/api/post-inference-bins",
            params={
                "device_id": "talpha-1",
                "from": "2026-02-01T00:00:00",
                "to": "2026-02-01T02:00:00",
            },
        )
    assert response.status_code == 422
