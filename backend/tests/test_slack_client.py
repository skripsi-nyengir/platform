from typing import Any

import httpx
import pytest

from anomaly_backend.slack import (
    Attachment,
    SlackClient,
    SlackConfigurationError,
    SlackError,
    SlackRateLimitError,
    SlackTransientError,
)


TOKEN = "xoxb-super-secret-value"
CHANNEL = "C0123456789"
CHART = Attachment(filename="score.png", title="Score", content=b"\x89PNG-score")
TELEMETRY = Attachment(filename="telemetry.png", title="Telemetry", content=b"\x89PNG-t")


class Recorder:
    """Captures every request so the call sequence itself can be asserted."""

    def __init__(self, responses: dict[str, httpx.Response] | None = None) -> None:
        self.requests: list[httpx.Request] = []
        self.responses = responses or {}

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for fragment, response in self.responses.items():
            if fragment in str(request.url):
                return response
        if "getUploadURLExternal" in str(request.url):
            index = sum(
                1 for item in self.requests if "getUploadURLExternal" in str(item.url)
            )
            return httpx.Response(
                200,
                json={
                    "ok": True,
                    "upload_url": f"https://files.slack.invalid/upload/{index}",
                    "file_id": f"F{index}",
                },
            )
        if "files.slack.invalid" in str(request.url):
            return httpx.Response(200, text="OK")
        if "completeUploadExternal" in str(request.url):
            return httpx.Response(200, json={"ok": True, "files": []})
        if "chat.postMessage" in str(request.url):
            return httpx.Response(200, json={"ok": True, "ts": "1.0"})
        raise AssertionError(f"unexpected request to {request.url}")

    @property
    def paths(self) -> list[str]:
        return [str(request.url) for request in self.requests]

    def body(self, index: int) -> Any:
        import json

        return json.loads(self.requests[index].content)


def _client(recorder: Recorder) -> SlackClient:
    transport = httpx.MockTransport(recorder.handler)
    return SlackClient(TOKEN, client=httpx.AsyncClient(transport=transport))


@pytest.mark.anyio
async def test_both_charts_upload_and_share_as_one_message() -> None:
    recorder = Recorder()

    async with _client(recorder) as slack:
        await slack.post_charts(
            channel_id=CHANNEL,
            initial_comment="episode opened",
            attachments=[CHART, TELEMETRY],
        )

    # Reserve, upload, reserve, upload, then a single share for both files.
    assert [url.rsplit("/", 1)[-1] for url in recorder.paths] == [
        "files.getUploadURLExternal",
        "1",
        "files.getUploadURLExternal",
        "2",
        "files.completeUploadExternal",
    ]
    completion = recorder.body(4)
    assert completion["channel_id"] == CHANNEL
    assert completion["initial_comment"] == "episode opened"
    assert [entry["title"] for entry in completion["files"]] == ["Score", "Telemetry"]


@pytest.mark.anyio
async def test_the_reserved_length_matches_the_bytes_actually_sent() -> None:
    recorder = Recorder()

    async with _client(recorder) as slack:
        await slack.post_charts(
            channel_id=CHANNEL, initial_comment="c", attachments=[CHART]
        )

    reserve = recorder.requests[0]
    assert f"length={len(CHART.content)}".encode() in reserve.content
    assert recorder.requests[1].content == CHART.content


@pytest.mark.anyio
async def test_the_bot_token_never_reaches_the_file_host() -> None:
    recorder = Recorder()

    async with _client(recorder) as slack:
        await slack.post_charts(
            channel_id=CHANNEL, initial_comment="c", attachments=[CHART]
        )

    api_calls = [r for r in recorder.requests if "slack.com" in str(r.url)]
    upload_calls = [r for r in recorder.requests if "files.slack.invalid" in str(r.url)]
    assert all(r.headers["authorization"] == f"Bearer {TOKEN}" for r in api_calls)
    # The upload URL is already pre-authorised; sending the token would leak it.
    assert all("authorization" not in r.headers for r in upload_calls)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failing", "response"),
    [
        ("getUploadURLExternal", httpx.Response(200, json={"ok": False, "error": "invalid_auth"})),
        ("getUploadURLExternal", httpx.Response(500, text="boom")),
        ("files.slack.invalid", httpx.Response(413, text="too large")),
        ("completeUploadExternal", httpx.Response(200, json={"ok": False, "error": "channel_not_found"})),
    ],
)
async def test_a_failure_at_any_step_raises_rather_than_half_posting(
    failing: str, response: httpx.Response
) -> None:
    recorder = Recorder({failing: response})

    with pytest.raises(SlackError):
        async with _client(recorder) as slack:
            await slack.post_charts(
                channel_id=CHANNEL, initial_comment="c", attachments=[CHART, TELEMETRY]
            )


@pytest.mark.anyio
async def test_the_error_message_is_sanitized_and_omits_the_token() -> None:
    recorder = Recorder(
        {"getUploadURLExternal": httpx.Response(200, json={"ok": False, "error": "invalid_auth"})}
    )

    with pytest.raises(SlackError) as failure:
        async with _client(recorder) as slack:
            await slack.post_charts(
                channel_id=CHANNEL, initial_comment="c", attachments=[CHART]
            )

    message = str(failure.value)
    assert message == "Slack rejected the bot credentials"
    # This string is written to the outbox's last_error and to the log.
    assert TOKEN not in message


@pytest.mark.anyio
async def test_a_reservation_without_an_upload_url_is_refused() -> None:
    recorder = Recorder(
        {"getUploadURLExternal": httpx.Response(200, json={"ok": True, "file_id": "F1"})}
    )

    with pytest.raises(SlackError, match="upload_url"):
        async with _client(recorder) as slack:
            await slack.post_charts(
                channel_id=CHANNEL, initial_comment="c", attachments=[CHART]
            )


@pytest.mark.anyio
async def test_posting_nothing_is_refused() -> None:
    recorder = Recorder()

    with pytest.raises(SlackError):
        async with _client(recorder) as slack:
            await slack.post_charts(
                channel_id=CHANNEL, initial_comment="c", attachments=[]
            )


@pytest.mark.anyio
async def test_text_message_uses_chat_post_message() -> None:
    recorder = Recorder()

    async with _client(recorder) as slack:
        await slack.post_message(channel_id=CHANNEL, text="integration test")

    request = recorder.requests[0]
    assert str(request.url).endswith("/chat.postMessage")
    assert recorder.body(0) == {"channel": CHANNEL, "text": "integration test"}
    assert request.headers["authorization"] == f"Bearer {TOKEN}"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("response", "error_type"),
    [
        (
            httpx.Response(200, json={"ok": False, "error": "invalid_auth"}),
            SlackConfigurationError,
        ),
        (
            httpx.Response(200, json={"ok": False, "error": "missing_scope"}),
            SlackConfigurationError,
        ),
        (
            httpx.Response(200, json={"ok": False, "error": "not_in_channel"}),
            SlackConfigurationError,
        ),
        (
            httpx.Response(200, json={"ok": False, "error": "no_permission"}),
            SlackConfigurationError,
        ),
        (
            httpx.Response(429, headers={"Retry-After": "17"}),
            SlackRateLimitError,
        ),
        (httpx.Response(503, text="unavailable"), SlackTransientError),
    ],
)
async def test_text_message_failures_are_typed_and_sanitized(
    response: httpx.Response, error_type: type[SlackError]
) -> None:
    recorder = Recorder({"chat.postMessage": response})

    with pytest.raises(error_type) as failure:
        async with _client(recorder) as slack:
            await slack.post_message(channel_id=CHANNEL, text="test")

    assert TOKEN not in str(failure.value)
    if isinstance(failure.value, SlackRateLimitError):
        assert failure.value.retry_after_seconds == 17
