from __future__ import annotations

import pytest

import backend.runtime as runtime
from backend.core.dynasty_divergence_review import load_dynasty_benchmark, review_dynasty_divergence
from backend.valuation.models import CommonDynastyRotoSettings

pytestmark = [pytest.mark.full_regression, pytest.mark.slow, pytest.mark.valuation]

RAW_TARGET_PLAYERS = (
    "Corbin Carroll",
    "Yordan Alvarez",
    "Kyle Tucker",
    "Yoshinobu Yamamoto",
    "Roman Anthony",
    "Fernando Tatis Jr.",
    "Wyatt Langford",
    "Bryan Woo",
    "Pete Crow-Armstrong",
)
ANCHOR_PLAYERS = (
    "Bobby Witt Jr.",
    "Shohei Ohtani",
    "Juan Soto",
    "Paul Skenes",
    "Julio Rodriguez",
    "Gunnar Henderson",
    "Elly De La Cruz",
    "Junior Caminero",
    "Nick Kurtz",
)
AGGREGATION_GUARD_PLAYERS = (
    "Tarik Skubal",
    "Ronald Acuna Jr.",
    "Aaron Judge",
    "Cal Raleigh",
    "Jose Ramirez",
    "Garrett Crochet",
)
DEPTH_BLEND_ALPHAS = (0.15, 0.25, 0.33, 0.50)


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
        methodology_fingerprint=runtime.core_default_dynasty_methodology_fingerprint(default_params=params),
    )


def _entry_by_player(review: dict[str, object]) -> dict[str, dict[str, object]]:
    entries = review.get("entries")
    assert isinstance(entries, list)
    return {
        str(entry.get("player") or ""): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("player") or "")
    }


def _absolute_benchmark_error(entry: dict[str, object]) -> int:
    value = entry.get("absolute_benchmark_error", entry.get("abs_rank_delta"))
    assert value is not None
    return int(value)


def _candidate_summary(
    control_review: dict[str, object],
    candidate_review: dict[str, object],
    *,
    alpha: float,
) -> dict[str, object]:
    control_entries = _entry_by_player(control_review)
    candidate_entries = _entry_by_player(candidate_review)
    control_wmae = float(control_review["weighted_mean_absolute_rank_error"])
    candidate_wmae = float(candidate_review["weighted_mean_absolute_rank_error"])

    dynasty_improvement_count = sum(
        int(control_entries[player]["model_rank"]) - int(candidate_entries[player]["model_rank"]) >= 10
        for player in RAW_TARGET_PLAYERS
    )
    start_year_improvement_count = sum(
        int(control_entries[player]["start_year_rank"]) - int(candidate_entries[player]["start_year_rank"]) > 0
        for player in RAW_TARGET_PLAYERS
    )
    jose_error_change = (
        _absolute_benchmark_error(candidate_entries["Jose Ramirez"])
        - _absolute_benchmark_error(control_entries["Jose Ramirez"])
    )
    judge_error_change = (
        _absolute_benchmark_error(candidate_entries["Aaron Judge"])
        - _absolute_benchmark_error(control_entries["Aaron Judge"])
    )
    acuna_error_change = (
        _absolute_benchmark_error(candidate_entries["Ronald Acuna Jr."])
        - _absolute_benchmark_error(control_entries["Ronald Acuna Jr."])
    )
    cal_error_change = (
        _absolute_benchmark_error(candidate_entries["Cal Raleigh"])
        - _absolute_benchmark_error(control_entries["Cal Raleigh"])
    )
    worst_anchor_error_regression = max(
        _absolute_benchmark_error(candidate_entries[player]) - _absolute_benchmark_error(control_entries[player])
        for player in ANCHOR_PLAYERS
    )
    worst_tracked_error_regression = max(
        _absolute_benchmark_error(candidate_entries[player]) - _absolute_benchmark_error(control_entries[player])
        for player in RAW_TARGET_PLAYERS + AGGREGATION_GUARD_PLAYERS + ANCHOR_PLAYERS
    )
    passes = (
        candidate_wmae <= (control_wmae * 0.75)
        and dynasty_improvement_count >= 7
        and start_year_improvement_count >= 6
        and jose_error_change <= 8
        and judge_error_change < 0
        and acuna_error_change < 0
        and worst_anchor_error_regression <= 8
        and cal_error_change <= 0
    )
    return {
        "alpha": alpha,
        "control_wmae": control_wmae,
        "candidate_wmae": candidate_wmae,
        "dynasty_improvement_count": dynasty_improvement_count,
        "start_year_improvement_count": start_year_improvement_count,
        "jose_error_change": jose_error_change,
        "judge_error_change": judge_error_change,
        "acuna_error_change": acuna_error_change,
        "cal_error_change": cal_error_change,
        "worst_anchor_error_regression": worst_anchor_error_regression,
        "worst_tracked_error_regression": worst_tracked_error_regression,
        "passes": passes,
    }


def _best_candidate(summaries: list[dict[str, object]]) -> dict[str, object] | None:
    passing = [summary for summary in summaries if bool(summary.get("passes"))]
    if not passing:
        return None
    return min(
        passing,
        key=lambda summary: (
            float(summary["candidate_wmae"]),
            int(summary["worst_tracked_error_regression"]),
            float(summary["alpha"]),
        ),
    )


def test_softened_replacement_depth_candidates_use_benchmark_error_ship_guard() -> None:
    assert CommonDynastyRotoSettings().replacement_depth_mode == "blended_depth"
    assert CommonDynastyRotoSettings().replacement_depth_blend_alpha == pytest.approx(0.33)

    control_review = _review_for_default_roto(
        {
            "replacement_depth_mode": "flat",
            "replacement_depth_blend_alpha": 0.33,
        }
    )
    candidate_summaries = [
        _candidate_summary(
            control_review,
            _review_for_default_roto(
                {
                    "replacement_depth_mode": "blended_depth",
                    "replacement_depth_blend_alpha": alpha,
                }
            ),
            alpha=alpha,
        )
        for alpha in DEPTH_BLEND_ALPHAS
    ]

    assert all(
        float(summary["candidate_wmae"]) < float(summary["control_wmae"])
        for summary in candidate_summaries
    )

    best = _best_candidate(candidate_summaries)
    assert best is not None
    passing = [summary for summary in candidate_summaries if bool(summary["passes"])]
    assert passing
    assert float(best["candidate_wmae"]) == min(float(summary["candidate_wmae"]) for summary in passing)
    assert best["alpha"] == pytest.approx(0.33)
