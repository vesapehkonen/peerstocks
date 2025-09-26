#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 ingest/tickers.txt" >&2
  exit 1
fi

TICKERS="$1"
if [ ! -f "${TICKERS}" ]; then
  echo "Tickers file '${TICKERS}' not found" >&2
  exit 1
fi

if [ -f ./.env ]; then
  set -a; . ./.env; set +a
fi

APP_ENV="${APP_ENV:-development}"
COMPOSE_FILE="compose.${APP_ENV}.yml"

if [ ! -f "${COMPOSE_FILE}" ]; then
  echo "Compose file '${COMPOSE_FILE}' not found" >&2
  exit 1
fi

BASENAME="$(basename "${TICKERS}")"

docker compose -f "${COMPOSE_FILE}" run --rm --no-deps   -v "$PWD/ingest:/app/ingest:ro" ingest   fetch_earnings_wrapper.py "/app/ingest/${BASENAME}" --run-summary
