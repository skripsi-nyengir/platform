from collections.abc import AsyncGenerator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
import os
from typing import Protocol

from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

DATABASE_ENV = {
    "POSTGRES_HOST": os.environ.get("POSTGRES_HOST", "db"),
    "POSTGRES_PORT": os.environ.get("POSTGRES_PORT", "5432"),
    "POSTGRES_DB": os.environ.get("POSTGRES_DB", "anomaly_detection"),
    "POSTGRES_USER": os.environ.get("POSTGRES_USER", "anomaly"),
    "POSTGRES_PASSWORD": os.environ.get(
        "POSTGRES_PASSWORD", "anomaly-dev-only"
    ),
}
for _key, _value in DATABASE_ENV.items():
    os.environ.setdefault(_key, _value)

from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.main import create_app


class ClientFactory(Protocol):
    def __call__(
        self, *routers: APIRouter
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


@pytest.fixture(autouse=True)
def postgres_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in DATABASE_ENV.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def client_factory() -> ClientFactory:
    @asynccontextmanager
    async def factory(
        *routers: APIRouter,
    ) -> AsyncGenerator[tuple[FastAPI, AsyncClient]]:
        engine = create_database_engine(Settings.from_environ())
        app = create_app(engine, *routers)
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        try:
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
            ) as client:
                yield app, client
        finally:
            await engine.dispose()

    return factory
