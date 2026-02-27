"""Tests for league mode calculator API dispatch."""

from __future__ import annotations

import threading

import pandas as pd
import pytest
from pydantic import ValidationError

from backend.services.calculator.service import (
    CalculateRequest,
    CalculatorService,
    CalculatorServiceContext,
)


class _Logger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.exception_messages: list[str] = []

    def info(self, message: str, *args) -> None:
        rendered = message % args if args else message
        self.info_messages.append(rendered)

    def exception(self, message: str, *args) -> None:
        rendered = message % args if args else message
        self.exception_messages.append(rendered)


class _CacheCallable:
    def __init__(self, frame: pd.DataFrame) -> None:
        self._frame = frame
        self._hits = 0
        self._misses = 0
        self.call_count = 0

    def __call__(self, **_kwargs) -> pd.DataFrame:
        self._misses += 1
        self.call_count += 1
        return self._frame

    def cache_info(self):
        return type("CacheInfo", (), {"hits": self._hits, "misses": self._misses})()


def _build_service() -> tuple[CalculatorService, _CacheCallable, _CacheCallable, _CacheCallable]:
    result_cache: dict[str, dict] = {}
    logger = _Logger()

    cache_frame = pd.DataFrame(
        [
            {
                "Player": "Test Player",
                "Team": "SEA",
                "Pos": "OF",
                "Age": 24,
                "DynastyValue": 12.5,
                "RawDynastyValue": 12.5,
                "minor_eligible": False,
                "Value_2026": 4.0,
            }
        ]
    )
    cached_common = _CacheCallable(cache_frame)
    cached_points = _CacheCallable(cache_frame)
    cached_league = _CacheCallable(cache_frame)

    ctx = CalculatorServiceContext(
        refresh_data_if_needed=lambda: None,
        coerce_meta_years=lambda _meta: [2026],
        get_meta=lambda: {"years": [2026]},
        calc_result_cache_key=lambda settings: f"cache:{settings.get('mode', 'common')}:{settings.get('scoring_mode', 'roto')}",
        result_cache_get=lambda key: result_cache.get(key),
        result_cache_set=lambda key, payload: result_cache.__setitem__(key, payload),
        calculate_common_dynasty_frame_cached=cached_common,
        calculate_points_dynasty_frame_cached=cached_points,
        calculate_league_dynasty_frame_cached=cached_league,
        roto_category_settings_from_dict=lambda _settings: {},
        is_user_fixable_calculation_error=lambda message: False,
        player_identity_by_name=lambda: {},
        normalize_player_key=lambda value: str(value or "").strip().lower().replace(" ", "-"),
        player_key_col="PlayerKey",
        player_entity_key_col="PlayerEntityKey",
        selected_roto_categories=lambda _settings: (["AVG"], ["K"]),
        start_year_roto_stats_by_entity=lambda **_kwargs: {},
        projection_identity_key=lambda row: str(getattr(row, "get", lambda *_a: "")("PlayerEntityKey") or ""),
        build_calculation_explanations=lambda _out, *, settings: {},
        clean_records_for_json=lambda records: records,
        flatten_explanations_for_export=lambda explanations: [],
        tabular_export_response=lambda *_a, **_kw: {},
        calc_logger=logger,
        enforce_rate_limit=lambda _req, *, action, limit_per_minute: None,
        sync_rate_limit_per_minute=7,
        sync_auth_rate_limit_per_minute=19,
        job_create_rate_limit_per_minute=5,
        job_create_auth_rate_limit_per_minute=15,
        job_status_rate_limit_per_minute=11,
        job_status_auth_rate_limit_per_minute=31,
        client_ip=lambda _request: "127.0.0.1",
        iso_now=lambda: "2026-02-27T00:00:00Z",
        active_jobs_for_ip=lambda _ip: 0,
        calculator_max_active_jobs_per_ip=3,
        calculator_max_active_jobs_total=10,
        calculator_job_lock=threading.Lock(),
        calculator_jobs={},
        cleanup_calculation_jobs=lambda *_a, **_kw: None,
        cache_calculation_job_snapshot=lambda _job: None,
        cached_calculation_job_snapshot=lambda _jid: None,
        calculation_job_public_payload=lambda job: {"job_id": job.get("job_id"), "status": job.get("status")},
        mark_job_cancelled_locked=lambda _job: None,
        calculator_job_executor=type("Executor", (), {"submit": lambda self, fn, *a: None})(),
        calc_job_cancelled_status="cancelled",
    )
    service = CalculatorService(ctx)
    return service, cached_common, cached_points, cached_league


class _FakeRequest:
    class state:
        calc_api_key_authenticated = False


def test_league_mode_dispatches_to_league_calculator() -> None:
    """League mode request should call the league calculator, not common."""
    service, cached_common, cached_points, cached_league = _build_service()
    req = CalculateRequest(mode="league", scoring_mode="roto")
    result = service.calculate_dynasty_values(req, _FakeRequest())
    assert cached_league.call_count == 1
    assert cached_common.call_count == 0
    assert cached_points.call_count == 0
    assert result["total"] == 1
    assert result["data"][0]["Player"] == "Test Player"


def test_common_mode_dispatches_to_common_calculator() -> None:
    """Common mode request should call the common calculator, not league."""
    service, cached_common, cached_points, cached_league = _build_service()
    req = CalculateRequest(mode="common", scoring_mode="roto")
    service.calculate_dynasty_values(req, _FakeRequest())
    assert cached_common.call_count == 1
    assert cached_league.call_count == 0


def test_league_mode_rejects_points_scoring() -> None:
    """League mode + points scoring should fail validation."""
    with pytest.raises(ValidationError, match="League mode only supports roto scoring"):
        CalculateRequest(mode="league", scoring_mode="points")


def test_league_mode_included_in_settings_dump() -> None:
    """The mode field should appear in the settings dump."""
    req = CalculateRequest(mode="league", scoring_mode="roto")
    settings = req.model_dump()
    assert settings["mode"] == "league"


def test_default_mode_is_common() -> None:
    """Default mode should be common when not specified."""
    req = CalculateRequest()
    assert req.mode == "common"
