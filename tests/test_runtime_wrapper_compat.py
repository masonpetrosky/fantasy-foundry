from __future__ import annotations

import pandas as pd

from backend import runtime
from backend.core import runtime_state_helpers


def test_runtime_validate_configuration_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_validate(*, state):
        calls["state"] = state

    monkeypatch.setattr(runtime_state_helpers, "validate_runtime_configuration", fake_validate)
    runtime._validate_runtime_configuration()
    assert calls["state"] is runtime


def test_runtime_inspect_precomputed_lookup_delegates(monkeypatch) -> None:
    sentinel = runtime.DynastyLookupCacheInspection(status="ready", expected_version="v1")
    calls: dict[str, object] = {}

    def fake_inspect(*, state):
        calls["state"] = state
        return sentinel

    monkeypatch.setattr(runtime_state_helpers, "inspect_precomputed_default_dynasty_lookup", fake_inspect)
    out = runtime._inspect_precomputed_default_dynasty_lookup()
    assert out is sentinel
    assert calls["state"] is runtime


def test_runtime_load_precomputed_lookup_delegates(monkeypatch) -> None:
    sentinel = ({"a": {}}, {"a": {}}, set(), ["Value_2026"])
    calls: dict[str, object] = {}

    def fake_load(*, state):
        calls["state"] = state
        return sentinel

    monkeypatch.setattr(runtime_state_helpers, "load_precomputed_default_dynasty_lookup", fake_load)
    out = runtime._load_precomputed_default_dynasty_lookup()
    assert out is sentinel
    assert calls["state"] is runtime


def test_runtime_common_frame_cached_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}
    sentinel = pd.DataFrame([{"Player": "A"}])

    def fake_common(*, state, **kwargs):
        calls["state"] = state
        calls["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(runtime_state_helpers, "calculate_common_dynasty_frame_cached", fake_common)
    runtime._calculate_common_dynasty_frame_cached.cache_clear()
    out = runtime._calculate_common_dynasty_frame_cached(
        teams=12,
        sims=10,
        horizon=3,
        discount=0.94,
        hit_c=1,
        hit_1b=1,
        hit_2b=1,
        hit_3b=1,
        hit_ss=1,
        hit_ci=1,
        hit_mi=1,
        hit_of=3,
        hit_ut=1,
        pit_p=4,
        pit_sp=0,
        pit_rp=0,
        bench=2,
        minors=0,
        ir=0,
        ip_min=0.0,
        ip_max=None,
        two_way="sum",
        start_year=2026,
        recent_projections=2,
        roto_hit_r=True,
    )
    assert out is sentinel
    assert calls["state"] is runtime
    assert isinstance(calls["kwargs"], dict)
    assert calls["kwargs"]["teams"] == 12
    assert calls["kwargs"]["roto_category_settings"] == {"roto_hit_r": True}


def test_runtime_points_frame_cached_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}
    sentinel = pd.DataFrame([{"Player": "B"}])

    def fake_points(*, state, **kwargs):
        calls["state"] = state
        calls["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(runtime_state_helpers, "calculate_points_dynasty_frame_cached", fake_points)
    runtime._calculate_points_dynasty_frame_cached.cache_clear()
    out = runtime._calculate_points_dynasty_frame_cached(
        teams=12,
        horizon=2,
        discount=0.94,
        hit_c=1,
        hit_1b=1,
        hit_2b=1,
        hit_3b=1,
        hit_ss=1,
        hit_ci=1,
        hit_mi=1,
        hit_of=3,
        hit_ut=1,
        pit_p=4,
        pit_sp=0,
        pit_rp=0,
        bench=2,
        minors=0,
        ir=0,
        two_way="sum",
        start_year=2026,
        recent_projections=1,
        pts_hit_1b=1.0,
        pts_hit_2b=2.0,
        pts_hit_3b=3.0,
        pts_hit_hr=4.0,
        pts_hit_r=1.0,
        pts_hit_rbi=1.0,
        pts_hit_sb=1.0,
        pts_hit_bb=1.0,
        pts_hit_so=-1.0,
        pts_pit_ip=3.0,
        pts_pit_w=5.0,
        pts_pit_l=-5.0,
        pts_pit_k=1.0,
        pts_pit_sv=5.0,
        pts_pit_svh=0.0,
        pts_pit_h=-1.0,
        pts_pit_er=-2.0,
        pts_pit_bb=-1.0,
    )
    assert out is sentinel
    assert calls["state"] is runtime
    assert isinstance(calls["kwargs"], dict)
    assert calls["kwargs"]["teams"] == 12
    assert calls["kwargs"]["pts_pit_bb"] == -1.0


def test_runtime_prewarm_and_overlay_and_service_delegates(monkeypatch) -> None:
    calls: dict[str, object] = {}

    def fake_prewarm(*, state):
        calls["prewarm_state"] = state

    def fake_overlay(*, state, job_id):
        calls["overlay"] = (state, job_id)
        return {"a": {"DynastyValue": 1.0}}

    def fake_service(*, state):
        calls["service_state"] = state
        return "service"

    def fake_log(*, state):
        calls["log_state"] = state

    monkeypatch.setattr(runtime_state_helpers, "prewarm_default_calculation_caches", fake_prewarm)
    monkeypatch.setattr(runtime_state_helpers, "calculator_overlay_values_for_job", fake_overlay)
    monkeypatch.setattr(runtime_state_helpers, "calculator_service_from_globals", fake_service)
    monkeypatch.setattr(runtime_state_helpers, "log_precomputed_dynasty_lookup_cache_status", fake_log)

    runtime._prewarm_default_calculation_caches()
    overlay = runtime._calculator_overlay_values_for_job("job-1")
    service = runtime._calculator_service_from_globals()
    runtime._log_precomputed_dynasty_lookup_cache_status()

    assert calls["prewarm_state"] is runtime
    assert calls["overlay"] == (runtime, "job-1")
    assert overlay == {"a": {"DynastyValue": 1.0}}
    assert calls["service_state"] is runtime
    assert service == "service"
    assert calls["log_state"] is runtime
