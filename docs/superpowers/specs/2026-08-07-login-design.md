# Login Authentication — Design

Date: 2026-08-07
Status: Validated, not yet implemented

## Goal

The platform runs on a public VPS (`anomaly.mytekna.io`) with **no authentication at
all**. Every `/api/*` route is open; nginx forwards straight to `api:8000`. Anyone who
knows the host can read telemetry, inference results, and alerts.

Two drivers:

1. **Close public access** — real protection over the dashboard and the API.
2. **Function completeness for the thesis defence** — authentication as a standard
   platform function that can be demonstrated and described in the manuscript.

Explicitly *not* a driver: replacing `alert_events.actor` with a relation to a user
entity. The alert flow is untouched.

Deliverable: a `/login` page, a revocable cookie session, every API route closed except
health probes, a logout action, automatic redirect on session expiry, failed-attempt
throttling — and a pre-defence manuscript that remains accurate afterwards.

## Decisions

| Aspect | Decision |
|---|---|
| Protection scope | UI + **all** `/api/*`. Only `/health`, `/ready`, and the auth endpoints stay open |
| Credentials | `users` table in PostgreSQL, populated through a CLI. **No registration endpoint** |
| Session mechanism | Opaque DB token + `HttpOnly` cookie |
| In scope | Login, logout, expiry + redirect, rate limiting |
| Out of scope | Password change UI, password reset, registration, roles/authorization |
| Rate limiting | Columns on `users`, per-username, 5 failures → 15-minute lock |
| UAT | Login is **outside** the UAT already performed; stated explicitly in the manuscript |
| New dependencies | **None.** `hashlib.scrypt`, `hmac`, `secrets` from the standard library |

### Why opaque DB sessions rather than JWT

Logout is in scope, and a stateless JWT cannot be revoked without a denylist — the
logout button would be cosmetic until the token expired on its own. That is a weak
claim to defend in the manuscript. An opaque token backed by a `user_sessions` row makes
logout a `DELETE`, needs no signing secret to manage or rotate, and costs one indexed
primary-key lookup per request.

### Why HTTP middleware rather than per-router dependencies

Middleware is *fail-closed*: any route added later is protected automatically. A
forgotten `Depends` on a new router leaks that endpoint with nothing failing to signal
it. The cost is that middleware sits outside `install_problem_handlers`, so it must
build its own RFC7807 responses and handle its own database errors.

## Architecture

### Data model

Two tables in `backend/anomaly_backend/tables.py`, following the `Text` primary-key
convention used by `devices` and `corpora`:

**`users`** — `user_id` (PK), `username` (unique), `password_hash`, `display_name`,
`failed_attempts` (default `0`), `locked_until` (nullable), `created_at`. Check
constraint `ck_users_failed_attempts_non_negative`.

**`user_sessions`** — `session_id` (PK) = **SHA-256 hex of the cookie token, not the
token itself**; `user_id` (FK → `users.user_id`, `ON DELETE CASCADE`); `created_at`;
`expires_at`. Check constraint `expires_at > created_at`, index on `expires_at`.

Storing the digest rather than the token means a database disclosure does not hand over
live sessions. Lookup stays a single primary-key hit and logout stays a `DELETE` by
primary key.

Migration `20260807_0016_user_authentication.py`, `down_revision = "20260804_0015"`.
`downgrade()` drops both tables.

`_MINIMUM_REVISION` in `routes/system.py` rises to `"20260807_0016"`; otherwise `/ready`
reports ready while the auth schema is absent. That constant is also echoed as
`minimum_database_revision` in the `/ready` payload and is pinned in 11 places across 6
test files, so the bump is an API-visible change, not an internal constant.

### Password hashing

`hashlib.scrypt` with n=2^14, r=8, p=1 and a 16-byte salt, encoded as
`scrypt$16384$8$1$<salt_b64>$<hash_b64>` so the parameters can be raised later without a
migration. Verification uses `hmac.compare_digest`. A constant `DUMMY_HASH` equalises
response time for unknown usernames.

### API surface

| Endpoint | Success | Failure |
|---|---|---|
| `POST /api/auth/login` | `200` + session payload + `Set-Cookie` | `401` bad credentials, `429` + `Retry-After` when locked |
| `POST /api/auth/logout` | `200` (idempotent) | — |
| `GET /api/auth/session` | `200` + session payload | `401` |

Every response carries a body; none return `204`. `requestJson()` in
`frontend/src/api/http.ts` always runs `schema.safeParse(body)`, and an empty body fails
that parse, which would force the shared HTTP client to grow a special case.

Cookie: `adp_session`, `HttpOnly`, `SameSite=Strict`, `Path=/`, `Max-Age` = TTL, `Secure`
driven by configuration. Lifetime is an **absolute 12 hours with no sliding renewal** —
simpler to implement and more honest to state in the manuscript.

`GET /api/auth/session` stays protected and answers `401` without a session; that
response is what drives the frontend guard. `POST /api/auth/logout` is allowlisted and
always answers `200` so repeated logout is harmless.

### Error semantics

`Unauthenticated` (401, slug `unauthenticated`) and `TooManyAttempts` (429, slug
`too-many-attempts`) join the existing `ProblemException` subclasses in `problems.py`.
The private `_problem_response` is promoted to a public `problem_response()` so the
middleware emits bodies identical in shape to every other error on the platform.

An unknown username still runs a scrypt verification against `DUMMY_HASH` and returns a
401 body identical to a wrong password.

**Accepted limitation:** lockout state exists only for accounts that exist, so a `429`
reveals that the username is registered. For a single-tenant platform this is
acceptable, and the manuscript should say so plainly rather than claim more.

Lockout: each failure increments `failed_attempts`; on reaching the configured maximum,
`locked_until` is set and the counter resets. A successful login clears both.

### Frontend flow

New files: `src/contracts/auth.ts` (Zod schemas), `src/api/auth.ts`,
`src/features/auth/useSession.ts`, `src/features/auth/RequireSession.tsx`,
`src/pages/LoginPage.tsx`, `src/app/SidebarLogoutButton.tsx`.

`http.ts` needs no change — the paths are same-origin, so the cookie is sent by default.

`/login` becomes a route sibling **outside** `AppShell`. `AppShell` is wrapped in
`RequireSession`, which renders a loading state while the session query is pending and
redirects to `/login` with the intended path in router state on `401`.

Expiry handling is centralised in `src/app/queryClient.ts`: a `QueryCache` and
`MutationCache` `onError` recognises `ApiError.status === 401` and clears the session
cache, which makes the guard redirect. `ApiError` already carries `status`, so no page
component needs to know that authentication exists.

`SidebarLogoutButton` mirrors `SidebarThemeToggle` exactly — Tooltip, `ListItemButton`,
`compact` prop — and sits below it in the sidebar footer. `LoginPage` uses the existing
`tokens` and palette, so light and dark are correct without new colour values.

### Configuration

`config.py` gains `auth_cookie_secure` (default `True`), `auth_session_ttl_seconds`
(default `43200`), `auth_max_failed_attempts` (default `5`), and `auth_lockout_seconds`
(default `900`), validated in `__post_init__` following the existing EDA worker pattern.

Accounts are created by `anomaly_backend/auth_cli.py` (`create-user`, `set-password`),
modelled on `eda_cli.py`. The password is read from **stdin**, never `argv`, so it does
not reach shell history or `ps`. There is no registration endpoint at all, which is what
keeps "login only" enforced at the API rather than merely hidden in the UI.

Expired sessions are collected opportunistically: every successful login deletes rows
whose `expires_at` has passed. No cron job or new worker.

## Testing

`backend/tests/conftest.py` builds every test app through a single `client_factory`
fixture used by 10 test files. Seeding a test user and attaching the session cookie
there keeps **all existing backend tests passing untouched**. A second factory variant
provides an unauthenticated client for the auth tests.

New backend tests cover the hash round-trip and malformed-hash rejection, cookie
attributes, identical `401` bodies for wrong password and unknown username, lockout and
recovery, expired-session rejection, logout revoking the session, `/health` and `/ready`
staying open, and a database failure producing `503` rather than passing the request
through.

One test carries most of the weight: **walk `app.routes` and assert every path outside
the allowlist rejects an unauthenticated request.** That is what preserves the
fail-closed property as new routes are added.

The frontend runs MSW with `onUnhandledRequest: 'error'`, and the Playwright suite uses
the same mocks. The default mock state must therefore be **authenticated**, or all 15
existing page test files land on the login screen. Dedicated `unauthenticated`,
`login-invalid`, and `login-locked` scenarios exercise the auth paths.

## Deployment impact

`scripts/deploy/anomaly-platform-deploy` verifies a release by fetching
`/api/system/status` and asserting `.telemetry.classification` with `jq`. Once that
endpoint answers `401`, `curl --fail` yields an empty string, `jq` fails, the loop times
out, and **the script rolls back every deployment**. This is a blocking consequence, not
a cosmetic one.

`verify_application()` will log in first, reading `AUTH_VERIFY_USERNAME` and
`AUTH_VERIFY_PASSWORD` from the same environment file that already holds
`POSTGRES_PASSWORD` and `MQTT_PASSWORD`, then reuse the cookie for the status call. The
cookie jar lives in a temporary file removed by a trap. `scripts/deploy/tests/deploy_test.sh`
already stubs `curl`, so coverage extends there.

`.env.example` and the compose files gain the four `AUTH_*` settings plus the deployment
verification credentials. `docs/cpu-vps-deployment.md` documents the bootstrap command.
`DESIGN.md` gains the `/login` route in its information architecture, the logout action
in its component list, and a revised *Open questions* section.

## Manuscript impact

`docs/naskah-skripsi-pra-sidang.md` states several things that stop being accurate once
login exists. These are updated after the code is complete and verified, in a separate
commit.

| Location | Change |
|---|---|
| Claim limits (§3.4) | Separate authentication from security claims: authentication exists and is tested, but no broad security-resistance claim is made |
| §3.5.1.6 database design | Accept `users` and `user_sessions`; the data dictionary gains two tables |
| `alert_events.actor` description | Clarify that a user entity now exists but `actor` **remains** a free-text attribute with no relation, so the two statements do not read as contradictory |
| Table 4.10 | Add an **Authentication** row with technical evidence |
| Figures 3.3 (use case) and 3.20 (ERD) | Need redrawing; assets live in `docs/naskah-skripsi-pra-sidang-assets/`. Accompanying prose is prepared here, redrawing is manual |

**Deliberately unchanged:** Table 4.14, the 70/80 score, 87.5%, and the phrase "eight
functions" in both abstracts and the conclusion. The UAT was already conducted with two
respondents; login cannot be claimed retroactively as part of it. Instead §4.3.4 gains
one sentence stating that authentication was implemented **after** the UAT and therefore
falls outside its scope.
