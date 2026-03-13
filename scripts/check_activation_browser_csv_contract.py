#!/usr/bin/env python3
"""Verify browser-exported activation CSV remains compatible with readout contract.

This check generates a sample CSV using frontend `analyticsEventsToCsv`, then
parses/validates it with `scripts/activation_readout.py`. It fails fast if the
frontend export schema drifts from the rollout readout expectations.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def _load_activation_readout_module(repo_root: Path):
    script_path = repo_root / "scripts" / "activation_readout.py"
    spec = importlib.util.spec_from_file_location("activation_readout", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load activation_readout module from {script_path}.")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _generate_browser_csv(repo_root: Path) -> str:
    node = shutil.which("node")
    if not node:
        raise RuntimeError("Node.js is required for this check but was not found on PATH.")

    sample_events = [
        {
            "event": "ff_landing_view",
            "timestamp": 1700000000000,
            "properties": {
                "session_id": "session-a",
                "source": "app_boot",
                "is_first_run": True,
                "section": "projections",
                "data_version": "v-test",
            },
        },
        {
            "event": "ff_quickstart_cta_click",
            "timestamp": 1700000000500,
            "properties": {
                "session_id": "session-a",
                "source": "activation_strip",
                "mode": "roto",
                "is_first_run": True,
                "section": "projections",
                "data_version": "v-test",
            },
        },
        {
            "event": "ff_calculator_panel_open",
            "timestamp": 1700000001000,
            "properties": {
                "session_id": "session-a",
                "source": "activation_strip",
                "section": "projections",
                "data_version": "v-test",
            },
        },
        {
            "event": "ff_calculation_submit",
            "timestamp": 1700000001500,
            "properties": {
                "session_id": "session-a",
                "source": "quickstart",
                "scoring_mode": "roto",
                "teams": 12,
                "horizon": 20,
                "section": "projections",
                "data_version": "v-test",
            },
        },
        {
            "event": "ff_calculation_success",
            "timestamp": 1700000002500,
            "properties": {
                "session_id": "session-a",
                "source": "quickstart",
                "scoring_mode": "roto",
                "teams": 12,
                "horizon": 20,
                "is_first_run": True,
                "time_to_first_success_ms": 42000,
                "job_id": "job-1",
                "section": "projections",
                "data_version": "v-test",
            },
        },
        {
            "event": "ff_calculation_error",
            "timestamp": 1700000003500,
            "properties": {
                "session_id": "session-b",
                "source": "manual",
                "error_message": "Calculation failed",
                "section": "projections",
                "data_version": "v-test",
            },
        },
    ]

    node_script = (
        "import { analyticsEventsToCsv } from './src/analytics.ts';\n"
        f"const events = {json.dumps(sample_events)};\n"
        "process.stdout.write(analyticsEventsToCsv(events));\n"
    )

    completed = subprocess.run(
        [node, "--input-type=module", "-e", node_script],
        cwd=repo_root / "frontend",
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "Failed to generate browser analytics CSV via Node.\n"
            f"stderr:\n{completed.stderr.strip()}"
        )
    csv_text = completed.stdout
    if not csv_text.strip():
        raise RuntimeError("Generated browser analytics CSV was empty.")
    return csv_text


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    activation_readout = _load_activation_readout_module(repo_root)
    csv_text = _generate_browser_csv(repo_root)

    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".csv", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(csv_text)

    try:
        events = activation_readout.load_events(tmp_path, fmt="csv")
        if not events:
            raise RuntimeError("Activation readout parser returned no events from generated browser CSV.")

        report = activation_readout.validate_event_contract(events)
        if report.has_errors:
            raise RuntimeError(
                "Activation contract validation failed for generated browser CSV.\n"
                f"missing_events={report.missing_events}\n"
                f"missing_field_counts={report.missing_field_counts}\n"
                f"missing_session_id_counts={report.missing_session_id_counts}"
            )
    finally:
        tmp_path.unlink(missing_ok=True)

    print("Browser analytics CSV contract check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
