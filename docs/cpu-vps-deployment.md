# CPU-only VPS deployment

The repository has two separate Compose entrypoints:

- `compose.cpu.yaml` is a standalone CPU stack. It builds
  `backend/Dockerfile.cpu`, installs the PyTorch CPU wheel, and selects CPU
  inference.
- `compose.gpu.yaml` loads the existing CUDA stack from `compose.yaml`, which
  continues to build the unchanged `backend/Dockerfile`.

Do not combine the CPU and GPU Compose files in one command. The target VPS in
this guide has no NVIDIA runtime, so use only `compose.cpu.yaml` there.

## Target assumptions

- Application VPS: `195.35.6.80` (`x86_64`, 4 vCPU, 15 GiB RAM).
- Administrative jump host: `69.62.82.215`.
- Docker Engine 28.1.1 and Docker Compose 2.35.1 are already installed.
- Traefik configuration is stored at
  `/root/dev-infrastructure/docker/traefik/docker-compose.yml` but must be
  started before the application so it creates the `reverse_proxy` network.
- The application hostname is `anomaly.mytekna.io`. Its public DNS A record,
  together with the Traefik dashboard hostname, must point to `195.35.6.80`
  before ACME certificate issuance.

Deployment is intentionally disabled until DNS, CI/CD, and the forced-command
account are configured. Keep the GitHub environment variable
`PRODUCTION_DEPLOY_ENABLED=false` until every preflight item passes.

The jump host does not permit SSH TCP forwarding. Open an administrative shell
with nested SSH instead of `ProxyJump`:

```sh
ssh root@69.62.82.215 -- ssh root@195.35.6.80
```

## Start Traefik

On the application VPS, create the Traefik `.env` from its example and set a
real `TRAEFIK_HOST`. Then validate and start the existing stack:

```sh
cd /root/dev-infrastructure/docker/traefik
docker compose config --quiet
docker compose up -d
docker network inspect reverse_proxy
```

Traefik owns host ports 80 and 443. The application Nginx container is reachable
only through the shared `reverse_proxy` network and does not publish a host port.

## Bootstrap the deployment boundary

Run `scripts/deploy/install-vps.sh` locally on the VPS as root from a verified
checkout. It installs root-owned Compose and deploy scripts under
`/opt/anomaly-platform` and `/usr/local/sbin`, creates `anomaly-deploy`, removes
that account from the Docker group, installs a command-only sudoers policy, and
adds an sshd `Match User` block. The account cannot request a PTY, forwarding,
an agent, X11, a tunnel, or an arbitrary command; only `preflight`, `deploy`,
and `rollback-last` reach the root-owned deployer.

Provision the public key in `/home/anomaly-deploy/.ssh/authorized_keys`. Keep
password authentication disabled. Before reloading sshd, run `sshd -t` from a
separate administrative session and keep that session open until a forced
`preflight` connection has been tested.

Docker must be logged in to GHCR as root with a PAT carrying only
`read:packages`. This credential stays in root's Docker config on the VPS; it is
never sent to GitHub Actions.

The mutable production inputs are deliberately outside Git:

- `/opt/anomaly-platform/shared/.env`, mode `0600` and root-owned;
- `/opt/anomaly-platform/shared/mqtt-ca.crt`, read-only in the subscriber;
- `/opt/anomaly-platform/shared/models/`, containing the immutable model bundle.

Create `.env` from `.env.example` and replace every placeholder. In particular:

- `APP_HOST=anomaly.mytekna.io` is the public hostname routed by Traefik.
- `MODEL_ARTIFACTS_DIR` resolves to the transferred artifact directory.
- `LIVE_MODEL_BUNDLE_ID` and optional `LIVE_MODEL_BUNDLE_IDS` name bundles that
  exist below that directory.
- Database and MQTT credentials are deployment-specific secrets and must not be
  committed.
- `INFERENCE_CPU_THREADS=1` is the conservative default. Increase it only after
  measuring backlog and host contention.
- `AUTH_COOKIE_SECURE=true` in production. It may only be relaxed for local http
  development, where a Secure cookie is discarded by the browser.
- `AUTH_VERIFY_USERNAME` and `AUTH_VERIFY_PASSWORD` name the account the deployer
  signs in as while verifying a release. Without them `deploy` refuses to run
  rather than skipping the telemetry check.

The production Compose overlay forces MQTT TLS, the CA mount, and
`LIVE_RUNTIME_MODE=production`; they cannot be relaxed by `.env`.

## Create the login accounts

Every `/api` path except `/health` and `/ready` requires a session cookie, and the
platform exposes no registration endpoint. Accounts exist only because they were
created here:

```sh
docker compose -f compose.cpu.yaml -f compose.production.cpu.yaml \
  run --rm api python -m anomaly_backend.auth_cli create-user operator
```

The command prompts for the password, or reads it from stdin when piped. It never
takes the password as an argument, so it stays out of shell history and out of
`ps`. Passwords must be at least 12 characters.

Create a second account for `AUTH_VERIFY_USERNAME` so a deployment verification
failure can be told apart from an operator's own sign-in problem.

`set-password` replaces a password and revokes that account's existing sessions,
which is also the way out of a lockout: five failed attempts lock an account for
fifteen minutes.

## Configure Slack alert notifications

The notifier posts a message with two charts — reconstruction error against threshold,
and temperature with relative humidity — when an episode opens, when it escalates to
critical, and when it closes.

Attaching an image requires a **bot token**; an incoming webhook accepts a message
payload only and cannot upload a file. In the Slack app configuration, add both
`files:write` (alert chart uploads) and `chat:write` (test messages) under
**OAuth & Permissions**, install the app to the workspace, and invite the bot to the
destination channel. Take the channel id from the channel's **View channel details**.

After signing in to the application, open `/settings/slack` and enter the `xoxb-` bot
token and destination channel id. Slack notifications are initially disabled; use
**Send Test** to verify the current form values, then save and enable the integration.
The token is stored server-side in PostgreSQL and is never shown again after it is
saved. Slack credentials, channel, and enablement are not configured in `.env`.

The notifier reads only what the live pipeline has already committed, so telemetry
never waits on Slack. If Slack is unreachable the rows accumulate in
`alert_notifications` as `pending`, retry up to `NOTIFIER_MAX_ATTEMPTS`, and then
retire as `failed` with the reason in `last_error`; nothing in the ingest path stalls.

`NOTIFIER_MAX_EPISODE_AGE_MINUTES` bounds how far back the notifier will look. Leave
it at the default unless you want a restart after long downtime to announce older
episodes. While the integration is disabled in `/settings/slack`, the service stays up
and idle rather than restarting in a loop.

## Configure GitHub and activate deployment

With GitHub CLI authenticated as a repository administrator, run:

```sh
PRODUCTION_SSH_KEY_FILE=/secure/path/deploy-key \
PRODUCTION_SSH_KNOWN_HOSTS_FILE=/secure/path/known-hosts \
scripts/deploy/configure-github.sh skripsi-nyengir/<repository>
```

This creates the `production` environment, installs the SSH secret, sets the
host to `195.35.6.80`, the user to `anomaly-deploy`, and leaves deployment
disabled. Do not use `ssh-keyscan` inside the workflow: verify and store the
server host key out of band.

The preflight must pass through the forced command:

```sh
ssh -i /secure/path/deploy-key anomaly-deploy@195.35.6.80 preflight
```

Only after DNS A records, Traefik, `reverse_proxy`, `.env`, MQTT CA, GHCR login,
and model artifacts are verified, change `PRODUCTION_DEPLOY_ENABLED` to `true`.

## CI and delivery behavior

Pull requests targeting `main` run the pragmatic unit gate only:

- backend pytest with TimescaleDB;
- the CPU worker test image target;
- frontend unit tests.

Ruff, Pyright, the migration and seed smoke test, frontend lint, build,
production-dist verification and Chromium end-to-end tests, Actionlint,
ShellCheck, Compose contract rendering, the deployment state-machine harness,
and the merged-PR gate harness are deferred. They run daily at 09:00 WIB and on
manual dispatch, and never deploy.

A push to `main` passes the delivery gate only when the pushed commit is
associated with exactly one merged pull request targeting `main` and the latest
PR unit-gate run for that pull request's exact head SHA completed successfully.
The workflow also validates the downloaded unit-gate evidence against the pull
request, head SHA, and workflow run. Direct pushes and stale, missing, failed, or
cancelled evidence fail before any image is published.

Each accepted merge builds and publishes exactly three images: API, CPU worker,
and web. They are tagged with the commit SHA, and their immutable digests are
recorded in the schema-2 `deployment-manifest.json` artifact before deployment
through the existing `production` environment and forced SSH command. Production
still builds nothing on the VPS; the EDA profile and CUDA image remain outside
production delivery.

`PRODUCTION_DEPLOY_ENABLED=false` skips the SSH deployment step. It does not
disable the accepted merge's image publication, schema-2 manifest artifact, or
release workflow behavior. Production operations share one concurrency group
and never cancel an active operation. Immediately before SSH, automatic delivery
checks the current `main` tip and skips a superseded SHA, allowing the newest
queued revision to win.

Release Please is not a deployment trigger. When an accepted merge creates a
semantic release, the workflow gives the already-built SHA images SemVer aliases
and attaches a backward-compatible schema-1 `release-manifest.json` to the GitHub
Release. It neither rebuilds the images nor redeploys them. Conventional Commits
continue to drive SemVer releases.

For local development, the standalone CPU and GPU entrypoints remain:

```sh
docker compose -f compose.cpu.yaml up -d --build
docker compose -f compose.gpu.yaml config --quiet
docker compose -f compose.gpu.yaml up -d --build
```

Do not combine those two entrypoints. Production always uses
`compose.cpu.yaml` plus `compose.production.cpu.yaml` and `--no-build`.

## Deployment and rollback behavior

The root deployer accepts only the exact schema-1 semantic release manifest or
the exact schema-2 SHA deployment manifest. Both schemas require digest-pinned
API, CPU worker, and web images from the approved GHCR namespace. The deployer
acquires a non-blocking `flock`, pulls all three digests, and creates a verified
custom-format database backup when a database already exists. Seven backups are
retained. It then runs migration, seed, and model bootstrap before recreating
API, worker, subscriber, notifier, and Nginx in place.

Health, readiness, and telemetry are polled over HTTPS for at most 180 seconds.
`failed` or any `retrying` state fails deployment; `degraded` is logged as a
warning. A failed release restores the current last-known-good images without
running an old migration. On the first release, where no previous image exists,
the application services stop and diagnostics are retained. Automatic and
manual rollback may cross manifest schema versions. Manual production operations
remain restricted to deploying a tagged schema-1 release manifest or swapping
to the previous last-known-good manifest with `rollback-last`.

Migrations follow expand-contract. A release may add compatible schema, but it
must not drop, rename, or change a contract still used by the rollback target.
Destructive cleanup requires at least two releases: expand first, then contract
only after the older release is no longer eligible for rollback. Database schema
is never downgraded automatically.

## Verify

After DNS and ACME have converged, verify the public path and the live runtime:

```sh
curl -fsS "https://anomaly.mytekna.io/health"
curl -fsS "https://anomaly.mytekna.io/ready"

# /api paths need a session. Reaching one without a cookie must answer 401.
curl -si "https://anomaly.mytekna.io/api/system/status" | head -1
curl -fsS -c /tmp/session -H 'content-type: application/json' \
  -d '{"username":"operator","password":"..."}' \
  "https://anomaly.mytekna.io/api/auth/login" >/dev/null
curl -fsS -b /tmp/session "https://anomaly.mytekna.io/api/system/status"
curl -fsS -b /tmp/session -X POST "https://anomaly.mytekna.io/api/auth/logout"
rm -f /tmp/session

docker compose -f compose.cpu.yaml logs --tail 200 worker live-subscriber
docker stats --no-stream
```

Acceptance requires the manifest's three exact digests, successful migration,
seed and bootstrap, valid backup inventory, HTTPS health/readiness, an
unauthenticated `/api` request answering 401, telemetry without `failed` or
`retrying`, and recorded `current`/`previous` manifests.
Readiness accepts a newer compatible linear Alembic revision, but rejects a
missing, malformed, branched, or older revision.
