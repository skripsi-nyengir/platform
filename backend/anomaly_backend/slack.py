"""Shared Slack transport for settings tests and alert-chart delivery."""

from dataclasses import dataclass

import httpx


_API = "https://slack.com/api"
_TIMEOUT = httpx.Timeout(15.0)
_CREDENTIAL_ERRORS = frozenset(
    {"invalid_auth", "not_authed", "account_inactive", "token_revoked"}
)
_CHANNEL_ERRORS = frozenset(
    {
        "channel_not_found",
        "not_in_channel",
        "is_archived",
        "restricted_action",
        "no_permission",
    }
)


@dataclass(frozen=True, slots=True)
class Attachment:
    filename: str
    title: str
    content: bytes


class SlackError(RuntimeError):
    """A safe-to-log Slack failure that never contains the bot token."""


class SlackConfigurationError(SlackError):
    """Credentials, permissions, or channel configuration were rejected."""


class SlackRateLimitError(SlackError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Slack rate limit exceeded")
        self.retry_after_seconds = retry_after_seconds


class SlackTransientError(SlackError):
    """Slack or the network is temporarily unavailable."""


def _configuration_message(code: str) -> str | None:
    if code in _CREDENTIAL_ERRORS:
        return "Slack rejected the bot credentials"
    if code == "missing_scope":
        return "The Slack bot is missing a required permission"
    if code in _CHANNEL_ERRORS:
        return "The Slack bot cannot post to that channel"
    return None


def _require_ok(payload: object, step: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise SlackTransientError(f"{step}: invalid response")
    if payload.get("ok") is not True:
        code = str(payload.get("error", "unknown_error"))
        if message := _configuration_message(code):
            raise SlackConfigurationError(message)
        raise SlackError(f"{step}: Slack rejected the request ({code})")
    return payload


class SlackClient:
    def __init__(self, token: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._token = token
        self._client = client
        self._owns_client = client is None

    async def __aenter__(self) -> "SlackClient":
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_TIMEOUT)
        return self

    async def __aexit__(self, *_exception: object) -> None:
        if self._owns_client and self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise SlackError("client used outside its context manager")
        return self._client

    def _authorization(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    @staticmethod
    def _raise_http_failure(response: httpx.Response, step: str) -> None:
        if response.status_code == 429:
            raw = response.headers.get("Retry-After", "1")
            try:
                retry_after = max(1, int(raw))
            except ValueError:
                retry_after = 1
            raise SlackRateLimitError(retry_after)
        if response.status_code >= 500:
            raise SlackTransientError(f"{step}: Slack is temporarily unavailable")
        if response.status_code >= 400:
            raise SlackConfigurationError("Slack rejected the request configuration")

    async def _post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        data: dict[str, str] | None = None,
        json: dict[str, object] | None = None,
        content: bytes | None = None,
    ) -> httpx.Response:
        try:
            return await self._http.post(
                url, headers=headers, data=data, json=json, content=content
            )
        except httpx.RequestError as error:
            raise SlackTransientError("Slack is temporarily unavailable") from error

    @staticmethod
    def _json(response: httpx.Response, step: str) -> object:
        try:
            return response.json()
        except ValueError as error:
            raise SlackTransientError(f"{step}: invalid response") from error

    async def post_message(self, *, channel_id: str, text: str) -> None:
        response = await self._post(
            f"{_API}/chat.postMessage",
            headers={**self._authorization(), "Content-Type": "application/json"},
            json={"channel": channel_id, "text": text},
        )
        self._raise_http_failure(response, "chat.postMessage")
        _ = _require_ok(self._json(response, "chat.postMessage"), "chat.postMessage")

    async def _reserve(self, attachment: Attachment) -> tuple[str, str]:
        response = await self._post(
            f"{_API}/files.getUploadURLExternal",
            headers=self._authorization(),
            data={"filename": attachment.filename, "length": str(len(attachment.content))},
        )
        self._raise_http_failure(response, "getUploadURLExternal")
        payload = _require_ok(
            self._json(response, "getUploadURLExternal"), "getUploadURLExternal"
        )
        upload_url = payload.get("upload_url")
        file_id = payload.get("file_id")
        if not isinstance(upload_url, str) or not isinstance(file_id, str):
            raise SlackTransientError(
                "getUploadURLExternal: response missing upload_url or file_id"
            )
        return upload_url, file_id

    async def _put_bytes(self, upload_url: str, attachment: Attachment) -> None:
        response = await self._post(
            upload_url,
            content=attachment.content,
            headers={"Content-Type": "application/octet-stream"},
        )
        self._raise_http_failure(response, "file upload")

    async def post_charts(
        self,
        *,
        channel_id: str,
        initial_comment: str,
        attachments: list[Attachment],
    ) -> None:
        if not attachments:
            raise SlackError("nothing to upload")
        files: list[dict[str, str]] = []
        for attachment in attachments:
            upload_url, file_id = await self._reserve(attachment)
            await self._put_bytes(upload_url, attachment)
            files.append({"id": file_id, "title": attachment.title})
        response = await self._post(
            f"{_API}/files.completeUploadExternal",
            headers={**self._authorization(), "Content-Type": "application/json"},
            json={
                "files": files,
                "channel_id": channel_id,
                "initial_comment": initial_comment,
            },
        )
        self._raise_http_failure(response, "completeUploadExternal")
        _ = _require_ok(
            self._json(response, "completeUploadExternal"),
            "completeUploadExternal",
        )
