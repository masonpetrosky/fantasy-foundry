#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm was not found in PATH."
  exit 1
fi

export npm_config_cache="${NPM_CONFIG_CACHE:-/tmp/fantasy-foundry-npm-cache}"
mkdir -p "$npm_config_cache"

echo "Installing frontend dependencies with npm ci..."
cd "$FRONTEND_DIR"
npm ci

echo "Building frontend assets..."
npm run build

echo "Checking frontend entry asset budgets..."
"$REPO_ROOT/scripts/check_frontend_asset_budget.sh"

echo "Checking frontend/dist parity..."
cd "$REPO_ROOT"
if ! git diff --quiet -- frontend/dist; then
  echo "frontend/dist is stale relative to a clean build."
  echo "Commit the added/modified/deleted files under frontend/dist."
  echo
  git --no-pager diff --name-status -- frontend/dist
  exit 1
fi

echo "frontend/dist is up to date."
