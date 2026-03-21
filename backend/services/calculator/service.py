from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import uuid4

import pandas as pd
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from backend.core.calculator_orchestration import finalize_job_locked
from backend.domain.constants import (
    CALCULATOR_RESULT_POINTS_EXPORT_ORDER,
    CALCULATOR_RESULT_STAT_EXPORT_ORDER,
    ROTO_HITTER_CATEGORY_FIELDS,
    ROTO_PITCHER_CATEGORY_FIELDS,
)

logger = logging.getLogger(__name__)


class CalculateRequest(BaseModel):
    mode: Literal["common", "league"] = "common"
    scoring_mode: Literal["roto", "points"] = "roto"
    points_valuation_mode: Literal["season_total", "weekly_h2h", "daily_h2h"] = "season_total"
    two_way: Literal["sum", "max"] = "sum"
    sgp_denominator_mode: Literal["classic", "robust"] = "classic"
    sgp_winsor_low_pct: float = Field(default=0.10, ge=0.0, le=1.0)
    sgp_winsor_high_pct: float = Field(default=0.90, ge=0.0, le=1.0)
    sgp_epsilon_counting: float = Field(default=0.15, ge=0.0, le=1000.0)
    sgp_epsilon_ratio: float = Field(default=0.0015, ge=0.0, le=1000.0)
    enable_playing_time_reliability: bool = False
    enable_age_risk_adjustment: bool = False
    enable_prospect_risk_adjustment: bool = True
    enable_bench_stash_relief: bool = False
    bench_negative_penalty: float = Field(default=0.55, ge=0.0, le=1.0)
    enable_ir_stash_relief: bool = False
    ir_negative_penalty: float = Field(default=0.20, ge=0.0, le=1.0)
    enable_replacement_blend: bool = True
    replacement_blend_alpha: float = Field(default=0.40, ge=0.0, le=1.0)
    teams: int = Field(default=12, ge=2, le=30)
    sims: int = Field(default=300, ge=1, le=5000)
    horizon: int = Field(default=20, ge=1, le=20)
    discount: float = Field(default=0.94, gt=0.0, le=1.0)
    hit_c: int = Field(default=1, ge=0, le=15)
    hit_1b: int = Field(default=1, ge=0, le=15)
    hit_2b: int = Field(default=1, ge=0, le=15)
    hit_3b: int = Field(default=1, ge=0, le=15)
    hit_ss: int = Field(default=1, ge=0, le=15)
    hit_ci: int = Field(default=1, ge=0, le=15)
    hit_mi: int = Field(default=1, ge=0, le=15)
    hit_of: int = Field(default=5, ge=0, le=15)
    hit_dh: int = Field(default=0, ge=0, le=15)
    hit_ut: int = Field(default=1, ge=0, le=15)
    pit_p: int = Field(default=9, ge=0, le=15)
    pit_sp: int = Field(default=0, ge=0, le=15)
    pit_rp: int = Field(default=0, ge=0, le=15)
    bench: int = Field(default=6, ge=0, le=40)
    minors: int = Field(default=0, ge=0, le=60)
    ir: int = Field(default=0, ge=0, le=40)
    keeper_limit: Optional[int] = Field(default=None, ge=1, le=60)
    ip_min: float = Field(default=0.0, ge=0.0)
    ip_max: Optional[float] = Field(default=None, ge=0.0)
    weekly_starts_cap: Optional[int] = Field(default=None, ge=1, le=40)
    allow_same_day_starts_overflow: bool = False
    weekly_acquisition_cap: Optional[int] = Field(default=None, ge=0, le=40)
    start_year: int = Field(default=2026, ge=1900)
    auction_budget: Optional[int] = Field(default=None, ge=1, le=9999)
    roto_hit_r: bool = True
    roto_hit_rbi: bool = True
    roto_hit_hr: bool = True
    roto_hit_sb: bool = True
    roto_hit_avg: bool = True
    roto_hit_obp: bool = False
    roto_hit_slg: bool = False
    roto_hit_ops: bool = False
    roto_hit_h: bool = False
    roto_hit_bb: bool = False
    roto_hit_2b: bool = False
    roto_hit_tb: bool = False
    roto_pit_w: bool = True
    roto_pit_k: bool = True
    roto_pit_sv: bool = True
    roto_pit_era: bool = True
    roto_pit_whip: bool = True
    roto_pit_qs: bool = False
    roto_pit_qa3: bool = False
    roto_pit_svh: bool = False
    pts_hit_1b: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_2b: float = Field(default=2.0, ge=-50.0, le=50.0)
    pts_hit_3b: float = Field(default=3.0, ge=-50.0, le=50.0)
    pts_hit_hr: float = Field(default=4.0, ge=-50.0, le=50.0)
    pts_hit_r: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_rbi: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_sb: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_bb: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_hbp: float = Field(default=0.0, ge=-50.0, le=50.0)
    pts_hit_so: float = Field(default=-1.0, ge=-50.0, le=50.0)
    pts_pit_ip: float = Field(default=3.0, ge=-50.0, le=50.0)
    pts_pit_w: float = Field(default=5.0, ge=-50.0, le=50.0)
    pts_pit_l: float = Field(default=-5.0, ge=-50.0, le=50.0)
    pts_pit_k: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_pit_sv: float = Field(default=5.0, ge=-50.0, le=50.0)
    pts_pit_hld: float = Field(default=0.0, ge=-50.0, le=50.0)
    pts_pit_h: float = Field(default=-1.0, ge=-50.0, le=50.0)
    pts_pit_er: float = Field(default=-2.0, ge=-50.0, le=50.0)
    pts_pit_bb: float = Field(default=-1.0, ge=-50.0, le=50.0)
    pts_pit_hbp: float = Field(default=0.0, ge=-50.0, le=50.0)
    pts_pit_svh: float | None = Field(default=None, ge=-50.0, le=50.0, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_points_svh(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw

        normalized = dict(raw)
        if normalized.get("pts_pit_hld") is not None:
            return normalized

        legacy_svh = normalized.get("pts_pit_svh")
        if legacy_svh is None:
            return normalized

        try:
            legacy_value = float(legacy_svh)
        except (TypeError, ValueError):
            return normalized

        try:
            current_sv = float(normalized.get("pts_pit_sv") or 0.0)
        except (TypeError, ValueError):
            current_sv = 0.0

        normalized["pts_pit_sv"] = current_sv + legacy_value
        normalized["pts_pit_hld"] = legacy_value
        return normalized

    @model_validator(mode="after")
    def validate_ip_bounds(self) -> "CalculateRequest":
        if self.sgp_winsor_low_pct >= self.sgp_winsor_high_pct:
            raise ValueError("sgp_winsor_low_pct must be less than sgp_winsor_high_pct")
        if self.ip_max is not None and self.ip_max < self.ip_min:
            raise ValueError("ip_max must be greater than or equal to ip_min")
        total_hitter_slots = (
            self.hit_c
            + self.hit_1b
            + self.hit_2b
            + self.hit_3b
            + self.hit_ss
            + self.hit_ci
            + self.hit_mi
            + self.hit_of
            + self.hit_dh
            + self.hit_ut
        )
        total_pitcher_slots = self.pit_p + self.pit_sp + self.pit_rp
        if total_hitter_slots <= 0:
            raise ValueError("At least one hitter slot must be greater than 0.")
        if total_pitcher_slots <= 0:
            raise ValueError("At least one pitcher slot must be greater than 0.")
        total_roster = total_hitter_slots + total_pitcher_slots + self.bench + self.minors + self.ir
        if total_roster > 150:
            raise ValueError(
                f"Total roster size ({total_roster}) exceeds the maximum of 150."
            )
        if self.scoring_mode == "roto":
            if not any(bool(getattr(self, field_key, False)) for field_key, _stat_col, _default in ROTO_HITTER_CATEGORY_FIELDS):
                raise ValueError("Roto scoring must include at least one hitting category.")
            if not any(bool(getattr(self, field_key, False)) for field_key, _stat_col, _default in ROTO_PITCHER_CATEGORY_FIELDS):
                raise ValueError("Roto scoring must include at least one pitching category.")
        if self.scoring_mode == "points":
            has_non_zero_rule = any(
                abs(value) > 1e-9
                for value in (
                    self.pts_hit_1b,
                    self.pts_hit_2b,
                    self.pts_hit_3b,
                    self.pts_hit_hr,
                    self.pts_hit_r,
                    self.pts_hit_rbi,
                    self.pts_hit_sb,
                    self.pts_hit_bb,
                    self.pts_hit_hbp,
                    self.pts_hit_so,
                    self.pts_pit_ip,
                    self.pts_pit_w,
                    self.pts_pit_l,
                    self.pts_pit_k,
                    self.pts_pit_sv,
                    self.pts_pit_hld,
                    self.pts_pit_h,
                    self.pts_pit_er,
                    self.pts_pit_bb,
                    self.pts_pit_hbp,
                )
            )
            if not has_non_zero_rule:
                raise ValueError("Points scoring must include at least one non-zero scoring rule.")
        return self


class CalculateExportRequest(CalculateRequest):
    format: Literal["csv", "xlsx"] = "csv"
    include_explanations: bool = False
    export_columns: list[str] | None = None


@dataclass(slots=True)
class CalculatorServiceContext:
    refresh_data_if_needed: Callable
    coerce_meta_years: Callable
    get_meta: Callable
    calc_result_cache_key: Callable
    result_cache_get: Callable
    result_cache_set: Callable
    calculate_common_dynasty_frame_cached: Callable
    calculate_points_dynasty_frame_cached: Callable
    roto_category_settings_from_dict: Callable
    is_user_fixable_calculation_error: Callable
    player_identity_by_name: Callable
    normalize_player_key: Callable
    player_key_col: str
    player_entity_key_col: str
    selected_roto_categories: Callable
    start_year_roto_stats_by_entity: Callable
    projection_identity_key: Callable
    build_calculation_explanations: Callable
    clean_records_for_json: Callable
    flatten_explanations_for_export: Callable
    tabular_export_response: Callable
    calc_logger: Any
    enforce_rate_limit: Callable
    sync_rate_limit_per_minute: int
    sync_auth_rate_limit_per_minute: int
    job_create_rate_limit_per_minute: int
    job_create_auth_rate_limit_per_minute: int
    job_status_rate_limit_per_minute: int
    job_status_auth_rate_limit_per_minute: int
    client_ip: Callable
    iso_now: Callable
    active_jobs_for_ip: Callable
    calculator_max_active_jobs_per_ip: int
    calculator_max_active_jobs_total: int
    calculator_job_lock: Any
    calculator_jobs: dict[str, dict]
    cleanup_calculation_jobs: Callable
    cache_calculation_job_snapshot: Callable
    cached_calculation_job_snapshot: Callable
    calculation_job_public_payload: Callable
    mark_job_cancelled_locked: Callable
    calculator_job_executor: Any
    calc_job_cancelled_status: str


class CalculatorService:
    def __init__(self, ctx: CalculatorServiceContext):
        self._ctx = ctx
        self.calculate_request_model = CalculateRequest
        self.calculate_export_request_model = CalculateExportRequest

    @staticmethod
    def _value_col_sort_key(col: str) -> tuple[int, int | str]:
        suffix = col.split("_", 1)[1] if "_" in col else col
        return (0, int(suffix)) if str(suffix).isdigit() else (1, suffix)

    @staticmethod
    def _request_is_calculate_api_key_authenticated(request: Request | Any | None) -> bool:
        state = getattr(request, "state", None)
        return bool(getattr(state, "calc_api_key_authenticated", False))

    @classmethod
    def _effective_rate_limit(
        cls,
        request: Request | Any | None,
        *,
        anonymous_limit: int,
        authenticated_limit: int,
    ) -> int:
        if cls._request_is_calculate_api_key_authenticated(request):
            return max(1, int(authenticated_limit))
        return max(1, int(anonymous_limit))

    @staticmethod
    def _active_job_total(calculator_jobs: dict[str, dict]) -> int:
        return sum(
            1
            for job in calculator_jobs.values()
            if str(job.get("status") or "").lower() in {"queued", "running"}
        )

    def _default_export_columns(self, rows: list[dict]) -> list[str]:
        seen: set[str] = set()
        available: list[str] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            for raw_key in row.keys():
                col = str(raw_key or "").strip()
                if not col or col in seen:
                    continue
                seen.add(col)
                available.append(col)

        if not available:
            return ["Player", "DynastyValue", "Age", "Team", "Pos"]

        available_set = set(available)
        year_cols = sorted(
            [col for col in available if col.startswith("Value_")],
            key=self._value_col_sort_key,
        )
        stat_cols = [col for col in CALCULATOR_RESULT_STAT_EXPORT_ORDER if col in available_set]
        points_cols = [col for col in CALCULATOR_RESULT_POINTS_EXPORT_ORDER if col in available_set]

        ordered: list[str] = []
        for col in ["Player", "DynastyValue", "Age", "Team", "Pos", *points_cols, *stat_cols, *year_cols]:
            if col in available_set and col not in ordered:
                ordered.append(col)
        return ordered

    def _run_calculate_request(self, req: CalculateRequest, *, source: str) -> dict:
        started = time.perf_counter()
        settings = req.model_dump()
        if req.scoring_mode == "points":
            active_cache = self._ctx.calculate_points_dynasty_frame_cached
        else:
            active_cache = self._ctx.calculate_common_dynasty_frame_cached
        cache_before = active_cache.cache_info()  # type: ignore[attr-defined]  # lru_cache
        result_cache_key = self._ctx.calc_result_cache_key(settings)
        result_cache_hit = False
        status_code = 200

        try:
            self._ctx.refresh_data_if_needed()
            valid_years = self._ctx.coerce_meta_years(self._ctx.get_meta())
            if valid_years and req.start_year not in set(valid_years):
                raise HTTPException(
                    status_code=422,
                    detail=f"start_year must be one of the available projection years: {valid_years}",
                )

            cached_payload = self._ctx.result_cache_get(result_cache_key)
            if cached_payload is not None:
                result_cache_hit = True
                return cached_payload

            try:
                if req.scoring_mode == "points":
                    out = self._ctx.calculate_points_dynasty_frame_cached(
                        teams=req.teams,
                        horizon=req.horizon,
                        discount=req.discount,
                        hit_c=req.hit_c,
                        hit_1b=req.hit_1b,
                        hit_2b=req.hit_2b,
                        hit_3b=req.hit_3b,
                        hit_ss=req.hit_ss,
                        hit_ci=req.hit_ci,
                        hit_mi=req.hit_mi,
                        hit_of=req.hit_of,
                        hit_dh=req.hit_dh,
                        hit_ut=req.hit_ut,
                        pit_p=req.pit_p,
                        pit_sp=req.pit_sp,
                        pit_rp=req.pit_rp,
                        bench=req.bench,
                        minors=req.minors,
                        ir=req.ir,
                        keeper_limit=req.keeper_limit,
                        two_way=req.two_way,
                        points_valuation_mode=req.points_valuation_mode,
                        ip_max=req.ip_max,
                        weekly_starts_cap=req.weekly_starts_cap,
                        allow_same_day_starts_overflow=req.allow_same_day_starts_overflow,
                        weekly_acquisition_cap=req.weekly_acquisition_cap,
                        enable_prospect_risk_adjustment=req.enable_prospect_risk_adjustment,
                        enable_bench_stash_relief=req.enable_bench_stash_relief,
                        bench_negative_penalty=req.bench_negative_penalty,
                        enable_ir_stash_relief=req.enable_ir_stash_relief,
                        ir_negative_penalty=req.ir_negative_penalty,
                        start_year=req.start_year,
                        pts_hit_1b=req.pts_hit_1b,
                        pts_hit_2b=req.pts_hit_2b,
                        pts_hit_3b=req.pts_hit_3b,
                        pts_hit_hr=req.pts_hit_hr,
                        pts_hit_r=req.pts_hit_r,
                        pts_hit_rbi=req.pts_hit_rbi,
                        pts_hit_sb=req.pts_hit_sb,
                        pts_hit_bb=req.pts_hit_bb,
                        pts_hit_hbp=req.pts_hit_hbp,
                        pts_hit_so=req.pts_hit_so,
                        pts_pit_ip=req.pts_pit_ip,
                        pts_pit_w=req.pts_pit_w,
                        pts_pit_l=req.pts_pit_l,
                        pts_pit_k=req.pts_pit_k,
                        pts_pit_sv=req.pts_pit_sv,
                        pts_pit_hld=req.pts_pit_hld,
                        pts_pit_h=req.pts_pit_h,
                        pts_pit_er=req.pts_pit_er,
                        pts_pit_bb=req.pts_pit_bb,
                        pts_pit_hbp=req.pts_pit_hbp,
                    ).copy(deep=True)
                else:
                    out = self._ctx.calculate_common_dynasty_frame_cached(
                        teams=req.teams,
                        sims=req.sims,
                        horizon=req.horizon,
                        discount=req.discount,
                        hit_c=req.hit_c,
                        hit_1b=req.hit_1b,
                        hit_2b=req.hit_2b,
                        hit_3b=req.hit_3b,
                        hit_ss=req.hit_ss,
                        hit_ci=req.hit_ci,
                        hit_mi=req.hit_mi,
                        hit_of=req.hit_of,
                        hit_dh=req.hit_dh,
                        hit_ut=req.hit_ut,
                        pit_p=req.pit_p,
                        pit_sp=req.pit_sp,
                        pit_rp=req.pit_rp,
                        bench=req.bench,
                        minors=req.minors,
                        ir=req.ir,
                        ip_min=req.ip_min,
                        ip_max=req.ip_max,
                        two_way=req.two_way,
                        start_year=req.start_year,
                        sgp_denominator_mode=req.sgp_denominator_mode,
                        sgp_winsor_low_pct=req.sgp_winsor_low_pct,
                        sgp_winsor_high_pct=req.sgp_winsor_high_pct,
                        sgp_epsilon_counting=req.sgp_epsilon_counting,
                        sgp_epsilon_ratio=req.sgp_epsilon_ratio,
                        enable_playing_time_reliability=req.enable_playing_time_reliability,
                        enable_age_risk_adjustment=req.enable_age_risk_adjustment,
                        enable_prospect_risk_adjustment=req.enable_prospect_risk_adjustment,
                        enable_bench_stash_relief=req.enable_bench_stash_relief,
                        bench_negative_penalty=req.bench_negative_penalty,
                        enable_ir_stash_relief=req.enable_ir_stash_relief,
                        ir_negative_penalty=req.ir_negative_penalty,
                        enable_replacement_blend=req.enable_replacement_blend,
                        replacement_blend_alpha=req.replacement_blend_alpha,
                        **self._ctx.roto_category_settings_from_dict(settings),
                    ).copy(deep=True)
            except ValueError as calc_error:
                message = str(calc_error)
                if self._ctx.is_user_fixable_calculation_error(message):
                    raise HTTPException(status_code=422, detail=message) from calc_error
                raise

            identity_by_name = self._ctx.player_identity_by_name()
            if self._ctx.player_key_col not in out.columns:
                out[self._ctx.player_key_col] = None
            if self._ctx.player_entity_key_col not in out.columns:
                out[self._ctx.player_entity_key_col] = None

            def _resolve_player_key(row: pd.Series) -> str:
                player_name = str(row.get("Player") or "").strip()
                existing_key = str(row.get(self._ctx.player_key_col) or "").strip()
                if existing_key:
                    return existing_key
                mapped_key, _mapped_entity = identity_by_name.get(
                    player_name,
                    (self._ctx.normalize_player_key(player_name), None),
                )
                return mapped_key

            def _resolve_entity_key(row: pd.Series) -> str | None:
                player_name = str(row.get("Player") or "").strip()
                existing_entity = str(row.get(self._ctx.player_entity_key_col) or "").strip()
                if existing_entity:
                    return existing_entity
                _mapped_key, mapped_entity = identity_by_name.get(
                    player_name,
                    (self._ctx.normalize_player_key(player_name), None),
                )
                return mapped_entity

            out[self._ctx.player_key_col] = out.apply(_resolve_player_key, axis=1)
            out[self._ctx.player_entity_key_col] = out.apply(_resolve_entity_key, axis=1)
            out["DynastyMatchStatus"] = out[self._ctx.player_entity_key_col].map(
                lambda value: "matched" if value else "no_unique_match"
            )
            selected_roto_stat_cols: list[str] = []
            selected_points_summary_cols: list[str] = []
            if req.scoring_mode == "roto":
                selected_hit_cats, selected_pit_cats = self._ctx.selected_roto_categories(settings)
                selected_roto_stat_cols = selected_hit_cats + selected_pit_cats
                if selected_roto_stat_cols:
                    stats_by_entity = self._ctx.start_year_roto_stats_by_entity(
                        start_year=req.start_year,
                    )
                    identity_keys = out.apply(self._ctx.projection_identity_key, axis=1)
                    for stat_col in selected_roto_stat_cols:
                        stat_lookup = {
                            key: values.get(stat_col)
                            for key, values in stats_by_entity.items()
                            if stat_col in values
                        }
                        out[stat_col] = identity_keys.map(stat_lookup)
            elif req.scoring_mode == "points":
                selected_points_summary_cols = [
                    col for col in CALCULATOR_RESULT_POINTS_EXPORT_ORDER
                    if col in out.columns
                ]
            stat_dynasty_cols: list[str] = []
            if req.scoring_mode == "roto":
                stat_dynasty_cols = sorted(c for c in out.columns if c.startswith("StatDynasty_"))

            explanations = self._ctx.build_calculation_explanations(out, settings=settings)

            # Auction dollar conversion
            if req.auction_budget is not None and "DynastyValue" in out.columns:
                total_budget = req.auction_budget * req.teams
                positive_values = out["DynastyValue"].clip(lower=0)
                total_positive = positive_values.sum()
                if total_positive > 0:
                    out["AuctionDollars"] = (positive_values / total_positive * total_budget).round(0).astype(int)
                    # $1 floor for players with positive dynasty value
                    out.loc[(out["DynastyValue"] > 0) & (out["AuctionDollars"] < 1), "AuctionDollars"] = 1
                else:
                    out["AuctionDollars"] = 0
                # Zero out auction dollars for negative dynasty values
                out.loc[out["DynastyValue"] <= 0, "AuctionDollars"] = 0

            year_cols = [c for c in out.columns if c.startswith("Value_")]
            auction_cols = ["AuctionDollars"] if "AuctionDollars" in out.columns else []
            cols = [
                "Player",
                self._ctx.player_key_col,
                self._ctx.player_entity_key_col,
                "DynastyMatchStatus",
                "Team",
                "Pos",
                "Age",
            ] + selected_roto_stat_cols + stat_dynasty_cols + selected_points_summary_cols + [
                "DynastyValue",
                "RawDynastyValue",
                "minor_eligible",
            ] + auction_cols + year_cols

            available_cols = [c for c in cols if c in out.columns]
            df = out[available_cols].copy()

            three_decimal_cols = {"AVG", "OBP", "SLG", "OPS"}
            for c in df.select_dtypes(include="float").columns:
                df[c] = df[c].round(3 if c in three_decimal_cols else 2)

            records = df.to_dict(orient="records")
            records = self._ctx.clean_records_for_json(records)
            diagnostics = out.attrs.get("valuation_diagnostics", {})
            if not isinstance(diagnostics, dict):
                diagnostics = {}

            payload = {
                "total": len(records),
                "settings": settings,
                "data": records,
                "explanations": explanations,
                "diagnostics": diagnostics,
            }
            self._ctx.result_cache_set(result_cache_key, payload)
            return payload

        except HTTPException as exc:
            status_code = exc.status_code
            raise
        except Exception as exc:  # noqa: BLE001 — last-resort catch to produce 500 response
            status_code = 500
            self._ctx.calc_logger.exception("calculator request failed source=%s", source)
            raise HTTPException(status_code=500, detail="Internal calculator error.") from exc
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
            cache_after = active_cache.cache_info()  # type: ignore[attr-defined]  # lru_cache
            cache_event = "none"
            if result_cache_hit:
                cache_event = "result-cache-hit"
            elif cache_after.hits > cache_before.hits:
                cache_event = "hit"
            elif cache_after.misses > cache_before.misses:
                cache_event = "miss"

            self._ctx.calc_logger.info(
                "calculator source=%s status=%s duration_ms=%s cache=%s settings=%s",
                source,
                status_code,
                duration_ms,
                cache_event,
                json.dumps(settings, sort_keys=True),
            )

    def _run_calculation_job(self, job_id: str, req_payload: dict) -> None:
        with self._ctx.calculator_job_lock:
            job = self._ctx.calculator_jobs.get(job_id)
            if job is None:
                return
            if str(job.get("status") or "").lower() == self._ctx.calc_job_cancelled_status or bool(job.get("cancel_requested")):
                self._ctx.mark_job_cancelled_locked(job)
                self._ctx.cache_calculation_job_snapshot(job)
                return
            job["status"] = "running"
            job["started_at"] = self._ctx.iso_now()
            job["updated_at"] = job["started_at"]
            job["error"] = None
            self._ctx.cache_calculation_job_snapshot(job)

        try:
            req = CalculateRequest(**req_payload)
            result = self._run_calculate_request(req, source="job")
            finalize_job_locked(self._ctx, job_id, status="completed", error=None, result=result)
        except HTTPException as exc:
            finalize_job_locked(
                self._ctx, job_id,
                status="failed",
                error={"status_code": exc.status_code, "detail": exc.detail},
                result=None,
            )
        except Exception:  # noqa: BLE001 — last-resort safety net for async job finalization
            self._ctx.calc_logger.exception("calculator job crashed job_id=%s", job_id)
            finalize_job_locked(
                self._ctx, job_id,
                status="failed",
                error={"status_code": 500, "detail": "Internal calculator error."},
                result=None,
            )
        finally:
            with self._ctx.calculator_job_lock:
                self._ctx.cleanup_calculation_jobs()

    def calculate_dynasty_values(self, req: CalculateRequest, request: Request):
        self._ctx.enforce_rate_limit(
            request,
            action="calc-sync",
            limit_per_minute=self._effective_rate_limit(
                request,
                anonymous_limit=self._ctx.sync_rate_limit_per_minute,
                authenticated_limit=self._ctx.sync_auth_rate_limit_per_minute,
            ),
        )
        return self._run_calculate_request(req, source="sync")

    def export_calculate_dynasty_values(self, req: CalculateExportRequest, request: Request):
        self._ctx.enforce_rate_limit(
            request,
            action="calc-sync",
            limit_per_minute=self._effective_rate_limit(
                request,
                anonymous_limit=self._ctx.sync_rate_limit_per_minute,
                authenticated_limit=self._ctx.sync_auth_rate_limit_per_minute,
            ),
        )
        payload = req.model_dump()
        export_format = str(payload.pop("format", "csv")).strip().lower()
        include_explanations = bool(payload.pop("include_explanations", False))
        requested_export_columns = payload.pop("export_columns", None)
        calc_req = CalculateRequest(**payload)
        result = self._run_calculate_request(calc_req, source="sync-export")
        result_rows = list(result.get("data", []))
        explain_rows = self._ctx.flatten_explanations_for_export(result.get("explanations", {})) if include_explanations else None
        return self._ctx.tabular_export_response(
            result_rows,
            filename_base=f"dynasty-rankings-{calc_req.scoring_mode}",
            file_format="xlsx" if export_format == "xlsx" else "csv",
            explain_rows=explain_rows,
            selected_columns=requested_export_columns,
            default_columns=self._default_export_columns(result_rows),
            required_columns=["Player", "DynastyValue"],
            disallowed_columns=[
                self._ctx.player_key_col,
                self._ctx.player_entity_key_col,
                "DynastyMatchStatus",
                "RawDynastyValue",
                "minor_eligible",
            ],
        )

    def create_calculate_dynasty_job(self, req: CalculateRequest, request: Request):
        self._ctx.enforce_rate_limit(
            request,
            action="calc-job-create",
            limit_per_minute=self._effective_rate_limit(
                request,
                anonymous_limit=self._ctx.job_create_rate_limit_per_minute,
                authenticated_limit=self._ctx.job_create_auth_rate_limit_per_minute,
            ),
        )
        client_ip = self._ctx.client_ip(request)
        created_at = self._ctx.iso_now()
        payload = req.model_dump()
        cache_key = self._ctx.calc_result_cache_key(payload)
        cached_result = self._ctx.result_cache_get(cache_key)
        job_id = uuid4().hex
        job = {
            "job_id": job_id,
            "status": "completed" if cached_result is not None else "queued",
            "created_at": created_at,
            "started_at": created_at if cached_result is not None else None,
            "completed_at": created_at if cached_result is not None else None,
            "updated_at": created_at,
            "created_ts": time.time(),
            "client_ip": client_ip,
            "settings": payload,
            "result": cached_result,
            "error": None,
            "cancel_requested": False,
            "future": None,
        }

        with self._ctx.calculator_job_lock:
            self._ctx.cleanup_calculation_jobs(job["created_ts"])
            if cached_result is None:
                active_total = self._active_job_total(self._ctx.calculator_jobs)
                if active_total >= self._ctx.calculator_max_active_jobs_total:
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            "Calculation queue is full right now. "
                            "Wait for active jobs to finish and retry."
                        ),
                    )
                active_for_ip = self._ctx.active_jobs_for_ip(client_ip)
                if active_for_ip >= self._ctx.calculator_max_active_jobs_per_ip:
                    raise HTTPException(
                        status_code=429,
                        detail=(
                            "Too many active calculation jobs for this client IP. "
                            "Wait for an existing job to finish and retry."
                        ),
                    )
            self._ctx.calculator_jobs[job_id] = job
            if cached_result is not None:
                self._ctx.cache_calculation_job_snapshot(job)
            response_payload = self._ctx.calculation_job_public_payload(job)

        if cached_result is None:
            try:
                future = self._ctx.calculator_job_executor.submit(self._run_calculation_job, job_id, payload)
            except RuntimeError as exc:
                with self._ctx.calculator_job_lock:
                    self._ctx.calculator_jobs.pop(job_id, None)
                raise HTTPException(status_code=503, detail="Calculation worker is unavailable.") from exc
            with self._ctx.calculator_job_lock:
                live_job = self._ctx.calculator_jobs.get(job_id)
                if live_job is not None:
                    live_job["future"] = future
            self._ctx.calc_logger.info("calculator job queued job_id=%s settings=%s", job_id, json.dumps(payload, sort_keys=True))
        else:
            self._ctx.calc_logger.info("calculator job cache-hit job_id=%s settings=%s", job_id, json.dumps(payload, sort_keys=True))

        return response_payload

    def get_calculate_dynasty_job(self, job_id: str, request: Request):
        self._ctx.enforce_rate_limit(
            request,
            action="calc-job-status",
            limit_per_minute=self._effective_rate_limit(
                request,
                anonymous_limit=self._ctx.job_status_rate_limit_per_minute,
                authenticated_limit=self._ctx.job_status_auth_rate_limit_per_minute,
            ),
        )
        with self._ctx.calculator_job_lock:
            self._ctx.cleanup_calculation_jobs()
            job = self._ctx.calculator_jobs.get(job_id)
            if job is None:
                cached_job = self._ctx.cached_calculation_job_snapshot(job_id)
                if cached_job is not None:
                    return cached_job
                raise HTTPException(status_code=404, detail="Calculation job not found or expired.")
            return self._ctx.calculation_job_public_payload(job)

    def cancel_calculate_dynasty_job(self, job_id: str, request: Request):
        self._ctx.enforce_rate_limit(
            request,
            action="calc-job-status",
            limit_per_minute=self._effective_rate_limit(
                request,
                anonymous_limit=self._ctx.job_status_rate_limit_per_minute,
                authenticated_limit=self._ctx.job_status_auth_rate_limit_per_minute,
            ),
        )
        with self._ctx.calculator_job_lock:
            self._ctx.cleanup_calculation_jobs()
            job = self._ctx.calculator_jobs.get(job_id)
            if job is None:
                cached_job = self._ctx.cached_calculation_job_snapshot(job_id)
                if cached_job is not None:
                    return cached_job
                raise HTTPException(status_code=404, detail="Calculation job not found or expired.")

            status = str(job.get("status") or "").lower()
            if status not in {"queued", "running"}:
                return self._ctx.calculation_job_public_payload(job)

            job["cancel_requested"] = True
            future = job.get("future")
            cancel_future = getattr(future, "cancel", None)
            if callable(cancel_future):
                try:
                    cancel_future()
                except Exception:  # noqa: BLE001 — Future.cancel() may raise on shutdown
                    logger.debug("cancel_future() raised for job_id=%s", job_id, exc_info=True)
            self._ctx.mark_job_cancelled_locked(job)
            self._ctx.cache_calculation_job_snapshot(job)
            return self._ctx.calculation_job_public_payload(job)
