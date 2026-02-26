from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "activation_readout.py"


def _load_activation_readout_module():
    spec = importlib.util.spec_from_file_location("activation_readout", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _event(module, **overrides):
    base = {
        "event": "ff_landing_view",
        "session_id": "session-1",
        "timestamp": "2026-02-25T00:00:00Z",
        "source": "hero_cta",
        "mode": "roto",
        "scoring_mode": "roto",
        "teams": 12.0,
        "horizon": 20.0,
        "is_first_run": True,
        "time_to_first_success_ms": None,
        "error_message": "",
    }
    base.update(overrides)
    return module.NormalizedEvent(**base)


def test_validate_event_contract_detects_missing_fields_and_events():
    module = _load_activation_readout_module()
    events = [
        _event(module, event="ff_landing_view", source="", is_first_run=True),
        _event(
            module,
            event="ff_calculation_submit",
            source="hero_cta",
            scoring_mode="roto",
            teams=None,
            horizon=None,
        ),
    ]

    report = module.validate_event_contract(events)

    assert "ff_quickstart_cta_click" in report.missing_events
    assert report.missing_field_counts["ff_landing_view"]["source"] == 1
    assert report.missing_field_counts["ff_calculation_submit"]["teams"] == 1
    assert report.missing_field_counts["ff_calculation_submit"]["horizon"] == 1


def test_build_funnel_metrics_computes_expected_rates_and_time():
    module = _load_activation_readout_module()
    events = [
        _event(module, event="ff_landing_view", session_id="s1"),
        _event(module, event="ff_calculator_panel_open", session_id="s1"),
        _event(module, event="ff_calculation_submit", session_id="s1"),
        _event(
            module,
            event="ff_calculation_success",
            session_id="s1",
            time_to_first_success_ms=60000.0,
            is_first_run=True,
        ),
        _event(module, event="ff_landing_view", session_id="s2"),
        _event(module, event="ff_calculator_panel_open", session_id="s2"),
        _event(module, event="ff_calculation_submit", session_id="s2"),
        _event(module, event="ff_calculation_error", session_id="s2", error_message="timeout"),
        _event(module, event="ff_landing_view", session_id="s3"),
    ]

    metrics = module.build_funnel_metrics(events)

    assert metrics.event_counts["ff_calculation_submit"] == 2
    assert metrics.session_counts["landing_sessions"] == 3
    assert math.isclose(metrics.landing_to_panel_rate, 2 / 3)
    assert math.isclose(metrics.panel_to_submit_rate, 1.0)
    assert math.isclose(metrics.submit_to_success_rate, 0.5)
    assert math.isclose(metrics.landing_to_success_rate, 1 / 3)
    assert math.isclose(metrics.calculation_error_rate, 0.5)
    assert math.isclose(metrics.calculation_error_session_rate, 0.5)
    assert metrics.median_time_to_first_success_ms == 60000.0
    assert metrics.p90_time_to_first_success_ms == 60000.0


def test_compare_rollout_returns_expand_when_targets_are_met():
    module = _load_activation_readout_module()
    baseline_events = [
        _event(module, event="ff_landing_view", session_id="s1"),
        _event(module, event="ff_calculator_panel_open", session_id="s1"),
        _event(module, event="ff_calculation_submit", session_id="s1"),
        _event(
            module,
            event="ff_calculation_success",
            session_id="s1",
            time_to_first_success_ms=120000.0,
            is_first_run=True,
        ),
    ]
    current_events = [
        _event(module, event="ff_landing_view", session_id="s1"),
        _event(module, event="ff_calculator_panel_open", session_id="s1"),
        _event(module, event="ff_calculation_submit", session_id="s1"),
        _event(
            module,
            event="ff_calculation_success",
            session_id="s1",
            time_to_first_success_ms=70000.0,
            is_first_run=True,
        ),
    ]
    baseline_metrics = module.build_funnel_metrics(baseline_events)
    current_metrics = module.build_funnel_metrics(current_events)

    comparison = module.compare_rollout(
        current_metrics,
        baseline_metrics,
        min_improvement_pct=30.0,
        max_error_rate_increase_pp=0.5,
        max_submit_success_drop_pp=1.0,
    )

    assert comparison.decision == "expand"
    assert comparison.time_to_first_success_improvement_pct is not None
    assert comparison.time_to_first_success_improvement_pct >= 30.0


def test_compare_rollout_returns_rollback_on_severe_regression():
    module = _load_activation_readout_module()
    baseline_events = [
        _event(module, event="ff_landing_view", session_id="s1"),
        _event(module, event="ff_calculator_panel_open", session_id="s1"),
        _event(module, event="ff_calculation_submit", session_id="s1"),
        _event(
            module,
            event="ff_calculation_success",
            session_id="s1",
            time_to_first_success_ms=70000.0,
            is_first_run=True,
        ),
    ]
    current_events = [
        _event(module, event="ff_landing_view", session_id="s1"),
        _event(module, event="ff_calculator_panel_open", session_id="s1"),
        _event(module, event="ff_calculation_submit", session_id="s1"),
        _event(module, event="ff_calculation_error", session_id="s1", error_message="500"),
    ]
    baseline_metrics = module.build_funnel_metrics(baseline_events)
    current_metrics = module.build_funnel_metrics(current_events)

    comparison = module.compare_rollout(
        current_metrics,
        baseline_metrics,
        min_improvement_pct=30.0,
        max_error_rate_increase_pp=0.5,
        max_submit_success_drop_pp=1.0,
    )

    assert comparison.decision == "rollback"


def test_load_events_supports_csv_alias_columns(tmp_path):
    module = _load_activation_readout_module()
    csv_path = tmp_path / "events.csv"
    csv_path.write_text(
        "\n".join(
            [
                "event_name,session,source,mode,teams,horizon,is_first_run,time_to_first_success_ms,timestamp_ms",
                "ff_quickstart_cta_click,s-1,hero_cta,roto,12,20,true,,1700000000000",
                "ff_calculation_success,s-1,hero_cta,roto,12,20,true,65000,1700000005000",
            ]
        ),
        encoding="utf-8",
    )

    events = module.load_events(csv_path, fmt="csv")

    assert len(events) == 2
    assert events[0].event == "ff_quickstart_cta_click"
    assert events[0].session_id == "s-1"
    assert events[0].timestamp == "1700000000000"
    assert events[1].time_to_first_success_ms == 65000.0
