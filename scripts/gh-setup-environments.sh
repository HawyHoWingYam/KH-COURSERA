#!/usr/bin/env bash
set -euo pipefail

# Bootstrap GitHub Environments (uat, production) with required reviewers via GitHub CLI.
# Requirements: gh CLI logged in with repo:admin scope.
# Usage:
#   ./scripts/gh-setup-environments.sh <owner/repo> <reviewer1_login,reviewer2_login,...>

REPO_SLUG=${1:-}
REVIEWERS_CSV=${2:-}

if [[ -z "$REPO_SLUG" || -z "$REVIEWERS_CSV" ]]; then
  echo "Usage: $0 <owner/repo> <reviewer1,reviewer2,...>" >&2
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI not found. Install: https://cli.github.com/" >&2
  exit 1
fi

IFS=',' read -r -a REVIEWERS <<< "$REVIEWERS_CSV"

resolve_user_id() {
  local login=$1
  gh api "/users/$login" --jq '.id'
}

create_env() {
  local env_name=$1
  echo "Configuring environment: $env_name"
  # Create or update environment
  gh api \
    -X PUT \
    -H "Accept: application/vnd.github+json" \
    "/repos/$REPO_SLUG/environments/$env_name" \
    -f wait_timer=0 >/dev/null

  # Build reviewers array payload
  local reviewers_payload='['
  local first=1
  for login in "${REVIEWERS[@]}"; do
    uid=$(resolve_user_id "$login")
    if [[ -n "$uid" ]]; then
      if [[ $first -eq 0 ]]; then reviewers_payload+=','; fi
      reviewers_payload+="{\"type\":\"User\",\"id\":$uid}"
      first=0
    fi
  done
  reviewers_payload+=']'

  # Set protection rules with reviewers
  gh api \
    -X PUT \
    -H "Accept: application/vnd.github+json" \
    "/repos/$REPO_SLUG/environments/$env_name/protection-rules" \
    -f prevent_self_review=true \
    -f reviewers="$reviewers_payload" >/dev/null
}

create_env uat
create_env production

echo "Done. Go to Settings → Environments to verify reviewers and use the envs in workflows."

