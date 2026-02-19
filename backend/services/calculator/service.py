from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional
from uuid import uuid4

import pandas as pd
from fastapi import HTTPException, Request
from pydantic import BaseModel, Field, model_validator

ROTO_HITTER_CATEGORY_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("roto_hit_r", "R", True),
    ("roto_hit_rbi", "RBI", True),
    ("roto_hit_hr", "HR", True),
    ("roto_hit_sb", "SB", True),
    ("roto_hit_avg", "AVG", True),
    ("roto_hit_obp", "OBP", False),
    ("roto_hit_slg", "SLG", False),
    ("roto_hit_ops", "OPS", False),
    ("roto_hit_h", "H", False),
    ("roto_hit_bb", "BB", False),
    ("roto_hit_2b", "2B", False),
    ("roto_hit_tb", "TB", False),
)
ROTO_PITCHER_CATEGORY_FIELDS: tuple[tuple[str, str, bool], ...] = (
    ("roto_pit_w", "W", True),
    ("roto_pit_k", "K", True),
    ("roto_pit_sv", "SV", True),
    ("roto_pit_era", "ERA", True),
    ("roto_pit_whip", "WHIP", True),
    ("roto_pit_qs", "QS", False),
    ("roto_pit_svh", "SVH", False),
)


class CalculateRequest(BaseModel):
    mode: Literal["common"] = "common"
    scoring_mode: Literal["roto", "points"] = "roto"
    two_way: Literal["sum", "max"] = "sum"
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
    hit_ut: int = Field(default=1, ge=0, le=15)
    pit_p: int = Field(default=9, ge=0, le=15)
    pit_sp: int = Field(default=0, ge=0, le=15)
    pit_rp: int = Field(default=0, ge=0, le=15)
    bench: int = Field(default=6, ge=0, le=40)
    minors: int = Field(default=0, ge=0, le=60)
    ir: int = Field(default=0, ge=0, le=40)
    ip_min: float = Field(default=0.0, ge=0.0)
    ip_max: Optional[float] = Field(default=None, ge=0.0)
    start_year: int = Field(default=2026, ge=1900)
    recent_projections: int = Field(default=3, ge=1, le=10)
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
    roto_pit_svh: bool = False
    pts_hit_1b: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_2b: float = Field(default=2.0, ge=-50.0, le=50.0)
    pts_hit_3b: float = Field(default=3.0, ge=-50.0, le=50.0)
    pts_hit_hr: float = Field(default=4.0, ge=-50.0, le=50.0)
    pts_hit_r: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_rbi: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_sb: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_bb: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_hit_so: float = Field(default=-1.0, ge=-50.0, le=50.0)
    pts_pit_ip: float = Field(default=3.0, ge=-50.0, le=50.0)
    pts_pit_w: float = Field(default=5.0, ge=-50.0, le=50.0)
    pts_pit_l: float = Field(default=-5.0, ge=-50.0, le=50.0)
    pts_pit_k: float = Field(default=1.0, ge=-50.0, le=50.0)
    pts_pit_sv: float = Field(default=5.0, ge=-50.0, le=50.0)
    pts_pit_svh: float = Field(default=0.0, ge=-50.0, le=50.0)
    pts_pit_h: float = Field(default=-1.0, ge=-50.0, le=50.0)
    pts_pit_er: float = Field(default=-2.0, ge=-50.0, le=50.0)
    pts_pit_bb: float = Field(default=-1.0, ge=-50.0, le=50.0)

    @model_validator(mode="after")
    def validate_ip_bounds(self) -> "CalculateRequest":
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
            + self.hit_ut
        )
        total_pitcher_slots = self.pit_p + self.pit_sp + self.pit_rp
        if total_hitter_slots <= 0:
            raise ValueError("At least one hitter slot must be greater than 0.")
        if total_pitcher_slots <= 0:
            raise ValueError("At least one pitcher slot must be greater than 0.")
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
                    self.pts_hit_so,
                    self.pts_pit_ip,
                    self.pts_pit_w,
                    self.pts_pit_l,
                    self.pts_pit_k,
                    self.pts_pit_sv,
                    self.pts_pit_svh,
                    self.pts_pit_h,
                    self.pts_pit_er,
                    self.pts_pit_bb,
                )
            )
            if not has_non_zero_rule:
                raise ValueError("Points scoring must include at least one non-zero scoring rule.")
        return self


class CalculateExportRequest(CalculateRequest):
    format: Literal["csv", "xlsx"] = "csv"
    include_explanations: bool = False


@dataclass(slots=True)
class CalculatorServiceContext:
    refresh_data_if_needed: callable
    coerce_meta_years: callable
    get_meta: callable
    calc_result_cache_key: callable
    result_cache_get: callable
    result_cache_set: callable
    calculate_common_dynasty_frame_cached: callable
    calculate_points_dynasty_frame_cached: callable
    roto_category_settings_from_dict: callable
    is_user_fixable_calculation_error: callable
    player_identity_by_name: callable
    normalize_player_key: callable
    player_key_col: str
    player_entity_key_col: str
    selected_roto_categories: callable
    start_year_roto_stats_by_entity: callable
    projection_identity_key: callable
    build_calculation_explanations: callable
    clean_records_for_json: callable
    flatten_explanations_for_export: callable
    tabular_export_response: callable
    calc_logger: Any
    enforce_rate_limit: callable
    sync_rate_limit_per_minute: int
    job_create_rate_limit_per_minute: int
    job_status_rate_limit_per_minute: int
    client_ip: callable
    iso_now: callable
    active_jobs_for_ip: callable
    calculator_max_active_jobs_per_ip: int
    calculator_job_lock: Any
    calculator_jobs: dict[str, dict]
    cleanup_calculation_jobs: callable
    cache_calculation_job_snapshot: callable
    cached_calculation_job_snapshot: callable
    calculation_job_public_payload: callable
    mark_job_cancelled_locked: callable
    calculator_job_executor: Any
    calc_job_cancelled_status: str


class CalculatorService:
    def __init__(self, ctx: CalculatorServiceContext):
        self._ctx = ctx
        self.calculate_request_model = CalculateRequest
        self.calculate_export_request_model = CalculateExportRequest

    def _run_calculate_request(self, req: CalculateRequest, *, source: str) -> dict:
        started = time.perf_counter()
        settings = req.model_dump()
        active_cache = (
            self._ctx.calculate_points_dynasty_frame_cached
            if req.scoring_mode == "points"
            else self._ctx.calculate_common_dynasty_frame_cached
        )
        cache_before = active_cache.cache_info()
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
                        hit_ut=req.hit_ut,
                        pit_p=req.pit_p,
                        pit_sp=req.pit_sp,
                        pit_rp=req.pit_rp,
                        bench=req.bench,
                        minors=req.minors,
                        ir=req.ir,
                        two_way=req.two_way,
                        start_year=req.start_year,
                        recent_projections=req.recent_projections,
                        pts_hit_1b=req.pts_hit_1b,
                        pts_hit_2b=req.pts_hit_2b,
                        pts_hit_3b=req.pts_hit_3b,
                        pts_hit_hr=req.pts_hit_hr,
                        pts_hit_r=req.pts_hit_r,
                        pts_hit_rbi=req.pts_hit_rbi,
                        pts_hit_sb=req.pts_hit_sb,
                        pts_hit_bb=req.pts_hit_bb,
                        pts_hit_so=req.pts_hit_so,
                        pts_pit_ip=req.pts_pit_ip,
                        pts_pit_w=req.pts_pit_w,
                        pts_pit_l=req.pts_pit_l,
                        pts_pit_k=req.pts_pit_k,
                        pts_pit_sv=req.pts_pit_sv,
                        pts_pit_svh=req.pts_pit_svh,
                        pts_pit_h=req.pts_pit_h,
                        pts_pit_er=req.pts_pit_er,
                        pts_pit_bb=req.pts_pit_bb,
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
                        recent_projections=req.recent_projections,
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
            if req.scoring_mode == "roto":
                selected_hit_cats, selected_pit_cats = self._ctx.selected_roto_categories(settings)
                selected_roto_stat_cols = selected_hit_cats + selected_pit_cats
                if selected_roto_stat_cols:
                    stats_by_entity = self._ctx.start_year_roto_stats_by_entity(
                        start_year=req.start_year,
                        recent_projections=req.recent_projections,
                    )
                    identity_keys = out.apply(self._ctx.projection_identity_key, axis=1)
                    for stat_col in selected_roto_stat_cols:
                        stat_lookup = {
                            key: values.get(stat_col)
                            for key, values in stats_by_entity.items()
                            if stat_col in values
                        }
                        out[stat_col] = identity_keys.map(stat_lookup)
            explanations = self._ctx.build_calculation_explanations(out, settings=settings)

            year_cols = [c for c in out.columns if c.startswith("Value_")]
            cols = [
                "Player",
                self._ctx.player_key_col,
                self._ctx.player_entity_key_col,
                "DynastyMatchStatus",
                "Team",
                "Pos",
                "Age",
            ] + selected_roto_stat_cols + [
                "DynastyValue",
                "RawDynastyValue",
                "minor_eligible",
            ] + year_cols

            available_cols = [c for c in cols if c in out.columns]
            df = out[available_cols].copy()

            three_decimal_cols = {"AVG", "OBP", "SLG", "OPS"}
            for c in df.select_dtypes(include="float").columns:
                df[c] = df[c].round(3 if c in three_decimal_cols else 2)

            records = df.to_dict(orient="records")
            records = self._ctx.clean_records_for_json(records)

            payload = {
                "total": len(records),
                "settings": settings,
                "data": records,
                "explanations": explanations,
            }
            self._ctx.result_cache_set(result_cache_key, payload)
            return payload

        except HTTPException as exc:
            status_code = exc.status_code
            raise
        except Exception as exc:
            status_code = 500
            self._ctx.calc_logger.exception("calculator request failed source=%s", source)
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000.0, 1)
            cache_after = active_cache.cache_info()
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
            with self._ctx.calculator_job_lock:
                job = self._ctx.calculator_jobs.get(job_id)
                if job is None:
                    return
                if str(job.get("status") or "").lower() == self._ctx.calc_job_cancelled_status or bool(job.get("cancel_requested")):
                    self._ctx.mark_job_cancelled_locked(job)
                    self._ctx.cache_calculation_job_snapshot(job)
                    return
                now = self._ctx.iso_now()
                job["status"] = "completed"
                job["result"] = result
                job["completed_at"] = now
                job["updated_at"] = now
                job["error"] = None
                self._ctx.cache_calculation_job_snapshot(job)
        except HTTPException as exc:
            with self._ctx.calculator_job_lock:
                job = self._ctx.calculator_jobs.get(job_id)
                if job is None:
                    return
                if str(job.get("status") or "").lower() == self._ctx.calc_job_cancelled_status or bool(job.get("cancel_requested")):
                    self._ctx.mark_job_cancelled_locked(job)
                    self._ctx.cache_calculation_job_snapshot(job)
                    return
                now = self._ctx.iso_now()
                job["status"] = "failed"
                job["error"] = {"status_code": exc.status_code, "detail": exc.detail}
                job["completed_at"] = now
                job["updated_at"] = now
                job["result"] = None
                self._ctx.cache_calculation_job_snapshot(job)
        except Exception as exc:
            self._ctx.calc_logger.exception("calculator job crashed job_id=%s", job_id)
            with self._ctx.calculator_job_lock:
                job = self._ctx.calculator_jobs.get(job_id)
                if job is None:
                    return
                if str(job.get("status") or "").lower() == self._ctx.calc_job_cancelled_status or bool(job.get("cancel_requested")):
                    self._ctx.mark_job_cancelled_locked(job)
                    self._ctx.cache_calculation_job_snapshot(job)
                    return
                now = self._ctx.iso_now()
                job["status"] = "failed"
                job["error"] = {"status_code": 500, "detail": str(exc)}
                job["completed_at"] = now
                job["updated_at"] = now
                job["result"] = None
                self._ctx.cache_calculation_job_snapshot(job)
        finally:
            with self._ctx.calculator_job_lock:
                self._ctx.cleanup_calculation_jobs()

    def calculate_dynasty_values(self, req: CalculateRequest, request: Request):
        self._ctx.enforce_rate_limit(
            request,
            action="calc-sync",
            limit_per_minute=self._ctx.sync_rate_limit_per_minute,
        )
        return self._run_calculate_request(req, source="sync")

    def export_calculate_dynasty_values(self, req: CalculateExportRequest, request: Request):
        self._ctx.enforce_rate_limit(
            request,
            action="calc-sync",
            limit_per_minute=self._ctx.sync_rate_limit_per_minute,
        )
        payload = req.model_dump()
        export_format = str(payload.pop("format", "csv")).strip().lower()
        include_explanations = bool(payload.pop("include_explanations", False))
        calc_req = CalculateRequest(**payload)
        result = self._run_calculate_request(calc_req, source="sync-export")
        explain_rows = self._ctx.flatten_explanations_for_export(result.get("explanations", {})) if include_explanations else None
        return self._ctx.tabular_export_response(
            result.get("data", []),
            filename_base=f"dynasty-rankings-{calc_req.scoring_mode}",
            file_format="xlsx" if export_format == "xlsx" else "csv",
            explain_rows=explain_rows,
        )

    def create_calculate_dynasty_job(self, req: CalculateRequest, request: Request):
        self._ctx.enforce_rate_limit(
            request,
            action="calc-job-create",
            limit_per_minute=self._ctx.job_create_rate_limit_per_minute,
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
            limit_per_minute=self._ctx.job_status_rate_limit_per_minute,
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
            limit_per_minute=self._ctx.job_status_rate_limit_per_minute,
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
                except Exception:
                    pass
            self._ctx.mark_job_cancelled_locked(job)
            self._ctx.cache_calculation_job_snapshot(job)
            return self._ctx.calculation_job_public_payload(job)
