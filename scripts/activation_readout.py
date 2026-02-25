#!/usr/bin/env python3
"""Activation rollout readout and event-contract validator.

This utility consumes analytics event exports (CSV/JSON/JSONL), validates
required activation-funnel event fields, computes funnel guardrails, and
optionally compares current vs baseline windows to recommend rollout action.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import median
from typing import Any, Iterable, Mapping

REQUIRED_ACTIVATION_EVENTS = (
    "ff_landing_view",
    "ff_quickstart_cta_click",
    "ff_calculator_panel_open",
    "ff_calculation_submit",
    "ff_calculation_success",
    "ff_calculation_error",
)

EVENT_REQUIRED_FIELDS = {
    "ff_landing_view": ("source", "is_first_run"),
    "ff_quickstart_cta_click": ("source", "mode"),
    "ff_calculator_panel_open": ("source",),
    "ff_calculation_submit": ("source", "scoring_mode", "teams", "horizon"),
    "ff_calculation_success": (
        "source",
        "scoring_mode",
        "teams",
        "horizon",
        "is_first_run",
        "time_to_first_success_ms",
    ),
    "ff_calculation_error": ("source", "error_message"),
}

FIELD_ALIASES = {
    "event": ("event", "event_name", "name"),
    "timestamp": ("timestamp", "event_timestamp", "event_time"),
    "session_id": ("session_id", "session", "analytics_session_id"),
    "source": ("source", "cta_source"),
    "mode": ("mode", "quickstart_mode"),
    "scoring_mode": ("scoring_mode", "scoringMode"),
    "teams": ("teams", "team_count"),
    "horizon": ("horizon", "horizon_years"),
    "is_first_run": ("is_first_run", "first_run"),
    "time_to_first_success_ms": ("time_to_first_success_ms", "ttf_success_ms"),
    "error_message": ("error_message", "message", "error"),
}


@dataclass(frozen=True)
class NormalizedEvent:
    event: str
    session_id: str
    timestamp: str
    source: str
    mode: str
    scoring_mode: str
    teams: float | None
    horizon: float | None
    is_first_run: bool | None
    time_to_first_success_ms: float | None
    error_message: str


@dataclass(frozen=True)
class ContractReport:
    missing_events: list[str]
    missing_field_counts: dict[str, dict[str, int]]
    missing_session_id_counts: dict[str, int]

    @property
    def has_errors(self) -> bool:
        if self.missing_events:
            return True
        if any(sum(field_counts.values()) > 0 for field_counts in self.missing_field_counts.values()):
            return True
        if any(count > 0 for count in self.missing_session_id_counts.values()):
            return True
        return False


@dataclass(frozen=True)
class FunnelMetrics:
    event_counts: dict[str, int]
    session_counts: dict[str, int]
    landing_to_panel_rate: float | None
    panel_to_submit_rate: float | None
    submit_to_success_rate: float | None
    landing_to_success_rate: float | None
    calculation_error_rate: float | None
    calculation_error_session_rate: float | None
    median_time_to_first_success_ms: float | None
    p90_time_to_first_success_ms: float | None
    source_breakdown: dict[str, dict[str, float | int | None]]


@dataclass(frozen=True)
class ComparisonResult:
    decision: str
    time_to_first_success_improvement_pct: float | None
    calculation_error_rate_delta_pp: float | None
    submit_to_success_rate_delta_pp: float | None
    reasons: list[str]


def _parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if not text:
        return None
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def _parse_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _first_value(record: Mapping[str, Any], aliases: Iterable[str]) -> Any:
    for key in aliases:
        if key in record:
            value = record.get(key)
            if value is None:
                continue
            text = str(value).strip()
            if text:
                return value
    return None


def _detect_format(path: Path, fmt: str) -> str:
    if fmt != "auto":
        return fmt
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return "csv"
    if suffix in {".jsonl", ".ndjson"}:
        return "jsonl"
    if suffix == ".json":
        return "json"
    return "csv"


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [dict(row) for row in reader]


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "events", "data"):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [row for row in candidate if isinstance(row, dict)]
        return [payload]
    return []


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def load_events(path: Path, fmt: str = "auto") -> list[NormalizedEvent]:
    resolved_format = _detect_format(path, fmt)
    if resolved_format == "csv":
        rows = _load_csv(path)
    elif resolved_format == "json":
        rows = _load_json(path)
    elif resolved_format == "jsonl":
        rows = _load_jsonl(path)
    else:
        raise ValueError(f"Unsupported input format: {resolved_format}")

    events: list[NormalizedEvent] = []
    for row in rows:
        event_name = _parse_text(_first_value(row, FIELD_ALIASES["event"]))
        if not event_name:
            continue
        events.append(
            NormalizedEvent(
                event=event_name,
                session_id=_parse_text(_first_value(row, FIELD_ALIASES["session_id"])),
                timestamp=_parse_text(_first_value(row, FIELD_ALIASES["timestamp"])),
                source=_parse_text(_first_value(row, FIELD_ALIASES["source"])),
                mode=_parse_text(_first_value(row, FIELD_ALIASES["mode"])),
                scoring_mode=_parse_text(_first_value(row, FIELD_ALIASES["scoring_mode"])),
                teams=_parse_float(_first_value(row, FIELD_ALIASES["teams"])),
                horizon=_parse_float(_first_value(row, FIELD_ALIASES["horizon"])),
                is_first_run=_parse_bool(_first_value(row, FIELD_ALIASES["is_first_run"])),
                time_to_first_success_ms=_parse_float(
                    _first_value(row, FIELD_ALIASES["time_to_first_success_ms"])
                ),
                error_message=_parse_text(_first_value(row, FIELD_ALIASES["error_message"])),
            )
        )
    return events


def validate_event_contract(events: list[NormalizedEvent]) -> ContractReport:
    event_rows: dict[str, list[NormalizedEvent]] = {}
    for event in events:
        event_rows.setdefault(event.event, []).append(event)

    missing_events = [event for event in REQUIRED_ACTIVATION_EVENTS if event not in event_rows]
    missing_field_counts: dict[str, dict[str, int]] = {}
    missing_session_id_counts: dict[str, int] = {}

    for event_name in REQUIRED_ACTIVATION_EVENTS:
        rows = event_rows.get(event_name, [])
        missing_session_id_counts[event_name] = sum(1 for row in rows if not row.session_id)
        field_counts: dict[str, int] = {}
        for field_name in EVENT_REQUIRED_FIELDS[event_name]:
            field_counts[field_name] = sum(
                1
                for row in rows
                if getattr(row, field_name) in (None, "")
            )
        missing_field_counts[event_name] = field_counts

    return ContractReport(
        missing_events=missing_events,
        missing_field_counts=missing_field_counts,
        missing_session_id_counts=missing_session_id_counts,
    )


def _sessions_for_event(events: list[NormalizedEvent], event_name: str) -> set[str]:
    return {event.session_id for event in events if event.event == event_name and event.session_id}


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    index = max(0, min(len(sorted_values) - 1, math.ceil((pct / 100.0) * len(sorted_values)) - 1))
    return sorted_values[index]


def build_funnel_metrics(events: list[NormalizedEvent]) -> FunnelMetrics:
    event_counts = {event_name: 0 for event_name in REQUIRED_ACTIVATION_EVENTS}
    for event in events:
        if event.event in event_counts:
            event_counts[event.event] += 1

    landing_sessions = _sessions_for_event(events, "ff_landing_view")
    panel_sessions = _sessions_for_event(events, "ff_calculator_panel_open")
    submit_sessions = _sessions_for_event(events, "ff_calculation_submit")
    success_sessions = _sessions_for_event(events, "ff_calculation_success")
    error_sessions = _sessions_for_event(events, "ff_calculation_error")

    landing_to_panel_rate = _safe_rate(len(landing_sessions & panel_sessions), len(landing_sessions))
    panel_to_submit_rate = _safe_rate(len(panel_sessions & submit_sessions), len(panel_sessions))
    submit_to_success_rate = _safe_rate(len(submit_sessions & success_sessions), len(submit_sessions))
    landing_to_success_rate = _safe_rate(len(landing_sessions & success_sessions), len(landing_sessions))
    calculation_error_rate = _safe_rate(
        event_counts["ff_calculation_error"],
        event_counts["ff_calculation_submit"],
    )
    calculation_error_session_rate = _safe_rate(
        len(submit_sessions & error_sessions),
        len(submit_sessions),
    )

    first_run_success_values = [
        event.time_to_first_success_ms
        for event in events
        if event.event == "ff_calculation_success"
        and event.time_to_first_success_ms is not None
        and event.is_first_run is not False
    ]
    median_time_to_first_success_ms = (
        median(first_run_success_values) if first_run_success_values else None
    )
    p90_time_to_first_success_ms = _percentile(first_run_success_values, 90.0)

    source_breakdown: dict[str, dict[str, float | int | None]] = {}
    for source in sorted({event.source for event in events if event.source}):
        source_events = [event for event in events if event.source == source]
        source_submit = [event for event in source_events if event.event == "ff_calculation_submit"]
        source_success = [event for event in source_events if event.event == "ff_calculation_success"]
        source_error = [event for event in source_events if event.event == "ff_calculation_error"]
        source_time_values = [
            event.time_to_first_success_ms
            for event in source_success
            if event.time_to_first_success_ms is not None and event.is_first_run is not False
        ]
        source_breakdown[source] = {
            "submit_events": len(source_submit),
            "success_events": len(source_success),
            "error_events": len(source_error),
            "submit_to_success_rate": _safe_rate(len(source_success), len(source_submit)),
            "median_time_to_first_success_ms": (
                median(source_time_values) if source_time_values else None
            ),
        }

    session_counts = {
        "landing_sessions": len(landing_sessions),
        "panel_sessions": len(panel_sessions),
        "submit_sessions": len(submit_sessions),
        "success_sessions": len(success_sessions),
        "error_sessions": len(error_sessions),
    }

    return FunnelMetrics(
        event_counts=event_counts,
        session_counts=session_counts,
        landing_to_panel_rate=landing_to_panel_rate,
        panel_to_submit_rate=panel_to_submit_rate,
        submit_to_success_rate=submit_to_success_rate,
        landing_to_success_rate=landing_to_success_rate,
        calculation_error_rate=calculation_error_rate,
        calculation_error_session_rate=calculation_error_session_rate,
        median_time_to_first_success_ms=median_time_to_first_success_ms,
        p90_time_to_first_success_ms=p90_time_to_first_success_ms,
        source_breakdown=source_breakdown,
    )


def compare_rollout(
    current: FunnelMetrics,
    baseline: FunnelMetrics,
    *,
    min_improvement_pct: float,
    max_error_rate_increase_pp: float,
    max_submit_success_drop_pp: float,
) -> ComparisonResult:
    reasons: list[str] = []
    improvement_pct: float | None = None
    error_delta_pp: float | None = None
    submit_success_delta_pp: float | None = None

    if (
        baseline.median_time_to_first_success_ms is not None
        and current.median_time_to_first_success_ms is not None
        and baseline.median_time_to_first_success_ms > 0
    ):
        improvement_pct = (
            (baseline.median_time_to_first_success_ms - current.median_time_to_first_success_ms)
            / baseline.median_time_to_first_success_ms
        ) * 100.0

    if baseline.calculation_error_rate is not None and current.calculation_error_rate is not None:
        error_delta_pp = (current.calculation_error_rate - baseline.calculation_error_rate) * 100.0

    if baseline.submit_to_success_rate is not None and current.submit_to_success_rate is not None:
        submit_success_delta_pp = (
            (current.submit_to_success_rate - baseline.submit_to_success_rate) * 100.0
        )

    passes_improvement = improvement_pct is not None and improvement_pct >= min_improvement_pct
    passes_error = error_delta_pp is None or error_delta_pp <= max_error_rate_increase_pp
    passes_submit_success = (
        submit_success_delta_pp is None or submit_success_delta_pp >= (-1.0 * max_submit_success_drop_pp)
    )

    if passes_improvement and passes_error and passes_submit_success:
        decision = "expand"
        reasons.append("Activation KPI and guardrails meet rollout thresholds.")
    else:
        severe_error_regression = (
            error_delta_pp is not None and error_delta_pp > (max_error_rate_increase_pp * 2.0)
        )
        severe_submit_drop = (
            submit_success_delta_pp is not None
            and submit_success_delta_pp < (-2.0 * max_submit_success_drop_pp)
        )
        severe_time_regression = improvement_pct is not None and improvement_pct < 0.0
        if severe_error_regression or severe_submit_drop or severe_time_regression:
            decision = "rollback"
            reasons.append("Severe regression detected in guardrails or activation speed.")
        else:
            decision = "hold"
            reasons.append("Mixed results; keep current rollout while gathering more data.")
        if improvement_pct is None:
            reasons.append("Missing baseline/current time-to-first-success values.")
        elif improvement_pct < min_improvement_pct:
            reasons.append(
                f"Time-to-first-success improvement {improvement_pct:.2f}% < target {min_improvement_pct:.2f}%."
            )
        if error_delta_pp is not None and error_delta_pp > max_error_rate_increase_pp:
            reasons.append(
                f"Calculation error rate increased by {error_delta_pp:.2f} pp (limit {max_error_rate_increase_pp:.2f} pp)."
            )
        if (
            submit_success_delta_pp is not None
            and submit_success_delta_pp < (-1.0 * max_submit_success_drop_pp)
        ):
            reasons.append(
                "Submit-to-success conversion dropped by "
                f"{abs(submit_success_delta_pp):.2f} pp "
                f"(limit {max_submit_success_drop_pp:.2f} pp)."
            )

    return ComparisonResult(
        decision=decision,
        time_to_first_success_improvement_pct=improvement_pct,
        calculation_error_rate_delta_pp=error_delta_pp,
        submit_to_success_rate_delta_pp=submit_success_delta_pp,
        reasons=reasons,
    )


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value * 100.0:.2f}%"


def _format_pp(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f} pp"


def _format_ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0f} ms"


def _print_contract_report(report: ContractReport) -> None:
    print("Contract Check")
    print("--------------")
    print(f"Missing required events: {', '.join(report.missing_events) if report.missing_events else 'none'}")
    for event_name in REQUIRED_ACTIVATION_EVENTS:
        field_counts = report.missing_field_counts.get(event_name, {})
        missing_fields = ", ".join(
            f"{field}={count}" for field, count in field_counts.items() if count > 0
        ) or "none"
        missing_session = report.missing_session_id_counts.get(event_name, 0)
        print(f"- {event_name}: missing fields [{missing_fields}] | missing session_id rows={missing_session}")
    print()


def _print_funnel_metrics(title: str, metrics: FunnelMetrics) -> None:
    print(title)
    print("-" * len(title))
    print(
        "Event counts:"
        f" landing={metrics.event_counts['ff_landing_view']}"
        f" panel_open={metrics.event_counts['ff_calculator_panel_open']}"
        f" submit={metrics.event_counts['ff_calculation_submit']}"
        f" success={metrics.event_counts['ff_calculation_success']}"
        f" error={metrics.event_counts['ff_calculation_error']}"
    )
    print(
        "Session counts:"
        f" landing={metrics.session_counts['landing_sessions']}"
        f" panel_open={metrics.session_counts['panel_sessions']}"
        f" submit={metrics.session_counts['submit_sessions']}"
        f" success={metrics.session_counts['success_sessions']}"
        f" error={metrics.session_counts['error_sessions']}"
    )
    print(
        "Funnel rates:"
        f" landing->panel={_format_pct(metrics.landing_to_panel_rate)}"
        f" panel->submit={_format_pct(metrics.panel_to_submit_rate)}"
        f" submit->success={_format_pct(metrics.submit_to_success_rate)}"
        f" landing->success={_format_pct(metrics.landing_to_success_rate)}"
    )
    print(
        "Guardrails:"
        f" calculation_error_rate={_format_pct(metrics.calculation_error_rate)}"
        f" calculation_error_session_rate={_format_pct(metrics.calculation_error_session_rate)}"
    )
    print(
        "First-run speed:"
        f" median={_format_ms(metrics.median_time_to_first_success_ms)}"
        f" p90={_format_ms(metrics.p90_time_to_first_success_ms)}"
    )
    if metrics.source_breakdown:
        print("Source breakdown:")
        for source, summary in metrics.source_breakdown.items():
            submit_events = summary.get("submit_events")
            success_events = summary.get("success_events")
            error_events = summary.get("error_events")
            submit_to_success = summary.get("submit_to_success_rate")
            median_ttf = summary.get("median_time_to_first_success_ms")
            print(
                f"- {source}: submit={submit_events} success={success_events} error={error_events}"
                f" submit->success={_format_pct(submit_to_success if isinstance(submit_to_success, float) else None)}"
                f" median_ttf={_format_ms(median_ttf if isinstance(median_ttf, (int, float)) else None)}"
            )
    print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate activation analytics exports and compute rollout readouts."
    )
    parser.add_argument("--input", required=True, type=Path, help="Current window event export file.")
    parser.add_argument(
        "--format",
        default="auto",
        choices=("auto", "csv", "json", "jsonl"),
        help="Input format for --input (default: auto by extension).",
    )
    parser.add_argument("--baseline", type=Path, help="Baseline window event export file.")
    parser.add_argument(
        "--baseline-format",
        default="auto",
        choices=("auto", "csv", "json", "jsonl"),
        help="Input format for --baseline (default: auto by extension).",
    )
    parser.add_argument(
        "--strict-contract",
        action="store_true",
        help="Exit non-zero when contract validation finds missing events/fields/session_ids.",
    )
    parser.add_argument(
        "--min-improvement-pct",
        type=float,
        default=30.0,
        help="Minimum time-to-first-success improvement percentage for expand decision.",
    )
    parser.add_argument(
        "--max-error-rate-increase-pp",
        type=float,
        default=0.5,
        help="Maximum allowed calculation error-rate increase in percentage points.",
    )
    parser.add_argument(
        "--max-submit-success-drop-pp",
        type=float,
        default=1.0,
        help="Maximum allowed submit-to-success conversion drop in percentage points.",
    )
    parser.add_argument(
        "--json-output",
        action="store_true",
        help="Print machine-readable JSON instead of text output.",
    )
    return parser


def _as_json_payload(
    current_contract: ContractReport,
    current_metrics: FunnelMetrics,
    baseline_metrics: FunnelMetrics | None,
    comparison: ComparisonResult | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "current_contract": asdict(current_contract),
        "current_metrics": asdict(current_metrics),
    }
    if baseline_metrics is not None:
        payload["baseline_metrics"] = asdict(baseline_metrics)
    if comparison is not None:
        payload["comparison"] = asdict(comparison)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    current_events = load_events(args.input, fmt=args.format)
    current_contract = validate_event_contract(current_events)
    current_metrics = build_funnel_metrics(current_events)

    baseline_metrics: FunnelMetrics | None = None
    comparison: ComparisonResult | None = None
    if args.baseline:
        baseline_events = load_events(args.baseline, fmt=args.baseline_format)
        baseline_metrics = build_funnel_metrics(baseline_events)
        comparison = compare_rollout(
            current_metrics,
            baseline_metrics,
            min_improvement_pct=args.min_improvement_pct,
            max_error_rate_increase_pp=args.max_error_rate_increase_pp,
            max_submit_success_drop_pp=args.max_submit_success_drop_pp,
        )

    if args.json_output:
        print(
            json.dumps(
                _as_json_payload(current_contract, current_metrics, baseline_metrics, comparison),
                indent=2,
                sort_keys=True,
            )
        )
    else:
        _print_contract_report(current_contract)
        _print_funnel_metrics("Current Window", current_metrics)
        if baseline_metrics is not None:
            _print_funnel_metrics("Baseline Window", baseline_metrics)
        if comparison is not None:
            print("Rollout Decision")
            print("----------------")
            print(f"Decision: {comparison.decision}")
            improvement_display = (
                f"{comparison.time_to_first_success_improvement_pct:.2f}%"
                if comparison.time_to_first_success_improvement_pct is not None
                else "n/a"
            )
            print(
                "Delta summary:"
                f" time_to_first_success_improvement={improvement_display}"
                f" error_rate_delta={_format_pp(comparison.calculation_error_rate_delta_pp)}"
                f" submit_to_success_delta={_format_pp(comparison.submit_to_success_rate_delta_pp)}"
            )
            print("Reasons:")
            for reason in comparison.reasons:
                print(f"- {reason}")

    if args.strict_contract and current_contract.has_errors:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
