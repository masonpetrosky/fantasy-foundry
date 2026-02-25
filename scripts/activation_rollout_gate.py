#!/usr/bin/env python3
"""Aggregate 24h/48h activation readouts into a final rollout decision."""

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


def _safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return 0
        try:
            return int(float(text))
        except ValueError:
            return 0
    return 0


def _contract_has_errors(contract: Mapping[str, Any]) -> bool:
    missing_events = contract.get("missing_events")
    if isinstance(missing_events, list) and missing_events:
        return True

    missing_field_counts = contract.get("missing_field_counts")
    if isinstance(missing_field_counts, dict):
        for event_fields in missing_field_counts.values():
            if not isinstance(event_fields, dict):
                continue
            if any(_safe_int(count) > 0 for count in event_fields.values()):
                return True

    missing_session_id_counts = contract.get("missing_session_id_counts")
    if isinstance(missing_session_id_counts, dict):
        if any(_safe_int(count) > 0 for count in missing_session_id_counts.values()):
            return True

    return False


def _normalize_decision(value: Any) -> str:
    decision = str(value or "").strip().lower()
    if decision in {"expand", "hold", "rollback"}:
        return decision
    return "unknown"


def _decision_action(decision: str) -> str:
    if decision == "expand":
        return "Expand rollout after both checkpoints passed."
    if decision == "hold":
        return "Hold rollout and gather more evidence before expanding."
    if decision == "rollback":
        return "Rollback activation rollout and investigate regressions."
    return "Decision unavailable. Investigate checkpoint data quality."


def _fmt_pct_from_percent(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f}%"
    return "n/a"


def _fmt_pp(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.2f} pp"
    return "n/a"


def _checkpoint_summary(*, payload: Mapping[str, Any], label: str, path: Path) -> dict[str, Any]:
    comparison = payload.get("comparison")
    comparison_map = comparison if isinstance(comparison, Mapping) else {}
    contract = payload.get("current_contract")
    contract_map = contract if isinstance(contract, Mapping) else {}

    reasons_raw = comparison_map.get("reasons")
    reasons = reasons_raw if isinstance(reasons_raw, list) else []
    normalized_reasons = [str(reason) for reason in reasons if str(reason).strip()]

    decision = _normalize_decision(comparison_map.get("decision"))
    contract_has_errors = _contract_has_errors(contract_map)

    return {
        "label": label,
        "path": str(path),
        "decision": decision,
        "contract_pass": not contract_has_errors,
        "time_to_first_success_improvement_pct": comparison_map.get("time_to_first_success_improvement_pct"),
        "calculation_error_rate_delta_pp": comparison_map.get("calculation_error_rate_delta_pp"),
        "submit_to_success_rate_delta_pp": comparison_map.get("submit_to_success_rate_delta_pp"),
        "reasons": normalized_reasons,
    }


def build_rollout_gate_payload(
    *,
    readout_24h: Mapping[str, Any],
    readout_48h: Mapping[str, Any],
    readout_24h_path: Path,
    readout_48h_path: Path,
    checkpoint_24h_label: str,
    checkpoint_48h_label: str,
) -> dict[str, Any]:
    checkpoint_24h = _checkpoint_summary(
        payload=readout_24h,
        label=checkpoint_24h_label,
        path=readout_24h_path,
    )
    checkpoint_48h = _checkpoint_summary(
        payload=readout_48h,
        label=checkpoint_48h_label,
        path=readout_48h_path,
    )
    checkpoints = [checkpoint_24h, checkpoint_48h]

    final_reasons: list[str] = []
    if any(not checkpoint["contract_pass"] for checkpoint in checkpoints):
        decision = "hold"
        final_reasons.append("At least one checkpoint failed strict event contract validation.")
    elif any(checkpoint["decision"] == "rollback" for checkpoint in checkpoints):
        decision = "rollback"
        final_reasons.append("At least one checkpoint returned rollback due to KPI/guardrail regression.")
    elif all(checkpoint["decision"] == "expand" for checkpoint in checkpoints):
        decision = "expand"
        final_reasons.append("Both 24h and 48h checkpoints met expand criteria.")
    else:
        decision = "hold"
        final_reasons.append("Checkpoint decisions were mixed or inconclusive.")

    for checkpoint in checkpoints:
        final_reasons.append(
            f"{checkpoint['label']}: decision={checkpoint['decision']} "
            f"contract_pass={checkpoint['contract_pass']}"
        )

    return {
        "decision": decision,
        "recommended_action": _decision_action(decision),
        "checkpoints": checkpoints,
        "reasons": final_reasons,
    }


def build_rollout_gate_markdown(
    *,
    gate_payload: Mapping[str, Any],
    memo_date: str,
    owner: str,
    release_commit: str,
) -> str:
    decision = _normalize_decision(gate_payload.get("decision"))
    recommended_action = str(gate_payload.get("recommended_action") or _decision_action(decision))
    checkpoints_raw = gate_payload.get("checkpoints")
    checkpoints = checkpoints_raw if isinstance(checkpoints_raw, list) else []
    reasons_raw = gate_payload.get("reasons")
    reasons = reasons_raw if isinstance(reasons_raw, list) else []

    table_lines = [
        "| Checkpoint | Contract Pass | Decision | TTF Improvement | Error-Rate Delta | Submit-Success Delta |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    source_lines: list[str] = []
    for checkpoint in checkpoints:
        if not isinstance(checkpoint, Mapping):
            continue
        label = str(checkpoint.get("label") or "unknown")
        contract_pass = bool(checkpoint.get("contract_pass"))
        checkpoint_decision = _normalize_decision(checkpoint.get("decision"))
        ttf_improvement = _fmt_pct_from_percent(checkpoint.get("time_to_first_success_improvement_pct"))
        error_delta = _fmt_pp(checkpoint.get("calculation_error_rate_delta_pp"))
        submit_delta = _fmt_pp(checkpoint.get("submit_to_success_rate_delta_pp"))
        table_lines.append(
            f"| {label} | {'Yes' if contract_pass else 'No'} | {checkpoint_decision.upper()} "
            f"| {ttf_improvement} | {error_delta} | {submit_delta} |"
        )
        source_path = str(checkpoint.get("path") or "").strip()
        if source_path:
            source_lines.append(f"- {label}: `{source_path}`")

    reason_lines = [f"- {str(reason)}" for reason in reasons if str(reason).strip()]
    if not reason_lines:
        reason_lines = ["- No reasons were provided in gate payload."]

    if not source_lines:
        source_lines = ["- Source readout paths unavailable."]

    return "\n".join(
        [
            f"# Activation Rollout Final Decision - {memo_date}",
            "",
            "## Summary",
            f"- Owner: {owner}",
            f"- Release commit: `{release_commit}`",
            f"- Decision: **{decision.upper()}**",
            f"- Recommended action: {recommended_action}",
            "",
            "## Checkpoint Results",
            *table_lines,
            "",
            "## Final Rationale",
            *reason_lines,
            "",
            "## Source Artifacts",
            *source_lines,
            "",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine 24h and 48h activation readouts into a final rollout decision.",
    )
    parser.add_argument("--readout-24h", type=Path, required=True, help="24h checkpoint readout JSON path.")
    parser.add_argument("--readout-48h", type=Path, required=True, help="48h checkpoint readout JSON path.")
    parser.add_argument("--output-json", type=Path, required=True, help="Final gate JSON output path.")
    parser.add_argument(
        "--output-markdown",
        type=Path,
        required=True,
        help="Final gate markdown output path.",
    )
    parser.add_argument("--memo-date", type=str, required=True, help="Memo date label (YYYY-MM-DD).")
    parser.add_argument("--owner", type=str, default="TBD", help="Decision owner.")
    parser.add_argument("--release-commit", type=str, default="unknown", help="Release commit sha.")
    parser.add_argument(
        "--checkpoint-24h-label",
        type=str,
        default="24h post-release (activation rollout)",
        help="Human label for 24h checkpoint.",
    )
    parser.add_argument(
        "--checkpoint-48h-label",
        type=str,
        default="48h post-release (activation rollout)",
        help="Human label for 48h checkpoint.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    readout_24h = _read_json(args.readout_24h)
    readout_48h = _read_json(args.readout_48h)
    gate_payload = build_rollout_gate_payload(
        readout_24h=readout_24h,
        readout_48h=readout_48h,
        readout_24h_path=args.readout_24h,
        readout_48h_path=args.readout_48h,
        checkpoint_24h_label=args.checkpoint_24h_label,
        checkpoint_48h_label=args.checkpoint_48h_label,
    )
    markdown = build_rollout_gate_markdown(
        gate_payload=gate_payload,
        memo_date=args.memo_date,
        owner=args.owner,
        release_commit=args.release_commit,
    )

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(gate_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    args.output_markdown.write_text(markdown, encoding="utf-8")

    print(f"Wrote activation rollout gate JSON: {args.output_json}")
    print(f"Wrote activation rollout final decision markdown: {args.output_markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
