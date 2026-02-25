#!/usr/bin/env python3
"""Generate a rollout decision memo from activation readout JSON output."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


def _read_json(path: Path) -> Mapping[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _fmt_pct(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value * 100.0:.2f}%"
    return "n/a"


def _fmt_ms(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.0f} ms"
    return "n/a"


def _fmt_pp(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f} pp"
    return "n/a"


def _decision_action(decision: str) -> str:
    if decision == "expand":
        return "Increase rollout cohort and schedule 48-hour re-check."
    if decision == "hold":
        return "Keep current cohort and gather more data before changing rollout."
    if decision == "rollback":
        return "Disable activation rollout flag and open regression follow-up."
    return "Decision unavailable. Investigate readout data quality."


def _missing_field_lines(contract: Mapping[str, Any]) -> list[str]:
    missing_field_counts = contract.get("missing_field_counts")
    if not isinstance(missing_field_counts, dict):
        return ["- Missing field data unavailable."]

    lines: list[str] = []
    for event_name in sorted(missing_field_counts.keys()):
        event_fields = missing_field_counts.get(event_name)
        if not isinstance(event_fields, dict):
            continue
        missing = [f"{field}={count}" for field, count in sorted(event_fields.items()) if int(count) > 0]
        if missing:
            lines.append(f"- `{event_name}`: {', '.join(missing)}")
    return lines or ["- No missing required event fields detected."]


def build_memo_markdown(
    *,
    readout_payload: Mapping[str, Any],
    memo_date: str,
    owner: str,
    release_commit: str,
    current_window_label: str,
    baseline_window_label: str,
    readout_json_path: Path,
) -> str:
    contract = readout_payload.get("current_contract", {})
    current_metrics = readout_payload.get("current_metrics", {})
    baseline_metrics = readout_payload.get("baseline_metrics", {})
    comparison = readout_payload.get("comparison", {})

    missing_events = contract.get("missing_events", [])
    if isinstance(missing_events, list) and missing_events:
        contract_status = f"Fail: missing required events ({', '.join(str(x) for x in missing_events)})."
    else:
        contract_status = "Pass: all required activation events present."

    session_missing_counts = contract.get("missing_session_id_counts", {})
    missing_session_total = 0
    if isinstance(session_missing_counts, dict):
        missing_session_total = sum(
            int(value) for value in session_missing_counts.values() if isinstance(value, (int, float))
        )

    decision = str(comparison.get("decision", "unknown")).strip().lower() or "unknown"
    decision_reasons = comparison.get("reasons", [])
    if not isinstance(decision_reasons, list):
        decision_reasons = []

    current_submit_success = current_metrics.get("submit_to_success_rate")
    baseline_submit_success = baseline_metrics.get("submit_to_success_rate")
    current_error_rate = current_metrics.get("calculation_error_rate")
    baseline_error_rate = baseline_metrics.get("calculation_error_rate")
    current_median_ttf = current_metrics.get("median_time_to_first_success_ms")
    baseline_median_ttf = baseline_metrics.get("median_time_to_first_success_ms")
    improvement_pct = comparison.get("time_to_first_success_improvement_pct")
    error_delta_pp = comparison.get("calculation_error_rate_delta_pp")
    submit_success_delta_pp = comparison.get("submit_to_success_rate_delta_pp")

    rows = [
        ("Landing -> Panel", _fmt_pct(current_metrics.get("landing_to_panel_rate")), _fmt_pct(baseline_metrics.get("landing_to_panel_rate"))),
        ("Panel -> Submit", _fmt_pct(current_metrics.get("panel_to_submit_rate")), _fmt_pct(baseline_metrics.get("panel_to_submit_rate"))),
        ("Submit -> Success", _fmt_pct(current_submit_success), _fmt_pct(baseline_submit_success)),
        ("Landing -> Success", _fmt_pct(current_metrics.get("landing_to_success_rate")), _fmt_pct(baseline_metrics.get("landing_to_success_rate"))),
        ("Calculation Error Rate", _fmt_pct(current_error_rate), _fmt_pct(baseline_error_rate)),
        ("Median Time To First Success", _fmt_ms(current_median_ttf), _fmt_ms(baseline_median_ttf)),
    ]

    metric_table_lines = [
        "| Metric | Current | Baseline |",
        "| --- | --- | --- |",
    ]
    metric_table_lines.extend([f"| {name} | {current} | {baseline} |" for name, current, baseline in rows])

    decision_reason_lines = decision_reasons or ["No explicit reason provided by comparison payload."]
    decision_reason_lines = [f"- {str(reason)}" for reason in decision_reason_lines]

    missing_field_lines = _missing_field_lines(contract)

    return "\n".join(
        [
            f"# Activation Rollout Decision - {memo_date}",
            "",
            "## Summary",
            f"- Owner: {owner}",
            f"- Release commit: `{release_commit}`",
            f"- Decision: **{decision.upper()}**",
            f"- Recommended action: { _decision_action(decision) }",
            "",
            "## Window Definitions",
            f"- Current window: {current_window_label}",
            f"- Baseline window: {baseline_window_label}",
            "",
            "## Contract Status",
            f"- Event contract: {contract_status}",
            f"- Rows missing `session_id`: {missing_session_total}",
            "- Missing required field counts:",
            *missing_field_lines,
            "",
            "## KPI and Guardrails",
            *metric_table_lines,
            "",
            "## Delta Summary",
            f"- Time-to-first-success improvement: {f'{improvement_pct:.2f}%' if isinstance(improvement_pct, (int, float)) else 'n/a'}",
            f"- Calculation error-rate delta: {_fmt_pp(error_delta_pp)}",
            f"- Submit-to-success delta: {_fmt_pp(submit_success_delta_pp)}",
            "",
            "## Decision Rationale",
            *decision_reason_lines,
            "",
            "## Source Artifact",
            f"- Readout JSON: `{readout_json_path}`",
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate activation rollout decision markdown from readout JSON.",
    )
    parser.add_argument("--readout-json", type=Path, required=True, help="Activation readout JSON file path.")
    parser.add_argument("--output", type=Path, required=True, help="Output markdown path.")
    parser.add_argument("--memo-date", type=str, required=True, help="Memo date label (YYYY-MM-DD).")
    parser.add_argument("--owner", type=str, default="TBD", help="Decision owner.")
    parser.add_argument("--release-commit", type=str, default="unknown", help="Release commit sha.")
    parser.add_argument(
        "--current-window-label",
        type=str,
        default="24h post-release",
        help="Human label for the current window.",
    )
    parser.add_argument(
        "--baseline-window-label",
        type=str,
        default="Comparable 24h pre-release",
        help="Human label for the baseline window.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = _read_json(args.readout_json)
    markdown = build_memo_markdown(
        readout_payload=payload,
        memo_date=args.memo_date,
        owner=args.owner,
        release_commit=args.release_commit,
        current_window_label=args.current_window_label,
        baseline_window_label=args.baseline_window_label,
        readout_json_path=args.readout_json,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")
    print(f"Wrote activation decision memo: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
