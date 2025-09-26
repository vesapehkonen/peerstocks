#!/usr/bin/env bash
set -euo pipefail

# clean.sh — cleanup script for React + FastAPI project
# Usage:
#   ./clean.sh        # perform cleanup
#   ./clean.sh --dry  # show what would be deleted, no removal

DRY_RUN=false
if [[ "${1:-}" == "--dry" ]]; then
  DRY_RUN=true
  echo "[Dry run mode: nothing will actually be deleted]"
fi

delete() {
  if $DRY_RUN; then
    echo "Would delete: $*"
  else
    rm -rf "$@"
    echo "Deleted: $*"
  fi
}

# 1. Editor backup files
find . -type f -name '*~' -print0 | while IFS= read -r -d '' f; do delete "$f"; done

# 2. Python caches
find . -type d -name '__pycache__' -prune -print0 | while IFS= read -r -d '' d; do delete "$d"; done
delete .pytest_cache .mypy_cache .ruff_cache htmlcov *.egg-info 2>/dev/null || true

# 3. React/Node build outputs & caches
delete build dist coverage .next .vite .turbo .parcel-cache .eslintcache .stylelintcache .tsbuildinfo 2>/dev/null || true

# 4. Generic cache and log files
delete .cache 2>/dev/null || true
find . -type f -name '*.log' -print0 | while IFS= read -r -d '' f; do delete "$f"; done

# 5. Delete temporary ndjson files
find . -type f -name '*.ndjson' -print0 | while IFS= read -r -d '' f; do delete "$f"; done

echo "✅ Cleanup complete"
