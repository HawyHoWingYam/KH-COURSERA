#!/usr/bin/env bash
# Print environment exports to switch DB target for backend.
# Usage:
#   source GeminiOCR/scripts/use-db.sh local
#   source GeminiOCR/scripts/use-db.sh sandbox
#   source GeminiOCR/scripts/use-db.sh uat
#   source GeminiOCR/scripts/use-db.sh production

set -euo pipefail

ENV=${1:-}
if [[ -z "$ENV" ]]; then
  echo "Usage: source $0 <local|sandbox|uat|production>" >&2
  return 1 2>/dev/null || exit 1
fi

case "$ENV" in
  local)
    echo "export DATABASE_URL=postgresql://user:pass@localhost:5432/gemini_dev?sslmode=disable"
    echo "unset DATABASE_SECRET_NAME"
    ;;
  sandbox)
    echo "unset DATABASE_URL"
    echo "export DATABASE_SECRET_NAME=sandbox/database"  # Secrets Manager JSON must include {\"database_url\": "...sslmode=require"}
    ;;
  uat)
    echo "unset DATABASE_URL"
    echo "export DATABASE_SECRET_NAME=uat/database"
    ;;
  production)
    echo "unset DATABASE_URL"
    echo "export DATABASE_SECRET_NAME=prod/database"
    ;;
  *)
    echo "Unknown env: $ENV" >&2
    return 1 2>/dev/null || exit 1
    ;;
esac

echo "# Now run migrations (example):"
echo "#   cd GeminiOCR/backend && ./scripts/manage_migrations.sh upgrade head"

