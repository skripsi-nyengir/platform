from collections.abc import Iterable
from typing import cast
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_core import ErrorDetails
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from anomaly_backend.contracts import ProblemDetails


class ProblemException(Exception):
    status: int = 500
    title: str = "Request failed"
    slug: str = "request-failed"

    def __init__(
        self,
        detail: str,
        errors: dict[str, list[str]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail: str = detail
        self.errors: dict[str, list[str]] | None = errors
        self.headers: dict[str, str] | None = headers


class InvalidQuery(ProblemException):
    status: int = 422
    title: str = "Invalid query"
    slug: str = "invalid-query"


class Unauthenticated(ProblemException):
    status: int = 401
    title: str = "Authentication required"
    slug: str = "unauthenticated"


class TooManyAttempts(ProblemException):
    status: int = 429
    title: str = "Too many attempts"
    slug: str = "too-many-attempts"


class InvalidSlackConfiguration(ProblemException):
    status: int = 422
    title: str = "Invalid Slack configuration"
    slug: str = "invalid-slack-configuration"


class SlackRateLimited(ProblemException):
    status: int = 429
    title: str = "Slack rate limit exceeded"
    slug: str = "slack-rate-limited"


class NotFound(ProblemException):
    status: int = 404
    title: str = "Not found"
    slug: str = "not-found"


class Conflict(ProblemException):
    status: int = 409
    title: str = "Conflict"
    slug: str = "conflict"


class DependencyFailure(Exception):
    pass


def new_request_id() -> str:
    return uuid4().hex


def _validation_errors(errors: Iterable[ErrorDetails]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for error in errors:
        location = error.get("loc", ())
        if location and location[0] in {"body", "query", "path", "header", "cookie"}:
            location = location[1:]
        key = ".".join(str(part) for part in location) or "request"
        grouped.setdefault(key, []).append(error.get("msg", "Invalid value"))
    return grouped


def problem_response(
    request: Request,
    *,
    status: int,
    title: str,
    slug: str,
    detail: str,
    errors: dict[str, list[str]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build an RFC7807 response.

    Public because middleware runs outside the exception handlers installed below and
    would otherwise have to invent a second error shape.
    """
    fields: dict[str, object] = {
        "type": f"https://example.invalid/problems/{slug}",
        "title": title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "request_id": new_request_id(),
    }
    if errors is not None:
        fields["errors"] = errors
    payload = ProblemDetails.model_validate(fields, strict=True)
    return JSONResponse(
        status_code=status,
        content=payload.model_dump(mode="json"),
        media_type="application/problem+json",
        headers=headers,
    )


async def _request_validation_handler(
    request: Request, exception: RequestValidationError
) -> JSONResponse:
    errors = cast(list[ErrorDetails], exception.errors())
    body_error = request.method in {"POST", "PUT", "PATCH", "DELETE"} and any(
        error.get("loc", (None,))[0] == "body" for error in errors
    )
    contract_body_error = (
        request.url.path == "/api/eda/compute"
        or (
            request.url.path == "/api/replay-jobs"
            and any(error.get("type") == "value_error" for error in errors)
        )
    )
    return problem_response(
        request,
        status=400 if body_error and not contract_body_error else 422,
        title=(
            "Invalid request body"
            if body_error and not contract_body_error
            else "Invalid query"
        ),
        slug=(
            "invalid-body"
            if body_error and not contract_body_error
            else "invalid-query"
        ),
        detail=(
            "Request body failed validation"
            if body_error and not contract_body_error
            else "Request parameters failed validation"
        ),
        errors=_validation_errors(errors),
    )


async def _domain_problem_handler(
    request: Request, exception: ProblemException
) -> JSONResponse:
    return problem_response(
        request,
        status=exception.status,
        title=exception.title,
        slug=exception.slug,
        detail=exception.detail,
        errors=exception.errors,
        headers=exception.headers,
    )


async def _http_problem_handler(
    request: Request, exception: StarletteHTTPException
) -> JSONResponse:
    return problem_response(
        request,
        status=exception.status_code,
        title={404: "Not found", 405: "Method not allowed"}.get(
            exception.status_code, "HTTP error"
        ),
        slug={404: "not-found", 405: "method-not-allowed"}.get(
            exception.status_code, "http-error"
        ),
        detail=str(exception.detail),
    )


async def _unavailable_handler(
    request: Request, exception: Exception
) -> JSONResponse:
    _ = exception
    return problem_response(
        request,
        status=503,
        title="Service unavailable",
        slug="service-unavailable",
        detail="The service is temporarily unavailable",
    )


def install_problem_handlers(app: FastAPI) -> None:
    _ = app.exception_handler(RequestValidationError)(_request_validation_handler)
    _ = app.exception_handler(ProblemException)(_domain_problem_handler)
    _ = app.exception_handler(StarletteHTTPException)(_http_problem_handler)
    _ = app.exception_handler(SQLAlchemyError)(_unavailable_handler)
    _ = app.exception_handler(DependencyFailure)(_unavailable_handler)
