from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

import pandas as pd
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.services.calculator.service import (
    CalculateExportRequest,
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

    def __call__(self, **_kwargs) -> pd.DataFrame:
        self._misses += 1
        return self._frame

    def cache_info(self):
        return type("CacheInfo", (), {"hits": self._hits, "misses": self._misses})()


class _Executor:
    def __init__(self, *, future: Any = None, raise_runtime: bool = False) -> None:
        self.future = future if future is not None else object()
        self.raise_runtime = raise_runtime
        self.calls: list[tuple[Any, tuple[Any, ...]]] = []

    def submit(self, fn, *args):
        self.calls.append((fn, args))
        if self.raise_runtime:
            raise RuntimeError("worker unavailable")
        return self.future


class _Future:
    def __init__(self, *, raise_on_cancel: bool = False) -> None:
        self.raise_on_cancel = raise_on_cancel
        self.cancel_calls = 0

    def cancel(self):
        self.cancel_calls += 1
        if self.raise_on_cancel:
            raise RuntimeError("cancel failed")
        return True


def _job(
    *,
    job_id: str,
    status: str = "queued",
    client_ip: str = "127.0.0.1",
    future: Any = None,
) -> dict:
    return {
        "job_id": job_id,
        "status": status,
        "created_at": "2026-02-25T00:00:00Z",
        "started_at": None,
        "completed_at": None,
        "updated_at": "2026-02-25T00:00:00Z",
        "created_ts": 0.0,
        "client_ip": client_ip,
        "settings": {},
        "result": None,
        "error": None,
        "cancel_requested": False,
        "future": future,
    }


@dataclass
class _Harness:
    service: CalculatorService
    jobs: dict[str, dict]
    result_cache: dict[str, dict]
    snapshots: dict[str, dict]
    cached_snapshots: dict[str, dict]
    cleanup_calls: list[tuple[tuple[Any, ...], dict[str, Any]]]
    rate_limit_calls: list[tuple[str, int]]
    export_calls: list[dict[str, Any]]
    flattened_inputs: list[dict[str, dict]]
    logger: _Logger
    executor: _Executor


def _build_harness(
    *,
    max_active_jobs_per_ip: int = 3,
    executor: _Executor | None = None,
) -> _Harness:
    jobs: dict[str, dict] = {}
    result_cache: dict[str, dict] = {}
    snapshots: dict[str, dict] = {}
    cached_snapshots: dict[str, dict] = {}
    cleanup_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    rate_limit_calls: list[tuple[str, int]] = []
    export_calls: list[dict[str, Any]] = []
    flattened_inputs: list[dict[str, dict]] = []
    logger = _Logger()
    calc_executor = executor or _Executor()
    iso_counter = {"value": 0}

    def iso_now() -> str:
        iso_counter["value"] += 1
        return f"2026-02-25T00:00:{iso_counter['value']:02d}Z"

    def calc_result_cache_key(settings: dict[str, Any]) -> str:
        return f"cache:{settings.get('scoring_mode', 'roto')}:{settings.get('teams', 0)}:{settings.get('start_year', 0)}"

    def result_cache_get(cache_key: str):
        return result_cache.get(cache_key)

    def result_cache_set(cache_key: str, payload: dict) -> None:
        result_cache[cache_key] = payload

    def active_jobs_for_ip(client_ip: str) -> int:
        return sum(
            1
            for job in jobs.values()
            if str(job.get("client_ip") or "") == client_ip
            and str(job.get("status") or "").lower() in {"queued", "running"}
        )

    def cleanup_calculation_jobs(*args, **kwargs) -> None:
        cleanup_calls.append((args, kwargs))

    def cache_calculation_job_snapshot(job: dict) -> None:
        snapshots[str(job.get("job_id") or "")] = dict(job)

    def cached_calculation_job_snapshot(job_id: str):
        return cached_snapshots.get(job_id)

    def calculation_job_public_payload(job: dict) -> dict:
        status = str(job.get("status") or "").lower()
        payload = {
            "job_id": str(job.get("job_id") or ""),
            "status": status,
            "settings": job.get("settings"),
        }
        if status == "completed":
            payload["result"] = job.get("result")
        if status in {"failed", "cancelled"}:
            payload["error"] = job.get("error")
        return payload

    def mark_job_cancelled_locked(job: dict) -> None:
        now = iso_now()
        job["status"] = "cancelled"
        job["cancel_requested"] = True
        job["result"] = None
        job["error"] = {"status_code": 499, "detail": "Calculation cancelled."}
        job["completed_at"] = job.get("completed_at") or now
        job["updated_at"] = now

    def tabular_export_response(
        result_rows: list[dict],
        *,
        filename_base: str,
        file_format: str,
        explain_rows: list[dict] | None,
        selected_columns: list[str] | None,
        default_columns: list[str],
        required_columns: list[str],
        disallowed_columns: list[str],
    ) -> dict:
        payload = {
            "rows": result_rows,
            "filename_base": filename_base,
            "file_format": file_format,
            "explain_rows": explain_rows,
            "selected_columns": selected_columns,
            "default_columns": default_columns,
            "required_columns": required_columns,
            "disallowed_columns": disallowed_columns,
        }
        export_calls.append(payload)
        return payload

    def flatten_explanations_for_export(explanations: dict[str, dict]) -> list[dict]:
        flattened_inputs.append(explanations)
        return [{"key": key} for key in sorted(explanations)]

    def enforce_rate_limit(_request: object, *, action: str, limit_per_minute: int) -> None:
        rate_limit_calls.append((action, limit_per_minute))

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

    ctx = CalculatorServiceContext(
        refresh_data_if_needed=lambda: None,
        coerce_meta_years=lambda _meta: [2026],
        get_meta=lambda: {"years": [2026]},
        calc_result_cache_key=calc_result_cache_key,
        result_cache_get=result_cache_get,
        result_cache_set=result_cache_set,
        calculate_common_dynasty_frame_cached=cached_common,
        calculate_points_dynasty_frame_cached=cached_points,
        roto_category_settings_from_dict=lambda _settings: {},
        is_user_fixable_calculation_error=lambda message: "not enough players" in message.lower(),
        player_identity_by_name=lambda: {},
        normalize_player_key=lambda value: str(value or "").strip().lower().replace(" ", "-"),
        player_key_col="PlayerKey",
        player_entity_key_col="PlayerEntityKey",
        selected_roto_categories=lambda _settings: (["AVG"], ["K"]),
        start_year_roto_stats_by_entity=lambda **_kwargs: {},
        projection_identity_key=lambda row: str(getattr(row, "get", lambda *_args: "")("PlayerEntityKey") or ""),
        build_calculation_explanations=lambda _out, *, settings: {"mode": {"mode": settings.get("scoring_mode", "roto")}},
        clean_records_for_json=lambda records: records,
        flatten_explanations_for_export=flatten_explanations_for_export,
        tabular_export_response=tabular_export_response,
        calc_logger=logger,
        enforce_rate_limit=enforce_rate_limit,
        sync_rate_limit_per_minute=7,
        job_create_rate_limit_per_minute=5,
        job_status_rate_limit_per_minute=11,
        client_ip=lambda _request: "127.0.0.1",
        iso_now=iso_now,
        active_jobs_for_ip=active_jobs_for_ip,
        calculator_max_active_jobs_per_ip=max_active_jobs_per_ip,
        calculator_job_lock=threading.Lock(),
        calculator_jobs=jobs,
        cleanup_calculation_jobs=cleanup_calculation_jobs,
        cache_calculation_job_snapshot=cache_calculation_job_snapshot,
        cached_calculation_job_snapshot=cached_calculation_job_snapshot,
        calculation_job_public_payload=calculation_job_public_payload,
        mark_job_cancelled_locked=mark_job_cancelled_locked,
        calculator_job_executor=calc_executor,
        calc_job_cancelled_status="cancelled",
    )
    service = CalculatorService(ctx)
    return _Harness(
        service=service,
        jobs=jobs,
        result_cache=result_cache,
        snapshots=snapshots,
        cached_snapshots=cached_snapshots,
        cleanup_calls=cleanup_calls,
        rate_limit_calls=rate_limit_calls,
        export_calls=export_calls,
        flattened_inputs=flattened_inputs,
        logger=logger,
        executor=calc_executor,
    )


def test_calculate_request_rejects_points_mode_with_all_zero_scoring_rules() -> None:
    points_fields = {
        field_name: 0.0
        for field_name in CalculateRequest.model_fields
        if field_name.startswith("pts_")
    }
    with pytest.raises(ValidationError, match="Points scoring must include at least one non-zero scoring rule."):
        CalculateRequest(scoring_mode="points", **points_fields)


def test_calculate_request_rejects_roto_mode_without_hitting_categories() -> None:
    disabled_hitting = {
        field_name: False
        for field_name in CalculateRequest.model_fields
        if field_name.startswith("roto_hit_")
    }
    with pytest.raises(ValidationError, match="Roto scoring must include at least one hitting category."):
        CalculateRequest(scoring_mode="roto", **disabled_hitting)


def test_calculate_request_rejects_roto_mode_without_pitching_categories() -> None:
    disabled_pitching = {
        field_name: False
        for field_name in CalculateRequest.model_fields
        if field_name.startswith("roto_pit_")
    }
    with pytest.raises(ValidationError, match="Roto scoring must include at least one pitching category."):
        CalculateRequest(scoring_mode="roto", **disabled_pitching)


def test_default_export_columns_fallback_for_empty_rows() -> None:
    harness = _build_harness()
    assert harness.service._default_export_columns([]) == ["Player", "DynastyValue", "Age", "Team", "Pos"]


def test_default_export_columns_orders_points_stats_and_year_columns() -> None:
    harness = _build_harness()
    rows = [
        {
            "Player": "Jane Roe",
            "DynastyValue": 12.3,
            "Age": 24,
            "Team": "SEA",
            "Pos": "OF",
            "PitchingPoints": 1.0,
            "HR": 42,
            "AVG": 0.301,
            "Value_2030": 3.2,
            "Value_total": 9.9,
        },
        {
            "Player": "John Roe",
            "Value_2027": 4.4,
            "HR": 28,
            "PitchingPoints": 0.0,
        },
    ]

    assert harness.service._default_export_columns(rows) == [
        "Player",
        "DynastyValue",
        "Age",
        "Team",
        "Pos",
        "PitchingPoints",
        "HR",
        "AVG",
        "Value_2027",
        "Value_2030",
        "Value_total",
    ]


def test_calculate_dynasty_values_enforces_rate_limit_and_uses_sync_source() -> None:
    harness = _build_harness()
    seen_sources: list[str] = []

    def fake_run(req: CalculateRequest, *, source: str) -> dict:
        assert isinstance(req, CalculateRequest)
        seen_sources.append(source)
        return {"ok": True}

    harness.service._run_calculate_request = fake_run

    response = harness.service.calculate_dynasty_values(CalculateRequest(), request=object())

    assert response == {"ok": True}
    assert seen_sources == ["sync"]
    assert harness.rate_limit_calls == [("calc-sync", 7)]


def test_export_calculate_values_uses_xlsx_and_includes_explanations_when_requested() -> None:
    harness = _build_harness()
    seen_sources: list[str] = []

    def fake_run(_req: CalculateRequest, *, source: str) -> dict:
        seen_sources.append(source)
        return {
            "data": [{"Player": "Jane Roe", "DynastyValue": 7.1, "PlayerKey": "jane-roe"}],
            "explanations": {"jane-roe": {"dynasty_value": 7.1}},
        }

    harness.service._run_calculate_request = fake_run
    req = CalculateExportRequest(
        scoring_mode="points",
        format="xlsx",
        include_explanations=True,
        export_columns=["Player", "DynastyValue"],
    )

    response = harness.service.export_calculate_dynasty_values(req, request=object())

    assert seen_sources == ["sync-export"]
    assert harness.rate_limit_calls == [("calc-sync", 7)]
    assert harness.flattened_inputs == [{"jane-roe": {"dynasty_value": 7.1}}]
    assert response["file_format"] == "xlsx"
    assert response["filename_base"] == "dynasty-rankings-points"
    assert response["selected_columns"] == ["Player", "DynastyValue"]
    assert "PlayerKey" in response["disallowed_columns"]
    assert "PlayerEntityKey" in response["disallowed_columns"]


def test_export_calculate_values_defaults_to_csv_and_skips_explanations_by_default() -> None:
    harness = _build_harness()
    harness.service._run_calculate_request = lambda _req, *, source: {
        "data": [{"Player": "Jane Roe", "DynastyValue": 7.1}],
        "explanations": {"jane-roe": {"dynasty_value": 7.1}},
    }
    req = CalculateExportRequest(format="csv", include_explanations=False)

    response = harness.service.export_calculate_dynasty_values(req, request=object())

    assert response["file_format"] == "csv"
    assert response["explain_rows"] is None
    assert harness.flattened_inputs == []


def test_create_calculate_job_uses_cached_result_without_submitting_executor_work() -> None:
    harness = _build_harness()
    req = CalculateRequest()
    cache_key = harness.service._ctx.calc_result_cache_key(req.model_dump())
    harness.result_cache[cache_key] = {"total": 1, "data": [{"Player": "Cached"}]}

    payload = harness.service.create_calculate_dynasty_job(req, request=object())

    assert payload["status"] == "completed"
    job_id = payload["job_id"]
    assert harness.jobs[job_id]["result"] == {"total": 1, "data": [{"Player": "Cached"}]}
    assert harness.executor.calls == []
    assert job_id in harness.snapshots
    assert harness.rate_limit_calls == [("calc-job-create", 5)]


def test_create_calculate_job_rejects_when_active_job_cap_is_reached() -> None:
    harness = _build_harness(max_active_jobs_per_ip=1)
    harness.jobs["existing"] = _job(job_id="existing", status="queued", client_ip="127.0.0.1")

    with pytest.raises(HTTPException, match="Too many active calculation jobs"):
        harness.service.create_calculate_dynasty_job(CalculateRequest(), request=object())

    assert set(harness.jobs) == {"existing"}


def test_create_calculate_job_returns_503_and_cleans_up_when_executor_submit_fails() -> None:
    executor = _Executor(raise_runtime=True)
    harness = _build_harness(executor=executor)

    with pytest.raises(HTTPException, match="Calculation worker is unavailable."):
        harness.service.create_calculate_dynasty_job(CalculateRequest(), request=object())

    assert harness.jobs == {}
    assert len(executor.calls) == 1


def test_create_calculate_job_enqueues_and_attaches_future_to_live_job() -> None:
    fake_future = _Future()
    harness = _build_harness(executor=_Executor(future=fake_future))

    payload = harness.service.create_calculate_dynasty_job(CalculateRequest(), request=object())

    assert payload["status"] == "queued"
    job_id = payload["job_id"]
    assert harness.jobs[job_id]["future"] is fake_future
    assert job_id not in harness.snapshots
    assert len(harness.executor.calls) == 1
    submitted_fn, submitted_args = harness.executor.calls[0]
    assert submitted_fn == harness.service._run_calculation_job
    assert submitted_args[0] == job_id
    assert isinstance(submitted_args[1], dict)
    assert any("calculator job queued" in message for message in harness.logger.info_messages)


def test_get_calculate_job_returns_cached_snapshot_when_not_found_in_memory() -> None:
    harness = _build_harness()
    harness.cached_snapshots["cached-job"] = {"job_id": "cached-job", "status": "completed", "result": {"total": 1}}

    payload = harness.service.get_calculate_dynasty_job("cached-job", request=object())

    assert payload["status"] == "completed"
    assert harness.rate_limit_calls == [("calc-job-status", 11)]


def test_get_calculate_job_raises_404_when_missing_from_memory_and_cache() -> None:
    harness = _build_harness()

    with pytest.raises(HTTPException, match="Calculation job not found or expired."):
        harness.service.get_calculate_dynasty_job("missing-job", request=object())


def test_cancel_calculate_job_returns_existing_payload_for_terminal_status() -> None:
    harness = _build_harness()
    harness.jobs["done"] = _job(job_id="done", status="completed")

    payload = harness.service.cancel_calculate_dynasty_job("done", request=object())

    assert payload["status"] == "completed"
    assert harness.jobs["done"]["cancel_requested"] is False


def test_cancel_calculate_job_marks_running_job_cancelled_even_if_future_cancel_raises() -> None:
    harness = _build_harness()
    future = _Future(raise_on_cancel=True)
    harness.jobs["job-1"] = _job(job_id="job-1", status="running", future=future)

    payload = harness.service.cancel_calculate_dynasty_job("job-1", request=object())

    assert payload["status"] == "cancelled"
    assert harness.jobs["job-1"]["cancel_requested"] is True
    assert harness.jobs["job-1"]["error"]["status_code"] == 499
    assert "job-1" in harness.snapshots
    assert future.cancel_calls == 1


def test_cancel_calculate_job_returns_cached_snapshot_when_job_missing() -> None:
    harness = _build_harness()
    harness.cached_snapshots["cached-job"] = {"job_id": "cached-job", "status": "completed"}

    payload = harness.service.cancel_calculate_dynasty_job("cached-job", request=object())

    assert payload == {"job_id": "cached-job", "status": "completed"}


def test_cancel_calculate_job_raises_404_when_job_missing_everywhere() -> None:
    harness = _build_harness()

    with pytest.raises(HTTPException, match="Calculation job not found or expired."):
        harness.service.cancel_calculate_dynasty_job("missing-job", request=object())


def test_run_calculation_job_marks_pre_cancelled_job_without_running_request() -> None:
    harness = _build_harness()
    job = _job(job_id="cancelled-job", status="cancelled")
    harness.jobs["cancelled-job"] = job

    def should_not_run(*_args, **_kwargs):
        raise AssertionError("run request should not be called")

    harness.service._run_calculate_request = should_not_run

    harness.service._run_calculation_job("cancelled-job", req_payload={})

    assert harness.jobs["cancelled-job"]["status"] == "cancelled"
    assert "cancelled-job" in harness.snapshots


def test_run_calculation_job_completes_and_stores_result_payload() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")
    harness.service._run_calculate_request = lambda _req, *, source: {"source": source, "total": 2}

    harness.service._run_calculation_job("job-1", req_payload={})

    job = harness.jobs["job-1"]
    assert job["status"] == "completed"
    assert job["result"] == {"source": "job", "total": 2}
    assert job["error"] is None
    assert len(harness.cleanup_calls) == 1


def test_run_calculation_job_marks_cancelled_when_cancel_requested_after_calculation() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def mark_cancel_and_return(_req, *, source: str):
        assert source == "job"
        harness.jobs["job-1"]["cancel_requested"] = True
        return {"total": 1}

    harness.service._run_calculate_request = mark_cancel_and_return

    harness.service._run_calculation_job("job-1", req_payload={})

    assert harness.jobs["job-1"]["status"] == "cancelled"
    assert harness.jobs["job-1"]["result"] is None
    assert harness.jobs["job-1"]["error"]["status_code"] == 499


def test_run_calculation_job_marks_failed_with_http_exception_details() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def raise_http(_req, *, source: str):
        assert source == "job"
        raise HTTPException(status_code=422, detail="bad settings")

    harness.service._run_calculate_request = raise_http

    harness.service._run_calculation_job("job-1", req_payload={})

    assert harness.jobs["job-1"]["status"] == "failed"
    assert harness.jobs["job-1"]["error"] == {"status_code": 422, "detail": "bad settings"}


def test_run_calculation_job_marks_cancelled_when_http_exception_arrives_after_cancel_request() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def cancel_then_raise_http(_req, *, source: str):
        assert source == "job"
        harness.jobs["job-1"]["cancel_requested"] = True
        raise HTTPException(status_code=422, detail="bad settings")

    harness.service._run_calculate_request = cancel_then_raise_http

    harness.service._run_calculation_job("job-1", req_payload={})

    assert harness.jobs["job-1"]["status"] == "cancelled"
    assert harness.jobs["job-1"]["error"]["status_code"] == 499


def test_run_calculation_job_marks_failed_with_internal_error_for_unhandled_exception() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def raise_runtime(_req, *, source: str):
        assert source == "job"
        raise RuntimeError("boom")

    harness.service._run_calculate_request = raise_runtime

    harness.service._run_calculation_job("job-1", req_payload={})

    assert harness.jobs["job-1"]["status"] == "failed"
    assert harness.jobs["job-1"]["error"] == {"status_code": 500, "detail": "Internal calculator error."}
    assert any("calculator job crashed" in message for message in harness.logger.exception_messages)
