#!/usr/bin/env bash
set -Eeuo pipefail

repository_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd)
deploy_script=$repository_root/scripts/deploy/anomaly-platform-deploy
force_command_script=$repository_root/scripts/deploy/anomaly-deploy-force-command
test_root=$(mktemp -d)
trap 'rm -rf "$test_root"' EXIT HUP INT TERM

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

make_manifest() {
  local release=$1 digit=$2
  printf '{"schema":1,"release":"%s","commit":"%040d","runtime":"ghcr.io/skripsi-nyengir/platform-api@sha256:%064d","worker":"ghcr.io/skripsi-nyengir/platform-worker-cpu@sha256:%064d","web":"ghcr.io/skripsi-nyengir/platform-web@sha256:%064d"}\n' \
    "$release" "$digit" "$digit" "$digit" "$digit"
}

make_schema_2_manifest() {
  local digit=$1
  printf '{"schema":2,"deployment":"sha-%040d","commit":"%040d","runtime":"ghcr.io/skripsi-nyengir/platform-api@sha256:%064d","worker":"ghcr.io/skripsi-nyengir/platform-worker-cpu@sha256:%064d","web":"ghcr.io/skripsi-nyengir/platform-web@sha256:%064d"}\n' \
    "$digit" "$digit" "$digit" "$digit" "$digit"
}

setup_case() {
  case_dir=$test_root/$1
  fake_bin=$case_dir/bin
  state_dir=$case_dir/state
  mkdir -p "$fake_bin" "$state_dir/shared/models" "$state_dir/manifests" "$state_dir/backups"
  printf 'model' >"$state_dir/shared/models/bundle.pt"
  printf 'ca' >"$state_dir/shared/mqtt-ca.crt"
  cat >"$state_dir/shared/.env" <<'EOF'
APP_HOST=anomaly.example.invalid
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=anomaly
POSTGRES_USER=anomaly
POSTGRES_PASSWORD=test
MQTT_BROKER_HOST=mqtt.example.invalid
MQTT_BROKER_PORT=8883
MQTT_TOPIC=telemetry/test
MQTT_CLIENT_ID=test
MODEL_ARTIFACTS_DIR=/models
LIVE_MODEL_BUNDLE_ID=test
AUTH_VERIFY_USERNAME=deploy-verifier
AUTH_VERIFY_PASSWORD=deploy-verifier-password
EOF
  cp "$repository_root/compose.cpu.yaml" "$state_dir/compose.cpu.yaml"
  cp "$repository_root/compose.production.cpu.yaml" "$state_dir/compose.production.cpu.yaml"

  cat >"$fake_bin/docker" <<'EOF'
#!/usr/bin/env bash
set -eu
printf '%s\n' "$*" >>"$FAKE_DOCKER_CALL_FILE"
args=" $* "
if [[ $args == *" ps --filter label=traefik.enable=true "* ]]; then echo traefik; exit 0; fi
if [[ $args == *" compose version "* || $args == *" network inspect reverse_proxy "* || $args == *" compose "*" config "* ]]; then exit 0; fi
if [[ $args == *" ps -q db "* ]]; then [[ ${FAKE_DB_EXISTS:-0} == 1 ]] && echo db-container; exit 0; fi
if [[ $args == *" exec -T db sh -eu -c "*"pg_dump -Fc"* ]]; then printf 'fake custom dump'; exit 0; fi
if [[ $args == *" exec -T db pg_restore --list "* ]]; then
  dump=$(cat)
  [[ $dump == 'fake custom dump' ]] || exit 65
  [[ ${FAKE_DB_VERIFY_MODE:-success} == success ]] || exit 86
  printf 'verified\n' >"$FAKE_DB_VERIFY_FILE"
  exit 0
fi
if [[ $args == *" run --rm "* ]]; then
  printf 'compose mutation\n' >>"$FAKE_MUTATION_FILE"
  exit 0
fi
if [[ $args == *" up -d "* ]]; then
  printf '%s\n' "$args" >>"$FAKE_START_ARGS_FILE"
  count=0
  [[ -f ${FAKE_START_COUNT_FILE:-/nonexistent} ]] && read -r count <"$FAKE_START_COUNT_FILE"
  printf '%s\n' "$((count + 1))" >"$FAKE_START_COUNT_FILE"
  exit 0
fi
if [[ $args == *" compose "*" stop "* ]]; then
  printf '%s\n' "$args" >>"$FAKE_STOP_ARGS_FILE"
  exit 0
fi
exit 0
EOF
  cat >"$fake_bin/sudo" <<'EOF'
#!/usr/bin/env bash
set -eu
[[ ${1:-} == -n ]] || exit 64
shift
[[ ${1:-} == /usr/local/sbin/anomaly-platform-deploy ]] || exit 64
shift
exec "$REAL_DEPLOY_SCRIPT" "$@"
EOF
  cat >"$fake_bin/curl" <<'EOF'
#!/usr/bin/env bash
set -eu
count=0
[[ -f ${FAKE_START_COUNT_FILE:-/nonexistent} ]] && read -r count <"$FAKE_START_COUNT_FILE"
if [[ ${FAKE_HEALTH_MODE:-success} == fail ]] || [[ ${FAKE_HEALTH_MODE:-success} == fail-first && $count -lt 2 ]]; then
  exit 22
fi
url=${*: -1}
args=" $* "
case $url in
  */health) printf '{"status":"alive"}' ;;
  */ready) printf '{"status":"ready"}' ;;
  */api/auth/login)
    printf 'login\n' >>"${FAKE_LOGIN_FILE:-/dev/null}"
    printf '{"username":"deploy-verifier"}'
    ;;
  */api/auth/logout) printf '{"request_id":"req"}' ;;
  */api/system/status)
    # Stands in for the session guard: without a cookie the real endpoint answers
    # 401 and curl --fail exits non-zero.
    [[ $args == *" --cookie "* ]] || exit 22
    printf '{"telemetry":{"classification":"healthy"}}'
    ;;
esac
EOF
  cat >"$fake_bin/pg_restore" <<'EOF'
#!/bin/sh
echo 'host pg_restore must not be called' >&2
exit 86
EOF
  chmod +x "$fake_bin"/*
  export PATH="$fake_bin:/usr/bin:/bin"
  export ANOMALY_DEPLOY_TESTING=1 ANOMALY_STATE_DIR="$state_dir"
  export ANOMALY_HEALTH_TIMEOUT=1 FAKE_START_COUNT_FILE="$case_dir/start-count"
  export FAKE_START_ARGS_FILE="$case_dir/start-args" FAKE_STOP_ARGS_FILE="$case_dir/stop-args"
  export FAKE_DB_VERIFY_FILE="$case_dir/db-verify" FAKE_MUTATION_FILE="$case_dir/mutations"
  export FAKE_LOGIN_FILE="$case_dir/logins" FAKE_DOCKER_CALL_FILE="$case_dir/docker-calls"
  export REAL_DEPLOY_SCRIPT="$deploy_script"
  unset FAKE_DB_EXISTS FAKE_DB_VERIFY_MODE FAKE_HEALTH_MODE
}

run_deploy() {
  "$deploy_script" deploy
}

assert_schema_2_rejected() {
  local name=$1 filter=$2
  setup_case "$name"
  make_schema_2_manifest 2 | jq "$filter" >"$case_dir/candidate.json"
  make_manifest v9.0.0 9 >"$state_dir/manifests/current.json"
  make_manifest v8.0.0 8 >"$state_dir/manifests/previous.json"
  cp "$state_dir/manifests/current.json" "$case_dir/current-before.json"
  cp "$state_dir/manifests/previous.json" "$case_dir/previous-before.json"
  if run_deploy <"$case_dir/candidate.json" >"$case_dir/output" 2>&1; then
    fail "$name manifest accepted"
  fi
  [[ ! -e $FAKE_DOCKER_CALL_FILE ]] || fail "$name manifest reached Docker"
  cmp -s "$case_dir/current-before.json" "$state_dir/manifests/current.json" \
    || fail "$name manifest changed current last-known-good state"
  cmp -s "$case_dir/previous-before.json" "$state_dir/manifests/previous.json" \
    || fail "$name manifest changed previous last-known-good state"
}

setup_case valid
make_manifest v0.1.0 1 | run_deploy
jq -e '.release == "v0.1.0"' "$state_dir/manifests/current.json" >/dev/null || fail "valid deploy"
grep -q 'deployment complete: v0.1.0' "$state_dir/logs/deploy.log" \
  || fail "schema 1 deployment did not log its semantic release"
grep -Eq ' up -d .* api worker live-subscriber notifier nginx ' "$FAKE_START_ARGS_FILE" \
  || fail "application start did not include notifier"

setup_case valid_schema_2
make_schema_2_manifest 2 | run_deploy
jq -e '.schema == 2 and .deployment == "sha-0000000000000000000000000000000000000002"' \
  "$state_dir/manifests/current.json" >/dev/null || fail "schema 2 deploy was not stored as current"
grep -q 'deployment complete: sha-0000000000000000000000000000000000000002' \
  "$state_dir/logs/deploy.log" || fail "schema 2 deployment identifier was not logged"

setup_case forced_command_schema_2
make_schema_2_manifest 3 \
  | SSH_ORIGINAL_COMMAND=deploy "$force_command_script"
jq -e '.schema == 2 and .deployment == "sha-0000000000000000000000000000000000000003"' \
  "$state_dir/manifests/current.json" >/dev/null \
  || fail "forced-command wrapper did not preserve schema 2 manifest stdin"

assert_schema_2_rejected mismatched_deployment \
  '.deployment = "sha-0000000000000000000000000000000000000003"'
assert_schema_2_rejected uppercase_commit \
  '.commit = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" | .deployment = ("sha-" + .commit)'
assert_schema_2_rejected short_commit \
  '.commit = "abcd" | .deployment = ("sha-" + .commit)'
assert_schema_2_rejected extra_key '.extra = true'
assert_schema_2_rejected missing_key 'del(.web)'
assert_schema_2_rejected mutable_image_tag \
  '.runtime = "ghcr.io/skripsi-nyengir/platform-api:latest"'
assert_schema_2_rejected wrong_repository \
  '.worker = "ghcr.io/skripsi-nyengir/platform-worker@sha256:2222222222222222222222222222222222222222222222222222222222222222"'
assert_schema_2_rejected unknown_schema '.schema = 3'
assert_schema_2_rejected wrong_schema_type '.schema = "2"'

setup_case failed_first_release_stops_notifier
export FAKE_HEALTH_MODE=fail
if make_manifest v0.1.0 1 | run_deploy >/dev/null 2>&1; then
  fail "unhealthy first release reported success"
fi
grep -Eq ' stop api worker live-subscriber notifier nginx ' "$FAKE_STOP_ARGS_FILE" \
  || fail "application stop did not include notifier"

setup_case verify_authenticates
make_manifest v0.1.0 1 | run_deploy
[[ -s "$case_dir/logins" ]] || fail "release verification did not sign in"

setup_case verify_requires_credentials
sed -i '/^AUTH_VERIFY_/d' "$state_dir/shared/.env"
if make_manifest v0.1.0 1 | run_deploy >/dev/null 2>&1; then
  fail "release verified without verification credentials"
fi

setup_case invalid
if printf '{"schema":2}\n' | run_deploy >/dev/null 2>&1; then fail "invalid manifest accepted"; fi

setup_case lock
exec 8>"$state_dir/deploy.lock"
flock -n 8
if "$deploy_script" preflight >/dev/null 2>&1; then fail "concurrent lock accepted"; fi
flock -u 8

setup_case backup
export FAKE_DB_EXISTS=1
for index in {1..8}; do
  touch -d "$index minutes ago" "$state_dir/backups/database-old-$index.dump"
done
make_manifest v0.2.0 2 | run_deploy
[[ -s $FAKE_DB_VERIFY_FILE ]] || fail "database backup was not verified inside the database container"
backup_count=$(find "$state_dir/backups" -name 'database-*.dump' | wc -l)
[[ $backup_count -eq 7 ]] || fail "backup rotation retained $backup_count files"

setup_case backup_verification_failure
export FAKE_DB_EXISTS=1 FAKE_DB_VERIFY_MODE=fail
if make_manifest v0.2.0 2 | run_deploy >"$case_dir/output" 2>&1; then fail "unverified backup accepted"; fi
grep -q 'database backup verification failed' "$case_dir/output" || fail "backup verification failure was not reported"
[[ ! -e $FAKE_MUTATION_FILE ]] || fail "deployment mutated services after backup verification failed"
[[ ! -e $state_dir/manifests/current.json ]] || fail "failed backup changed current manifest"
if find "$state_dir/backups" -name 'database-*.dump' -print -quit | grep -q .; then
  fail "unverified database backup was retained"
fi

setup_case rollback
make_manifest v0.1.0 1 >"$state_dir/manifests/current.json"
export FAKE_HEALTH_MODE=fail-first
if make_manifest v0.2.0 2 | run_deploy >/dev/null 2>&1; then fail "failed release reported success"; fi
[[ $(cat "$case_dir/start-count") -ge 2 ]] || fail "automatic rollback did not restart"
jq -e '.release == "v0.1.0"' "$state_dir/manifests/current.json" >/dev/null || fail "rollback changed current manifest"

setup_case schema_2_automatic_rollback
make_schema_2_manifest 1 >"$state_dir/manifests/current.json"
export FAKE_HEALTH_MODE=fail-first
if make_manifest v0.2.0 2 | run_deploy >/dev/null 2>&1; then fail "failed release reported success"; fi
[[ $(cat "$case_dir/start-count") -ge 2 ]] || fail "schema 2 automatic rollback did not restart"
jq -e '.schema == 2 and .deployment == "sha-0000000000000000000000000000000000000001"' \
  "$state_dir/manifests/current.json" >/dev/null || fail "automatic rollback changed schema 2 current manifest"

setup_case mixed_history_manual_rollback
make_manifest v0.1.0 1 >"$state_dir/manifests/current.json"
make_schema_2_manifest 2 >"$state_dir/manifests/previous.json"
"$deploy_script" rollback-last
jq -e '.schema == 2 and .deployment == "sha-0000000000000000000000000000000000000002"' \
  "$state_dir/manifests/current.json" >/dev/null || fail "manual rollback did not activate schema 2"
jq -e '.schema == 1 and .release == "v0.1.0"' "$state_dir/manifests/previous.json" >/dev/null \
  || fail "manual rollback did not retain schema 1 as previous"
grep -q 'rollback complete: sha-0000000000000000000000000000000000000002' \
  "$state_dir/logs/deploy.log" || fail "schema 2 rollback identifier was not logged"
"$deploy_script" rollback-last
jq -e '.schema == 1 and .release == "v0.1.0"' "$state_dir/manifests/current.json" >/dev/null \
  || fail "reverse manual rollback did not reactivate schema 1"
jq -e '.schema == 2 and .deployment == "sha-0000000000000000000000000000000000000002"' \
  "$state_dir/manifests/previous.json" >/dev/null || fail "reverse rollback did not retain schema 2 as previous"
grep -q 'rollback complete: v0.1.0' "$state_dir/logs/deploy.log" \
  || fail "schema 1 rollback identifier was not logged"

setup_case rollback_failure
make_manifest v0.1.0 1 >"$state_dir/manifests/current.json"
make_manifest v0.0.9 9 >"$state_dir/manifests/previous.json"
export FAKE_HEALTH_MODE=fail
if "$deploy_script" rollback-last >"$case_dir/output" 2>&1; then fail "failed rollback reported success"; fi
grep -q 'production status is critical' "$case_dir/output" || fail "critical rollback status missing"

echo "deploy script contract tests passed"
