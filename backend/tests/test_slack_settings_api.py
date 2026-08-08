import asyncio
from collections.abc import AsyncIterator
from typing import ClassVar
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from anomaly_backend import tables
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine
from anomaly_backend.routes.slack_settings import router
from anomaly_backend.slack import (
    SlackConfigurationError,
    SlackRateLimitError,
    SlackTransientError,
)
from anomaly_backend.sql.slack_settings import read_slack_settings
from anomaly_worker.notifier_service import deliver_once
from conftest import ClientFactory


TOKEN = "xoxb-api-secret"
REPLACEMENT = "xoxb-api-replacement"
CHANNEL = "C0123456789"


class RecordingSlackClient:
    messages: ClassVar[list[tuple[str, str, str]]] = []
    error: ClassVar[Exception | None] = None

    def __init__(self, token: str) -> None:
        self.token = token

    async def __aenter__(self) -> "RecordingSlackClient":
        return self

    async def __aexit__(self, *_exception: object) -> None:
        return None

    async def post_message(self, *, channel_id: str, text: str) -> None:
        if self.error is not None:
            raise self.error
        self.messages.append((self.token, channel_id, text))


@pytest.fixture(autouse=True)
async def reset_settings() -> AsyncIterator[None]:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            _ = await connection.execute(
                tables.slack_settings.update().values(
                    enabled=False,
                    bot_token=None,
                    channel_id=None,
                    updated_by_user_id=None,
                )
            )
            await connection.commit()
        RecordingSlackClient.messages = []
        RecordingSlackClient.error = None
        yield
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_seeded_settings_are_disabled_and_never_expose_the_token(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(router) as (_, client):
        response = await client.get("/api/settings/slack")

    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert response.json()["bot_token_configured"] is False
    assert "bot_token" not in response.json()

    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            count = await connection.scalar(select(func.count()).select_from(tables.slack_settings))
    finally:
        await engine.dispose()
    assert count == 1


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("bot_token", "channel_id"),
    [(None, None), ("   ", CHANNEL), (TOKEN, "   ")],
)
async def test_database_rejects_enabled_settings_without_credentials(
    bot_token: str | None,
    channel_id: str | None,
) -> None:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            with pytest.raises(IntegrityError):
                _ = await connection.execute(
                    tables.slack_settings.update().values(
                        enabled=True,
                        bot_token=bot_token,
                        channel_id=channel_id,
                    )
                )
            await connection.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_settings_routes_require_authentication(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(router, authenticated=False) as (_, client):
        response = await client.get("/api/settings/slack")

    assert response.status_code == 401


@pytest.mark.anyio
async def test_put_preserves_replaces_and_clears_the_token(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(router) as (_, client):
        saved = await client.put(
            "/api/settings/slack",
            json={"enabled": True, "channel_id": CHANNEL, "bot_token": TOKEN},
        )
        preserved = await client.put(
            "/api/settings/slack",
            json={"enabled": True, "channel_id": "C1111111111"},
        )
        replaced = await client.put(
            "/api/settings/slack",
            json={
                "enabled": True,
                "channel_id": CHANNEL,
                "bot_token": REPLACEMENT,
            },
        )
        cleared = await client.put(
            "/api/settings/slack",
            json={"enabled": False, "channel_id": CHANNEL, "bot_token": None},
        )

    for response in (saved, preserved, replaced, cleared):
        assert response.status_code == 200
        assert "bot_token" not in response.json()
        assert response.json()["updated_by_username"] == "test-operator"
    assert saved.json()["bot_token_configured"] is True
    assert preserved.json()["bot_token_configured"] is True
    assert replaced.json()["bot_token_configured"] is True
    assert cleared.json()["bot_token_configured"] is False

    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as connection:
            stored = await connection.scalar(select(tables.slack_settings.c.bot_token))
    finally:
        await engine.dispose()
    assert stored is None


@pytest.mark.anyio
async def test_locked_settings_read_observes_the_latest_committed_token(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(router) as (_, client):
        response = await client.put(
            "/api/settings/slack",
            json={"enabled": False, "channel_id": CHANNEL, "bot_token": TOKEN},
        )
    assert response.status_code == 200

    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as first, engine.connect() as second:
            current = await read_slack_settings(first, for_update=True)
            assert current.bot_token == TOKEN

            waiting = asyncio.create_task(
                read_slack_settings(second, for_update=True)
            )
            await asyncio.sleep(0.05)
            assert not waiting.done()

            _ = await first.execute(
                tables.slack_settings.update().values(bot_token=REPLACEMENT)
            )
            await first.commit()

            latest = await asyncio.wait_for(waiting, timeout=1)
            assert latest.bot_token == REPLACEMENT
            await second.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_enabling_or_clearing_while_enabled_is_refused(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(router) as (_, client):
        missing = await client.put(
            "/api/settings/slack", json={"enabled": True, "channel_id": CHANNEL}
        )
        _ = await client.put(
            "/api/settings/slack",
            json={"enabled": False, "channel_id": CHANNEL, "bot_token": TOKEN},
        )
        clear_enabled = await client.put(
            "/api/settings/slack",
            json={"enabled": True, "channel_id": CHANNEL, "bot_token": None},
        )

    assert missing.status_code == 422
    assert clear_enabled.status_code == 422
    assert missing.json()["type"].endswith("/invalid-slack-configuration")


@pytest.mark.anyio
async def test_test_uses_unsaved_values_without_persisting_them(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(router) as (_, client):
        _ = await client.put(
            "/api/settings/slack",
            json={"enabled": False, "channel_id": CHANNEL, "bot_token": TOKEN},
        )
        with patch(
            "anomaly_backend.routes.slack_settings.SlackClient",
            RecordingSlackClient,
        ):
            response = await client.post(
                "/api/settings/slack/test",
                json={"channel_id": "C9999999999", "bot_token": REPLACEMENT},
            )
        after = await client.get("/api/settings/slack")

    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert response.json()["sent_at"].endswith("Z")
    token, channel, message = RecordingSlackClient.messages[0]
    assert (token, channel) == (REPLACEMENT, "C9999999999")
    assert "Slack integration test" in message
    assert message.endswith("Z")
    assert after.json()["channel_id"] == CHANNEL


@pytest.mark.anyio
async def test_test_reuses_the_stored_token_when_the_form_omits_it(
    client_factory: ClientFactory,
) -> None:
    async with client_factory(router) as (_, client):
        _ = await client.put(
            "/api/settings/slack",
            json={"enabled": False, "channel_id": CHANNEL, "bot_token": TOKEN},
        )
        with patch(
            "anomaly_backend.routes.slack_settings.SlackClient",
            RecordingSlackClient,
        ):
            response = await client.post(
                "/api/settings/slack/test",
                json={"channel_id": "C9999999999"},
            )

    assert response.status_code == 200
    assert RecordingSlackClient.messages[0][:2] == (TOKEN, "C9999999999")


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("error", "status", "slug"),
    [
        (
            SlackConfigurationError("Slack rejected the bot credentials"),
            422,
            "invalid-slack-configuration",
        ),
        (SlackRateLimitError(23), 429, "slack-rate-limited"),
        (SlackTransientError("outage"), 503, "service-unavailable"),
    ],
)
async def test_test_maps_slack_failures_without_exposing_credentials(
    client_factory: ClientFactory,
    error: Exception,
    status: int,
    slug: str,
) -> None:
    RecordingSlackClient.error = error
    async with client_factory(router) as (_, client):
        with patch(
            "anomaly_backend.routes.slack_settings.SlackClient",
            RecordingSlackClient,
        ):
            response = await client.post(
                "/api/settings/slack/test",
                json={"channel_id": CHANNEL, "bot_token": TOKEN},
            )

    assert response.status_code == status
    assert response.json()["type"].endswith(f"/{slug}")
    assert TOKEN not in response.text
    if status == 429:
        assert response.headers["retry-after"] == "23"


@pytest.mark.anyio
async def test_notifier_reloads_settings_and_disabled_cycles_do_not_enqueue() -> None:
    engine = create_database_engine(Settings.from_environ())
    enqueue = AsyncMock(return_value=0)
    claim = AsyncMock(return_value=[])
    try:
        with (
            patch("anomaly_worker.notifier_service.enqueue_missing", enqueue),
            patch("anomaly_worker.notifier_service.claim_pending", claim),
        ):
            assert await deliver_once(engine, Settings.from_environ()) == 0
            enqueue.assert_not_awaited()
            claim.assert_not_awaited()

            async with engine.connect() as connection:
                _ = await connection.execute(
                    tables.slack_settings.update().values(
                        enabled=True, bot_token=TOKEN, channel_id=CHANNEL
                    )
                )
                await connection.commit()

            assert await deliver_once(engine, Settings.from_environ()) == 0
            enqueue.assert_awaited_once()
            claim.assert_awaited_once()
    finally:
        await engine.dispose()
