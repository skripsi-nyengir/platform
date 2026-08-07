"""Credential checks, failed-attempt lockout, and session lifecycle."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import math
import secrets
from uuid import uuid4

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend import tables
from anomaly_backend.passwords import DUMMY_HASH, hash_password, verify_password


_TOKEN_BYTES = 32

SESSION_COOKIE = "adp_session"


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: str
    username: str
    display_name: str


@dataclass(frozen=True, slots=True)
class ActiveSession:
    user: AuthenticatedUser
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class LockedOut:
    retry_after_seconds: int


def session_digest(token: str) -> str:
    """Derive the stored session identifier from a cookie token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def current_instant() -> datetime:
    return datetime.now(timezone.utc)


async def authenticate(
    connection: AsyncConnection,
    username: str,
    password: str,
    *,
    max_failed_attempts: int,
    lockout_seconds: int,
    now: datetime,
) -> AuthenticatedUser | LockedOut | None:
    """Check credentials and maintain lockout state.

    Returns the user on success, ``LockedOut`` while the account is locked, and
    ``None`` for any credential failure. An unknown username and a wrong password are
    indistinguishable to the caller.
    """
    record = (
        (
            await connection.execute(
                select(
                    tables.users.c.user_id,
                    tables.users.c.username,
                    tables.users.c.display_name,
                    tables.users.c.password_hash,
                    tables.users.c.failed_attempts,
                    tables.users.c.locked_until,
                )
                .where(tables.users.c.username == username)
                .with_for_update()
            )
        )
        .mappings()
        .one_or_none()
    )
    if record is None:
        # Spend the same work as a real verification so a missing account cannot be
        # identified by how quickly the request comes back.
        _ = verify_password(password, DUMMY_HASH)
        await connection.rollback()
        return None

    locked_until = record["locked_until"]
    if locked_until is not None and locked_until > now:
        # Release the row lock without writing; a locked account must not have its
        # window extended by further attempts.
        await connection.rollback()
        remaining = (locked_until - now).total_seconds()
        return LockedOut(retry_after_seconds=max(1, math.ceil(remaining)))

    if not verify_password(password, record["password_hash"]):
        attempts = record["failed_attempts"] + 1
        exhausted = attempts >= max_failed_attempts
        # The counter resets as the lock is set, so the account gets a full budget
        # again once the window passes.
        _ = await connection.execute(
            update(tables.users)
            .where(tables.users.c.user_id == record["user_id"])
            .values(
                failed_attempts=0 if exhausted else attempts,
                locked_until=(
                    now + timedelta(seconds=lockout_seconds) if exhausted else None
                ),
            )
        )
        await connection.commit()
        # Report the lock on the attempt that causes it rather than the one after, so
        # the caller learns why it is being refused.
        return LockedOut(retry_after_seconds=lockout_seconds) if exhausted else None

    _ = await connection.execute(
        update(tables.users)
        .where(tables.users.c.user_id == record["user_id"])
        .values(failed_attempts=0, locked_until=None)
    )
    await connection.commit()
    return AuthenticatedUser(
        user_id=record["user_id"],
        username=record["username"],
        display_name=record["display_name"],
    )


async def create_session(
    connection: AsyncConnection,
    user_id: str,
    *,
    ttl_seconds: int,
    now: datetime,
) -> tuple[str, datetime]:
    """Issue a session and return its cookie token with the absolute expiry.

    Expired rows are collected here rather than by a scheduled job: every successful
    login is already a write, so the cleanup costs nothing extra.
    """
    expires_at = now + timedelta(seconds=ttl_seconds)
    token = secrets.token_urlsafe(_TOKEN_BYTES)
    _ = await connection.execute(
        delete(tables.user_sessions).where(tables.user_sessions.c.expires_at <= now)
    )
    _ = await connection.execute(
        insert(tables.user_sessions).values(
            session_id=session_digest(token),
            user_id=user_id,
            created_at=now,
            expires_at=expires_at,
        )
    )
    await connection.commit()
    return token, expires_at


async def lookup_session(
    connection: AsyncConnection,
    token: str,
    *,
    now: datetime,
) -> ActiveSession | None:
    record = (
        (
            await connection.execute(
                select(
                    tables.users.c.user_id,
                    tables.users.c.username,
                    tables.users.c.display_name,
                    tables.user_sessions.c.expires_at,
                )
                .select_from(
                    tables.user_sessions.join(
                        tables.users,
                        tables.user_sessions.c.user_id == tables.users.c.user_id,
                    )
                )
                .where(
                    tables.user_sessions.c.session_id == session_digest(token),
                    tables.user_sessions.c.expires_at > now,
                )
            )
        )
        .mappings()
        .one_or_none()
    )
    if record is None:
        return None
    return ActiveSession(
        user=AuthenticatedUser(
            user_id=record["user_id"],
            username=record["username"],
            display_name=record["display_name"],
        ),
        expires_at=record["expires_at"],
    )


async def revoke_session(connection: AsyncConnection, token: str) -> None:
    _ = await connection.execute(
        delete(tables.user_sessions).where(
            tables.user_sessions.c.session_id == session_digest(token)
        )
    )
    await connection.commit()


async def upsert_user(
    connection: AsyncConnection,
    username: str,
    password: str,
    display_name: str,
    *,
    now: datetime,
) -> tuple[str, bool]:
    """Create ``username`` or reset its password.

    Returns the user id and whether the account was newly created. Resetting a
    password also clears lockout state, which is what makes this the recovery path for
    an operator who locked themselves out.
    """
    existing = await connection.scalar(
        select(tables.users.c.user_id).where(tables.users.c.username == username)
    )
    password_hash = hash_password(password)
    if existing is not None:
        _ = await connection.execute(
            update(tables.users)
            .where(tables.users.c.user_id == existing)
            .values(
                password_hash=password_hash,
                display_name=display_name,
                failed_attempts=0,
                locked_until=None,
            )
        )
        _ = await connection.execute(
            delete(tables.user_sessions).where(
                tables.user_sessions.c.user_id == existing
            )
        )
        await connection.commit()
        return str(existing), False

    user_id = uuid4().hex
    _ = await connection.execute(
        insert(tables.users).values(
            user_id=user_id,
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            failed_attempts=0,
            locked_until=None,
            created_at=now,
        )
    )
    await connection.commit()
    return user_id, True
