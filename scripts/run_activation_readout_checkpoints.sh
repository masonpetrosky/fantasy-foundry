#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/run_activation_readout_checkpoints.sh \
    --current-24h tmp/activation_current_24h.csv \
    --baseline-24h tmp/activation_baseline_24h.csv \
    --date-24h YYYY-MM-DD \
    --current-48h tmp/activation_current_48h.csv \
    --baseline-48h tmp/activation_baseline_48h.csv \
    --date-48h YYYY-MM-DD \
    [--owner "Owner Name"] \
    [--release-commit COMMIT_SHA] \
    [--output-dir tmp] \
    [--docs-dir docs]

Runs strict activation readout at both checkpoints (24h/48h), writes
checkpoint decision memos, then generates a final combined decision artifact.
EOF
}

CURRENT_24H=""
BASELINE_24H=""
DATE_24H=""
CURRENT_48H=""
BASELINE_48H=""
DATE_48H=""
OWNER="TBD"
RELEASE_COMMIT=""
OUTPUT_DIR="tmp"
DOCS_DIR="docs"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --current-24h)
      CURRENT_24H="${2:-}"
      shift 2
      ;;
    --baseline-24h)
      BASELINE_24H="${2:-}"
      shift 2
      ;;
    --date-24h)
      DATE_24H="${2:-}"
      shift 2
      ;;
    --current-48h)
      CURRENT_48H="${2:-}"
      shift 2
      ;;
    --baseline-48h)
      BASELINE_48H="${2:-}"
      shift 2
      ;;
    --date-48h)
      DATE_48H="${2:-}"
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

if [[ -z "$CURRENT_24H" || -z "$BASELINE_24H" || -z "$DATE_24H" || -z "$CURRENT_48H" || -z "$BASELINE_48H" || -z "$DATE_48H" ]]; then
  echo "All checkpoint file/date arguments are required."
  usage
  exit 1
fi

for required_file in "$CURRENT_24H" "$BASELINE_24H" "$CURRENT_48H" "$BASELINE_48H"; do
  if [[ ! -f "$required_file" ]]; then
    echo "Required file not found: $required_file"
    exit 1
  fi
done

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_READOUT_SCRIPT="$REPO_ROOT/scripts/run_activation_readout.sh"
if [[ ! -f "$RUN_READOUT_SCRIPT" ]]; then
  echo "Missing script: $RUN_READOUT_SCRIPT"
  exit 1
fi

if [[ -n "$RELEASE_COMMIT" ]]; then
  RESOLVED_RELEASE_COMMIT="$RELEASE_COMMIT"
else
  RESOLVED_RELEASE_COMMIT="$(git -C "$REPO_ROOT" rev-parse --short HEAD)"
fi

echo "Running 24h checkpoint readout..."
"$RUN_READOUT_SCRIPT" \
  --current "$CURRENT_24H" \
  --baseline "$BASELINE_24H" \
  --date "$DATE_24H" \
  --owner "$OWNER" \
  --release-commit "$RESOLVED_RELEASE_COMMIT" \
  --current-window-label "24h post-release (activation rollout)" \
  --baseline-window-label "Comparable 24h pre-release window" \
  --output-dir "$OUTPUT_DIR" \
  --docs-dir "$DOCS_DIR"

echo
echo "Running 48h checkpoint readout..."
"$RUN_READOUT_SCRIPT" \
  --current "$CURRENT_48H" \
  --baseline "$BASELINE_48H" \
  --date "$DATE_48H" \
  --owner "$OWNER" \
  --release-commit "$RESOLVED_RELEASE_COMMIT" \
  --current-window-label "48h post-release (activation rollout)" \
  --baseline-window-label "Comparable 48h pre-release window" \
  --output-dir "$OUTPUT_DIR" \
  --docs-dir "$DOCS_DIR"

READOUT_24H_JSON="$REPO_ROOT/$OUTPUT_DIR/activation_readout_${DATE_24H}.json"
READOUT_48H_JSON="$REPO_ROOT/$OUTPUT_DIR/activation_readout_${DATE_48H}.json"
FINAL_GATE_JSON="$REPO_ROOT/$OUTPUT_DIR/activation_rollout_gate_${DATE_48H}.json"
FINAL_GATE_MD="$REPO_ROOT/$DOCS_DIR/activation-rollout-final-decision-${DATE_48H}.md"

echo
echo "Generating final rollout gate decision..."
python "$REPO_ROOT/scripts/activation_rollout_gate.py" \
  --readout-24h "$READOUT_24H_JSON" \
  --readout-48h "$READOUT_48H_JSON" \
  --output-json "$FINAL_GATE_JSON" \
  --output-markdown "$FINAL_GATE_MD" \
  --memo-date "$DATE_48H" \
  --owner "$OWNER" \
  --release-commit "$RESOLVED_RELEASE_COMMIT"

echo
echo "Checkpoint rollout readout complete."
echo "- 24h readout JSON: $READOUT_24H_JSON"
echo "- 48h readout JSON: $READOUT_48H_JSON"
echo "- Final gate JSON: $FINAL_GATE_JSON"
echo "- Final gate markdown: $FINAL_GATE_MD"
