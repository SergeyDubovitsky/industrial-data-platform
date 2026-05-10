#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/../.." && pwd)"
ENV_FILE="${LOCAL_STACK_ENV_FILE:-${REPO_ROOT}/.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
  ENV_FILE="${REPO_ROOT}/.env.example"
fi

export LOCAL_STACK_ENV_FILE="${ENV_FILE}"

compose() {
  docker compose \
    --env-file "${ENV_FILE}" \
    -f "${SCRIPT_DIR}/compose.yaml" \
    "$@"
}

compose build \
  idp-config-registry \
  grafana \
  kafka-connect

compose up -d --remove-orphans postgres

compose run --rm --no-deps idp-config-registry \
  alembic -c apps/idp_config_registry/alembic.ini upgrade head

compose up -d --remove-orphans \
  mqtt-broker \
  kafka \
  kafka-init \
  redpanda-connect \
  redpanda-connect-config-projection \
  redpanda-connect-source-config-snapshot \
  clickhouse \
  postgres \
  idp-config-registry \
  idp-config-registry-outbox-worker \
  kafka-connect \
  kafka-ui \
  mqttx-web \
  grafana
