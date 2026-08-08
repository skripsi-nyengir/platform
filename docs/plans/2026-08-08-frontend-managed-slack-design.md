# Frontend-Managed Slack Notifications

## Goal

Move the Slack bot integration from deployment environment variables into an
authenticated settings page. A signed-in operator can configure the bot token,
channel, and enabled state, send a real test message with the current unsaved form
values, and apply changes without restarting the notifier.

## Architecture

PostgreSQL owns one Slack settings record. It stores the enabled flag, channel ID,
plaintext bot token, update timestamp, and updating user. The token is plaintext by
explicit product choice, but remains server-only: API responses, logs, validation
errors, and the browser never receive a stored token.

The authenticated API exposes read, update, and test operations under
`/api/settings/slack`. Omitting the token during an update preserves it, supplying a
string replaces it, and supplying `null` clears it. A test request accepts the
current channel and an optional candidate token; an omitted candidate reuses the
stored token. Tests call Slack directly and never persist or enable the form values.

The notifier continues to upload the two existing alert charts with the bot token.
It reads a fresh database settings snapshot at the start of each polling cycle, so
disable, channel, and credential changes take effect without a process restart.
Polling, lease, retry, chart-margin, and episode-age tuning remain operational
environment settings.

## Frontend Behavior

`/settings/slack` is available to every authenticated user. The page shows the
enabled state, channel ID, whether a token is configured, and update metadata. The
password field is always empty; leaving it empty preserves the stored token. A
separate clear action removes the token and requires notifications to be disabled.

“Send test notification” uses the current unsaved channel and token. If the token
field is empty and a stored token exists, the request reuses it. Success and safe,
actionable failures render inline. A successful test neither saves nor enables the
integration, and enabling is not gated on a prior test.

## Slack and Deployment

Normal chart alerts retain the `files:write` scope. The text-only test uses
`chat.postMessage`, requiring `chat:write`; the bot must be invited to the selected
channel. Production deployment starts the notifier as a persistent service.
Slack-specific environment variables are removed, while the notifier's operational
tuning remains in `.env`.

## Verification

Backend coverage proves persistence semantics, authentication, redaction, Slack
error handling, per-cycle reload, and unchanged chart delivery. Frontend coverage
proves masked loading, preserve/replace/clear behavior, unsaved tests, safe errors,
and route/navigation integration. Deployment checks prove Slack secrets are absent
from Compose and `.env.example`, and that production start/stop includes the
notifier.
