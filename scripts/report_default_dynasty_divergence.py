#!/usr/bin/env python3
"""Profile-driven dynasty audit reporting for standard roto, deep roto, and points."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.core.calculator_helpers import with_resolved_hidden_dynasty_modeling_settings


def _resolved_dynasty_params(params: dict[str, Any]) -> dict[str, Any]:
    return with_resolved_hidden_dynasty_modeling_settings(params)


def _settings_snapshot(params: dict[str, Any]) -> dict[str, Any]:
    return {
        str(key): params[key]
        for key in sorted(params.keys(), key=str)
    }


def _replacement_depth_blend_alpha_by_slot_json(params: dict[str, Any]) -> str:
    raw_mapping = params.get("replacement_depth_blend_alpha_by_slot")
    if not isinstance(raw_mapping, dict) or not raw_mapping:
        return ""
    normalized: dict[str, float] = {}
    for raw_slot, raw_alpha in raw_mapping.items():
        slot = str(raw_slot or "").strip().upper()
        if not slot:
            continue
        try:
            alpha = float(raw_alpha)
        except (TypeError, ValueError):
            continue
        normalized[slot] = alpha
    if not normalized:
        return ""
    return json.dumps(normalized, sort_keys=True, separators=(",", ":"))


def _common_roto_snapshot(*, params: dict[str, Any]) -> dict[str, Any]:
    import backend.runtime as runtime

    params = _resolved_dynasty_params(params)
    out = runtime._calculate_common_dynasty_frame_cached(
        teams=int(params["teams"]),
        sims=int(params["sims"]),
        horizon=int(params["horizon"]),
        discount=float(params["discount"]),
        hit_c=int(params["hit_c"]),
        hit_1b=int(params["hit_1b"]),
        hit_2b=int(params["hit_2b"]),
        hit_3b=int(params["hit_3b"]),
        hit_ss=int(params["hit_ss"]),
        hit_ci=int(params["hit_ci"]),
        hit_mi=int(params["hit_mi"]),
        hit_of=int(params["hit_of"]),
        hit_dh=int(params.get("hit_dh", 0)),
        hit_ut=int(params["hit_ut"]),
        pit_p=int(params["pit_p"]),
        pit_sp=int(params["pit_sp"]),
        pit_rp=int(params["pit_rp"]),
        bench=int(params["bench"]),
        minors=int(params["minors"]),
        ir=int(params["ir"]),
        ip_min=float(params["ip_min"]),
        ip_max=params["ip_max"],
        two_way=str(params["two_way"]),
        start_year=int(params["start_year"]),
        sgp_denominator_mode=str(params.get("sgp_denominator_mode", "classic")),
        sgp_winsor_low_pct=float(params.get("sgp_winsor_low_pct", 0.10)),
        sgp_winsor_high_pct=float(params.get("sgp_winsor_high_pct", 0.90)),
        sgp_epsilon_counting=float(params.get("sgp_epsilon_counting", 0.15)),
        sgp_epsilon_ratio=float(params.get("sgp_epsilon_ratio", 0.0015)),
        enable_playing_time_reliability=bool(params.get("enable_playing_time_reliability", False)),
        enable_age_risk_adjustment=bool(params.get("enable_age_risk_adjustment", False)),
        enable_prospect_risk_adjustment=bool(params.get("enable_prospect_risk_adjustment", True)),
        enable_bench_stash_relief=bool(params.get("enable_bench_stash_relief", False)),
        bench_negative_penalty=float(params.get("bench_negative_penalty", 0.55)),
        enable_ir_stash_relief=bool(params.get("enable_ir_stash_relief", False)),
        ir_negative_penalty=float(params.get("ir_negative_penalty", 0.20)),
        enable_replacement_blend=bool(params.get("enable_replacement_blend", True)),
        replacement_blend_alpha=float(params.get("replacement_blend_alpha", 0.40)),
        replacement_depth_mode=str(params.get("replacement_depth_mode", "blended_depth")),
        replacement_depth_blend_alpha=float(params.get("replacement_depth_blend_alpha", 0.33)),
        replacement_depth_blend_alpha_by_slot_json=_replacement_depth_blend_alpha_by_slot_json(params),
        **runtime._roto_category_settings_from_dict(params),
    ).copy(deep=True)
    explanations = runtime._build_calculation_explanations(
        out,
        settings={**params, "scoring_mode": "roto"},
    )
    rows = (
        out.sort_values("DynastyValue", ascending=False)
        .reset_index(drop=True)[
            [
                "Player",
                runtime.PLAYER_KEY_COL,
                runtime.PLAYER_ENTITY_KEY_COL,
                "Team",
                "Pos",
                "DynastyValue",
                "RawDynastyValue",
            ]
        ]
        .to_dict(orient="records")
    )
    return {
        "rows": rows,
        "explanations": explanations,
        "methodology_fingerprint": runtime.core_default_dynasty_methodology_fingerprint(default_params=params),
        "settings_snapshot": _settings_snapshot(params),
        "valuation_diagnostics": out.attrs.get("valuation_diagnostics", {}),
    }


def _common_roto_league_settings(*, runtime_module: Any, params: dict[str, Any]) -> Any:
    from backend.valuation.models import CommonDynastyRotoSettings

    params = _resolved_dynasty_params(params)
    hitter_categories, pitcher_categories = runtime_module._selected_roto_categories(params)
    return CommonDynastyRotoSettings(
        n_teams=int(params["teams"]),
        sims_for_sgp=int(params["sims"]),
        horizon_years=int(params["horizon"]),
        discount=float(params["discount"]),
        hitter_slots={
            "C": int(params["hit_c"]),
            "1B": int(params["hit_1b"]),
            "2B": int(params["hit_2b"]),
            "3B": int(params["hit_3b"]),
            "SS": int(params["hit_ss"]),
            "CI": int(params["hit_ci"]),
            "MI": int(params["hit_mi"]),
            "OF": int(params["hit_of"]),
            "DH": int(params.get("hit_dh", 0)),
            "UT": int(params["hit_ut"]),
        },
        pitcher_slots={
            "P": int(params["pit_p"]),
            "SP": int(params["pit_sp"]),
            "RP": int(params["pit_rp"]),
        },
        bench_slots=int(params["bench"]),
        minor_slots=int(params["minors"]),
        ir_slots=int(params["ir"]),
        ip_min=float(params["ip_min"]),
        ip_max=params["ip_max"],
        two_way=str(params["two_way"]),
        sgp_denominator_mode=str(params.get("sgp_denominator_mode", "classic")),
        sgp_winsor_low_pct=float(params.get("sgp_winsor_low_pct", 0.10)),
        sgp_winsor_high_pct=float(params.get("sgp_winsor_high_pct", 0.90)),
        sgp_epsilon_counting=float(params.get("sgp_epsilon_counting", 0.15)),
        sgp_epsilon_ratio=float(params.get("sgp_epsilon_ratio", 0.0015)),
        enable_playing_time_reliability=bool(params.get("enable_playing_time_reliability", False)),
        enable_age_risk_adjustment=bool(params.get("enable_age_risk_adjustment", False)),
        enable_prospect_risk_adjustment=bool(params.get("enable_prospect_risk_adjustment", True)),
        enable_bench_stash_relief=bool(params.get("enable_bench_stash_relief", False)),
        bench_negative_penalty=float(params.get("bench_negative_penalty", 0.55)),
        enable_ir_stash_relief=bool(params.get("enable_ir_stash_relief", False)),
        ir_negative_penalty=float(params.get("ir_negative_penalty", 0.20)),
        enable_replacement_blend=bool(params.get("enable_replacement_blend", True)),
        replacement_blend_alpha=float(params.get("replacement_blend_alpha", 0.40)),
        replacement_depth_mode=str(params.get("replacement_depth_mode", "blended_depth")),
        replacement_depth_blend_alpha=float(params.get("replacement_depth_blend_alpha", 0.33)),
        replacement_depth_blend_alpha_by_slot={
            str(slot).strip().upper(): float(alpha)
            for slot, alpha in dict(params.get("replacement_depth_blend_alpha_by_slot") or {}).items()
            if str(slot).strip()
        },
        hitter_categories=tuple(hitter_categories),
        pitcher_categories=tuple(pitcher_categories),
    )


def _runtime_projection_frames(*, runtime_module: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
    bat = pd.DataFrame(runtime_module.BAT_DATA).copy(deep=True)
    pit = pd.DataFrame(runtime_module.PIT_DATA).copy(deep=True)

    for missing_col in ("BB", "HBP", "SF", "2B", "3B"):
        if missing_col not in bat.columns:
            bat[missing_col] = 0.0

    if "SV" not in pit.columns:
        if {"SVH", "HLD"}.issubset(pit.columns):
            pit["SV"] = (pit["SVH"] - pit["HLD"]).clip(lower=0.0).fillna(0.0)
        elif "SVH" in pit.columns:
            pit["SV"] = pit["SVH"].fillna(0.0)
        else:
            pit["SV"] = 0.0
    pit["SV"] = pit["SV"].fillna(0.0)

    if "SVH" not in pit.columns:
        if {"SV", "HLD"}.issubset(pit.columns):
            pit["SVH"] = pit["SV"].fillna(0.0) + pit["HLD"].fillna(0.0)
        else:
            pit["SVH"] = pit["SV"].fillna(0.0)
    pit["SVH"] = pit["SVH"].fillna(0.0)

    if "QS" not in pit.columns:
        pit["QS"] = pit["QA3"].fillna(0.0) if "QA3" in pit.columns else 0.0
    if "QA3" not in pit.columns:
        pit["QA3"] = pit["QS"].fillna(0.0) if "QS" in pit.columns else 0.0
    pit["QS"] = pit["QS"].fillna(0.0)
    pit["QA3"] = pit["QA3"].fillna(0.0)

    return bat, pit


def _start_year_projection_stats_by_entity(*, runtime_module: Any, start_year: int) -> dict[str, dict[str, float]]:
    stats_by_entity: dict[str, dict[str, float]] = {}
    hitter_fields = ("AB", "R", "HR", "RBI", "SB", "AVG", "OPS")
    pitcher_fields = ("IP", "W", "K", "ERA", "WHIP", "QS", "SV")

    def merge_rows(rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
        for row in rows:
            year = runtime_module._coerce_record_year(row.get("Year"))
            if year != int(start_year):
                continue
            entity_key = str(
                row.get(runtime_module.PLAYER_ENTITY_KEY_COL)
                or row.get(runtime_module.PLAYER_KEY_COL)
                or runtime_module._normalize_player_key(row.get("Player"))
            ).strip()
            if not entity_key:
                continue
            entry = stats_by_entity.setdefault(entity_key, {})
            for field in fields:
                value = runtime_module._coerce_numeric(row.get(field))
                if value is None:
                    continue
                entry[field] = float(value)

    merge_rows(runtime_module.BAT_DATA, hitter_fields)
    merge_rows(runtime_module.PIT_DATA, pitcher_fields)
    return stats_by_entity


def _raw_start_year_snapshot(*, params: dict[str, Any]) -> dict[str, Any]:
    import backend.runtime as runtime
    from backend.valuation.common_math import compute_year_context, compute_year_player_values
    from backend.valuation.two_way import combine_two_way

    start_year = int(params["start_year"])
    bat, pit = _runtime_projection_frames(runtime_module=runtime)
    lg = _common_roto_league_settings(runtime_module=runtime, params=params)
    ctx = compute_year_context(start_year, bat, pit, lg, rng_seed=start_year)
    hit_vals, pit_vals = compute_year_player_values(ctx, lg)
    combined = combine_two_way(hit_vals, pit_vals, two_way=lg.two_way).copy(deep=True)

    identity_by_name = runtime._player_identity_by_name()
    combined["Player"] = combined["Player"].astype("string").fillna("").str.strip()
    combined[runtime.PLAYER_KEY_COL] = combined["Player"].map(
        lambda name: (identity_by_name.get(str(name)) or (runtime._normalize_player_key(name), None))[0]
    )
    combined[runtime.PLAYER_ENTITY_KEY_COL] = combined["Player"].map(
        lambda name: (identity_by_name.get(str(name)) or (runtime._normalize_player_key(name), None))[1]
        or (identity_by_name.get(str(name)) or (runtime._normalize_player_key(name), None))[0]
    )
    sgp_cols = sorted([col for col in combined.columns if str(col).startswith("SGP_")])
    rows = (
        combined.sort_values("YearValue", ascending=False)
        .reset_index(drop=True)[
            [
                "Player",
                runtime.PLAYER_KEY_COL,
                runtime.PLAYER_ENTITY_KEY_COL,
                "Team",
                "Pos",
                "BestSlot",
                "YearValue",
                *sgp_cols,
            ]
        ]
        .to_dict(orient="records")
    )
    return {
        "rows": rows,
        "start_year_projection_stats_by_entity": _start_year_projection_stats_by_entity(
            runtime_module=runtime,
            start_year=start_year,
        ),
    }


def _default_roto_params(*, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.core.calculator_helpers import with_resolved_hidden_dynasty_modeling_settings
    import backend.runtime as runtime

    params = dict(runtime._default_calculation_cache_params())
    if isinstance(overrides, dict):
        params.update(overrides)
    return with_resolved_hidden_dynasty_modeling_settings(params)


def _deep_roto_params(*, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.core.calculator_helpers import with_resolved_hidden_dynasty_modeling_settings
    import backend.runtime as runtime
    from backend.core.calculator_helpers import PREWARM_CONFIGS

    params = dict(runtime._default_calculation_cache_params())
    deep_config = next(cfg for cfg in PREWARM_CONFIGS if cfg.get("label") == "12T-deep-dynasty-roto")
    params.update({key: value for key, value in deep_config.items() if key not in {"label", "mode"}})
    if isinstance(overrides, dict):
        params.update(overrides)
    return with_resolved_hidden_dynasty_modeling_settings(params)


def _slot_context_candidate_params() -> dict[str, dict[str, Any]]:
    base = _default_roto_params()
    matrix = (
        ("control", 0.33, 0.33),
        ("A", 0.25, 0.33),
        ("B", 0.20, 0.33),
        ("C", 0.33, 0.25),
        ("D", 0.33, 0.20),
        ("E", 0.25, 0.25),
        ("F", 0.20, 0.25),
    )
    out: dict[str, dict[str, Any]] = {}
    for candidate_id, of_alpha, p_alpha in matrix:
        params = dict(base)
        params["replacement_depth_mode"] = "blended_depth"
        params["replacement_depth_blend_alpha"] = 0.33
        if candidate_id != "control":
            params["replacement_depth_blend_alpha_by_slot"] = {
                "OF": of_alpha,
                "P": p_alpha,
            }
        out[candidate_id] = params
    return out


def _points_profile_params(profile_id: str, *, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.core.calculator_helpers import with_resolved_hidden_dynasty_modeling_settings
    import backend.runtime as runtime

    params = dict(runtime._default_calculation_cache_params())
    params.update(runtime.POINTS_HITTER_SLOT_DEFAULTS)
    params.update(runtime.POINTS_PITCHER_SLOT_DEFAULTS)
    params.update(runtime.DEFAULT_POINTS_SCORING)
    params["scoring_mode"] = "points"
    params["keeper_limit"] = None
    params["points_valuation_mode"] = "season_total"
    params["weekly_starts_cap"] = None
    params["allow_same_day_starts_overflow"] = False
    params["weekly_acquisition_cap"] = None
    params["ip_max"] = None
    mode_profile = str(profile_id or "").strip()
    if mode_profile == "points_weekly_h2h":
        params.update(
            {
                "points_valuation_mode": "weekly_h2h",
                "weekly_starts_cap": 7,
                "allow_same_day_starts_overflow": False,
                "weekly_acquisition_cap": 2,
            }
        )
    elif mode_profile == "points_daily_h2h":
        params.update(
            {
                "points_valuation_mode": "daily_h2h",
                "weekly_starts_cap": 7,
                "allow_same_day_starts_overflow": False,
                "weekly_acquisition_cap": 2,
            }
        )
    if isinstance(overrides, dict):
        params.update(overrides)
    return with_resolved_hidden_dynasty_modeling_settings(params)


def _points_snapshot(*, params: dict[str, Any]) -> dict[str, Any]:
    import backend.runtime as runtime

    out = runtime._calculate_points_dynasty_frame_cached(
        teams=int(params["teams"]),
        horizon=int(params["horizon"]),
        discount=float(params["discount"]),
        hit_c=int(params["hit_c"]),
        hit_1b=int(params["hit_1b"]),
        hit_2b=int(params["hit_2b"]),
        hit_3b=int(params["hit_3b"]),
        hit_ss=int(params["hit_ss"]),
        hit_ci=int(params["hit_ci"]),
        hit_mi=int(params["hit_mi"]),
        hit_of=int(params["hit_of"]),
        hit_dh=int(params.get("hit_dh", 0)),
        hit_ut=int(params["hit_ut"]),
        pit_p=int(params["pit_p"]),
        pit_sp=int(params["pit_sp"]),
        pit_rp=int(params["pit_rp"]),
        bench=int(params["bench"]),
        minors=int(params["minors"]),
        ir=int(params["ir"]),
        keeper_limit=params.get("keeper_limit"),
        two_way=str(params["two_way"]),
        points_valuation_mode=str(params.get("points_valuation_mode", "season_total")),
        weekly_starts_cap=params.get("weekly_starts_cap"),
        allow_same_day_starts_overflow=bool(params.get("allow_same_day_starts_overflow", False)),
        weekly_acquisition_cap=params.get("weekly_acquisition_cap"),
        start_year=int(params["start_year"]),
        pts_hit_1b=float(params["pts_hit_1b"]),
        pts_hit_2b=float(params["pts_hit_2b"]),
        pts_hit_3b=float(params["pts_hit_3b"]),
        pts_hit_hr=float(params["pts_hit_hr"]),
        pts_hit_r=float(params["pts_hit_r"]),
        pts_hit_rbi=float(params["pts_hit_rbi"]),
        pts_hit_sb=float(params["pts_hit_sb"]),
        pts_hit_bb=float(params["pts_hit_bb"]),
        pts_hit_hbp=float(params["pts_hit_hbp"]),
        pts_hit_so=float(params["pts_hit_so"]),
        pts_pit_ip=float(params["pts_pit_ip"]),
        pts_pit_w=float(params["pts_pit_w"]),
        pts_pit_l=float(params["pts_pit_l"]),
        pts_pit_k=float(params["pts_pit_k"]),
        pts_pit_sv=float(params["pts_pit_sv"]),
        pts_pit_hld=float(params["pts_pit_hld"]),
        pts_pit_h=float(params["pts_pit_h"]),
        pts_pit_er=float(params["pts_pit_er"]),
        pts_pit_bb=float(params["pts_pit_bb"]),
        pts_pit_hbp=float(params["pts_pit_hbp"]),
        ip_max=params.get("ip_max"),
        enable_prospect_risk_adjustment=bool(params.get("enable_prospect_risk_adjustment", True)),
        enable_bench_stash_relief=bool(params.get("enable_bench_stash_relief", False)),
        bench_negative_penalty=float(params.get("bench_negative_penalty", 0.55)),
        enable_ir_stash_relief=bool(params.get("enable_ir_stash_relief", False)),
        ir_negative_penalty=float(params.get("ir_negative_penalty", 0.20)),
    ).copy(deep=True)
    return _points_snapshot_payload(runtime_module=runtime, out=out, params=params)


def _points_snapshot_payload(*, runtime_module: Any, out: Any, params: dict[str, Any]) -> dict[str, Any]:
    explanations = runtime_module._build_calculation_explanations(
        out,
        settings={**params, "scoring_mode": "points"},
    )
    rows = (
        out.sort_values("DynastyValue", ascending=False)
        .reset_index(drop=True)[
            [
                "Player",
                runtime_module.PLAYER_KEY_COL,
                runtime_module.PLAYER_ENTITY_KEY_COL,
                "Team",
                "Pos",
                "DynastyValue",
                "RawDynastyValue",
                "SelectedPoints",
                "minor_eligible",
            ]
        ]
        .to_dict(orient="records")
    )
    return {
        "rows": rows,
        "explanations": explanations,
        "methodology_fingerprint": runtime_module.core_default_dynasty_methodology_fingerprint(default_params=params),
        "settings_snapshot": _settings_snapshot(params),
        "valuation_diagnostics": out.attrs.get("valuation_diagnostics", {}),
    }


def _points_hitter_row(
    *,
    player: str,
    player_key: str,
    year: int,
    age: int,
    pos: str = "OF",
    team: str = "SEA",
    ab: float,
    hits: float,
    doubles: float = 0.0,
    triples: float = 0.0,
    hr: float = 0.0,
    runs: float = 0.0,
    rbi: float = 0.0,
    sb: float = 0.0,
    bb: float = 0.0,
    hbp: float = 0.0,
    so: float = 0.0,
) -> dict[str, Any]:
    return {
        "Player": player,
        "Team": team,
        "Year": year,
        "Pos": pos,
        "Age": age,
        "AB": ab,
        "H": hits,
        "2B": doubles,
        "3B": triples,
        "HR": hr,
        "R": runs,
        "RBI": rbi,
        "SB": sb,
        "BB": bb,
        "HBP": hbp,
        "SO": so,
        "PlayerKey": player_key,
        "PlayerEntityKey": player_key,
    }


def _points_pitcher_row(
    *,
    player: str,
    player_key: str,
    year: int,
    age: int,
    pos: str = "SP",
    team: str = "SEA",
    g: float,
    ip: float,
    gs: float,
    hits: float = 0.0,
    er: float = 0.0,
    bb: float = 0.0,
    hbp: float = 0.0,
    k: float = 0.0,
    wins: float = 0.0,
    losses: float = 0.0,
    sv: float = 0.0,
    hld: float = 0.0,
) -> dict[str, Any]:
    return {
        "Player": player,
        "Team": team,
        "Year": year,
        "Pos": pos,
        "Age": age,
        "G": g,
        "IP": ip,
        "GS": gs,
        "H": hits,
        "ER": er,
        "BB": bb,
        "HBP": hbp,
        "K": k,
        "W": wins,
        "L": losses,
        "SV": sv,
        "HLD": hld,
        "PlayerKey": player_key,
        "PlayerEntityKey": player_key,
    }


def _synthetic_points_params(*, overrides: dict[str, Any]) -> dict[str, Any]:
    from backend.core.calculator_helpers import with_resolved_hidden_dynasty_modeling_settings
    params = _points_profile_params("points_season_total")
    params.update(
        {
            "teams": 1,
            "horizon": 1,
            "discount": 1.0,
            "hit_c": 0,
            "hit_1b": 0,
            "hit_2b": 0,
            "hit_3b": 0,
            "hit_ss": 0,
            "hit_ci": 0,
            "hit_mi": 0,
            "hit_of": 0,
            "hit_dh": 0,
            "hit_ut": 0,
            "pit_p": 0,
            "pit_sp": 0,
            "pit_rp": 0,
            "bench": 0,
            "minors": 0,
            "ir": 0,
            "keeper_limit": None,
            "two_way": "sum",
            "points_valuation_mode": "season_total",
            "weekly_starts_cap": None,
            "allow_same_day_starts_overflow": False,
            "weekly_acquisition_cap": None,
            "start_year": 2026,
            "ip_max": None,
            "pts_hit_1b": 1.0,
            "pts_hit_2b": 0.0,
            "pts_hit_3b": 0.0,
            "pts_hit_hr": 0.0,
            "pts_hit_r": 0.0,
            "pts_hit_rbi": 0.0,
            "pts_hit_sb": 0.0,
            "pts_hit_bb": 0.0,
            "pts_hit_hbp": 0.0,
            "pts_hit_so": 0.0,
            "pts_pit_ip": 3.0,
            "pts_pit_w": 0.0,
            "pts_pit_l": 0.0,
            "pts_pit_k": 0.0,
            "pts_pit_sv": 0.0,
            "pts_pit_hld": 0.0,
            "pts_pit_h": 0.0,
            "pts_pit_er": 0.0,
            "pts_pit_bb": 0.0,
            "pts_pit_hbp": 0.0,
            "enable_prospect_risk_adjustment": True,
            "enable_bench_stash_relief": False,
            "bench_negative_penalty": 0.55,
            "enable_ir_stash_relief": False,
            "ir_negative_penalty": 0.20,
        }
    )
    params.update(overrides)
    return with_resolved_hidden_dynasty_modeling_settings(params)


def _run_synthetic_points_snapshot(
    *,
    bat_rows: list[dict[str, Any]],
    pit_rows: list[dict[str, Any]],
    params: dict[str, Any],
) -> dict[str, Any]:
    import backend.app as app_module

    params = _resolved_dynasty_params(params)
    years = sorted(
        {
            int(row.get("Year"))
            for row in [*bat_rows, *pit_rows]
            if isinstance(row, dict) and row.get("Year") is not None
        }
    )
    app_module._calculate_points_dynasty_frame_cached.cache_clear()
    app_module._playable_pool_counts_by_year.cache_clear()
    with patch.object(app_module, "BAT_DATA", bat_rows), patch.object(app_module, "PIT_DATA", pit_rows), patch.object(
        app_module,
        "META",
        {"years": years},
    ):
        out = app_module._calculate_points_dynasty_frame_cached(
            teams=int(params["teams"]),
            horizon=int(params["horizon"]),
            discount=float(params["discount"]),
            hit_c=int(params["hit_c"]),
            hit_1b=int(params["hit_1b"]),
            hit_2b=int(params["hit_2b"]),
            hit_3b=int(params["hit_3b"]),
            hit_ss=int(params["hit_ss"]),
            hit_ci=int(params["hit_ci"]),
            hit_mi=int(params["hit_mi"]),
            hit_of=int(params["hit_of"]),
            hit_dh=int(params.get("hit_dh", 0)),
            hit_ut=int(params["hit_ut"]),
            pit_p=int(params["pit_p"]),
            pit_sp=int(params["pit_sp"]),
            pit_rp=int(params["pit_rp"]),
            bench=int(params["bench"]),
            minors=int(params["minors"]),
            ir=int(params["ir"]),
            keeper_limit=params.get("keeper_limit"),
            two_way=str(params["two_way"]),
            points_valuation_mode=str(params.get("points_valuation_mode", "season_total")),
            weekly_starts_cap=params.get("weekly_starts_cap"),
            allow_same_day_starts_overflow=bool(params.get("allow_same_day_starts_overflow", False)),
            weekly_acquisition_cap=params.get("weekly_acquisition_cap"),
            start_year=int(params["start_year"]),
            pts_hit_1b=float(params["pts_hit_1b"]),
            pts_hit_2b=float(params["pts_hit_2b"]),
            pts_hit_3b=float(params["pts_hit_3b"]),
            pts_hit_hr=float(params["pts_hit_hr"]),
            pts_hit_r=float(params["pts_hit_r"]),
            pts_hit_rbi=float(params["pts_hit_rbi"]),
            pts_hit_sb=float(params["pts_hit_sb"]),
            pts_hit_bb=float(params["pts_hit_bb"]),
            pts_hit_hbp=float(params["pts_hit_hbp"]),
            pts_hit_so=float(params["pts_hit_so"]),
            pts_pit_ip=float(params["pts_pit_ip"]),
            pts_pit_w=float(params["pts_pit_w"]),
            pts_pit_l=float(params["pts_pit_l"]),
            pts_pit_k=float(params["pts_pit_k"]),
            pts_pit_sv=float(params["pts_pit_sv"]),
            pts_pit_hld=float(params["pts_pit_hld"]),
            pts_pit_h=float(params["pts_pit_h"]),
            pts_pit_er=float(params["pts_pit_er"]),
            pts_pit_bb=float(params["pts_pit_bb"]),
            pts_pit_hbp=float(params["pts_pit_hbp"]),
            ip_max=params.get("ip_max"),
            enable_prospect_risk_adjustment=bool(params.get("enable_prospect_risk_adjustment", True)),
            enable_bench_stash_relief=bool(params.get("enable_bench_stash_relief", False)),
            bench_negative_penalty=float(params.get("bench_negative_penalty", 0.55)),
            enable_ir_stash_relief=bool(params.get("enable_ir_stash_relief", False)),
            ir_negative_penalty=float(params.get("ir_negative_penalty", 0.20)),
        ).copy(deep=True)
        return _points_snapshot_payload(runtime_module=app_module, out=out, params=params)


def _default_roto_snapshot(*, overrides: dict[str, Any] | None = None) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], str]:
    snapshot = _common_roto_snapshot(params=_default_roto_params(overrides=overrides))
    return (
        snapshot["rows"],
        snapshot["explanations"],
        str(snapshot["methodology_fingerprint"]),
    )


def _projection_refresh_context() -> tuple[str | None, dict[str, dict[str, Any]], bool, str | None]:
    import backend.runtime as runtime
    from backend.services.projections.delta import (
        compute_projection_delta_detail_map,
        load_previous_data,
    )

    projection_data_version = str(runtime._current_data_version() or "").strip() or None
    prev_data = load_previous_data(runtime.DATA_DIR)
    if prev_data is None:
        return projection_data_version, {}, False, None

    prev_bat_raw, prev_pit_raw = prev_data
    prev_bat_raw, prev_pit_raw = runtime._with_player_identity_keys(prev_bat_raw, prev_pit_raw)
    prev_bat = runtime._average_recent_projection_rows(prev_bat_raw, is_hitter=True)
    prev_pit = runtime._average_recent_projection_rows(prev_pit_raw, is_hitter=False)
    detail_map = compute_projection_delta_detail_map(
        runtime.BAT_DATA,
        runtime.PIT_DATA,
        prev_bat,
        prev_pit,
    )
    return projection_data_version, detail_map, True, "bat_prev/pit_prev"


def _points_profile_snapshots() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    profile_ids = ("points_season_total", "points_weekly_h2h", "points_daily_h2h")
    profile_snapshots = {
        profile_id: _points_snapshot(params=_points_profile_params(profile_id))
        for profile_id in profile_ids
    }
    depth_bat_rows = [
        _points_hitter_row(player="Hitter A", player_key="hitter-a", year=2026, age=24, ab=50.0, hits=10.0),
        _points_hitter_row(player="Hitter B", player_key="hitter-b", year=2026, age=25, ab=50.0, hits=8.0),
        _points_hitter_row(player="Hitter C", player_key="hitter-c", year=2026, age=26, ab=50.0, hits=6.0),
        _points_hitter_row(player="Hitter D", player_key="hitter-d", year=2026, age=27, ab=50.0, hits=0.0),
    ]
    keeper_limit_bat_rows = [
        _points_hitter_row(player="Hitter A", player_key="hitter-a", year=2026, age=24, ab=50.0, hits=0.0),
        _points_hitter_row(player="Hitter B", player_key="hitter-b", year=2026, age=25, ab=50.0, hits=0.0),
        _points_hitter_row(player="Hitter C", player_key="hitter-c", year=2026, age=26, ab=50.0, hits=0.0),
        _points_hitter_row(player="Hitter D", player_key="hitter-d", year=2026, age=27, ab=50.0, hits=0.0),
        _points_hitter_row(player="Hitter A", player_key="hitter-a", year=2027, age=25, ab=50.0, hits=0.0),
        _points_hitter_row(player="Hitter B", player_key="hitter-b", year=2027, age=26, ab=50.0, hits=0.0),
        _points_hitter_row(player="Hitter C", player_key="hitter-c", year=2027, age=27, ab=50.0, hits=0.0),
        _points_hitter_row(player="Hitter D", player_key="hitter-d", year=2027, age=28, ab=50.0, hits=1.0),
    ]
    weekly_stream_pit_rows = [
        _points_pitcher_row(player="Ace A", player_key="ace-a", year=2026, age=28, g=26.0, ip=180.0, gs=26.0),
        _points_pitcher_row(
            player="Starter B",
            player_key="starter-b",
            year=2026,
            age=29,
            g=26.0,
            ip=156.0,
            gs=26.0,
        ),
        _points_pitcher_row(
            player="Streamer C",
            player_key="streamer-c",
            year=2026,
            age=30,
            g=26.0,
            ip=78.0,
            gs=26.0,
        ),
    ]
    weekly_stream_bat_rows = [
        _points_hitter_row(
            player="Utility Bat",
            player_key="utility-bat",
            year=2026,
            age=27,
            ab=100.0,
            hits=20.0,
        ),
    ]
    reliever_fractional_pit_rows = [
        _points_pitcher_row(player="Ace A", player_key="ace-a", year=2026, age=28, g=30.0, ip=180.0, gs=30.0),
        _points_pitcher_row(
            player="Starter B",
            player_key="starter-b",
            year=2026,
            age=29,
            g=30.0,
            ip=150.0,
            gs=30.0,
        ),
        _points_pitcher_row(
            player="Reliever C",
            player_key="reliever-c",
            year=2026,
            age=30,
            pos="RP",
            g=60.0,
            ip=60.0,
            gs=0.1,
        ),
    ]
    daily_cap_pit_rows = [
        _points_pitcher_row(player="Ace A", player_key="ace-a", year=2026, age=28, g=52.0, ip=156.0, gs=52.0),
        _points_pitcher_row(
            player="Starter B",
            player_key="starter-b",
            year=2026,
            age=29,
            g=52.0,
            ip=130.0,
            gs=52.0,
        ),
        _points_pitcher_row(
            player="Streamer C",
            player_key="streamer-c",
            year=2026,
            age=30,
            g=52.0,
            ip=104.0,
            gs=52.0,
        ),
        _points_pitcher_row(
            player="Starter D",
            player_key="starter-d",
            year=2026,
            age=31,
            g=52.0,
            ip=78.0,
            gs=52.0,
        ),
    ]
    daily_cap_bat_rows = [
        _points_hitter_row(
            player="Utility Bat",
            player_key="utility-bat",
            year=2026,
            age=27,
            ab=100.0,
            hits=20.0,
        ),
    ]
    ip_cap_pit_rows = [
        _points_pitcher_row(player="Ace A", player_key="ace-a", year=2026, age=28, g=30.0, ip=180.0, gs=30.0),
        _points_pitcher_row(
            player="Starter B",
            player_key="starter-b",
            year=2026,
            age=29,
            g=30.0,
            ip=160.0,
            gs=30.0,
        ),
        _points_pitcher_row(
            player="Starter C",
            player_key="starter-c",
            year=2026,
            age=30,
            g=30.0,
            ip=120.0,
            gs=30.0,
        ),
    ]
    ip_cap_bat_rows = [
        _points_hitter_row(
            player="Utility Bat",
            player_key="utility-bat",
            year=2026,
            age=27,
            ab=100.0,
            hits=20.0,
        ),
    ]
    stash_bat_rows = [
        _points_hitter_row(player="Starter A", player_key="starter-a", year=2026, age=28, ab=100.0, hits=20.0),
        _points_hitter_row(player="Starter A", player_key="starter-a", year=2027, age=29, ab=100.0, hits=20.0),
        _points_hitter_row(player="Bench Bat", player_key="bench-bat", year=2026, age=22, ab=50.0, hits=5.0),
        _points_hitter_row(player="Bench Bat", player_key="bench-bat", year=2027, age=23, ab=100.0, hits=20.0),
        _points_hitter_row(player="Injured Bat", player_key="injured-bat", year=2026, age=23, ab=10.0, hits=5.0),
        _points_hitter_row(player="Injured Bat", player_key="injured-bat", year=2027, age=24, ab=100.0, hits=20.0),
        _points_hitter_row(player="Replacement C", player_key="replacement-c", year=2026, age=30, ab=100.0, hits=10.0),
        _points_hitter_row(player="Replacement C", player_key="replacement-c", year=2027, age=31, ab=100.0, hits=10.0),
    ]
    prospect_bat_rows = [
        _points_hitter_row(player="Starter A", player_key="starter-a", year=2026, age=28, ab=100.0, hits=20.0),
        _points_hitter_row(player="Starter A", player_key="starter-a", year=2027, age=29, ab=100.0, hits=20.0),
        _points_hitter_row(player="Prospect A", player_key="prospect-a", year=2026, age=22, ab=20.0, hits=8.0),
        _points_hitter_row(player="Prospect A", player_key="prospect-a", year=2027, age=23, ab=40.0, hits=20.0),
        _points_hitter_row(player="Prospect B", player_key="prospect-b", year=2026, age=21, ab=20.0, hits=7.0),
        _points_hitter_row(player="Prospect B", player_key="prospect-b", year=2027, age=22, ab=40.0, hits=18.0),
        _points_hitter_row(player="Replacement C", player_key="replacement-c", year=2026, age=30, ab=100.0, hits=10.0),
        _points_hitter_row(player="Replacement C", player_key="replacement-c", year=2027, age=31, ab=100.0, hits=10.0),
    ]

    scenario_snapshots = {
        "season_total_shallow_base": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in depth_bat_rows],
            pit_rows=[],
            params=_synthetic_points_params(overrides={"hit_of": 1}),
        ),
        "season_total_deep_replacement_depth": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in depth_bat_rows],
            pit_rows=[],
            params=_synthetic_points_params(overrides={"hit_of": 1, "bench": 8, "minors": 12, "ir": 6}),
        ),
        "season_total_keeper_limit_control": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in keeper_limit_bat_rows],
            pit_rows=[],
            params=_synthetic_points_params(overrides={"hit_of": 1, "bench": 2, "horizon": 2}),
        ),
        "season_total_keeper_limit_override": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in keeper_limit_bat_rows],
            pit_rows=[],
            params=_synthetic_points_params(overrides={"hit_of": 1, "bench": 2, "horizon": 2, "keeper_limit": 1}),
        ),
        "weekly_streaming_control_season_total": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in weekly_stream_bat_rows],
            pit_rows=[dict(row) for row in weekly_stream_pit_rows],
            params=_synthetic_points_params(overrides={"hit_of": 1, "pit_p": 2}),
        ),
        "weekly_streaming_suppression": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in weekly_stream_bat_rows],
            pit_rows=[dict(row) for row in weekly_stream_pit_rows],
            params=_synthetic_points_params(
                overrides={
                    "hit_of": 1,
                    "pit_p": 2,
                    "points_valuation_mode": "weekly_h2h",
                    "weekly_starts_cap": 2,
                    "weekly_acquisition_cap": 1,
                    "allow_same_day_starts_overflow": False,
                }
            ),
        ),
        "weekly_same_day_starts_control": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in weekly_stream_bat_rows],
            pit_rows=[dict(row) for row in weekly_stream_pit_rows],
            params=_synthetic_points_params(
                overrides={
                    "hit_of": 1,
                    "pit_p": 2,
                    "points_valuation_mode": "weekly_h2h",
                    "weekly_starts_cap": 2,
                    "weekly_acquisition_cap": 1,
                    "allow_same_day_starts_overflow": False,
                }
            ),
        ),
        "weekly_same_day_starts_overflow": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in weekly_stream_bat_rows],
            pit_rows=[dict(row) for row in weekly_stream_pit_rows],
            params=_synthetic_points_params(
                overrides={
                    "hit_of": 1,
                    "pit_p": 2,
                    "points_valuation_mode": "weekly_h2h",
                    "weekly_starts_cap": 2,
                    "weekly_acquisition_cap": 1,
                    "allow_same_day_starts_overflow": True,
                }
            ),
        ),
        "weekly_reliever_fractional_start_handling": _run_synthetic_points_snapshot(
            bat_rows=[],
            pit_rows=[dict(row) for row in reliever_fractional_pit_rows],
            params=_synthetic_points_params(
                overrides={
                    "pit_p": 1,
                    "points_valuation_mode": "weekly_h2h",
                    "weekly_starts_cap": 2,
                    "weekly_acquisition_cap": 1,
                    "allow_same_day_starts_overflow": False,
                }
            ),
        ),
        "daily_starts_cap_control_season_total": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in daily_cap_bat_rows],
            pit_rows=[dict(row) for row in daily_cap_pit_rows],
            params=_synthetic_points_params(overrides={"hit_of": 1, "pit_p": 2}),
        ),
        "daily_starts_cap_behavior": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in daily_cap_bat_rows],
            pit_rows=[dict(row) for row in daily_cap_pit_rows],
            params=_synthetic_points_params(
                overrides={
                    "hit_of": 1,
                    "pit_p": 2,
                    "points_valuation_mode": "daily_h2h",
                    "weekly_starts_cap": 2,
                    "weekly_acquisition_cap": 0,
                    "allow_same_day_starts_overflow": False,
                }
            ),
        ),
        "season_total_ip_max_control": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in ip_cap_bat_rows],
            pit_rows=[dict(row) for row in ip_cap_pit_rows],
            params=_synthetic_points_params(overrides={"hit_of": 1, "pit_p": 2}),
        ),
        "season_total_ip_max_hard_cap": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in ip_cap_bat_rows],
            pit_rows=[dict(row) for row in ip_cap_pit_rows],
            params=_synthetic_points_params(overrides={"hit_of": 1, "pit_p": 2, "ip_max": 240.0}),
        ),
        "season_total_bench_ir_stash_control": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in stash_bat_rows],
            pit_rows=[],
            params=_synthetic_points_params(
                overrides={
                    "horizon": 2,
                    "discount": 0.94,
                    "hit_of": 1,
                    "bench": 1,
                    "ir": 1,
                    "bench_negative_penalty": 0.5,
                    "ir_negative_penalty": 0.2,
                }
            ),
        ),
        "season_total_bench_ir_stash_relief": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in stash_bat_rows],
            pit_rows=[],
            params=_synthetic_points_params(
                overrides={
                    "horizon": 2,
                    "discount": 0.94,
                    "hit_of": 1,
                    "bench": 1,
                    "ir": 1,
                    "enable_bench_stash_relief": True,
                    "enable_ir_stash_relief": True,
                    "bench_negative_penalty": 0.5,
                    "ir_negative_penalty": 0.2,
                }
            ),
        ),
        "season_total_without_prospect_risk": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in prospect_bat_rows],
            pit_rows=[],
            params=_synthetic_points_params(
                overrides={
                    "horizon": 2,
                    "discount": 0.94,
                    "hit_of": 1,
                    "enable_prospect_risk_adjustment": False,
                }
            ),
        ),
        "season_total_prospect_risk_discount": _run_synthetic_points_snapshot(
            bat_rows=[dict(row) for row in prospect_bat_rows],
            pit_rows=[],
            params=_synthetic_points_params(
                overrides={
                    "horizon": 2,
                    "discount": 0.94,
                    "hit_of": 1,
                    "enable_prospect_risk_adjustment": True,
                }
            ),
        ),
    }
    return profile_snapshots, scenario_snapshots


def _keeper_points_imported_params(*, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    from backend.core.calculator_helpers import with_resolved_hidden_dynasty_modeling_settings
    params = _points_profile_params("points_weekly_h2h")
    params.update(
        {
            "hit_c": 1,
            "hit_1b": 1,
            "hit_2b": 1,
            "hit_3b": 1,
            "hit_ss": 1,
            "hit_ci": 0,
            "hit_mi": 0,
            "hit_of": 3,
            "hit_dh": 1,
            "hit_ut": 2,
            "pit_p": 7,
            "pit_sp": 0,
            "pit_rp": 0,
            "bench": 10,
            "minors": 0,
            "ir": 4,
            "keeper_limit": 7,
            "weekly_starts_cap": 12,
            "allow_same_day_starts_overflow": True,
            "weekly_acquisition_cap": 7,
            # Total bases scoring.
            "pts_hit_1b": 1.0,
            "pts_hit_2b": 2.0,
            "pts_hit_3b": 3.0,
            "pts_hit_hr": 4.0,
            "pts_hit_r": 1.0,
            "pts_hit_rbi": 1.0,
            "pts_hit_sb": 1.0,
            "pts_hit_bb": 1.0,
            "pts_hit_hbp": 1.0,
            "pts_hit_so": -1.0,
            "pts_pit_ip": 3.0,
            "pts_pit_w": 2.0,
            "pts_pit_l": -2.0,
            "pts_pit_k": 1.0,
            "pts_pit_sv": 5.0,
            "pts_pit_hld": 2.0,
            "pts_pit_h": -1.0,
            "pts_pit_er": -2.0,
            "pts_pit_bb": -1.0,
            "pts_pit_hbp": -1.0,
        }
    )
    if isinstance(overrides, dict):
        params.update(overrides)
    return with_resolved_hidden_dynasty_modeling_settings(params)


def _imported_profile_review(
    *,
    profile_id: str,
    benchmark_path: str | None,
    delta_threshold: int,
    top_n_absolute: int,
    projection_data_version: str | None,
    projection_delta_details: dict[str, dict[str, Any]],
    has_previous_projection_snapshot: bool,
    previous_projection_source: str | None,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from backend.core.dynasty_divergence_review import (
        load_dynasty_benchmark,
        review_dynasty_divergence,
    )

    normalized_profile_id = str(profile_id or "").strip()
    if normalized_profile_id == "shallow_roto_imported":
        params = _default_roto_params(overrides=overrides)
        snapshot = _common_roto_snapshot(params=params)
        raw_start_year_snapshot = _raw_start_year_snapshot(params=params)
        return review_dynasty_divergence(
            model_rows=snapshot["rows"],
            explanations=snapshot["explanations"],
            benchmark_entries=load_dynasty_benchmark(benchmark_path or None, profile_id=normalized_profile_id),
            raw_start_year_rows=raw_start_year_snapshot["rows"],
            start_year_projection_stats_by_entity=raw_start_year_snapshot["start_year_projection_stats_by_entity"],
            delta_threshold=delta_threshold,
            top_n_absolute=top_n_absolute,
            methodology_fingerprint=str(snapshot["methodology_fingerprint"]),
            projection_data_version=projection_data_version,
            projection_delta_details=projection_delta_details,
            has_previous_projection_snapshot=has_previous_projection_snapshot,
            previous_projection_source=previous_projection_source,
            profile_id=normalized_profile_id,
            settings_snapshot=snapshot["settings_snapshot"],
        )
    if normalized_profile_id == "deep_roto_imported":
        params = _deep_roto_params(overrides=overrides)
        snapshot = _common_roto_snapshot(params=params)
        raw_start_year_snapshot = _raw_start_year_snapshot(params=params)
        return review_dynasty_divergence(
            model_rows=snapshot["rows"],
            explanations=snapshot["explanations"],
            benchmark_entries=load_dynasty_benchmark(benchmark_path or None, profile_id=normalized_profile_id),
            raw_start_year_rows=raw_start_year_snapshot["rows"],
            start_year_projection_stats_by_entity=raw_start_year_snapshot["start_year_projection_stats_by_entity"],
            delta_threshold=delta_threshold,
            top_n_absolute=top_n_absolute,
            methodology_fingerprint=str(snapshot["methodology_fingerprint"]),
            projection_data_version=projection_data_version,
            projection_delta_details=projection_delta_details,
            has_previous_projection_snapshot=has_previous_projection_snapshot,
            previous_projection_source=previous_projection_source,
            profile_id=normalized_profile_id,
            settings_snapshot=snapshot["settings_snapshot"],
        )
    if normalized_profile_id == "keeper_points_imported":
        params = _keeper_points_imported_params(overrides=overrides)
        snapshot = _points_snapshot(params=params)
        return review_dynasty_divergence(
            model_rows=snapshot["rows"],
            explanations=snapshot["explanations"],
            benchmark_entries=load_dynasty_benchmark(benchmark_path or None, profile_id=normalized_profile_id),
            delta_threshold=delta_threshold,
            top_n_absolute=top_n_absolute,
            methodology_fingerprint=str(snapshot["methodology_fingerprint"]),
            projection_data_version=projection_data_version,
            projection_delta_details=projection_delta_details,
            has_previous_projection_snapshot=has_previous_projection_snapshot,
            previous_projection_source=previous_projection_source,
            profile_id=normalized_profile_id,
            settings_snapshot=snapshot["settings_snapshot"],
        )
    raise ValueError(f"Unsupported imported benchmark profile: {normalized_profile_id}")


def _render_imported_profile_bundle_markdown(reviews: dict[str, dict[str, Any]]) -> str:
    sections = ["# Imported Benchmark Summary", ""]
    for profile_id, review in reviews.items():
        top_entries = [
            entry
            for entry in list(review.get("review_candidates") or [])[:5]
            if isinstance(entry, dict)
        ]
        sections.append(f"## {profile_id}")
        sections.append(
            f"- weighted_mae: {float(review.get('weighted_mean_absolute_rank_error') or 0.0):.4f}"
        )
        sections.append(f"- compared_players: {int(review.get('benchmark_player_count') or 0)}")
        for entry in top_entries:
            sections.append(
                "- "
                + f"{entry.get('player')}: model {entry.get('model_rank')} vs benchmark {entry.get('benchmark_rank')} "
                + f"(delta {entry.get('rank_delta')})"
            )
        sections.append("")
    return "\n".join(sections).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run profile-driven dynasty audit reports.")
    parser.add_argument(
        "--profile",
        default="standard_roto",
        choices=(
            "standard_roto",
            "deep_roto",
            "points_season_total",
            "points_weekly_h2h",
            "points_daily_h2h",
            "shallow_roto_imported",
            "deep_roto_imported",
            "keeper_points_imported",
            "all_imported",
        ),
        help="Audit profile to run.",
    )
    parser.add_argument("--benchmark", default="", help="Optional path to a benchmark JSON fixture.")
    parser.add_argument("--delta-threshold", type=int, default=15, help="Rank delta threshold for review candidates.")
    parser.add_argument("--top-n-absolute", type=int, default=999, help="Maximum number of review candidates to print.")
    parser.add_argument("--out-json", default="", help="Optional JSON output path.")
    parser.add_argument("--out-md", default="", help="Optional Markdown output path.")
    parser.add_argument("--out-memo", default="", help="Optional markdown output path for the default-roto target-player memo.")
    parser.add_argument(
        "--out-aggregation-memo",
        default="",
        help="Optional markdown output path for the aggregation-gap memo.",
    )
    parser.add_argument(
        "--out-refresh-memo",
        default="",
        help="Optional markdown output path for the projection-refresh memo.",
    )
    parser.add_argument(
        "--out-attribution-memo",
        default="",
        help="Optional markdown output path for the standard-roto attribution memo.",
    )
    parser.add_argument(
        "--out-deep-memo",
        default="",
        help="Optional markdown output path for the deep-roto audit memo.",
    )
    parser.add_argument(
        "--out-points-memo",
        default="",
        help="Optional markdown output path for the points audit memo.",
    )
    parser.add_argument(
        "--out-slot-context-memo",
        default="",
        help="Optional markdown output path for the standard-roto slot-context memo.",
    )
    parser.add_argument(
        "--replacement-depth-mode",
        default="",
        help="Optional internal replacement-depth mode override for roto profile review.",
    )
    parser.add_argument(
        "--replacement-depth-blend-alpha",
        type=float,
        default=None,
        help="Optional internal replacement-depth blend alpha override for blended-depth review.",
    )
    return parser.parse_args()


def _write_optional(path_text: str, content: str) -> None:
    out_path_text = str(path_text or "").strip()
    if not out_path_text:
        return
    out_path = Path(out_path_text).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")


def main() -> None:
    from backend.core.dynasty_divergence_review import (
        load_dynasty_benchmark,
        render_aggregation_gap_memo_markdown,
        render_attribution_memo_markdown,
        render_deep_roto_markdown,
        render_deep_roto_memo_markdown,
        render_dynasty_divergence_markdown,
        render_dynasty_divergence_memo_markdown,
        render_projection_refresh_memo_markdown,
        render_slot_context_memo_markdown,
        review_deep_roto_profile,
        review_dynasty_divergence,
        review_slot_context_candidates,
    )
    from backend.core.points_audit_review import (
        render_points_audit_markdown,
        render_points_audit_memo_markdown,
        review_points_audit,
    )

    args = parse_args()
    overrides: dict[str, Any] = {}
    replacement_depth_mode = str(args.replacement_depth_mode or "").strip()
    if replacement_depth_mode:
        overrides["replacement_depth_mode"] = replacement_depth_mode
    if args.replacement_depth_blend_alpha is not None:
        overrides["replacement_depth_blend_alpha"] = float(args.replacement_depth_blend_alpha)

    profile_id = str(args.profile or "standard_roto").strip() or "standard_roto"
    projection_data_version, projection_delta_details, has_previous_projection_snapshot, previous_projection_source = (
        _projection_refresh_context()
    )

    if profile_id == "all_imported":
        imported_profile_ids = (
            "shallow_roto_imported",
            "deep_roto_imported",
            "keeper_points_imported",
        )
        reviews = {
            imported_profile_id: _imported_profile_review(
                profile_id=imported_profile_id,
                benchmark_path=args.benchmark or None,
                delta_threshold=max(int(args.delta_threshold), 1),
                top_n_absolute=max(int(args.top_n_absolute), 1),
                projection_data_version=projection_data_version,
                projection_delta_details=projection_delta_details,
                has_previous_projection_snapshot=has_previous_projection_snapshot,
                previous_projection_source=previous_projection_source,
                overrides=overrides,
            )
            for imported_profile_id in imported_profile_ids
        }
        markdown = _render_imported_profile_bundle_markdown(reviews)
        print(markdown, end="")
        if str(args.out_json or "").strip():
            _write_optional(args.out_json, json.dumps(reviews, indent=2, sort_keys=True) + "\n")
        _write_optional(args.out_md, markdown)
        return

    if profile_id in {"shallow_roto_imported", "deep_roto_imported", "keeper_points_imported"}:
        review = _imported_profile_review(
            profile_id=profile_id,
            benchmark_path=args.benchmark or None,
            delta_threshold=max(int(args.delta_threshold), 1),
            top_n_absolute=max(int(args.top_n_absolute), 1),
            projection_data_version=projection_data_version,
            projection_delta_details=projection_delta_details,
            has_previous_projection_snapshot=has_previous_projection_snapshot,
            previous_projection_source=previous_projection_source,
            overrides=overrides,
        )
        markdown = render_dynasty_divergence_markdown(review)
        print(markdown, end="")
        if str(args.out_json or "").strip():
            _write_optional(args.out_json, json.dumps(review, indent=2, sort_keys=True) + "\n")
        _write_optional(args.out_md, markdown)
        _write_optional(args.out_memo, render_dynasty_divergence_memo_markdown(review))
        return

    if profile_id == "standard_roto":
        params = _default_roto_params(overrides=overrides)
        snapshot = _common_roto_snapshot(params=params)
        raw_start_year_snapshot = _raw_start_year_snapshot(params=params)
        benchmark_entries = load_dynasty_benchmark(args.benchmark or None)
        review = review_dynasty_divergence(
            model_rows=snapshot["rows"],
            explanations=snapshot["explanations"],
            benchmark_entries=benchmark_entries,
            raw_start_year_rows=raw_start_year_snapshot["rows"],
            start_year_projection_stats_by_entity=raw_start_year_snapshot["start_year_projection_stats_by_entity"],
            delta_threshold=max(int(args.delta_threshold), 1),
            top_n_absolute=max(int(args.top_n_absolute), 1),
            methodology_fingerprint=str(snapshot["methodology_fingerprint"]),
            projection_data_version=projection_data_version,
            projection_delta_details=projection_delta_details,
            has_previous_projection_snapshot=has_previous_projection_snapshot,
            previous_projection_source=previous_projection_source,
            profile_id="standard_roto",
            settings_snapshot=snapshot["settings_snapshot"],
        )
        markdown = render_dynasty_divergence_markdown(review)
        print(markdown, end="")
        if str(args.out_json or "").strip():
            _write_optional(args.out_json, json.dumps(review, indent=2, sort_keys=True) + "\n")
        _write_optional(args.out_md, markdown)
        _write_optional(args.out_memo, render_dynasty_divergence_memo_markdown(review))
        _write_optional(args.out_aggregation_memo, render_aggregation_gap_memo_markdown(review))
        _write_optional(args.out_refresh_memo, render_projection_refresh_memo_markdown(review))
        _write_optional(args.out_attribution_memo, render_attribution_memo_markdown(review))
        if str(args.out_slot_context_memo or "").strip():
            candidate_snapshots = {
                candidate_id: _common_roto_snapshot(params=params)
                for candidate_id, params in _slot_context_candidate_params().items()
            }
            candidate_reviews = {
                candidate_id: review_dynasty_divergence(
                    model_rows=candidate_snapshot["rows"],
                    explanations=candidate_snapshot["explanations"],
                    benchmark_entries=benchmark_entries,
                    raw_start_year_rows=raw_start_year_snapshot["rows"],
                    start_year_projection_stats_by_entity=raw_start_year_snapshot["start_year_projection_stats_by_entity"],
                    delta_threshold=max(int(args.delta_threshold), 1),
                    top_n_absolute=max(int(args.top_n_absolute), 1),
                    methodology_fingerprint=str(candidate_snapshot["methodology_fingerprint"]),
                    projection_data_version=projection_data_version,
                    projection_delta_details=projection_delta_details,
                    has_previous_projection_snapshot=has_previous_projection_snapshot,
                    previous_projection_source=previous_projection_source,
                    profile_id="standard_roto",
                    settings_snapshot=candidate_snapshot["settings_snapshot"],
                )
                for candidate_id, candidate_snapshot in candidate_snapshots.items()
            }
            slot_context_review = review_slot_context_candidates(
                control_review=review,
                candidate_reviews=candidate_reviews,
            )
            _write_optional(args.out_slot_context_memo, render_slot_context_memo_markdown(slot_context_review))
        return

    if profile_id == "deep_roto":
        deep_snapshot = _common_roto_snapshot(params=_deep_roto_params(overrides=overrides))
        standard_snapshot = _common_roto_snapshot(params=_default_roto_params())
        review = review_deep_roto_profile(
            deep_model_rows=deep_snapshot["rows"],
            deep_explanations=deep_snapshot["explanations"],
            deep_valuation_diagnostics=deep_snapshot["valuation_diagnostics"],
            standard_model_rows=standard_snapshot["rows"],
            standard_explanations=standard_snapshot["explanations"],
            projection_data_version=projection_data_version,
            methodology_fingerprint=str(deep_snapshot["methodology_fingerprint"]),
            settings_snapshot=deep_snapshot["settings_snapshot"],
            profile_id="deep_roto",
            top_n_absolute=max(int(args.top_n_absolute), 1),
        )
        markdown = render_deep_roto_markdown(review)
        print(markdown, end="")
        if str(args.out_json or "").strip():
            _write_optional(args.out_json, json.dumps(review, indent=2, sort_keys=True) + "\n")
        _write_optional(args.out_md, markdown)
        _write_optional(args.out_deep_memo or args.out_memo, render_deep_roto_memo_markdown(review))
        return

    profile_snapshots, scenario_snapshots = _points_profile_snapshots()
    review = review_points_audit(
        profile_snapshots=profile_snapshots,
        scenario_snapshots=scenario_snapshots,
        projection_data_version=projection_data_version,
        profile_id=profile_id,
    )
    markdown = render_points_audit_markdown(review)
    print(markdown, end="")
    if str(args.out_json or "").strip():
        _write_optional(args.out_json, json.dumps(review, indent=2, sort_keys=True) + "\n")
    _write_optional(args.out_md, markdown)
    _write_optional(args.out_points_memo or args.out_memo, render_points_audit_memo_markdown(review))


if __name__ == "__main__":
    main()
