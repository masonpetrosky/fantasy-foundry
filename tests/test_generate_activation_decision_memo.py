from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_activation_decision_memo.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("generate_activation_decision_memo", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample_readout_payload() -> dict:
    return {
        "current_contract": {
            "missing_events": [],
            "missing_field_counts": {
                "ff_landing_view": {"source": 0, "is_first_run": 0},
                "ff_quickstart_cta_click": {"source": 0, "mode": 0},
                "ff_calculator_panel_open": {"source": 0},
                "ff_calculation_submit": {"source": 0, "scoring_mode": 0, "teams": 0, "horizon": 0},
                "ff_calculation_success": {
                    "source": 0,
                    "scoring_mode": 0,
                    "teams": 0,
                    "horizon": 0,
                    "is_first_run": 0,
                    "time_to_first_success_ms": 0,
                },
                "ff_calculation_error": {"source": 0, "error_message": 0},
            },
            "missing_session_id_counts": {
                "ff_landing_view": 0,
                "ff_quickstart_cta_click": 0,
                "ff_calculator_panel_open": 0,
                "ff_calculation_submit": 0,
                "ff_calculation_success": 0,
                "ff_calculation_error": 0,
            },
        },
        "current_metrics": {
            "landing_to_panel_rate": 0.5,
            "panel_to_submit_rate": 0.6,
            "submit_to_success_rate": 0.8,
            "landing_to_success_rate": 0.24,
            "calculation_error_rate": 0.05,
            "median_time_to_first_success_ms": 70000.0,
        },
        "baseline_metrics": {
            "landing_to_panel_rate": 0.4,
            "panel_to_submit_rate": 0.5,
            "submit_to_success_rate": 0.82,
            "landing_to_success_rate": 0.19,
            "calculation_error_rate": 0.04,
            "median_time_to_first_success_ms": 110000.0,
        },
        "comparison": {
            "decision": "hold",
            "time_to_first_success_improvement_pct": 36.36,
            "calculation_error_rate_delta_pp": 1.0,
            "submit_to_success_rate_delta_pp": -2.0,
            "reasons": ["Example reason"],
        },
    }


def test_build_memo_markdown_contains_decision_and_table_rows():
    module = _load_module()
    markdown = module.build_memo_markdown(
        readout_payload=_sample_readout_payload(),
        memo_date="2026-02-25",
        owner="Analytics Team",
        release_commit="abc1234",
        current_window_label="Current 24h",
        baseline_window_label="Baseline 24h",
        readout_json_path=Path("tmp/activation_readout_2026-02-25.json"),
    )

    assert "# Activation Rollout Decision - 2026-02-25" in markdown
    assert "Decision: **HOLD**" in markdown
    assert "| Submit -> Success |" in markdown
    assert "Example reason" in markdown


def test_cli_writes_markdown_file(tmp_path):
    readout_path = tmp_path / "readout.json"
    output_path = tmp_path / "memo.md"
    readout_path.write_text(json.dumps(_sample_readout_payload()), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--readout-json",
            str(readout_path),
            "--output",
            str(output_path),
            "--memo-date",
            "2026-02-25",
            "--owner",
            "Analytics Team",
            "--release-commit",
            "abc1234",
        ],
        check=True,
    )

    content = output_path.read_text(encoding="utf-8")
    assert "Activation Rollout Decision - 2026-02-25" in content
    assert "Owner: Analytics Team" in content
