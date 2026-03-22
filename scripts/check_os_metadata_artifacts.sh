#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

mapfile -t metadata_files < <(
  find . \
    -path './.git' -prune -o \
    -path './.venv' -prune -o \
    -path './frontend/node_modules' -prune -o \
    -path './frontend/coverage' -prune -o \
    -path './htmlcov' -prune -o \
    -type f \
    \( -name '*:Zone.Identifier' -o -name '._*' \) \
    -print |
    sed 's#^\./##' |
    sort
)

if [[ ${#metadata_files[@]} -gt 0 ]]; then
  echo "OS metadata artifacts found (must be removed before commit/build validation):"
  printf ' - %s\n' "${metadata_files[@]}"
  exit 1
fi

echo "OS metadata artifact scrub passed."
