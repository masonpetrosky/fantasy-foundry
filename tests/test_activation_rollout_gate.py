from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "activation_rollout_gate.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("activation_rollout_gate", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sample_checkpoint_payload(*, decision: str, contract_ok: bool = True) -> dict:
    return {
        "current_contract": {
            "missing_events": [] if contract_ok else ["ff_quickstart_cta_click"],
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
        "comparison": {
            "decision": decision,
            "time_to_first_success_improvement_pct": 32.0,
            "calculation_error_rate_delta_pp": 0.1,
            "submit_to_success_rate_delta_pp": -0.3,
            "reasons": [f"{decision} reason"],
        },
    }


def test_build_rollout_gate_payload_expands_when_both_checkpoints_expand():
    module = _load_module()
    payload = module.build_rollout_gate_payload(
        readout_24h=_sample_checkpoint_payload(decision="expand"),
        readout_48h=_sample_checkpoint_payload(decision="expand"),
        readout_24h_path=Path("tmp/activation_readout_2026-02-26.json"),
        readout_48h_path=Path("tmp/activation_readout_2026-02-27.json"),
        checkpoint_24h_label="24h",
        checkpoint_48h_label="48h",
    )

    assert payload["decision"] == "expand"
    assert payload["checkpoints"][0]["contract_pass"] is True
    assert payload["checkpoints"][1]["contract_pass"] is True
    assert "Both 24h and 48h checkpoints met expand criteria." in payload["reasons"]


def test_build_rollout_gate_payload_rolls_back_if_any_checkpoint_rolls_back():
    module = _load_module()
    payload = module.build_rollout_gate_payload(
        readout_24h=_sample_checkpoint_payload(decision="expand"),
        readout_48h=_sample_checkpoint_payload(decision="rollback"),
        readout_24h_path=Path("tmp/activation_readout_2026-02-26.json"),
        readout_48h_path=Path("tmp/activation_readout_2026-02-27.json"),
        checkpoint_24h_label="24h",
        checkpoint_48h_label="48h",
    )

    assert payload["decision"] == "rollback"
    assert payload["recommended_action"].startswith("Rollback activation rollout")


def test_build_rollout_gate_payload_holds_when_contract_fails():
    module = _load_module()
    payload = module.build_rollout_gate_payload(
        readout_24h=_sample_checkpoint_payload(decision="expand", contract_ok=False),
        readout_48h=_sample_checkpoint_payload(decision="expand", contract_ok=True),
        readout_24h_path=Path("tmp/activation_readout_2026-02-26.json"),
        readout_48h_path=Path("tmp/activation_readout_2026-02-27.json"),
        checkpoint_24h_label="24h",
        checkpoint_48h_label="48h",
    )

    assert payload["decision"] == "hold"
    assert payload["checkpoints"][0]["contract_pass"] is False
    assert "failed strict event contract validation" in " ".join(payload["reasons"])


def test_cli_writes_json_and_markdown(tmp_path):
    readout_24h = tmp_path / "activation_readout_2026-02-26.json"
    readout_48h = tmp_path / "activation_readout_2026-02-27.json"
    output_json = tmp_path / "activation_rollout_gate_2026-02-27.json"
    output_markdown = tmp_path / "activation-rollout-final-decision-2026-02-27.md"

    readout_24h.write_text(json.dumps(_sample_checkpoint_payload(decision="expand")), encoding="utf-8")
    readout_48h.write_text(json.dumps(_sample_checkpoint_payload(decision="hold")), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--readout-24h",
            str(readout_24h),
            "--readout-48h",
            str(readout_48h),
            "--output-json",
            str(output_json),
            "--output-markdown",
            str(output_markdown),
            "--memo-date",
            "2026-02-27",
            "--owner",
            "Analytics Team",
            "--release-commit",
            "abc1234",
        ],
        check=True,
    )

    gate_payload = json.loads(output_json.read_text(encoding="utf-8"))
    markdown = output_markdown.read_text(encoding="utf-8")
    assert gate_payload["decision"] == "hold"
    assert "# Activation Rollout Final Decision - 2026-02-27" in markdown
    assert "Decision: **HOLD**" in markdown
