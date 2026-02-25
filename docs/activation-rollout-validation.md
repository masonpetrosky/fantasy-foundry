# Activation Rollout Validation

This runbook validates the activation-funnel rollout after shipping UX changes.

## Goal

Confirm that the latest activation changes:

- improve median `landing -> first successful calculation` time by at least `30%`
- do not regress guardrails (`ff_calculation_error`, submit-to-success conversion)

## Required Event Coverage

The validation script expects these events in the export window:

- `ff_landing_view`
- `ff_quickstart_cta_click`
- `ff_calculator_panel_open`
- `ff_calculation_submit`
- `ff_calculation_success`
- `ff_calculation_error`

## Export Requirements

You can export either CSV, JSON, or JSONL. Include at least:

- `event` (or `event_name`)
- `session_id`
- `source`
- `timestamp` (recommended)

For richer validation include:

- `is_first_run`
- `time_to_first_success_ms`
- `scoring_mode`
- `teams`
- `horizon`
- `error_message`

## Run The Readout

```bash
python scripts/activation_readout.py \
  --input tmp/activation_current.csv \
  --baseline tmp/activation_baseline.csv \
  --strict-contract
```

### One-command workflow (recommended)

```bash
scripts/run_activation_readout.sh \
  --current tmp/activation_current.csv \
  --baseline tmp/activation_baseline.csv \
  --date 2026-02-25 \
  --owner "Analytics Team"
```

Generates:

- `tmp/activation_readout_<date>.txt`
- `tmp/activation_readout_<date>.json`
- `docs/activation-rollout-decision-<date>.md`

### JSON output (optional)

```bash
python scripts/activation_readout.py \
  --input tmp/activation_current.csv \
  --baseline tmp/activation_baseline.csv \
  --json-output
```

## Decision Thresholds

Defaults in `scripts/activation_readout.py`:

- `--min-improvement-pct 30`
- `--max-error-rate-increase-pp 0.5`
- `--max-submit-success-drop-pp 1.0`

Decision outcomes:

- `expand`: KPI and guardrails pass
- `hold`: mixed results, gather more data
- `rollback`: severe regression detected

## Operational Cadence

1. Run first readout at 24 hours post-release.
2. Run second readout at 48 hours post-release.
3. If traffic is low, extend window before deciding.

## Troubleshooting

- Missing events:
  - verify export filters include all six required events
  - verify event naming was not transformed in the analytics tool
- Missing `session_id`:
  - ensure analytics payloads include `session_id` (the frontend helper injects it)
- No `time_to_first_success_ms`:
  - verify `ff_calculation_success` payload still includes this property
