from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_gate_module():
    repo_root = Path(__file__).resolve().parent.parent
    script_path = repo_root / "scripts" / "check_projection_quality_report.py"
    spec = importlib.util.spec_from_file_location("projection_quality_gate", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_validate_projection_quality_report_accepts_valid_payload() -> None:
    module = _load_gate_module()
    payload = {
        "validation_window": {
            "min_year": 2026,
            "max_year": 2045,
            "expected_years": list(range(2026, 2046)),
        },
        "year_sets_match": True,
        "bat": {
            "invalid_year_values": 0,
            "blank_player_rows": 0,
            "blank_team_rows": 0,
            "date_coverage_pct": 100.0,
        },
        "pitch": {
            "invalid_year_values": 0,
            "blank_player_rows": 0,
            "blank_team_rows": 0,
            "date_coverage_pct": 99.5,
        },
    }

    violations = module.validate_projection_quality_report(payload, min_date_coverage_pct=95.0)

    assert violations == []


def test_validate_projection_quality_report_reports_guardrail_violations() -> None:
    module = _load_gate_module()
    payload = {
        "validation_window": {
            "min_year": 2026,
            "max_year": 2045,
            "expected_years": [2026, 2027],
        },
        "year_sets_match": False,
        "bat": {
            "invalid_year_values": 1,
            "blank_player_rows": 2,
            "blank_team_rows": 0,
            "date_coverage_pct": 80.0,
        },
        "pitch": {
            "invalid_year_values": 0,
            "blank_player_rows": 0,
            "blank_team_rows": 1,
            "date_coverage_pct": "not-a-number",
        },
    }

    violations = module.validate_projection_quality_report(payload, min_date_coverage_pct=95.0)

    assert any("bat: invalid_year_values=1" in issue for issue in violations)
    assert any("bat: blank_player_rows=2" in issue for issue in violations)
    assert any("bat: date_coverage_pct=80.0" in issue for issue in violations)
    assert any("pitch: blank_team_rows=1" in issue for issue in violations)
    assert any("pitch: date_coverage_pct is missing or non-numeric." in issue for issue in violations)
    assert any("year_sets_match must be true." in issue for issue in violations)
