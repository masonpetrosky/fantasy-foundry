"""Runtime bootstrap wiring helpers extracted from backend.runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping, cast

from backend.core.runtime_endpoint_handlers import (
    RuntimeEndpointHandlerConfig,
    build_runtime_endpoint_handlers,
)
from backend.core.runtime_orchestration_helpers import build_runtime_orchestration_helpers
from backend.core.runtime_state_protocols import RuntimeBootstrapState, RuntimeOrchestrationState
from backend.services.projections import ProjectionService, ProjectionServiceContext

REQUIRED_RUNTIME_ALIAS_KEYS = frozenset(
    {
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
)


@dataclass(slots=True)
class RuntimeBootstrapArtifacts:
    projection_service: ProjectionService
    calculator_service: Any
    runtime_orchestration_helpers: Any
    runtime_endpoint_handlers: Any
    run_calculate_request_fn: Callable[..., dict]
    alias_map: dict[str, Any]


def missing_runtime_alias_keys(alias_map: Mapping[str, Any]) -> set[str]:
    return set(REQUIRED_RUNTIME_ALIAS_KEYS) - set(alias_map.keys())


def unexpected_runtime_alias_keys(alias_map: Mapping[str, Any]) -> set[str]:
    return set(alias_map.keys()) - set(REQUIRED_RUNTIME_ALIAS_KEYS)


def validate_runtime_alias_map(alias_map: Mapping[str, Any]) -> None:
    missing = missing_runtime_alias_keys(alias_map)
    unexpected = unexpected_runtime_alias_keys(alias_map)
    if not missing and not unexpected:
        return
    details: list[str] = []
    if missing:
        details.append(f"missing={sorted(missing)}")
    if unexpected:
        details.append(f"unexpected={sorted(unexpected)}")
    raise RuntimeError("Invalid runtime alias map contract: " + "; ".join(details))


def build_runtime_bootstrap(*, state_module: RuntimeBootstrapState) -> RuntimeBootstrapArtifacts:
    projection_service = ProjectionService(
        ProjectionServiceContext(
            refresh_data_if_needed=state_module._refresh_data_if_needed,
            get_bat_data=lambda: state_module.BAT_DATA,
            get_pit_data=lambda: state_module.PIT_DATA,
            get_meta=lambda: state_module.META,
            normalize_player_key=state_module._normalize_player_key,
            dynasty_helpers=state_module.PROJECTION_DYNASTY_HELPERS,
            coerce_meta_years=state_module._coerce_meta_years,
            tabular_export_response=state_module._tabular_export_response,
            calculator_overlay_values_for_job=state_module._calculator_overlay_values_for_job,
            player_key_col=state_module.PLAYER_KEY_COL,
            player_entity_key_col=state_module.PLAYER_ENTITY_KEY_COL,
            position_token_split_re=state_module.POSITION_TOKEN_SPLIT_RE,
            position_display_order=state_module.POSITION_DISPLAY_ORDER,
            projection_text_sort_cols=state_module.PROJECTION_TEXT_SORT_COLS,
            all_tab_hitter_stat_cols=state_module.ALL_TAB_HITTER_STAT_COLS,
            all_tab_pitch_stat_cols=state_module.ALL_TAB_PITCH_STAT_COLS,
            projection_query_cache_maxsize=state_module.PROJECTION_QUERY_CACHE_MAXSIZE,
            rate_limits=state_module.PROJECTION_RATE_LIMITS,
            filter_records=lambda *args, **kwargs: state_module.filter_records(*args, **kwargs),
        )
    )
    calculator_service = state_module._calculator_service_from_globals()
    runtime_orchestration_helpers = build_runtime_orchestration_helpers(
        state=cast(RuntimeOrchestrationState, state_module)
    )
    status_orchestration_context = runtime_orchestration_helpers.status_orchestration_context
    calculator_orchestration_context = runtime_orchestration_helpers.calculator_orchestration_context

    def run_calculate_request(req: Any, *, source: str) -> dict:
        return state_module._calculator_service_from_globals()._run_calculate_request(req, source=source)

    runtime_endpoint_handlers = build_runtime_endpoint_handlers(
        RuntimeEndpointHandlerConfig(
            status_orchestration_context_getter=lambda: status_orchestration_context(),
            calculator_orchestration_context_getter=lambda: calculator_orchestration_context(),
            projection_service_getter=lambda: state_module.PROJECTION_SERVICE,
            run_calculate_request_getter=lambda: state_module._run_calculate_request,
            enforce_rate_limit_getter=lambda: state_module._enforce_rate_limit,
            projection_rate_limit_per_minute_getter=lambda: projection_service.projection_rate_limit_per_minute,
            projection_export_rate_limit_per_minute_getter=lambda: projection_service.projection_export_rate_limit_per_minute,
        )
    )

    alias_map = {
        "CalculateRequest": calculator_service.calculate_request_model,
        "CalculateExportRequest": calculator_service.calculate_export_request_model,
        "_cached_projection_rows": projection_service._cached_projection_rows,
        "_cached_all_projection_rows": projection_service._cached_all_projection_rows,
        "_projection_sortable_columns_for_dataset": projection_service._projection_sortable_columns_for_dataset,
        "_status_orchestration_context": status_orchestration_context,
        "_calculator_orchestration_context": calculator_orchestration_context,
        "_run_calculate_request": run_calculate_request,
        "_meta_payload": runtime_endpoint_handlers.meta_payload,
        "get_meta": runtime_endpoint_handlers.get_meta,
        "_version_payload": runtime_endpoint_handlers.version_payload,
        "_payload_etag": runtime_endpoint_handlers.payload_etag,
        "_etag_matches": runtime_endpoint_handlers.etag_matches,
        "get_version": runtime_endpoint_handlers.get_version,
        "_dynasty_lookup_cache_health_payload": runtime_endpoint_handlers.dynasty_lookup_cache_health_payload,
        "get_health": runtime_endpoint_handlers.get_health,
        "get_ready": runtime_endpoint_handlers.get_ready,
        "get_ops": runtime_endpoint_handlers.get_ops,
        "_run_calculation_job": runtime_endpoint_handlers.run_calculation_job,
        "projection_response": runtime_endpoint_handlers.projection_response,
        "export_projections": runtime_endpoint_handlers.export_projections,
        "calculate_dynasty_values": runtime_endpoint_handlers.calculate_dynasty_values,
        "export_calculate_dynasty_values": runtime_endpoint_handlers.export_calculate_dynasty_values,
        "create_calculate_dynasty_job": runtime_endpoint_handlers.create_calculate_dynasty_job,
        "get_calculate_dynasty_job": runtime_endpoint_handlers.get_calculate_dynasty_job,
        "cancel_calculate_dynasty_job": runtime_endpoint_handlers.cancel_calculate_dynasty_job,
    }
    validate_runtime_alias_map(alias_map)
    return RuntimeBootstrapArtifacts(
        projection_service=projection_service,
        calculator_service=calculator_service,
        runtime_orchestration_helpers=runtime_orchestration_helpers,
        runtime_endpoint_handlers=runtime_endpoint_handlers,
        run_calculate_request_fn=run_calculate_request,
        alias_map=alias_map,
    )


def apply_runtime_aliases(*, state_module: Any, artifacts: RuntimeBootstrapArtifacts) -> None:
    for name, value in artifacts.alias_map.items():
        setattr(state_module, name, value)
