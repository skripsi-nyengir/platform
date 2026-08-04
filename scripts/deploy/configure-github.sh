#!/usr/bin/env bash
set -Eeuo pipefail

repository=${1:-}
: "${repository:?usage: configure-github.sh OWNER/REPO}"
: "${PRODUCTION_SSH_KEY_FILE:?set PRODUCTION_SSH_KEY_FILE}"
: "${PRODUCTION_SSH_KNOWN_HOSTS_FILE:?set PRODUCTION_SSH_KNOWN_HOSTS_FILE}"

gh api --method PUT "repos/$repository/environments/production" >/dev/null
gh variable set PRODUCTION_HOST --repo "$repository" --env production --body 195.35.6.80
gh variable set PRODUCTION_USER --repo "$repository" --env production --body anomaly-deploy
gh variable set PRODUCTION_DEPLOY_ENABLED --repo "$repository" --env production --body false
gh variable set PRODUCTION_SSH_KNOWN_HOSTS --repo "$repository" --env production \
  --body "$(<"$PRODUCTION_SSH_KNOWN_HOSTS_FILE")"
gh secret set PRODUCTION_SSH_KEY --repo "$repository" --env production \
  <"$PRODUCTION_SSH_KEY_FILE"

echo "GitHub production environment configured with deployment disabled"
