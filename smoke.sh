#!/usr/bin/env bash
# PeerStocks quick smoke test
# - Spins up dev stack
# - Waits for OpenSearch
# - Initializes indices
# - Seeds a small ticker set over an older date range
# - Fetches prices & earnings
# - Optional: hits a backend health endpoint if provided
# - Prompts for OPENAI_API_KEY and POLYGON_API_KEY if not set
#
# Usage:
#   COMPOSE=compose.dev.yml ./smoke.sh
#   BACKEND_HEALTH_URL="http://localhost/healthz" ./smoke.sh
#   # You may also pre-set keys to skip the prompt:
#   OPENAI_API_KEY=sk-... POLYGON_API_KEY=... ./smoke.sh
#
# Stop on first error:
set -Eeuo pipefail

# ---- Config (can override via env) ----
COMPOSE_FILE="${COMPOSE:-compose.dev.yml}"
SMOKE_DIR="${SMOKE_DIR:-.smoke}"
OS_DATA_DIR="$SMOKE_DIR/opensearch/data"
OS_LOG_DIR="$SMOKE_DIR/opensearch/logs"
TICKERS_FILE="$SMOKE_DIR/tickers_smoke.txt"
OS_URL="${OPENSEARCH_URL:-http://localhost:9200}"
BACKEND_HEALTH_URL="${BACKEND_HEALTH_URL:-http://localhost:8000/healthz}"
START_FRONTEND="${START_FRONTEND:-1}"
FRONTEND_DIR="${FRONTEND_DIR:-frontend}"
FRONTEND_MODE="${FRONTEND_MODE:-auto}"
KEEP_CONTAINERS="${KEEP_CONTAINERS:-0}"

FRONTEND_PGID_FILE="${FRONTEND_PGID_FILE:-$SMOKE_DIR/frontend.pgid}"
FRONTEND_LOG="$SMOKE_DIR/frontend.log"
FRONTEND_PID_FILE="$SMOKE_DIR/frontend.pid"


# ---- Helpers ----
log() { printf "\033[1;34m[smoke]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2; exit 1; }

cleanup() {
  ec=${1:-$?}
  log "Starting cleanup..."

  # Stop frontend process group if running
  if [[ -f "$FRONTEND_PGID_FILE" ]]; then
    pgid="$(cat "$FRONTEND_PGID_FILE" || true)"
    if [[ -n "${pgid:-}" ]]; then
      log "Stopping frontend process group (PGID $pgid)..."
      # Try a gentle Ctrl+C equivalent first (React dev server handles SIGINT nicely)
      kill -INT "-$pgid" 2>/dev/null || true
      sleep 2
      # Then TERM
      kill -TERM "-$pgid" 2>/dev/null || true
      sleep 2
      # Finally, KILL if still around
      kill -KILL "-$pgid" 2>/dev/null || true
    fi
    rm -f "$FRONTEND_PGID_FILE"
  fi

  # (Optional) still try the parent PID in case the PGID path failed
  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    pid="$(cat "$FRONTEND_PID_FILE" || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      log "Stopping frontend parent (PID $pid)..."
      kill "$pid" 2>/dev/null || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$FRONTEND_PID_FILE"
  fi

  # Bring down docker compose unless told to keep
  if [[ "$KEEP_CONTAINERS" != "1" ]]; then
    log "docker compose down (remove orphans)..."
    docker compose -f "$COMPOSE_FILE" down --remove-orphans || true
  else
    log "KEEP_CONTAINERS=1 -> leaving containers up."
  fi
  log "Cleanup complete."
  exit "$ec"
}
trap 'cleanup $?' EXIT
trap 'cleanup 130' INT
trap 'cleanup 143' TERM

# ---- Helpers ----
log() { printf "\033[1;34m[smoke]\033[0m %s\n" "$*"; }
die() { printf "\033[1;31m[error]\033[0m %s\n" "$*" >&2; exit 1; }

# Ensure required tools
command -v docker >/dev/null 2>&1 || die "Docker is required"
command -v docker compose >/dev/null 2>&1 || die "Docker Compose V2 is required"
command -v curl >/dev/null 2>&1 || die "curl is required"

read -r -p "Build docker images (Y/N): " do_build; echo

# build docker images
if [[ "$do_build" == "Y" || "$do_build" == "y" ]]; then
  docker build -t backend:latest   backend
  docker build -t ingest:latest    ingest
  docker build -t frontend:latest  --build-arg REACT_APP_API_BASE_URL=/api frontend
fi

export $(grep -v '^#' ./.env | xargs)

# --- Prompt for required API keys if not set ---
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  read -r -s -p "Enter OPENAI_API_KEY: " OPENAI_API_KEY; echo
fi
if [[ -z "${POLYGON_API_KEY:-}" ]]; then
  read -r -s -p "Enter POLYGON_API_KEY: " POLYGON_API_KEY; echo
fi

# Basic validation
[[ -n "$OPENAI_API_KEY" ]] || die "OPENAI_API_KEY is required"
[[ -n "$POLYGON_API_KEY" ]] || die "POLYGON_API_KEY is required"

# Export so docker compose picks them up (overriding env files)
export OPENAI_API_KEY
export POLYGON_API_KEY

# Fresh empty OpenSearch data/logs
log "Preparing empty OpenSearch data/log directories under $SMOKE_DIR ..."
rm -rf "$OS_DATA_DIR" "$OS_LOG_DIR"
mkdir -p "$OS_DATA_DIR" "$OS_LOG_DIR"

# Provide small ticker set if none exists
if [[ ! -f "$TICKERS_FILE" ]]; then
  log "Creating smoke tickers file at $TICKERS_FILE ..."
  mkdir -p "$(dirname "$TICKERS_FILE")"
  cat > "$TICKERS_FILE" <<EOF
AAPL
MSFT
EOF
fi

# Start/refresh containers
log "(re)starting dev stack via $COMPOSE_FILE ..."
docker compose -f "$COMPOSE_FILE" down -v --remove-orphans || true
docker compose -f "$COMPOSE_FILE" up -d

# Wait for OpenSearch
log "Waiting for OpenSearch at $OS_URL ..."
retries=30
until curl -fsS --connect-timeout 2 --max-time 5 --retry 0 \
       "$OS_URL/_cluster/health?wait_for_status=yellow&wait_for_no_initializing_shards=true&timeout=5s" > /dev/null
do
  ((retries--)) || { echo "OpenSearch not ready in time"; exit 1; }
  sleep 2
done
log "OpenSearch is up."

# Initialize indices
log "Init OpenSearch indices ..."
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -v "$PWD/ingest:/app/ingest" ingest init_indices.py

# Seed a small set of tickers with an older date range so newer updates can be fetched later
log "Seeding tickers (older date range) ..."
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -v "$PWD/$TICKERS_FILE:/app/tickers.txt" ingest seed_new_tickers.py /app/tickers.txt 2015-01-01 2020-01-01

# Fetch latest prices & earnings for the same tickers
log "Fetching latest prices ..."
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -v "$PWD/$TICKERS_FILE:/app/tickers.txt" ingest fetch_prices_wrapper.py /app/tickers.txt

log "Fetching latest earnings ..."
docker compose -f "$COMPOSE_FILE" run --rm --no-deps -v "$PWD/$TICKERS_FILE:/app/tickers.txt" ingest fetch_earnings_wrapper.py /app/tickers.txt

# Optional: backend health ping (if you expose one)
if [[ -n "$BACKEND_HEALTH_URL" ]]; then
  log "Hitting backend health: $BACKEND_HEALTH_URL ..."
  curl -sSf "$BACKEND_HEALTH_URL" >/dev/null || die "Backend health check failed"
  log "Backend health OK."
fi

# Optionally start frontend
start_frontend() {
  log "Starting frontend in $FRONTEND_DIR ..."
  [[ -d "$FRONTEND_DIR" ]] || { log "Frontend dir '$FRONTEND_DIR' not found; skipping."; return; }
  pushd "$FRONTEND_DIR" >/dev/null

  # ensure deps
  if command -v npm >/dev/null 2>&1; then
    npm ci
  else
    log "npm not found; cannot start frontend."
    popd >/dev/null
    return
  fi

  cmd="npm start"
  log "Frontend command: $cmd"

  set +e
  if command -v setsid >/dev/null 2>&1; then
    # Start in a new session so PGID == PID, making group-kill easy
    setsid bash -lc "$cmd" >"$OLDPWD/$FRONTEND_LOG" 2>&1 &
  else
    # Fallback: normal background, we'll detect PGID via ps
    bash -lc "$cmd" >"$OLDPWD/$FRONTEND_LOG" 2>&1 &
  fi
  FRONTEND_PID=$!
  set -e

  # Determine process group id (PGID)
  PGID="$(ps -o pgid= "$FRONTEND_PID" | tr -d ' ' || true)"
  [[ -n "$PGID" ]] || PGID="$FRONTEND_PID"

  echo "$FRONTEND_PID" > "$OLDPWD/$FRONTEND_PID_FILE"
  echo "$PGID"        > "$OLDPWD/$FRONTEND_PGID_FILE"

  popd >/dev/null
  log "Frontend started (PID $FRONTEND_PID, PGID $PGID). Logs: $FRONTEND_LOG"
}

read -r -p "Do you want start front end (Y/N): " START_FRONTEND; echo

if [[ "$START_FRONTEND" == "Y" || "$START_FRONTEND" == "y" ]]; then
  start_frontend
else
    log "Run frontend manually:"
    log "  cd frontend"
    log "  npm start."
fi
log "Open the UI in your browser (e.g., http://localhost:3000) and visually spot-check the charts."
read -r -p "Press ENTER to stop frontend and shut down Docker..."
log "Smoke steps completed."
log "\nAll smoke steps completed."
