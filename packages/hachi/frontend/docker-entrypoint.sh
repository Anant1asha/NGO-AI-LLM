#!/bin/sh
# Frontend container entrypoint. Reads the gateway bearer token from the mounted secret
# file into an env var, then hands off to the stock nginx entrypoint — which runs
# envsubst over /etc/nginx/templates/*.template (injecting GATEWAY_TARGET / GATEWAY_TOKEN)
# and starts nginx. The browser never sees the token; nginx adds it to proxied requests.
set -e

_token_file="${HACHI_GATEWAY_AUTH_HEADER_FILE:-/run/secrets/gateway_api_token}"
if [ -f "$_token_file" ]; then
    GATEWAY_TOKEN="$(cat "$_token_file")"
fi
export GATEWAY_TOKEN="${GATEWAY_TOKEN:-}"
export GATEWAY_TARGET="${HACHI_GATEWAY_BASE_URL:-http://hachi:8787}"

exec /docker-entrypoint.sh "$@"
