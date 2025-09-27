#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd -P)"
# shellcheck source=lib_ingest.sh
source "$SCRIPT_DIR/lib_ingest.sh"

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 /path/to/tickers.txt" >&2
  exit 1
fi

ingest_init "$SCRIPT_DIR"
ingest_prices "$1"
