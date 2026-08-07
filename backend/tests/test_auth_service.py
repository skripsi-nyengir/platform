from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.auth import (
    ActiveSession,
    AuthenticatedUser,
    LockedOut,
    authenticate,
    create_session,
    lookup_session,
    revoke_session,
    session_digest,
    upsert_user,
)
from anomaly_backend.config import Settings
from anomaly_backend.db import create_database_engine


NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)
PASSWORD = "operator-password"
LOCKOUT_POLICY = {"max_failed_attempts": 3, "lockout_seconds": 900}


@pytest.fixture
async def connection() -> AsyncGenerator[AsyncConnection]:
    engine = create_database_engine(Settings.from_environ())
    try:
        async with engine.connect() as active:
            # Scoped to this module's account: the shared conftest test operator owns
            # the session cookie every other test file depends on.
            _ = await active.execute(
                delete(tables.users).where(tables.users.c.username == "operator")
            )
            await active.commit()
            yield active
            # Scoped to this module's account: the shared conftest test operator owns
            # the session cookie every other test file depends on.
            _ = await active.execute(
                delete(tables.users).where(tables.users.c.username == "operator")
            )
            await active.commit()
    finally:
        await engine.dispose()


async def _stored_sessions(connection: AsyncConnection, user_id: str) -> list[str]:
    rows = await connection.scalars(
        select(tables.user_sessions.c.session_id).where(
            tables.user_sessions.c.user_id == user_id
        )
    )
    return list(rows)


async def _seed_operator(connection: AsyncConnection) -> str:
    user_id, _ = await upsert_user(
        connection, "operator", PASSWORD, "Operator", now=NOW
    )
    return user_id


@pytest.mark.anyio
async def test_upsert_creates_then_resets_without_duplicating(
    connection: AsyncConnection,
) -> None:
    user_id = await _seed_operator(connection)
    again, created = await upsert_user(
        connection, "operator", "a-different-password", "Renamed", now=NOW
    )

    assert (again, created) == (user_id, False)
    assert (
        await connection.scalar(
            select(tables.users.c.display_name).where(
                tables.users.c.user_id == user_id
            )
        )
        == "Renamed"
    )
    assert not await authenticate(
        connection, "operator", PASSWORD, now=NOW, **LOCKOUT_POLICY
    )
    assert isinstance(
        await authenticate(
            connection, "operator", "a-different-password", now=NOW, **LOCKOUT_POLICY
        ),
        AuthenticatedUser,
    )


@pytest.mark.anyio
async def test_resetting_a_password_revokes_that_account_sessions(
    connection: AsyncConnection,
) -> None:
    user_id = await _seed_operator(connection)
    token, _ = await create_session(connection, user_id, ttl_seconds=3600, now=NOW)

    _ = await upsert_user(connection, "operator", "brand-new-password", "Op", now=NOW)

    assert await lookup_session(connection, token, now=NOW) is None


@pytest.mark.anyio
async def test_authenticate_accepts_the_right_password(
    connection: AsyncConnection,
) -> None:
    user_id = await _seed_operator(connection)

    result = await authenticate(
        connection, "operator", PASSWORD, now=NOW, **LOCKOUT_POLICY
    )

    assert result == AuthenticatedUser(
        user_id=user_id, username="operator", display_name="Operator"
    )


@pytest.mark.anyio
async def test_unknown_username_and_wrong_password_are_both_plain_none(
    connection: AsyncConnection,
) -> None:
    _ = await _seed_operator(connection)

    assert (
        await authenticate(connection, "operator", "wrong", now=NOW, **LOCKOUT_POLICY)
        is None
    )
    assert (
        await authenticate(connection, "ghost", PASSWORD, now=NOW, **LOCKOUT_POLICY)
        is None
    )


@pytest.mark.anyio
async def test_an_unknown_username_is_never_locked_out(
    connection: AsyncConnection,
) -> None:
    # Lockout state only exists for real rows. Documented as an accepted limitation:
    # a 429 therefore reveals that a username is registered.
    for _ in range(5):
        result = await authenticate(
            connection, "ghost", "wrong", now=NOW, **LOCKOUT_POLICY
        )
        assert result is None


@pytest.mark.anyio
async def test_repeated_failures_lock_the_account_then_release_it(
    connection: AsyncConnection,
) -> None:
    _ = await _seed_operator(connection)

    for _ in range(2):
        assert (
            await authenticate(
                connection, "operator", "wrong", now=NOW, **LOCKOUT_POLICY
            )
            is None
        )

    # The attempt that exhausts the budget reports the lock itself.
    third = await authenticate(
        connection, "operator", "wrong", now=NOW, **LOCKOUT_POLICY
    )
    assert third == LockedOut(retry_after_seconds=900)

    # The right password is still refused while the window is open.
    during = await authenticate(
        connection, "operator", PASSWORD, now=NOW + timedelta(seconds=60), **LOCKOUT_POLICY
    )
    assert during == LockedOut(retry_after_seconds=840)

    after = await authenticate(
        connection,
        "operator",
        PASSWORD,
        now=NOW + timedelta(seconds=901),
        **LOCKOUT_POLICY,
    )
    assert isinstance(after, AuthenticatedUser)


@pytest.mark.anyio
async def test_a_successful_login_clears_earlier_failures(
    connection: AsyncConnection,
) -> None:
    _ = await _seed_operator(connection)
    _ = await authenticate(connection, "operator", "wrong", now=NOW, **LOCKOUT_POLICY)
    _ = await authenticate(connection, "operator", PASSWORD, now=NOW, **LOCKOUT_POLICY)

    # Two fresh failures must not trip a lock that a stale counter would have reached.
    for _ in range(2):
        assert (
            await authenticate(
                connection, "operator", "wrong", now=NOW, **LOCKOUT_POLICY
            )
            is None
        )


@pytest.mark.anyio
async def test_sessions_store_a_digest_rather_than_the_token(
    connection: AsyncConnection,
) -> None:
    user_id = await _seed_operator(connection)
    token, expires_at = await create_session(
        connection, user_id, ttl_seconds=3600, now=NOW
    )

    stored = await _stored_sessions(connection, user_id)

    assert expires_at == NOW + timedelta(seconds=3600)
    assert stored == [session_digest(token)]
    assert token not in stored


@pytest.mark.anyio
async def test_lookup_returns_the_user_until_the_session_expires(
    connection: AsyncConnection,
) -> None:
    user_id = await _seed_operator(connection)
    token, expires_at = await create_session(
        connection, user_id, ttl_seconds=3600, now=NOW
    )

    active = await lookup_session(connection, token, now=NOW + timedelta(seconds=3599))
    assert active == ActiveSession(
        user=AuthenticatedUser(
            user_id=user_id, username="operator", display_name="Operator"
        ),
        expires_at=expires_at,
    )

    assert await lookup_session(connection, token, now=expires_at) is None
    assert await lookup_session(connection, "not-a-token", now=NOW) is None


@pytest.mark.anyio
async def test_revoking_a_session_makes_its_token_useless(
    connection: AsyncConnection,
) -> None:
    user_id = await _seed_operator(connection)
    token, _ = await create_session(connection, user_id, ttl_seconds=3600, now=NOW)

    await revoke_session(connection, token)

    assert await lookup_session(connection, token, now=NOW) is None
    # Revoking an already-revoked token is harmless, which keeps logout idempotent.
    await revoke_session(connection, token)


@pytest.mark.anyio
async def test_a_new_login_collects_expired_sessions(
    connection: AsyncConnection,
) -> None:
    user_id = await _seed_operator(connection)
    stale, _ = await create_session(connection, user_id, ttl_seconds=60, now=NOW)

    later = NOW + timedelta(seconds=120)
    fresh, _ = await create_session(connection, user_id, ttl_seconds=3600, now=later)

    stored = await _stored_sessions(connection, user_id)
    assert stored == [session_digest(fresh)]
    assert session_digest(stale) not in stored
