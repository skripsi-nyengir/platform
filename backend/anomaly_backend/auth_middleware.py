"""Fail-closed session enforcement for every request.

Enforcement lives in middleware rather than a per-router dependency so that a route
added later is protected by default. A forgotten ``Depends`` would expose an endpoint
with nothing failing to signal it; a forgotten allowlist entry merely refuses traffic,
which is the safe direction to be wrong in.
"""

from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI, Request, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from anomaly_backend.auth import SESSION_COOKIE, current_instant, lookup_session
from anomaly_backend.problems import problem_response


# Reachable without a session. Health and readiness serve Traefik and Docker, which
# have no credentials; login has to be reachable to obtain one; logout is harmless and
# stays usable when a session has already lapsed.
OPEN_ROUTES = frozenset(
    {
        ("GET", "/health"),
        ("GET", "/ready"),
        ("POST", "/api/auth/login"),
        ("POST", "/api/auth/logout"),
    }
)


def install_session_guard(app: FastAPI) -> None:
    @app.middleware("http")
    async def enforce_session(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if (request.method, request.url.path) in OPEN_ROUTES:
            return await call_next(request)

        token = request.cookies.get(SESSION_COOKIE)
        if token is None:
            return _unauthenticated(request)

        engine = cast(AsyncEngine, request.app.state.engine)
        try:
            async with engine.connect() as connection:
                session = await lookup_session(
                    connection, token, now=current_instant()
                )
        except SQLAlchemyError:
            # Exceptions raised here never reach install_problem_handlers, so a
            # database outage has to be answered explicitly. Answering 503 rather than
            # continuing keeps the guard closed when it cannot verify anything.
            return problem_response(
                request,
                status=503,
                title="Service unavailable",
                slug="service-unavailable",
                detail="The service is temporarily unavailable",
            )

        if session is None:
            return _unauthenticated(request)

        request.state.session = session
        request.state.user = session.user
        return await call_next(request)

    _ = enforce_session


def _unauthenticated(request: Request) -> Response:
    return problem_response(
        request,
        status=401,
        title="Authentication required",
        slug="unauthenticated",
        detail="Authentication is required",
    )
