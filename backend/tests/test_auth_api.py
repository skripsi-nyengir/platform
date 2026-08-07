from datetime import timedelta
import re
from typing import cast

from fastapi.testclient import TestClient
from httpx import Response
import pytest
from sqlalchemy import delete, insert
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend import auth_middleware, tables
from anomaly_backend.auth import (
    SESSION_COOKIE,
    current_instant,
    session_digest,
    upsert_user,
)
from anomaly_backend.db import create_database_engine
from anomaly_backend.config import Settings
from anomaly_backend.main import app as production_app
from anomaly_backend.routes.auth import router as auth_router
from anomaly_backend.routes.system import router as system_router
from conftest import ClientFactory


USERNAME = "api-operator"
PASSWORD = "api-operator-password"
_PATH_PARAMETER = re.compile(r"\{[^}]+\}")


async def _seed_account(password: str = PASSWORD) -> str:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            _ = await connection.execute(
                delete(tables.users).where(tables.users.c.username == USERNAME)
            )
            await connection.commit()
            user_id, _ = await upsert_user(
                connection, USERNAME, password, "API Operator", now=current_instant()
            )
            return user_id
    finally:
        await engine.dispose()


async def _insert_session(user_id: str, token: str, *, ttl_seconds: int) -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            now = current_instant()
            expires_at = now + timedelta(seconds=ttl_seconds)
            _ = await connection.execute(
                insert(tables.user_sessions).values(
                    session_id=session_digest(token),
                    user_id=user_id,
                    # Kept strictly before expiry so an intentionally expired session
                    # still satisfies ck_user_sessions_expiry_after_creation.
                    created_at=expires_at - timedelta(hours=1),
                    expires_at=expires_at,
                )
            )
            await connection.commit()
    finally:
        await engine.dispose()


def _endpoints(routes: object) -> list[tuple[str, str]]:
    """Flatten the app's routes into (method, path) pairs.

    FastAPI wraps each included router, so the mounted endpoints only appear through
    ``original_router``; reading ``app.routes`` directly finds nothing to check.
    """
    found: list[tuple[str, str]] = []
    for route in cast(list[object], routes):
        included = getattr(route, "original_router", None)
        if included is not None:
            found.extend(_endpoints(included.routes))
            continue
        path = cast(str, getattr(route, "path", ""))
        methods = cast("set[str] | None", getattr(route, "methods", None)) or set()
        found.extend(
            (method, path) for method in sorted(methods - {"HEAD", "OPTIONS"}) if path
        )
    return found


@pytest.mark.anyio
async def test_login_returns_the_session_and_sets_a_hardened_cookie(
    client_factory: ClientFactory,
) -> None:
    _ = await _seed_account()

    async with client_factory(auth_router, authenticated=False) as (_, client):
        response = await client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == USERNAME
    assert body["display_name"] == "API Operator"
    assert body["expires_at"].endswith("Z")

    cookie = response.headers["set-cookie"]
    assert cookie.startswith(f"{SESSION_COOKIE}=")
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    # The cookie must carry the token, never anything derived from the account.
    assert USERNAME not in cookie


@pytest.mark.anyio
async def test_wrong_password_and_unknown_username_are_indistinguishable(
    client_factory: ClientFactory,
) -> None:
    _ = await _seed_account()

    async with client_factory(auth_router, authenticated=False) as (_, client):
        wrong = await client.post(
            "/api/auth/login", json={"username": USERNAME, "password": "not-it"}
        )
        unknown = await client.post(
            "/api/auth/login", json={"username": "nobody", "password": PASSWORD}
        )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.headers["content-type"].startswith("application/problem+json")
    assert "set-cookie" not in wrong.headers

    def comparable(response: Response) -> dict[str, object]:
        body = dict(response.json())
        # request_id and instance are per-request; everything else must match.
        _ = body.pop("request_id")
        return body

    assert comparable(wrong) == comparable(unknown)
    assert comparable(wrong)["title"] == "Authentication required"


@pytest.mark.anyio
async def test_repeated_failures_answer_429_with_retry_after(
    client_factory: ClientFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AUTH_MAX_FAILED_ATTEMPTS", "3")
    monkeypatch.setenv("AUTH_LOCKOUT_SECONDS", "60")
    _ = await _seed_account()

    async with client_factory(auth_router, authenticated=False) as (_, client):
        first = await client.post(
            "/api/auth/login", json={"username": USERNAME, "password": "no"}
        )
        second = await client.post(
            "/api/auth/login", json={"username": USERNAME, "password": "no"}
        )
        third = await client.post(
            "/api/auth/login", json={"username": USERNAME, "password": "no"}
        )
        # The right password stays refused for as long as the window is open.
        correct = await client.post(
            "/api/auth/login", json={"username": USERNAME, "password": PASSWORD}
        )

    assert (first.status_code, second.status_code) == (401, 401)
    assert third.status_code == 429
    assert third.headers["retry-after"] == "60"
    assert third.json()["title"] == "Too many attempts"
    assert correct.status_code == 429


@pytest.mark.anyio
async def test_session_endpoint_reports_the_signed_in_account(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(auth_router) as (_, client):
        response = await client.get("/api/auth/session")

    assert response.status_code == 200
    assert response.json()["username"] == "test-operator"


@pytest.mark.anyio
async def test_session_endpoint_refuses_without_a_cookie(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(auth_router, authenticated=False) as (_, client):
        response = await client.get("/api/auth/session")

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["type"].endswith("/unauthenticated")


@pytest.mark.anyio
async def test_an_expired_session_is_refused(client_factory: ClientFactory) -> None:
    user_id = await _seed_account()
    token = "expired-session-token"
    await _insert_session(user_id, token, ttl_seconds=-1)

    async with client_factory(auth_router, authenticated=False) as (_, client):
        response = await client.get(
            "/api/auth/session", cookies={SESSION_COOKIE: token}
        )

    assert response.status_code == 401


@pytest.mark.anyio
async def test_logout_revokes_the_session_and_clears_the_cookie(
    client_factory: ClientFactory,
) -> None:
    user_id = await _seed_account()
    token = "logout-session-token"
    await _insert_session(user_id, token, ttl_seconds=3600)

    async with client_factory(auth_router, authenticated=False) as (_, client):
        before = await client.get("/api/auth/session", cookies={SESSION_COOKIE: token})
        logout = await client.post("/api/auth/logout", cookies={SESSION_COOKIE: token})
        after = await client.get("/api/auth/session", cookies={SESSION_COOKIE: token})

    assert before.status_code == 200
    assert logout.status_code == 200
    assert 'adp_session=""' in logout.headers["set-cookie"]
    assert after.status_code == 401


@pytest.mark.anyio
async def test_logout_is_idempotent_without_a_session(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(auth_router, authenticated=False) as (_, client):
        first = await client.post("/api/auth/logout")
        second = await client.post(
            "/api/auth/logout", cookies={SESSION_COOKIE: "never-existed"}
        )

    assert (first.status_code, second.status_code) == (200, 200)


@pytest.mark.anyio
async def test_health_and_readiness_stay_open_without_a_session(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(system_router, authenticated=False) as (_, client):
        health = await client.get("/health")
        readiness = await client.get("/ready")

    assert health.status_code == 200
    assert readiness.status_code in {200, 503}
    assert readiness.json()["status"] in {"ready", "not_ready"}


@pytest.mark.anyio
async def test_a_database_failure_refuses_rather_than_letting_the_request_through(
    client_factory: ClientFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def explode(*_args: object, **_kwargs: object) -> None:
        raise OperationalError("select", {}, Exception("connection lost"))

    monkeypatch.setattr(auth_middleware, "lookup_session", explode)

    async with client_factory(system_router) as (_, client):
        response = await client.get("/api/system/status")

    # Not 200, and not a traceback: the guard cannot verify, so it refuses.
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")


def test_every_production_route_outside_the_allowlist_requires_a_session() -> None:
    """The regression test that keeps the guard closed as routes are added.

    Enumerating the real app means a new router cannot quietly ship unprotected: the
    only way to exempt a path is to add it to OPEN_ROUTES on purpose.
    """
    endpoints = _endpoints(production_app.routes)
    checked = 0
    with TestClient(production_app) as client:
        for method, path in endpoints:
            if (method, path) in auth_middleware.OPEN_ROUTES:
                continue
            concrete = _PATH_PARAMETER.sub("placeholder", path)
            response = client.request(method, concrete)
            assert response.status_code == 401, (
                f"{method} {path} answered {response.status_code} without a session"
            )
            checked += 1

    # Guard against the walk silently finding nothing and passing vacuously.
    assert len(endpoints) > 30
    assert checked == len(endpoints) - len(auth_middleware.OPEN_ROUTES)


def test_the_allowlist_only_contains_probes_and_the_auth_entry_points() -> None:
    assert auth_middleware.OPEN_ROUTES == frozenset(
        {
            ("GET", "/health"),
            ("GET", "/ready"),
            ("POST", "/api/auth/login"),
            ("POST", "/api/auth/logout"),
        }
    )


@pytest.mark.anyio
async def test_an_unknown_path_is_refused_before_it_can_report_not_found(
    client_factory: ClientFactory,
) -> None:
    # Answering 404 here would let an anonymous caller map which routes exist.
    async with client_factory(auth_router, authenticated=False) as (_, client):
        response = await client.get("/api/does-not-exist")

    assert response.status_code == 401


def test_engine_is_available_to_the_guard() -> None:
    assert isinstance(production_app.state.engine, AsyncEngine)
