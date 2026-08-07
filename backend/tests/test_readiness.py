from unittest.mock import AsyncMock

import pytest

from anomaly_backend.db import _single_migration_revision
from anomaly_backend.routes import system
from conftest import ClientFactory


@pytest.mark.parametrize(
    ("revision", "compatible"),
    [
        ("20260807_0016", False),
        ("20260808_0017", True),
        ("20260809_0018", True),
        ("not-a-revision", False),
        (None, False),
    ],
)
def test_revision_compatibility_is_ordinal_and_fail_closed(
    revision: str | None,
    compatible: bool,
) -> None:
    assert system._revision_is_compatible(revision) is compatible


def test_branched_migration_history_is_rejected() -> None:
    assert _single_migration_revision(["20260804_0015", "20260805_0016"]) is None


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("revision", "status_code"),
    [
        ("20260807_0016", 503),
        ("20260808_0017", 200),
        ("20260809_0018", 200),
        ("malformed", 503),
        (None, 503),
    ],
)
async def test_readiness_accepts_equal_or_newer_linear_revision(
    client_factory: ClientFactory,
    monkeypatch: pytest.MonkeyPatch,
    revision: str | None,
    status_code: int,
) -> None:
    monkeypatch.setattr(system, "database_is_healthy", AsyncMock(return_value=True))
    monkeypatch.setattr(
        system,
        "current_migration_revision",
        AsyncMock(return_value=revision),
    )

    async with client_factory(system.router) as (_, client):
        response = await client.get("/ready")

    assert response.status_code == status_code
    if status_code == 200:
        body = response.json()
        assert body["database_revision"] == revision
        assert body["minimum_database_revision"] == "20260808_0017"
