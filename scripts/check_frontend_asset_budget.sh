#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$REPO_ROOT/frontend/dist"
INDEX_FILE="$DIST_DIR/index.html"
MAX_ENTRY_JS_BYTES="${FF_MAX_ENTRY_JS_BYTES:-400000}"
MAX_ENTRY_CSS_BYTES="${FF_MAX_ENTRY_CSS_BYTES:-170000}"
MAX_INITIAL_JS_BYTES="${FF_MAX_INITIAL_JS_BYTES:-450000}"

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

# Extract entry-point JS/CSS assets referenced directly in index.html.
# Lazy-loaded chunks (React.lazy, dynamic imports) are not entry assets
# and should not count against the budget.
entry_assets_raw="$(grep -oP 'assets/[^"'"'"']+\.(js|css)' "$INDEX_FILE" | sort -u)"
if [[ -z "$entry_assets_raw" ]]; then
  echo "No entry JS/CSS assets found in $INDEX_FILE."
  exit 1
fi
IFS=$'\n' read -r -d '' -a entry_assets <<< "$entry_assets_raw" || true

echo "Checking entry-point asset budgets..."
status=0
initial_js_total=0
for rel_asset in "${entry_assets[@]}"; do
  abs_path="$DIST_DIR/$rel_asset"
  if [[ ! -f "$abs_path" ]]; then
    echo "Missing asset: $rel_asset"
    status=1
    continue
  fi

  size_bytes="$(wc -c < "$abs_path")"
  if [[ "$rel_asset" == *.js ]]; then
    limit="$MAX_ENTRY_JS_BYTES"
    type_label="JS"
    initial_js_total=$((initial_js_total + size_bytes))
  else
    limit="$MAX_ENTRY_CSS_BYTES"
    type_label="CSS"
  fi

  if (( size_bytes > limit )); then
    echo "Budget exceeded for $type_label entry asset $rel_asset: ${size_bytes} bytes > ${limit} bytes."
    status=1
  else
    echo "OK $type_label $rel_asset: ${size_bytes} bytes (limit ${limit})."
  fi
done

if (( initial_js_total > MAX_INITIAL_JS_BYTES )); then
  echo "Budget exceeded for total initial JS: ${initial_js_total} bytes > ${MAX_INITIAL_JS_BYTES} bytes."
  status=1
else
  echo "OK total initial JS: ${initial_js_total} bytes (limit ${MAX_INITIAL_JS_BYTES})."
fi

exit "$status"
