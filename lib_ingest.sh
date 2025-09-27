# Common helpers for ingest wrappers. Intentionally does NOT set shell options.

# Initialize env and compose file using the given project root (usually the wrapper's dir)
ingest_init() {
  INGEST_ROOT_DIR="$1"

  # If APP_ENV not set, try to read it from .env (support optional 'export' and whitespace)
  if [ -z "${APP_ENV:-}" ] && [ -f "$INGEST_ROOT_DIR/.env" ]; then
    APP_ENV="$(
      sed -nE 's/^[[:space:]]*(export[[:space:]]+)?APP_ENV[[:space:]]*=[[:space:]]*//p' "$INGEST_ROOT_DIR/.env" | head -n1
    )"
    # Strip surrounding quotes if present
    APP_ENV="${APP_ENV%\"}"; APP_ENV="${APP_ENV#\"}"
    APP_ENV="${APP_ENV%\'}"; APP_ENV="${APP_ENV#\'}"
  fi

  # Fail if APP_ENV is still unset
  : "${APP_ENV:?APP_ENV must be defined (either exported or set in .env)}"

  INGEST_COMPOSE_FILE="$INGEST_ROOT_DIR/compose.${APP_ENV}.yml"
  if [ ! -f "$INGEST_COMPOSE_FILE" ]; then
    echo "Compose file '$(basename "$INGEST_COMPOSE_FILE")' not found in $INGEST_ROOT_DIR" >&2
    exit 1
  fi
}

# Return an absolute path for a possibly-relative path
_ingest_abs_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *)  printf '%s/%s\n' "$PWD" "$1" ;;
  esac
}

# Mount the provided file and run the given python entrypoint with extra args
# Usage: _ingest_mount_and_run <tickers_file> <py_entrypoint> [args...]
_ingest_mount_and_run() {
  local tickers_path="$1"; shift
  local py_entry="$1"; shift

  local abs="$(_ingest_abs_path "$tickers_path")"
  if [ ! -f "$abs" ]; then
    echo "Tickers file '$tickers_path' not found" >&2
    exit 1
  fi

  local base target
  base="$(basename "$abs")"
  target="/app/ingest/$base"

  ( cd "$INGEST_ROOT_DIR"
    docker compose -f "$INGEST_COMPOSE_FILE" run --rm --no-deps \
      -v "$abs:$target:ro" \
      ingest "$py_entry" "$target" "$@"
  )
}

# Public commands (thin wrappers for clarity)
ingest_seed()     { _ingest_mount_and_run "$1" seed_new_tickers.py; }
ingest_earnings() { _ingest_mount_and_run "$1" fetch_earnings_wrapper.py --run-summary; }
ingest_prices()   { _ingest_mount_and_run "$1" fetch_prices_wrapper.py   --run-summary; }
