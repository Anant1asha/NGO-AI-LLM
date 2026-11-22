#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUNTIME_DIR="${ROOT_DIR}/.qa-runtime/${STAMP}"
TOKEN_FILE="${RUNTIME_DIR}/gateway-token.txt"

mkdir -p "${RUNTIME_DIR}/config" "${RUNTIME_DIR}/data" "${RUNTIME_DIR}/state" "${RUNTIME_DIR}/cache"
cp "${ROOT_DIR}/qa/fixtures/.env.sample" "${RUNTIME_DIR}/.env"
printf '%s\n' 'qa-phase-token' > "${TOKEN_FILE}"

cat <<EOF
Isolated QA runtime created:
  ${RUNTIME_DIR}

Next steps (run in your shell):
  export XDG_CONFIG_HOME="${RUNTIME_DIR}/config"
  export XDG_DATA_HOME="${RUNTIME_DIR}/data"
  export XDG_STATE_HOME="${RUNTIME_DIR}/state"
  export XDG_CACHE_HOME="${RUNTIME_DIR}/cache"
  export HACHI_GATEWAY_API_TOKEN_FILE="${TOKEN_FILE}"
  export HACHI_GATEWAY_AUTH_HEADER_FILE="${TOKEN_FILE}"
  cd "${ROOT_DIR}"
  uv run hachi gateway --host 127.0.0.1 --port 8787 --runtime

Cleanup:
  rm -rf "${RUNTIME_DIR}"
EOF
