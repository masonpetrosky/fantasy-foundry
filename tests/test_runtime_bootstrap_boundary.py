from __future__ import annotations

import re
from types import SimpleNamespace

from backend.core import runtime_bootstrap


class _FakeEndpointHandlers:
    def __init__(self, config):
        self.config = config

    def meta_payload(self):
        return {"meta": True}

    def get_meta(self, request):
        return {"request": request}

    def version_payload(self):
        return {"version": "v1"}

    def payload_etag(self, payload):
        return "etag"

    def etag_matches(self, if_none_match, current_etag):
        return if_none_match == current_etag

    def get_version(self, request):
        return {"version": "v1"}

    def dynasty_lookup_cache_health_payload(self):
        return {"status": "ready"}

    def get_health(self):
        return {"status": "ok"}

    def get_ready(self):
        return {"ready": True}

    def get_ops(self):
        return {"ops": True}

    def run_calculation_job(self, job_id, req_payload):
        return {"job_id": job_id, "req_payload": req_payload}

    def projection_response(self, *args, **kwargs):
        return {"projection": True}

    def export_projections(self, *args, **kwargs):
        return {"export": True}

    def calculate_dynasty_values(self, req, request):
        return {"calc": True}

    def export_calculate_dynasty_values(self, req, request):
        return {"calc_export": True}

    def create_calculate_dynasty_job(self, req, request):
        return {"job": "created"}

    def get_calculate_dynasty_job(self, job_id, request):
        return {"job": job_id}

    def cancel_calculate_dynasty_job(self, job_id, request):
        return {"job": job_id, "status": "cancelled"}


def test_build_runtime_bootstrap_wires_services_handlers_and_aliases(monkeypatch) -> None:
    calls: dict[str, object] = {}
    filter_calls: list[tuple[tuple, dict]] = []
    run_calls: list[tuple[object, str]] = []

    class FakeProjectionService:
        def __init__(self, ctx):
            calls["projection_ctx"] = ctx
            self._cached_projection_rows = SimpleNamespace(name="projection-cache")
            self._cached_all_projection_rows = SimpleNamespace(name="all-cache")
            self._projection_sortable_columns_for_dataset = SimpleNamespace(name="sortable-cache")

    class FakeCalculatorService:
        calculate_request_model = object()
        calculate_export_request_model = object()

        def _run_calculate_request(self, req, *, source: str):
            run_calls.append((req, source))
            return {"source": source, "ok": True}

    calculator_service = FakeCalculatorService()

    class FakeOrchestrationHelpers:
        def status_orchestration_context(self):
            return "status-context"

        def calculator_orchestration_context(self):
            return "calculator-context"

    def fake_filter_records(*args, **kwargs):
        filter_calls.append((args, kwargs))
        return [{"filtered": True}]

    state = SimpleNamespace(
        _refresh_data_if_needed=lambda: None,
        BAT_DATA=[{"Player": "A"}],
        PIT_DATA=[{"Player": "B"}],
        META={"years": [2026]},
        _normalize_player_key=lambda value: str(value or "").strip().lower().replace(" ", "-"),
        _resolve_projection_year_filter=lambda year, years, valid_years=None: {2026},
        _parse_dynasty_years=lambda raw, valid_years=None: [2026],
        _attach_dynasty_values=lambda rows, dynasty_years=None: rows,
        _coerce_meta_years=lambda meta: [2026],
        _tabular_export_response=lambda *args, **kwargs: {"ok": True},
        _calculator_overlay_values_for_job=lambda job_id: {},
        PLAYER_KEY_COL="PlayerKey",
        PLAYER_ENTITY_KEY_COL="PlayerEntityKey",
        POSITION_TOKEN_SPLIT_RE=re.compile(r"[\s,/]+"),
        POSITION_DISPLAY_ORDER=("C", "OF", "SP"),
        PROJECTION_TEXT_SORT_COLS={"Player", "Team"},
        ALL_TAB_HITTER_STAT_COLS=("AB", "R"),
        ALL_TAB_PITCH_STAT_COLS=("IP", "K"),
        PROJECTION_QUERY_CACHE_MAXSIZE=8,
        filter_records=fake_filter_records,
        _enforce_rate_limit=lambda *args, **kwargs: None,
        PROJECTION_RATE_LIMIT_PER_MINUTE=111,
        PROJECTION_EXPORT_RATE_LIMIT_PER_MINUTE=222,
        _calculator_service_from_globals=lambda: calculator_service,
    )

    monkeypatch.setattr(runtime_bootstrap, "ProjectionService", FakeProjectionService)
    monkeypatch.setattr(
        runtime_bootstrap,
        "build_runtime_orchestration_helpers",
        lambda *, state: FakeOrchestrationHelpers(),
    )
    monkeypatch.setattr(
        runtime_bootstrap,
        "build_runtime_endpoint_handlers",
        lambda config: _FakeEndpointHandlers(config),
    )

    artifacts = runtime_bootstrap.build_runtime_bootstrap(state_module=state)

    assert artifacts.calculator_service is calculator_service
    assert isinstance(artifacts.projection_service, FakeProjectionService)
    assert isinstance(artifacts.runtime_endpoint_handlers, _FakeEndpointHandlers)
    assert artifacts.run_calculate_request_fn({"request": "job"}, source="job") == {"source": "job", "ok": True}

    ctx = calls["projection_ctx"]
    assert ctx.get_bat_data() == [{"Player": "A"}]
    assert ctx.get_pit_data() == [{"Player": "B"}]
    assert ctx.get_meta() == {"years": [2026]}
    assert ctx.filter_records([{"Player": "A"}], None, None, None, None) == [{"filtered": True}]
    assert len(filter_calls) == 1

    handler_config = artifacts.runtime_endpoint_handlers.config
    assert handler_config.status_orchestration_context_getter() == "status-context"
    assert handler_config.calculator_orchestration_context_getter() == "calculator-context"
    state.PROJECTION_SERVICE = artifacts.projection_service
    state._run_calculate_request = artifacts.run_calculate_request_fn
    assert handler_config.projection_service_getter() is artifacts.projection_service
    assert handler_config.projection_rate_limit_per_minute_getter() == 111
    assert handler_config.projection_export_rate_limit_per_minute_getter() == 222
    assert handler_config.run_calculate_request_getter()({"request": "api"}, source="api") == {
        "source": "api",
        "ok": True,
    }
    assert run_calls == [({"request": "job"}, "job"), ({"request": "api"}, "api")]

    required_aliases = {
        "CalculateRequest",
        "CalculateExportRequest",
        "_cached_projection_rows",
        "_cached_all_projection_rows",
        "_projection_sortable_columns_for_dataset",
        "_status_orchestration_context",
        "_calculator_orchestration_context",
        "_run_calculate_request",
        "_meta_payload",
        "get_meta",
        "_version_payload",
        "_payload_etag",
        "_etag_matches",
        "get_version",
        "_dynasty_lookup_cache_health_payload",
        "get_health",
        "get_ready",
        "get_ops",
        "_run_calculation_job",
        "projection_response",
        "export_projections",
        "calculate_dynasty_values",
        "export_calculate_dynasty_values",
        "create_calculate_dynasty_job",
        "get_calculate_dynasty_job",
        "cancel_calculate_dynasty_job",
    }
    assert required_aliases.issubset(set(artifacts.alias_map.keys()))
    assert artifacts.alias_map["CalculateRequest"] is calculator_service.calculate_request_model
    assert artifacts.alias_map["CalculateExportRequest"] is calculator_service.calculate_export_request_model


def test_apply_runtime_aliases_sets_attributes_idempotently() -> None:
    state = SimpleNamespace()
    artifacts = runtime_bootstrap.RuntimeBootstrapArtifacts(
        projection_service=object(),
        calculator_service=object(),
        runtime_orchestration_helpers=object(),
        runtime_endpoint_handlers=object(),
        run_calculate_request_fn=lambda *args, **kwargs: {"ok": True},
        alias_map={"alpha": 1, "beta": "two"},
    )

    runtime_bootstrap.apply_runtime_aliases(state_module=state, artifacts=artifacts)
    runtime_bootstrap.apply_runtime_aliases(state_module=state, artifacts=artifacts)

    assert state.alpha == 1
    assert state.beta == "two"
