"""Slack file upload for alert notifications.

Incoming webhooks accept a message payload only and cannot carry a file, so attaching
a rendered chart requires a bot token and the three-step external upload:

1. ``files.getUploadURLExternal`` reserves a URL and a file id
2. the bytes are POSTed to that URL
3. ``files.completeUploadExternal`` shares the finished files into a channel

Completing several files in one call produces a single message carrying all of them,
which is why both charts arrive together rather than as two notifications.
"""

from dataclasses import dataclass

import httpx


_API = "https://slack.com/api"
_TIMEOUT = httpx.Timeout(15.0)


@dataclass(frozen=True, slots=True)
class Attachment:
    filename: str
    title: str
    content: bytes


class SlackError(RuntimeError):
    """A Slack call failed.

    The message carries the HTTP status and Slack's own error code only. The bot
    token must never reach a log line, an exception, or the outbox's last_error.
    """


def _require_ok(payload: object, step: str) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise SlackError(f"{step}: response was not a JSON object")
    if payload.get("ok") is not True:
        raise SlackError(f"{step}: {payload.get('error', 'unknown_error')}")
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

    async def _reserve(self, attachment: Attachment) -> tuple[str, str]:
        response = await self._http.post(
            f"{_API}/files.getUploadURLExternal",
            headers=self._authorization(),
            data={
                "filename": attachment.filename,
                "length": str(len(attachment.content)),
            },
        )
        if response.status_code >= 400:
            raise SlackError(f"getUploadURLExternal: HTTP {response.status_code}")
        payload = _require_ok(response.json(), "getUploadURLExternal")
        upload_url = payload.get("upload_url")
        file_id = payload.get("file_id")
        if not isinstance(upload_url, str) or not isinstance(file_id, str):
            raise SlackError("getUploadURLExternal: response missing upload_url or file_id")
        return upload_url, file_id

    async def _put_bytes(self, upload_url: str, attachment: Attachment) -> None:
        # The upload URL is pre-authorised; sending the bot token here would leak it
        # to a host that does not need it.
        response = await self._http.post(
            upload_url,
            content=attachment.content,
            headers={"Content-Type": "application/octet-stream"},
        )
        if response.status_code >= 400:
            raise SlackError(f"file upload: HTTP {response.status_code}")

    async def post_charts(
        self,
        *,
        channel_id: str,
        initial_comment: str,
        attachments: list[Attachment],
    ) -> None:
        """Upload every attachment and share them as one message."""
        if not attachments:
            raise SlackError("nothing to upload")

        files: list[dict[str, str]] = []
        for attachment in attachments:
            upload_url, file_id = await self._reserve(attachment)
            await self._put_bytes(upload_url, attachment)
            files.append({"id": file_id, "title": attachment.title})

        response = await self._http.post(
            f"{_API}/files.completeUploadExternal",
            headers={**self._authorization(), "Content-Type": "application/json"},
            json={
                "files": files,
                "channel_id": channel_id,
                "initial_comment": initial_comment,
            },
        )
        if response.status_code >= 400:
            raise SlackError(f"completeUploadExternal: HTTP {response.status_code}")
        _ = _require_ok(response.json(), "completeUploadExternal")
