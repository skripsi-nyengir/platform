#!/bin/sh
set -eu

repository_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../.." && pwd)
temporary_directory=$(mktemp -d)
trap 'rm -rf "$temporary_directory"' EXIT HUP INT TERM

export POSTGRES_HOST=db
export POSTGRES_PORT=5432
export POSTGRES_DB=anomaly
export POSTGRES_USER=anomaly
export POSTGRES_PASSWORD=ci-only
export NGINX_PORT=8080
export APP_HOST=anomaly.example.invalid
export MQTT_BROKER_HOST=mqtt.example.invalid
export MQTT_BROKER_PORT=8883
export MQTT_TOPIC=telemetry/test
export MQTT_CLIENT_ID=compose-contract
export MODEL_ARTIFACTS_DIR=/opt/anomaly-platform/shared/models
export LIVE_MODEL_BUNDLE_ID=ci-contract
unset MQTT_USERNAME MQTT_PASSWORD
export RUNTIME_IMAGE=ghcr.io/skripsi-nyengir/platform-api@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
export WORKER_IMAGE=ghcr.io/skripsi-nyengir/platform-worker-cpu@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
export WEB_IMAGE=ghcr.io/skripsi-nyengir/platform-web@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc

docker compose -f "$repository_root/compose.cpu.yaml" config >"$temporary_directory/cpu.yaml"
docker compose -f "$repository_root/compose.gpu.yaml" config >"$temporary_directory/gpu.yaml"
docker compose \
  -f "$repository_root/compose.cpu.yaml" \
  -f "$repository_root/compose.production.cpu.yaml" \
  config >"$temporary_directory/production.yaml"

if grep -q 'build:' "$temporary_directory/production.yaml"; then
  echo "production Compose must not contain build instructions" >&2
  exit 1
fi
if grep -q 'runtime: nvidia' "$temporary_directory/production.yaml"; then
  echo "production CPU Compose must not require NVIDIA" >&2
  exit 1
fi
if grep -Eq '^  eda-(worker|cli):' "$temporary_directory/production.yaml"; then
  echo "production Compose must not include EDA services" >&2
  exit 1
fi

grep -q "image: $RUNTIME_IMAGE" "$temporary_directory/production.yaml"
grep -q "image: $WORKER_IMAGE" "$temporary_directory/production.yaml"
grep -q "image: $WEB_IMAGE" "$temporary_directory/production.yaml"
grep -q 'LIVE_RUNTIME_MODE: production' "$temporary_directory/production.yaml"
grep -q 'MQTT_TLS_ENABLED: "true"' "$temporary_directory/production.yaml"
grep -q 'source: /opt/anomaly-platform/shared/mqtt-ca.crt' "$temporary_directory/production.yaml"
grep -q 'target: /run/secrets/mqtt-ca.crt' "$temporary_directory/production.yaml"

echo "CPU, production CPU, and GPU Compose contracts rendered successfully"
