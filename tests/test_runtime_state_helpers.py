from __future__ import annotations

import threading
from types import SimpleNamespace

from backend.core import runtime_state_helpers


def _overlay_state(*, jobs: dict[str, dict]) -> SimpleNamespace:
    return SimpleNamespace(
        CALCULATOR_JOB_LOCK=threading.Lock(),
        CALCULATOR_JOBS=jobs,
        _cached_calculation_job_snapshot=lambda _job_id: None,
        PLAYER_ENTITY_KEY_COL="PlayerEntityKey",
        PLAYER_KEY_COL="PlayerKey",
    )


def test_calculator_overlay_values_for_job_includes_points_and_stat_dynasty_fields() -> None:
    state = _overlay_state(
        jobs={
            "job-1": {
                "job_id": "job-1",
                "status": "completed",
                "result": {
                    "data": [
                        {
                            "PlayerEntityKey": "alpha",
                            "PlayerKey": "alpha",
                            "DynastyValue": 12.5,
                            "Value_2026": 11.0,
                            "StatDynasty_HR": 2.4,
                            "SelectedPoints": 18.5,
                            "HittingPoints": 20.0,
                            "KeepDropKeep": False,
                            "Team": "SEA",
                        }
                    ]
                },
            }
        }
    )

    overlay = runtime_state_helpers.calculator_overlay_values_for_job(
        state=state,
        job_id="job-1",
    )

    assert overlay == {
        "alpha": {
            "DynastyValue": 12.5,
            "Value_2026": 11.0,
            "StatDynasty_HR": 2.4,
            "SelectedPoints": 18.5,
            "HittingPoints": 20.0,
            "KeepDropKeep": False,
        }
    }
