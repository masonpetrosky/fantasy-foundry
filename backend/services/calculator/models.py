from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from backend.domain.constants import ROTO_HITTER_CATEGORY_FIELDS, ROTO_PITCHER_CATEGORY_FIELDS


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
            raise ValueError(f"Total roster size ({total_roster}) exceeds the maximum of 150.")

        if self.scoring_mode == "roto":
            if not any(
                bool(getattr(self, field_key, False))
                for field_key, _stat_col, _default in ROTO_HITTER_CATEGORY_FIELDS
            ):
                raise ValueError("Roto scoring must include at least one hitting category.")
            if not any(
                bool(getattr(self, field_key, False))
                for field_key, _stat_col, _default in ROTO_PITCHER_CATEGORY_FIELDS
            ):
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
