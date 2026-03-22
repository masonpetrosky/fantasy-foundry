from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException

from backend.core.calculator_helpers import with_resolved_hidden_dynasty_modeling_settings
from backend.core.calculator_orchestration import (
    CalculatorOrchestrationContext,
    calculate_dynasty_values,
    cancel_calculate_dynasty_job,
    create_calculate_dynasty_job,
    export_calculate_dynasty_values,
    get_calculate_dynasty_job,
    run_calculation_job,
)


class _RequestModel:
    def __init__(self, **payload: Any) -> None:
        self._payload = dict(payload)
        self.scoring_mode = str(self._payload.get("scoring_mode") or "roto")

    def model_dump(self) -> dict[str, Any]:
        return dict(self._payload)


class _Logger:
    def __init__(self) -> None:
        self.info_messages: list[str] = []
        self.exception_messages: list[str] = []

    def info(self, message: str, *args: Any) -> None:
        rendered = message % args if args else message
        self.info_messages.append(rendered)

    def exception(self, message: str, *args: Any) -> None:
        rendered = message % args if args else message
        self.exception_messages.append(rendered)


class _Future:
    def __init__(self, *, raise_on_cancel: bool = False) -> None:
        self.raise_on_cancel = raise_on_cancel
        self.cancel_calls = 0

    def cancel(self) -> bool:
        self.cancel_calls += 1
        if self.raise_on_cancel:
            raise RuntimeError("cancel failed")
        return True


class _Executor:
    def __init__(
        self,
        *,
        future: Any = None,
        raise_runtime: bool = False,
        on_submit: Any = None,
    ) -> None:
        self.future = future if future is not None else object()
        self.raise_runtime = raise_runtime
        self.on_submit = on_submit
        self.calls: list[tuple[Any, tuple[Any, ...]]] = []

    def submit(self, fn: Any, *args: Any) -> Any:
        self.calls.append((fn, args))
        if callable(self.on_submit):
            self.on_submit(fn, args)
        if self.raise_runtime:
            raise RuntimeError("worker unavailable")
        return self.future


def _job(
    *,
    job_id: str,
    status: str = "queued",
    client_ip: str = "127.0.0.1",
    future: Any = None,
) -> dict[str, Any]:
    return {
        "job_id": job_id,
        "status": status,
        "created_at": "2026-02-25T00:00:00Z",
        "started_at": None,
        "completed_at": None,
        "updated_at": "2026-02-25T00:00:00Z",
        "created_ts": 0.0,
        "client_ip": client_ip,
        "settings": {"scoring_mode": "roto"},
        "result": None,
        "error": None,
        "cancel_requested": False,
        "future": future,
    }


@dataclass
class _Harness:
    ctx: CalculatorOrchestrationContext
    jobs: dict[str, dict[str, Any]]
    cached_results: dict[str, dict[str, Any]]
    cached_job_snapshots: dict[str, dict[str, Any]]
    snapshot_by_job_id: dict[str, dict[str, Any]]
    snapshot_history: list[tuple[str, str]]
    rate_limit_calls: list[tuple[str, int]]
    cleanup_calls: list[Any]
    track_calls: list[tuple[str, str]]
    untrack_calls: list[tuple[str, str | None]]
    set_cancel_calls: list[str]
    clear_cancel_calls: list[str]
    cancel_markers: set[str]
    flattened_inputs: list[dict[str, dict[str, Any]]]
    export_calls: list[dict[str, Any]]
    logger: _Logger
    executor: _Executor


def _build_harness(
    *,
    max_active_jobs_per_ip: int = 3,
    max_active_jobs_total: int = 10,
    executor: _Executor | None = None,
) -> _Harness:
    jobs: dict[str, dict[str, Any]] = {}
    cached_results: dict[str, dict[str, Any]] = {}
    cached_job_snapshots: dict[str, dict[str, Any]] = {}
    snapshot_by_job_id: dict[str, dict[str, Any]] = {}
    snapshot_history: list[tuple[str, str]] = []
    rate_limit_calls: list[tuple[str, int]] = []
    cleanup_calls: list[Any] = []
    track_calls: list[tuple[str, str]] = []
    untrack_calls: list[tuple[str, str | None]] = []
    set_cancel_calls: list[str] = []
    clear_cancel_calls: list[str] = []
    cancel_markers: set[str] = set()
    flattened_inputs: list[dict[str, dict[str, Any]]] = []
    export_calls: list[dict[str, Any]] = []
    logger = _Logger()
    calc_executor = executor or _Executor()
    clock = {"count": 0}

    def iso_now() -> str:
        clock["count"] += 1
        return f"2026-02-25T00:00:{clock['count']:02d}Z"

    def calc_result_cache_key(settings: dict[str, Any]) -> str:
        return f"cache:{json.dumps(settings, sort_keys=True, separators=(',', ':'))}"

    def result_cache_get(cache_key: str) -> dict[str, Any] | None:
        return cached_results.get(cache_key)

    def active_jobs_for_ip(client_ip: str) -> int:
        return sum(
            1
            for job in jobs.values()
            if str(job.get("client_ip") or "") == client_ip
            and str(job.get("status") or "").lower() in {"queued", "running"}
        )

    def cleanup_calculation_jobs(now_ts: float | None) -> None:
        cleanup_calls.append(now_ts)

    def cache_calculation_job_snapshot(job: dict[str, Any]) -> None:
        job_id = str(job.get("job_id") or "")
        snapshot = dict(job)
        snapshot_by_job_id[job_id] = snapshot
        snapshot_history.append((job_id, str(snapshot.get("status") or "")))

    def cached_calculation_job_snapshot(job_id: str) -> dict[str, Any] | None:
        return cached_job_snapshots.get(job_id)

    def calculation_job_public_payload(job: dict[str, Any]) -> dict[str, Any]:
        status = str(job.get("status") or "").lower()
        payload: dict[str, Any] = {
            "job_id": str(job.get("job_id") or ""),
            "status": status,
            "settings": job.get("settings"),
        }
        if status == "completed":
            payload["result"] = job.get("result")
        elif status in {"failed", "cancelled"}:
            payload["error"] = job.get("error")
        return payload

    def mark_job_cancelled_locked(job: dict[str, Any]) -> None:
        now = iso_now()
        job["status"] = "cancelled"
        job["cancel_requested"] = True
        job["result"] = None
        job["error"] = {"status_code": 499, "detail": "Calculation cancelled."}
        job["completed_at"] = job.get("completed_at") or now
        job["updated_at"] = now

    def track_active_job(job_id: str, client_ip: str) -> None:
        track_calls.append((job_id, client_ip))

    def untrack_active_job(job_id: str, client_ip: str | None) -> None:
        untrack_calls.append((job_id, client_ip))

    def set_job_cancel_requested(job_id: str) -> None:
        cancel_markers.add(job_id)
        set_cancel_calls.append(job_id)

    def clear_job_cancel_requested(job_id: str) -> None:
        cancel_markers.discard(job_id)
        clear_cancel_calls.append(job_id)

    def job_cancel_requested(job_id: str) -> bool:
        return job_id in cancel_markers

    def flatten_explanations_for_export(explanations: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        flattened_inputs.append(explanations)
        return [{"entity_key": key} for key in sorted(explanations)]

    def tabular_export_response(
        rows: list[dict[str, Any]],
        *,
        filename_base: str,
        file_format: str,
        explain_rows: list[dict[str, Any]] | None,
        selected_columns: list[str] | None,
        default_columns: list[str],
        required_columns: list[str],
        disallowed_columns: set[str],
    ) -> dict[str, Any]:
        payload = {
            "rows": rows,
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

    def enforce_rate_limit(_request: object, *, action: str, limit_per_minute: int) -> None:
        rate_limit_calls.append((action, limit_per_minute))

    ctx = CalculatorOrchestrationContext(
        calculate_request_model=_RequestModel,
        enforce_rate_limit=enforce_rate_limit,
        sync_rate_limit_per_minute=13,
        sync_auth_rate_limit_per_minute=23,
        job_create_rate_limit_per_minute=11,
        job_create_auth_rate_limit_per_minute=21,
        job_status_rate_limit_per_minute=17,
        job_status_auth_rate_limit_per_minute=27,
        flatten_explanations_for_export=flatten_explanations_for_export,
        tabular_export_response=tabular_export_response,
        default_calculator_export_columns=lambda _rows: ["Player", "DynastyValue"],
        export_internal_column_blocklist={"PlayerKey", "PlayerEntityKey", "RawDynastyValue"},
        calc_result_cache_key=calc_result_cache_key,
        result_cache_get=result_cache_get,
        client_ip=lambda _request: "127.0.0.1",
        iso_now=iso_now,
        active_jobs_for_ip=active_jobs_for_ip,
        calculator_max_active_jobs_per_ip=max_active_jobs_per_ip,
        calculator_max_active_jobs_total=max_active_jobs_total,
        calculator_job_lock=threading.Lock(),
        calculator_jobs=jobs,
        cleanup_calculation_jobs=cleanup_calculation_jobs,
        cache_calculation_job_snapshot=cache_calculation_job_snapshot,
        cached_calculation_job_snapshot=cached_calculation_job_snapshot,
        calculation_job_public_payload=calculation_job_public_payload,
        mark_job_cancelled_locked=mark_job_cancelled_locked,
        calculator_job_executor=calc_executor,
        calc_job_cancelled_status="cancelled",
        calc_logger=logger,
        track_active_job=track_active_job,
        untrack_active_job=untrack_active_job,
        set_job_cancel_requested=set_job_cancel_requested,
        clear_job_cancel_requested=clear_job_cancel_requested,
        job_cancel_requested=job_cancel_requested,
    )
    return _Harness(
        ctx=ctx,
        jobs=jobs,
        cached_results=cached_results,
        cached_job_snapshots=cached_job_snapshots,
        snapshot_by_job_id=snapshot_by_job_id,
        snapshot_history=snapshot_history,
        rate_limit_calls=rate_limit_calls,
        cleanup_calls=cleanup_calls,
        track_calls=track_calls,
        untrack_calls=untrack_calls,
        set_cancel_calls=set_cancel_calls,
        clear_cancel_calls=clear_cancel_calls,
        cancel_markers=cancel_markers,
        flattened_inputs=flattened_inputs,
        export_calls=export_calls,
        logger=logger,
        executor=calc_executor,
    )


def test_run_calculation_job_returns_early_when_job_missing() -> None:
    harness = _build_harness()
    run_calculation_job("missing", {}, ctx=harness.ctx, run_calculate_request=lambda *_args, **_kwargs: {})

    assert harness.cleanup_calls == []
    assert harness.clear_cancel_calls == []
    assert harness.untrack_calls == []


def test_run_calculation_job_marks_cancelled_when_cancel_requested_before_start() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")
    harness.cancel_markers.add("job-1")

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=lambda *_args, **_kwargs: {"total": 1})

    job = harness.jobs["job-1"]
    assert job["status"] == "cancelled"
    assert job["cancel_requested"] is True
    assert harness.snapshot_by_job_id["job-1"]["status"] == "cancelled"
    assert harness.clear_cancel_calls == ["job-1"]
    assert harness.untrack_calls == [("job-1", "127.0.0.1")]


def test_run_calculation_job_success_path_transitions_running_to_completed() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")
    seen_sources: list[str] = []

    def fake_run(req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert isinstance(req, _RequestModel)
        seen_sources.append(source)
        return {"total": 2}

    run_calculation_job("job-1", {"scoring_mode": "points"}, ctx=harness.ctx, run_calculate_request=fake_run)

    job = harness.jobs["job-1"]
    assert seen_sources == ["job"]
    assert job["status"] == "completed"
    assert job["result"] == {"total": 2}
    assert job["error"] is None
    assert ("job-1", "running") in harness.snapshot_history
    assert ("job-1", "completed") in harness.snapshot_history
    assert harness.cleanup_calls == [None]
    assert harness.clear_cancel_calls == ["job-1"]
    assert harness.untrack_calls == [("job-1", "127.0.0.1")]


def test_run_calculation_job_marks_cancelled_if_cancel_requested_after_calculation() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert source == "job"
        harness.jobs["job-1"]["cancel_requested"] = True
        return {"total": 1}

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=fake_run)

    assert harness.jobs["job-1"]["status"] == "cancelled"
    assert harness.jobs["job-1"]["result"] is None
    assert harness.jobs["job-1"]["error"]["status_code"] == 499


def test_run_calculation_job_returns_cleanly_when_job_removed_before_completion_writeback() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert source == "job"
        harness.jobs.pop("job-1", None)
        return {"total": 1}

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=fake_run)

    assert "job-1" not in harness.jobs
    assert harness.cleanup_calls == [None]
    assert harness.clear_cancel_calls == ["job-1"]
    assert harness.untrack_calls == [("job-1", "127.0.0.1")]


def test_run_calculation_job_records_http_exception_details() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert source == "job"
        raise HTTPException(status_code=422, detail="invalid request")

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=fake_run)

    assert harness.jobs["job-1"]["status"] == "failed"
    assert harness.jobs["job-1"]["error"] == {"status_code": 422, "detail": "invalid request"}


def test_run_calculation_job_http_exception_with_late_cancel_marks_cancelled() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert source == "job"
        harness.cancel_markers.add("job-1")
        raise HTTPException(status_code=422, detail="invalid request")

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=fake_run)

    assert harness.jobs["job-1"]["status"] == "cancelled"
    assert harness.jobs["job-1"]["error"]["status_code"] == 499


def test_run_calculation_job_returns_cleanly_when_job_removed_before_http_error_writeback() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert source == "job"
        harness.jobs.pop("job-1", None)
        raise HTTPException(status_code=422, detail="bad request")

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=fake_run)

    assert "job-1" not in harness.jobs
    assert harness.cleanup_calls == [None]
    assert harness.clear_cancel_calls == ["job-1"]
    assert harness.untrack_calls == [("job-1", "127.0.0.1")]


def test_run_calculation_job_unexpected_exception_sets_internal_error_and_logs() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert source == "job"
        raise RuntimeError("boom")

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=fake_run)

    assert harness.jobs["job-1"]["status"] == "failed"
    assert harness.jobs["job-1"]["error"] == {"status_code": 500, "detail": "Internal calculator error."}
    assert any("calculator job crashed job_id=job-1" in line for line in harness.logger.exception_messages)


def test_run_calculation_job_unexpected_exception_with_late_cancel_marks_cancelled() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert source == "job"
        harness.cancel_markers.add("job-1")
        raise RuntimeError("boom")

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=fake_run)

    assert harness.jobs["job-1"]["status"] == "cancelled"
    assert harness.jobs["job-1"]["error"]["status_code"] == 499


def test_run_calculation_job_returns_cleanly_when_job_removed_before_runtime_error_writeback() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued")

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert source == "job"
        harness.jobs.pop("job-1", None)
        raise RuntimeError("boom")

    run_calculation_job("job-1", {}, ctx=harness.ctx, run_calculate_request=fake_run)

    assert "job-1" not in harness.jobs
    assert any("calculator job crashed job_id=job-1" in line for line in harness.logger.exception_messages)
    assert harness.cleanup_calls == [None]
    assert harness.clear_cancel_calls == ["job-1"]
    assert harness.untrack_calls == [("job-1", "127.0.0.1")]


def test_calculate_dynasty_values_enforces_rate_limit_and_uses_sync_source() -> None:
    harness = _build_harness()
    seen_sources: list[str] = []

    def fake_run(req: _RequestModel, *, source: str) -> dict[str, Any]:
        assert isinstance(req, _RequestModel)
        seen_sources.append(source)
        return {"ok": True}

    payload = calculate_dynasty_values(
        _RequestModel(scoring_mode="points"),
        object(),
        ctx=harness.ctx,
        run_calculate_request=fake_run,
    )

    assert payload == {"ok": True}
    assert seen_sources == ["sync"]
    assert harness.rate_limit_calls == [("calc-sync", 13)]


def test_calculate_dynasty_values_uses_authenticated_sync_rate_limit() -> None:
    harness = _build_harness()
    request = SimpleNamespace(state=SimpleNamespace(calc_api_key_authenticated=True))

    calculate_dynasty_values(
        _RequestModel(scoring_mode="points"),
        request,
        ctx=harness.ctx,
        run_calculate_request=lambda _req, *, source: {"source": source, "ok": True},
    )

    assert harness.rate_limit_calls == [("calc-sync", 23)]


def test_export_calculate_dynasty_values_supports_xlsx_with_explanations() -> None:
    harness = _build_harness()
    seen_sources: list[str] = []

    def fake_run(_req: _RequestModel, *, source: str) -> dict[str, Any]:
        seen_sources.append(source)
        return {
            "data": [{"Player": "A", "DynastyValue": 1.0}],
            "explanations": {"a": {"dynasty_value": 1.0}},
        }

    response = export_calculate_dynasty_values(
        _RequestModel(
            scoring_mode="points",
            format="xlsx",
            include_explanations=True,
            export_columns=["Player", "DynastyValue"],
        ),
        object(),
        ctx=harness.ctx,
        run_calculate_request=fake_run,
    )

    assert seen_sources == ["sync-export"]
    assert harness.rate_limit_calls == [("calc-sync", 13)]
    assert harness.flattened_inputs == [{"a": {"dynasty_value": 1.0}}]
    assert response["file_format"] == "xlsx"
    assert response["filename_base"] == "dynasty-rankings-points"
    assert response["selected_columns"] == ["Player", "DynastyValue"]
    assert response["disallowed_columns"] == {"PlayerKey", "PlayerEntityKey", "RawDynastyValue"}


def test_export_calculate_dynasty_values_defaults_to_csv_without_explanations() -> None:
    harness = _build_harness()

    response = export_calculate_dynasty_values(
        _RequestModel(
            scoring_mode="roto",
            format="parquet",
            include_explanations=False,
            export_columns=None,
        ),
        object(),
        ctx=harness.ctx,
        run_calculate_request=lambda _req, *, source: {
            "data": [{"Player": "A", "DynastyValue": 1.0}],
            "explanations": {"a": {"dynasty_value": 1.0}},
        },
    )

    assert response["file_format"] == "csv"
    assert response["explain_rows"] is None
    assert harness.flattened_inputs == []


def test_create_calculate_dynasty_job_returns_cached_result_without_executor_submit() -> None:
    harness = _build_harness()
    req = _RequestModel(scoring_mode="roto", teams=12)
    cache_key = harness.ctx.calc_result_cache_key(with_resolved_hidden_dynasty_modeling_settings(req.model_dump()))
    harness.cached_results[cache_key] = {"total": 1, "data": [{"Player": "Cached"}]}

    payload = create_calculate_dynasty_job(
        req,
        object(),
        ctx=harness.ctx,
        run_calculation_job=lambda _job_id, _payload: None,
    )

    job_id = payload["job_id"]
    assert payload["status"] == "completed"
    assert harness.jobs[job_id]["result"] == {"total": 1, "data": [{"Player": "Cached"}]}
    assert harness.executor.calls == []
    assert harness.track_calls == []
    assert harness.clear_cancel_calls == []
    assert any("calculator job cache-hit" in line for line in harness.logger.info_messages)


def test_create_calculate_dynasty_job_enforces_active_job_cap() -> None:
    harness = _build_harness(max_active_jobs_per_ip=1)
    harness.jobs["existing"] = _job(job_id="existing", status="queued")

    with pytest.raises(HTTPException, match="Too many active calculation jobs"):
        create_calculate_dynasty_job(
            _RequestModel(scoring_mode="roto", teams=12),
            object(),
            ctx=harness.ctx,
            run_calculation_job=lambda _job_id, _payload: None,
        )

    assert set(harness.jobs) == {"existing"}


def test_create_calculate_dynasty_job_enforces_global_active_job_cap() -> None:
    harness = _build_harness(max_active_jobs_total=1)
    harness.jobs["existing"] = _job(job_id="existing", status="running", client_ip="10.10.10.10")

    with pytest.raises(HTTPException, match="Calculation queue is full right now"):
        create_calculate_dynasty_job(
            _RequestModel(scoring_mode="roto", teams=12),
            object(),
            ctx=harness.ctx,
            run_calculation_job=lambda _job_id, _payload: None,
        )

    assert set(harness.jobs) == {"existing"}


def test_create_calculate_dynasty_job_raises_503_and_untracks_when_executor_unavailable() -> None:
    harness = _build_harness(executor=_Executor(raise_runtime=True))

    with pytest.raises(HTTPException, match="Calculation worker is unavailable."):
        create_calculate_dynasty_job(
            _RequestModel(scoring_mode="roto"),
            object(),
            ctx=harness.ctx,
            run_calculation_job=lambda _job_id, _payload: None,
        )

    assert harness.jobs == {}
    assert len(harness.executor.calls) == 1
    assert len(harness.untrack_calls) == 1
    assert harness.untrack_calls[0][1] == "127.0.0.1"


def test_create_calculate_dynasty_job_queues_and_attaches_future() -> None:
    future = _Future()
    harness = _build_harness(executor=_Executor(future=future))

    payload = create_calculate_dynasty_job(
        _RequestModel(scoring_mode="roto"),
        object(),
        ctx=harness.ctx,
        run_calculation_job=lambda _job_id, _payload: None,
    )

    job_id = payload["job_id"]
    assert payload["status"] == "queued"
    assert harness.jobs[job_id]["future"] is future
    assert harness.track_calls == [(job_id, "127.0.0.1")]
    assert harness.clear_cancel_calls == [job_id]
    assert len(harness.executor.calls) == 1
    assert any("calculator job queued" in line for line in harness.logger.info_messages)


def test_create_calculate_dynasty_job_handles_job_removed_before_future_assignment() -> None:
    removed_job_ids: list[str] = []

    def on_submit(_fn: Any, args: tuple[Any, ...]) -> None:
        removed_job_ids.append(str(args[0]))
        harness.jobs.pop(str(args[0]), None)

    harness = _build_harness(executor=_Executor(future=_Future(), on_submit=on_submit))

    payload = create_calculate_dynasty_job(
        _RequestModel(scoring_mode="roto"),
        object(),
        ctx=harness.ctx,
        run_calculation_job=lambda _job_id, _payload: None,
    )

    assert payload["status"] == "queued"
    assert removed_job_ids == [payload["job_id"]]
    assert payload["job_id"] not in harness.jobs


def test_get_calculate_dynasty_job_returns_live_job_payload() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="completed")
    harness.jobs["job-1"]["result"] = {"total": 1}

    payload = get_calculate_dynasty_job("job-1", object(), ctx=harness.ctx)

    assert payload["status"] == "completed"
    assert payload["result"] == {"total": 1}
    assert harness.rate_limit_calls == [("calc-job-status", 17)]


def test_get_calculate_dynasty_job_falls_back_to_cached_snapshot() -> None:
    harness = _build_harness()
    harness.cached_job_snapshots["job-1"] = {"job_id": "job-1", "status": "completed"}

    payload = get_calculate_dynasty_job("job-1", object(), ctx=harness.ctx)

    assert payload == {"job_id": "job-1", "status": "completed", "settings": None, "result": None}


def test_get_calculate_dynasty_job_raises_404_when_missing() -> None:
    harness = _build_harness()

    with pytest.raises(HTTPException, match="Calculation job not found or expired."):
        get_calculate_dynasty_job("missing", object(), ctx=harness.ctx)


def test_cancel_calculate_dynasty_job_synthesizes_cancellation_for_cached_active_job() -> None:
    harness = _build_harness()
    harness.cached_job_snapshots["ghost"] = {"status": "queued", "settings": {"mode": "x"}}

    payload = cancel_calculate_dynasty_job("ghost", object(), ctx=harness.ctx)

    assert payload["status"] == "cancelled"
    assert payload["error"]["status_code"] == 499
    assert harness.set_cancel_calls == ["ghost"]
    assert harness.untrack_calls == [("ghost", None)]
    assert "ghost" in harness.snapshot_by_job_id


def test_cancel_calculate_dynasty_job_returns_cached_terminal_job_without_changes() -> None:
    harness = _build_harness()
    cached = {"job_id": "done", "status": "completed", "result": {"total": 1}}
    harness.cached_job_snapshots["done"] = cached

    payload = cancel_calculate_dynasty_job("done", object(), ctx=harness.ctx)

    assert payload == {"job_id": "done", "status": "completed", "settings": None, "result": {"total": 1}}
    assert harness.set_cancel_calls == []


def test_cancel_calculate_dynasty_job_raises_404_when_not_found_anywhere() -> None:
    harness = _build_harness()

    with pytest.raises(HTTPException, match="Calculation job not found or expired."):
        cancel_calculate_dynasty_job("missing", object(), ctx=harness.ctx)


def test_cancel_calculate_dynasty_job_returns_terminal_live_job() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="completed")

    payload = cancel_calculate_dynasty_job("job-1", object(), ctx=harness.ctx)

    assert payload["status"] == "completed"
    assert harness.jobs["job-1"]["cancel_requested"] is False


def test_cancel_calculate_dynasty_job_cancels_live_queued_job_with_future() -> None:
    harness = _build_harness()
    future = _Future()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued", future=future)

    payload = cancel_calculate_dynasty_job("job-1", object(), ctx=harness.ctx)

    assert payload["status"] == "cancelled"
    assert payload["error"]["status_code"] == 499
    assert harness.jobs["job-1"]["cancel_requested"] is True
    assert future.cancel_calls == 1
    assert harness.set_cancel_calls == ["job-1"]
    assert harness.untrack_calls == [("job-1", "127.0.0.1")]


def test_cancel_calculate_dynasty_job_swallow_future_cancel_errors() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="running", future=_Future(raise_on_cancel=True))

    payload = cancel_calculate_dynasty_job("job-1", object(), ctx=harness.ctx)

    assert payload["status"] == "cancelled"
    assert payload["error"]["status_code"] == 499


def test_cancel_calculate_dynasty_job_handles_non_callable_future_cancel() -> None:
    harness = _build_harness()
    harness.jobs["job-1"] = _job(job_id="job-1", status="queued", future=object())

    payload = cancel_calculate_dynasty_job("job-1", object(), ctx=harness.ctx)

    assert payload["status"] == "cancelled"
    assert payload["error"]["status_code"] == 499
