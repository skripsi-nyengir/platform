import asyncio
from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import timedelta
import os
from pathlib import Path
import secrets
import subprocess
import sys
from typing import Protocol

from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
import psycopg
from psycopg import sql
import pytest
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncEngine

TEST_DATABASE_NAME = "anomaly_detection_test"
# ponytail: one recreated DB per session isolates runs; use per-worker names for parallel tests.
DATABASE_ENV = {
    "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "db"),
    "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
    "POSTGRES_DB": TEST_DATABASE_NAME,
    "POSTGRES_USER": os.environ.get("POSTGRES_USER", "anomaly"),
    "POSTGRES_PASSWORD": os.environ.get(
        "POSTGRES_PASSWORD", "anomaly-dev-only"
    ),
}
for _key, _value in DATABASE_ENV.items():
    os.environ[_key] = _value

from anomaly_backend import tables  # noqa: E402
from anomaly_backend.auth import (  # noqa: E402
    SESSION_COOKIE,
    current_instant,
    session_digest,
    upsert_user,
)
from anomaly_backend.config import Settings  # noqa: E402
from anomaly_backend.db import create_database_engine  # noqa: E402
from anomaly_backend.main import create_app  # noqa: E402


TEST_USERNAME = "test-operator"
TEST_PASSWORD = "test-operator-password"
_SESSION_TTL_SECONDS = 24 * 60 * 60


class ClientFactory(Protocol):
    def __call__(
        self, *routers: APIRouter, authenticated: bool = True
    ) -> AbstractAsyncContextManager[tuple[FastAPI, AsyncClient]]: ...


class TerminalReporter(Protocol):
    def write_line(self, line: str) -> None: ...


def pytest_terminal_summary(terminalreporter: TerminalReporter) -> None:
    for label, variable in (
        ("task21 canonical parity report", "EDA_CANONICAL_PARITY_REPORT"),
        ("task21 canonical integration report", "EDA_CANONICAL_INTEGRATION_REPORT"),
    ):
        if value := os.environ.get(variable):
            terminalreporter.write_line(f"{label} {value}")


@pytest.fixture(scope="session", autouse=True)
def test_database() -> None:
    settings = Settings.from_environ()
    assert settings.postgres_db == TEST_DATABASE_NAME
    with psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        dbname="postgres",
        user=settings.postgres_user,
        password=settings.postgres_password,
        autocommit=True,
    ) as connection:
        identifier = sql.Identifier(TEST_DATABASE_NAME)
        _ = connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(identifier)
        )
        _ = connection.execute(sql.SQL("CREATE DATABASE {}").format(identifier))

    backend = Path(__file__).parents[1]
    for command in (
        (sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"),
        (sys.executable, "-m", "anomaly_backend.seed"),
    ):
        _ = subprocess.run(command, cwd=backend, check=True)


@pytest.fixture(autouse=True)
def postgres_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in DATABASE_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def _ensure_test_session(engine: AsyncEngine, token: str) -> None:
    """Make ``token`` a live session, recreating the account and row if needed.

    test_migration drops the public schema and replays the migrations, which takes the
    account and its session with it. Restoring on demand keeps every test file that
    runs afterwards authenticated without making them aware of any of this.
    """
    async with engine.connect() as connection:
        now = current_instant()
        digest = session_digest(token)
        present = await connection.scalar(
            select(tables.user_sessions.c.session_id).where(
                tables.user_sessions.c.session_id == digest,
                tables.user_sessions.c.expires_at > now,
            )
        )
        if present is not None:
            return
        user_id, _ = await upsert_user(
            connection, TEST_USERNAME, TEST_PASSWORD, "Test Operator", now=now
        )
        _ = await connection.execute(
            insert(tables.user_sessions).values(
                session_id=digest,
                user_id=user_id,
                created_at=now,
                expires_at=now + timedelta(seconds=_SESSION_TTL_SECONDS),
            )
        )
        await connection.commit()


@pytest.fixture(scope="session")
def test_session_token(test_database: None) -> str:
    # A stable token for the whole run, so restoring the row after a schema rebuild
    # keeps every already-constructed client valid.
    _ = test_database
    return secrets.token_urlsafe(32)


@pytest.fixture
def session_cookies(test_session_token: str) -> dict[str, str]:
    """Cookies for tests that drive the production app through TestClient."""

    async def prepare() -> None:
        engine = create_database_engine(Settings.from_environ())
        try:
            await _ensure_test_session(engine, test_session_token)
        finally:
            await engine.dispose()

    asyncio.run(prepare())
    return {SESSION_COOKIE: test_session_token}


@pytest.fixture
def client_factory(test_session_token: str) -> ClientFactory:
    @asynccontextmanager
    async def factory(
        *routers: APIRouter,
        authenticated: bool = True,
    ) -> AsyncGenerator[tuple[FastAPI, AsyncClient]]:
        engine = create_database_engine(Settings.from_environ())
        app = create_app(engine, *routers)
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        cookies: dict[str, str] = {}
        try:
            if authenticated:
                await _ensure_test_session(engine, test_session_token)
                cookies[SESSION_COOKIE] = test_session_token
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
                cookies=cookies,
            ) as client:
                yield app, client
        finally:
            await engine.dispose()

    return factory
