from __future__ import annotations

import pytest

import backend.runtime as runtime
from backend.core.dynasty_divergence_review import load_dynasty_benchmark, review_dynasty_divergence

pytestmark = [pytest.mark.full_regression, pytest.mark.slow, pytest.mark.valuation]

AGGREGATION_TARGETS = (
    "Tarik Skubal",
    "Ronald Acuna Jr.",
    "Aaron Judge",
    "Cal Raleigh",
    "Jose Ramirez",
    "Garrett Crochet",
)
ANCHOR_PLAYERS = (
    "Bobby Witt Jr.",
    "Shohei Ohtani",
    "Juan Soto",
    "Paul Skenes",
    "Junior Caminero",
    "Nick Kurtz",
    "Gunnar Henderson",
    "Elly De La Cruz",
    "Julio Rodriguez",
    "Roman Anthony",
)
RAW_GUARD_PLAYERS = (
    "Corbin Carroll",
    "Yordan Alvarez",
    "Kyle Tucker",
    "Yoshinobu Yamamoto",
)


def _review_for_default_roto(overrides: dict[str, object]) -> dict[str, object]:
    params = dict(runtime._default_calculation_cache_params())
    params.update(overrides)
    frame = runtime._calculate_common_dynasty_frame_cached(
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
        **runtime._roto_category_settings_from_dict(params),
    ).copy(deep=True)
    explanations = runtime._build_calculation_explanations(
        frame,
        settings={**params, "scoring_mode": "roto"},
    )
    rows = (
        frame.sort_values("DynastyValue", ascending=False)
        .reset_index(drop=True)[
            [
                "Player",
                runtime.PLAYER_KEY_COL,
                runtime.PLAYER_ENTITY_KEY_COL,
                "Team",
                "DynastyValue",
            ]
        ]
        .to_dict(orient="records")
    )
    return review_dynasty_divergence(
        model_rows=rows,
        explanations=explanations,
        benchmark_entries=load_dynasty_benchmark(),
        delta_threshold=15,
        top_n_absolute=999,
        methodology_fingerprint=runtime._default_dynasty_methodology_fingerprint(),
    )


def _entry_by_player(review: dict[str, object]) -> dict[str, dict[str, object]]:
    entries = review.get("entries")
    assert isinstance(entries, list)
    entry_map = {
        str(entry.get("player") or ""): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "")
    }
    return entry_map


def test_default_replacement_blend_candidate_beats_legacy_control() -> None:
    control_review = _review_for_default_roto(
        {
            "enable_replacement_blend": False,
            "replacement_blend_alpha": 0.70,
        }
    )
    candidate_review = _review_for_default_roto(
        {
            "enable_replacement_blend": True,
            "replacement_blend_alpha": 0.40,
        }
    )

    control_wmae = float(control_review["weighted_mean_absolute_rank_error"])
    candidate_wmae = float(candidate_review["weighted_mean_absolute_rank_error"])
    assert candidate_wmae < control_wmae

    control_entries = _entry_by_player(control_review)
    candidate_entries = _entry_by_player(candidate_review)

    aggregation_improvements = {
        player: int(control_entries[player]["model_rank"]) - int(candidate_entries[player]["model_rank"])
        for player in AGGREGATION_TARGETS
    }
    assert all(improvement >= 8 for improvement in aggregation_improvements.values())

    anchor_regressions = {
        player: int(candidate_entries[player]["model_rank"]) - int(control_entries[player]["model_rank"])
        for player in ANCHOR_PLAYERS
    }
    assert max(anchor_regressions.values()) <= 8

    raw_guard_regressions = {
        player: int(candidate_entries[player]["model_rank"]) - int(control_entries[player]["model_rank"])
        for player in RAW_GUARD_PLAYERS
    }
    assert max(raw_guard_regressions.values()) <= 0
