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

The production Compose overlay forces MQTT TLS, the CA mount, and
`LIVE_RUNTIME_MODE=production`; they cannot be relaxed by `.env`.

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
Merge the Release Please PR for `v0.1.0` only after that activation. Conventional
Commits drive later SemVer releases.

Production never builds on the VPS. The workflow publishes exactly three CPU
images, records their immutable digests in `release-manifest.json`, attaches it
to the GitHub Release, and invokes `deploy` over SSH. The EDA profile and CUDA
image remain outside the v1 production release.

For local development, the standalone CPU and GPU entrypoints remain:

```sh
docker compose -f compose.cpu.yaml up -d --build
docker compose -f compose.gpu.yaml config --quiet
docker compose -f compose.gpu.yaml up -d --build
```

Do not combine those two entrypoints. Production always uses
`compose.cpu.yaml` plus `compose.production.cpu.yaml` and `--no-build`.

## Deployment and rollback behavior

The root deployer validates the fixed manifest schema and GHCR namespace,
acquires a non-blocking `flock`, pulls all three digests, and creates a verified
custom-format database backup when a database already exists. Seven backups are
retained. It then runs migration, seed, and model bootstrap before recreating
API, worker, subscriber, and Nginx in place.

Health, readiness, and telemetry are polled over HTTPS for at most 180 seconds.
`failed` or any `retrying` state fails deployment; `degraded` is logged as a
warning. A failed release restores the current last-known-good images without
running an old migration. On the first release, where no previous image exists,
the application services stop and diagnostics are retained. Manual operations
are restricted to deploying a tagged release manifest or swapping to the
previous last-known-good manifest.

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
curl -fsS "https://anomaly.mytekna.io/api/system/status"
docker compose -f compose.cpu.yaml logs --tail 200 worker live-subscriber
docker stats --no-stream
```

Acceptance requires the manifest's three exact digests, successful migration,
seed and bootstrap, valid backup inventory, HTTPS health/readiness, telemetry
without `failed` or `retrying`, and recorded `current`/`previous` manifests.
Readiness accepts a newer compatible linear Alembic revision, but rejects a
missing, malformed, branched, or older revision.
