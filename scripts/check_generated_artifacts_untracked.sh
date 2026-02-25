#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mapfile -t tracked_generated_artifacts < <(
  git ls-files -- \
    .coverage \
    .coverage.* \
    coverage.xml \
    htmlcov \
    frontend/coverage
)

if [[ ${#tracked_generated_artifacts[@]} -gt 0 ]]; then
  echo "Generated coverage artifacts are tracked by git (must remain untracked):"
  printf ' - %s\n' "${tracked_generated_artifacts[@]}"
  echo
  echo "Remove each from the index, for example:"
  echo "  git rm --cached <path>"
  exit 1
fi

echo "Generated coverage artifacts are not tracked."
