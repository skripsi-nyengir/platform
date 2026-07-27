from contextlib import AbstractAsyncContextManager
from typing import Annotated, Protocol, cast

from fastapi import APIRouter, Depends, FastAPI, Query
from httpx import AsyncClient, Response
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from anomaly_backend.contracts import (
    AlertCommandRequest,
    HistoricalDateTime,
    ProblemDetails,
    current_historical_datetime,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import Conflict, DependencyFailure, InvalidQuery, NotFound


PROBLEM_KEYS = {"type", "title", "status", "detail", "instance", "request_id"}


class ClientFactory(Protocol):
    def __call__(
        self, *routers: APIRouter
    ) -> AbstractAsyncContextManager[tuple[FastAPI, AsyncClient]]: ...


def response_payload(response: Response) -> dict[str, object]:
    return cast(dict[str, object], response.json())


def assert_problem(
    response_status: int,
    response_headers: object,
    payload: dict[str, object],
    status: int,
    *,
    has_errors: bool = False,
) -> ProblemDetails:
    assert response_status == status
    assert getattr(response_headers, "get")("content-type") == "application/problem+json"
    assert set(payload) == PROBLEM_KEYS | ({"errors"} if has_errors else set())
    problem = ProblemDetails.model_validate(payload, strict=True)
    assert problem.status == status
    assert problem.request_id
    return problem


@pytest.mark.anyio
async def test_mutation_body_validation_is_strict_problem_400(
    client_factory: ClientFactory,
) -> None:
    router = APIRouter()

    async def body_stub(command: AlertCommandRequest) -> dict[str, str]:
        return {"command_id": command.command_id}

    router.add_api_route("/stub/body", body_stub, methods=["POST"])

    async with client_factory(router) as (_, client):
        malformed_json = await client.post(
            "/stub/body",
            content="{",
            headers={"content-type": "application/json"},
        )
        malformed_timestamp = await client.post(
            "/stub/body",
            json={"command_id": "command-1", "event_ts": "2025-12-18T07:52:42Z"},
        )

    for response in (malformed_json, malformed_timestamp):
        problem = assert_problem(
            response.status_code,
            response.headers,
            response_payload(response),
            400,
            has_errors=True,
        )
        assert problem.instance == "/stub/body"
        assert problem.errors


@pytest.mark.anyio
async def test_mutation_query_validation_remains_422_and_sanitizes_input(
    client_factory: ClientFactory,
) -> None:
    router = APIRouter()

    async def body_and_query_stub(
        command: AlertCommandRequest,
        count: Annotated[int, Query()],
    ) -> dict[str, object]:
        return {"command_id": command.command_id, "count": count}

    router.add_api_route(
        "/stub/body-and-query",
        body_and_query_stub,
        methods=["POST"],
    )

    invalid_value = "secret-invalid-count"
    async with client_factory(router) as (_, client):
        response = await client.post(
            "/stub/body-and-query",
            params={"count": invalid_value},
            json={"command_id": "command-1"},
        )

    problem = assert_problem(
        response.status_code,
        response.headers,
        response_payload(response),
        422,
        has_errors=True,
    )
    assert problem.errors
    assert invalid_value not in response.text


@pytest.mark.anyio
async def test_query_path_and_no_offset_validation_are_422_with_fresh_ids(
    client_factory: ClientFactory,
) -> None:
    router = APIRouter()

    async def query_stub(
        item_id: int,
        count: int,
        at: Annotated[HistoricalDateTime, Query()],
    ) -> dict[str, object]:
        return {"item_id": item_id, "count": count, "at": at}

    router.add_api_route("/stub/query/{item_id}", query_stub, methods=["GET"])

    async with client_factory(router) as (_, client):
        first = await client.get(
            "/stub/query/not-an-int",
            params={"count": "also-bad", "at": "2025-12-18T07:52:42Z"},
        )
        second = await client.get(
            "/stub/query/not-an-int",
            params={"count": "also-bad", "at": "2025-12-18T07:52:42Z"},
        )

    first_problem = assert_problem(
        first.status_code,
        first.headers,
        response_payload(first),
        422,
        has_errors=True,
    )
    second_problem = assert_problem(
        second.status_code,
        second.headers,
        response_payload(second),
        422,
        has_errors=True,
    )
    assert first_problem.request_id != second_problem.request_id


@pytest.mark.anyio
async def test_invalid_query_is_strict_problem_422(
    client_factory: ClientFactory,
) -> None:
    router = APIRouter()

    async def invalid_query_stub() -> None:
        raise InvalidQuery("Query parameters failed validation", {"cursor": ["Invalid cursor"]})

    router.add_api_route("/stub/invalid-query", invalid_query_stub, methods=["GET"])

    async with client_factory(router) as (_, client):
        response = await client.get("/stub/invalid-query")

    problem = assert_problem(
        response.status_code,
        response.headers,
        response_payload(response),
        422,
        has_errors=True,
    )
    assert problem.errors == {"cursor": ["Invalid cursor"]}


@pytest.mark.anyio
async def test_not_found_and_redirect_boundary_use_strict_problem_404(
    client_factory: ClientFactory,
) -> None:
    router = APIRouter()

    async def not_found_stub() -> None:
        raise NotFound("The fixture resource was not found")

    async def exact_stub() -> dict[str, bool]:
        return {"ok": True}

    router.add_api_route("/stub/not-found", not_found_stub, methods=["GET"])
    router.add_api_route("/stub/exact", exact_stub, methods=["GET"])

    async with client_factory(router) as (_, client):
        responses = [
            await client.get("/stub/not-found", follow_redirects=False),
            await client.get("/missing", follow_redirects=False),
            await client.get("/stub/exact/", follow_redirects=False),
        ]

    for response in responses:
        problem = assert_problem(
            response.status_code,
            response.headers,
            response_payload(response),
            404,
        )
        assert problem.instance in {"/stub/not-found", "/missing", "/stub/exact/"}
        assert "location" not in response.headers


@pytest.mark.anyio
async def test_conflict_is_strict_problem_409(
    client_factory: ClientFactory,
) -> None:
    router = APIRouter()

    async def conflict_stub() -> None:
        raise Conflict("The command conflicts with persisted state")

    router.add_api_route("/stub/conflict", conflict_stub, methods=["POST"])

    async with client_factory(router) as (_, client):
        response = await client.post("/stub/conflict")

    problem = assert_problem(
        response.status_code,
        response.headers,
        response_payload(response),
        409,
    )
    assert problem.detail == "The command conflicts with persisted state"


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure",
    [
        SQLAlchemyError("database unavailable"),
        DependencyFailure("dependency unavailable"),
    ],
)
async def test_database_and_dependency_failures_are_strict_problem_503(
    client_factory: ClientFactory,
    failure: Exception,
) -> None:
    router = APIRouter()

    async def unavailable_stub(
        connection: Annotated[AsyncConnection, Depends(get_connection)],
    ) -> None:
        _ = connection
        raise failure

    router.add_api_route("/stub/unavailable", unavailable_stub, methods=["GET"])

    async with client_factory(router) as (_, client):
        response = await client.get("/stub/unavailable")

    problem = assert_problem(
        response.status_code,
        response.headers,
        response_payload(response),
        503,
    )
    assert problem.detail == "The service is temporarily unavailable"
    assert str(failure) not in response.text


@pytest.mark.anyio
async def test_injected_engine_supplies_a_fresh_connection_per_request(
    client_factory: ClientFactory,
) -> None:
    router = APIRouter()
    connections: list[AsyncConnection] = []

    async def connection_stub(
        connection: Annotated[AsyncConnection, Depends(get_connection)],
    ) -> dict[str, int]:
        connections.append(connection)
        return {"value": int(await connection.scalar(select(1)) or 0)}

    router.add_api_route("/stub/connection", connection_stub, methods=["GET"])

    async with client_factory(router) as (_, client):
        first = await client.get("/stub/connection")
        second = await client.get("/stub/connection")

    assert first.json() == second.json() == {"value": 1}
    assert len(connections) == 2
    assert connections[0] is not connections[1]
    for connection in connections:
        sync_connection = connection.sync_connection
        assert sync_connection is not None
        assert sync_connection.closed


@pytest.mark.anyio
async def test_client_factory_owns_fresh_engine_client_and_cleanup(
    client_factory: ClientFactory,
) -> None:
    async with client_factory() as (first_app, client):
        first_client = client
        first_engine = cast(AsyncEngine, first_app.state.engine)
        first_pool = first_engine.pool
        assert not client.is_closed

    async with client_factory() as (second_app, second_client):
        second_engine = cast(AsyncEngine, second_app.state.engine)
        assert second_engine is not first_engine
        assert second_client is not first_client

    assert first_client.is_closed
    assert first_engine.pool is not first_pool
    assert second_client.is_closed


def test_runtime_timestamp_is_strict_no_offset_seconds() -> None:
    value = current_historical_datetime()

    assert len(value) == 19
    assert value[4] == value[7] == "-"
    assert value[10] == "T"
    assert value[13] == value[16] == ":"
    assert "Z" not in value and "+" not in value
