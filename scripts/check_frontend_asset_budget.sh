#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$REPO_ROOT/frontend/dist"
INDEX_FILE="$DIST_DIR/index.html"
MAX_ENTRY_JS_BYTES="${FF_MAX_ENTRY_JS_BYTES:-400000}"
MAX_ENTRY_CSS_BYTES="${FF_MAX_ENTRY_CSS_BYTES:-170000}"

if [[ ! -f "$INDEX_FILE" ]]; then
  echo "Missing $INDEX_FILE. Build frontend assets first (cd frontend && npm run build)."
  exit 1
fi

required_seo_patterns=(
  '<link rel="canonical" href="https://fantasy-foundry.com/">'
  '<meta name="robots" content="index, follow, max-image-preview:large">'
  '"@type": "WebSite"'
  '"@type": "SoftwareApplication"'
)
for pattern in "${required_seo_patterns[@]}"; do
  if ! grep -Fq "$pattern" "$INDEX_FILE"; then
    echo "Missing required SEO pattern in frontend/dist/index.html: $pattern"
    exit 1
  fi
done

mapfile -t entry_assets < <(
  cd "$DIST_DIR/assets"
  find . -maxdepth 1 -type f \( -name "*.js" -o -name "*.css" \) | sort
)
if [[ ${#entry_assets[@]} -eq 0 ]]; then
  echo "No JS/CSS assets found in $DIST_DIR/assets."
  exit 1
fi

echo "Checking asset budgets in frontend/dist/assets..."
status=0
for asset in "${entry_assets[@]}"; do
  rel_asset="${asset#./}"
  abs_path="$DIST_DIR/assets/$rel_asset"
  if [[ ! -f "$abs_path" ]]; then
    echo "Missing asset: $rel_asset"
    status=1
    continue
  fi

  size_bytes="$(wc -c < "$abs_path")"
  if [[ "$rel_asset" == *.js ]]; then
    limit="$MAX_ENTRY_JS_BYTES"
    type_label="JS"
  else
    limit="$MAX_ENTRY_CSS_BYTES"
    type_label="CSS"
  fi

  if (( size_bytes > limit )); then
    echo "Budget exceeded for $type_label asset $rel_asset: ${size_bytes} bytes > ${limit} bytes."
    status=1
  else
    echo "OK $type_label $rel_asset: ${size_bytes} bytes (limit ${limit})."
  fi
done

exit "$status"
