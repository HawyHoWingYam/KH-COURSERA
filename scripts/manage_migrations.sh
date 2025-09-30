#!/usr/bin/env bash
set -euo pipefail

# Simple wrapper for Alembic commands.
# Usage examples:
#   ./scripts/manage_migrations.sh upgrade head
#   ./scripts/manage_migrations.sh revision --autogenerate -m "add table"
#
# DATABASE_URL can be provided, or DATABASE_SECRET_NAME (resolved by app runtime).

HERE=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONPATH="$HERE"

if ! command -v alembic >/dev/null 2>&1; then
  echo "alembic not found. Install with: pip install -r requirements.txt" >&2
  exit 1
fi

cd "$HERE"
exec alembic "$@"

