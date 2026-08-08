from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from anomaly_backend.auth import AuthenticatedUser
from anomaly_backend.contracts import (
    SlackSettingsResponse,
    SlackSettingsUpdateRequest,
    SlackTestRequest,
    SlackTestResponse,
    format_operational_instant,
)
from anomaly_backend.db import get_connection
from anomaly_backend.problems import (
    DependencyFailure,
    InvalidSlackConfiguration,
    SlackRateLimited,
    new_request_id,
)
from anomaly_backend.slack import (
    SlackClient,
    SlackConfigurationError,
    SlackError,
    SlackRateLimitError,
)
from anomaly_backend.sql.slack_settings import (
    SlackSettingsSnapshot,
    read_slack_settings,
    write_slack_settings,
)


router = APIRouter(prefix="/api/settings/slack")


def _response(settings: SlackSettingsSnapshot) -> SlackSettingsResponse:
    return SlackSettingsResponse(
        request_id=new_request_id(),
        enabled=settings.enabled,
        bot_token_configured=bool(settings.bot_token),
        channel_id=settings.channel_id,
        updated_at=format_operational_instant(settings.updated_at),
        updated_by_username=settings.updated_by_username,
    )


def _required_user(request: Request) -> AuthenticatedUser:
    user = getattr(request.state, "user", None)
    if not isinstance(user, AuthenticatedUser):
        # The session middleware guarantees this for protected routes.
        raise RuntimeError("authenticated route has no user")
    return user


def _normalise_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalised = value.strip()
    return normalised or None


@router.get("", response_model=SlackSettingsResponse)
async def get_settings(
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> SlackSettingsResponse:
    return _response(await read_slack_settings(connection))


@router.put("", response_model=SlackSettingsResponse)
async def put_settings(
    body: SlackSettingsUpdateRequest,
    request: Request,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> SlackSettingsResponse:
    current = await read_slack_settings(connection, for_update=True)
    token = (
        _normalise_optional(body.bot_token)
        if "bot_token" in body.model_fields_set
        else current.bot_token
    )
    channel_id = _normalise_optional(body.channel_id)
    if body.enabled and (token is None or channel_id is None):
        raise InvalidSlackConfiguration(
            "A bot token and channel ID are required before Slack notifications can be enabled"
        )
    user = _required_user(request)
    updated = await write_slack_settings(
        connection,
        enabled=body.enabled,
        bot_token=token,
        channel_id=channel_id,
        updated_by_user_id=user.user_id,
        updated_by_username=user.username,
    )
    return _response(updated)


@router.post("/test", response_model=SlackTestResponse)
async def test_settings(
    body: SlackTestRequest,
    connection: Annotated[AsyncConnection, Depends(get_connection)],
) -> SlackTestResponse:
    current = await read_slack_settings(connection)
    token = (
        _normalise_optional(body.bot_token)
        if "bot_token" in body.model_fields_set
        else current.bot_token
    )
    channel_id = _normalise_optional(body.channel_id)
    if token is None or channel_id is None:
        raise InvalidSlackConfiguration(
            "A bot token and channel ID are required to send a Slack test"
        )
    timestamp = datetime.now(timezone.utc).replace(microsecond=0)
    message = (
        "Slack integration test — anomaly detection platform — "
        f"{timestamp.isoformat().replace('+00:00', 'Z')}"
    )
    try:
        async with SlackClient(token) as slack:
            await slack.post_message(channel_id=channel_id, text=message)
    except SlackConfigurationError as error:
        raise InvalidSlackConfiguration(str(error)) from error
    except SlackRateLimitError as error:
        raise SlackRateLimited(
            "Slack asked the platform to retry the test later",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    except SlackError as error:
        raise DependencyFailure("Slack is temporarily unavailable") from error
    return SlackTestResponse(
        request_id=new_request_id(),
        status="sent",
        sent_at=format_operational_instant(datetime.now(timezone.utc)),
    )
