from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.auth import (
    SESSION_COOKIE,
    ActiveSession,
    LockedOut,
    authenticate,
    create_session,
    current_instant,
    revoke_session,
)
from anomaly_backend.config import Settings
from anomaly_backend.contracts import (
    LoginRequest,
    LogoutResponse,
    SessionResponse,
    format_operational_instant,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import (
    TooManyAttempts,
    Unauthenticated,
    new_request_id,
)


# Wrong password and unknown username share this wording so the response cannot be
# used to enumerate accounts.
_REJECTED = "Username or password is incorrect"

router = APIRouter(prefix="/api/auth")


def auth_settings() -> Settings:
    return Settings.from_environ()


def _set_session_cookie(
    response: Response, token: str, *, settings: Settings
) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.auth_session_ttl_seconds,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )


@router.post("/login", response_model=SessionResponse)
async def login(
    body: LoginRequest,
    response: Response,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(auth_settings)],
) -> SessionResponse:
    now = current_instant()
    outcome = await authenticate(
        connection,
        body.username,
        body.password,
        max_failed_attempts=settings.auth_max_failed_attempts,
        lockout_seconds=settings.auth_lockout_seconds,
        now=now,
    )
    if isinstance(outcome, LockedOut):
        raise TooManyAttempts(
            "Too many failed sign-in attempts; try again later",
            headers={"Retry-After": str(outcome.retry_after_seconds)},
        )
    if outcome is None:
        raise Unauthenticated(_REJECTED)

    token, expires_at = await create_session(
        connection,
        outcome.user_id,
        ttl_seconds=settings.auth_session_ttl_seconds,
        now=now,
    )
    _set_session_cookie(response, token, settings=settings)
    return SessionResponse(
        request_id=new_request_id(),
        username=outcome.username,
        display_name=outcome.display_name,
        expires_at=format_operational_instant(expires_at),
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    response: Response,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
    settings: Annotated[Settings, Depends(auth_settings)],
    adp_session: Annotated[str | None, Cookie()] = None,
) -> LogoutResponse:
    # Allowlisted and always successful: logging out twice, or with a token the server
    # has already forgotten, is not an error worth surfacing.
    if adp_session is not None:
        await revoke_session(connection, adp_session)
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="strict",
    )
    return LogoutResponse(request_id=new_request_id())


@router.get("/session", response_model=SessionResponse)
async def read_session(request: Request) -> SessionResponse:
    # The middleware has already resolved and validated the session; refusing here
    # would mean looking it up a second time.
    session = getattr(request.state, "session", None)
    if not isinstance(session, ActiveSession):
        raise Unauthenticated("Authentication is required")
    return SessionResponse(
        request_id=new_request_id(),
        username=session.user.username,
        display_name=session.user.display_name,
        expires_at=format_operational_instant(session.expires_at),
    )
