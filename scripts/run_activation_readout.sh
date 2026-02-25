#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/run_activation_readout.sh \
    --current tmp/activation_current.csv \
    --baseline tmp/activation_baseline.csv \
    [--date YYYY-MM-DD] \
    [--owner "Owner Name"] \
    [--release-commit COMMIT_SHA] \
    [--current-window-label "24h post-release"] \
    [--baseline-window-label "Comparable 24h pre-release"] \
    [--output-dir tmp] \
    [--docs-dir docs]

Runs activation readout, writes text/json artifacts, and generates
docs/activation-rollout-decision-<date>.md by default.
EOF
}

CURRENT_PATH=""
BASELINE_PATH=""
REPORT_DATE="$(date +%F)"
OWNER="TBD"
OUTPUT_DIR="tmp"
DOCS_DIR="docs"
RELEASE_COMMIT=""
CURRENT_WINDOW_LABEL="24h post-release (activation rollout)"
BASELINE_WINDOW_LABEL="Comparable 24h pre-release window"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --current)
      CURRENT_PATH="${2:-}"
      shift 2
      ;;
    --baseline)
      BASELINE_PATH="${2:-}"
      shift 2
      ;;
    --date)
      REPORT_DATE="${2:-}"
      shift 2
      ;;
    --owner)
      OWNER="${2:-}"
      shift 2
      ;;
    --release-commit)
      RELEASE_COMMIT="${2:-}"
      shift 2
      ;;
    --current-window-label)
      CURRENT_WINDOW_LABEL="${2:-}"
      shift 2
      ;;
    --baseline-window-label)
      BASELINE_WINDOW_LABEL="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --docs-dir)
      DOCS_DIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$CURRENT_PATH" || -z "$BASELINE_PATH" ]]; then
  echo "Both --current and --baseline are required."
  usage
  exit 1
fi

if [[ ! -f "$CURRENT_PATH" ]]; then
  echo "Current export file not found: $CURRENT_PATH"
  exit 1
fi

if [[ ! -f "$BASELINE_PATH" ]]; then
  echo "Baseline export file not found: $BASELINE_PATH"
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEXT_OUTPUT="$REPO_ROOT/$OUTPUT_DIR/activation_readout_${REPORT_DATE}.txt"
JSON_OUTPUT="$REPO_ROOT/$OUTPUT_DIR/activation_readout_${REPORT_DATE}.json"
DECISION_OUTPUT="$REPO_ROOT/$DOCS_DIR/activation-rollout-decision-${REPORT_DATE}.md"
if [[ -n "${RELEASE_COMMIT:-}" ]]; then
  RESOLVED_RELEASE_COMMIT="$RELEASE_COMMIT"
else
  RESOLVED_RELEASE_COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
fi

mkdir -p "$(dirname "$TEXT_OUTPUT")" "$(dirname "$JSON_OUTPUT")" "$(dirname "$DECISION_OUTPUT")"

echo "Running activation readout (strict contract)..."
python "$REPO_ROOT/scripts/activation_readout.py" \
  --input "$CURRENT_PATH" \
  --baseline "$BASELINE_PATH" \
  --strict-contract > "$TEXT_OUTPUT"

echo "Writing activation readout JSON..."
python "$REPO_ROOT/scripts/activation_readout.py" \
  --input "$CURRENT_PATH" \
  --baseline "$BASELINE_PATH" \
  --json-output > "$JSON_OUTPUT"

echo "Generating decision memo..."
python "$REPO_ROOT/scripts/generate_activation_decision_memo.py" \
  --readout-json "$JSON_OUTPUT" \
  --output "$DECISION_OUTPUT" \
  --memo-date "$REPORT_DATE" \
  --owner "$OWNER" \
  --release-commit "$RESOLVED_RELEASE_COMMIT" \
  --current-window-label "$CURRENT_WINDOW_LABEL" \
  --baseline-window-label "$BASELINE_WINDOW_LABEL"

echo
echo "Activation readout complete."
echo "- Text report: $TEXT_OUTPUT"
echo "- JSON report: $JSON_OUTPUT"
echo "- Decision memo: $DECISION_OUTPUT"
