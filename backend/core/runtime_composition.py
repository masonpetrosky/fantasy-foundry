"""Runtime app composition helpers extracted from backend.runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from fastapi import FastAPI, Request

from backend.api.app_factory import create_app
from backend.core.metrics import MetricsCollector
from backend.core.runtime_endpoint_handlers import BillingWiring, RouterWiringConfig, wire_routers


@dataclass(frozen=True, slots=True)
class RuntimeAppConfig:
    title: str
    version: str
    app_build_id: str
    api_no_cache_headers: dict[str, str]
    cors_allow_origins: tuple[str, ...]
    environment: str
    canonical_host: str
    enable_startup_calc_prewarm: bool
    docs_enabled: bool
    slow_request_threshold_seconds: float


@dataclass(slots=True)
class RuntimeCompositionArtifacts:
    app: FastAPI
    router_wiring_config: RouterWiringConfig
    metrics_collector: MetricsCollector | None
    billing_wiring: BillingWiring | None


def build_runtime_composition(
    *,
    app_config: RuntimeAppConfig,
    metrics_collector: MetricsCollector | None,
    billing_wiring: BillingWiring | None,
    refresh_data_if_needed: Callable[[], None],
    current_data_version: Callable[[], str],
    client_identity_resolver: Callable[[Request | None], str],
    prewarm_default_calculation_caches: Callable[[], None],
    calculator_job_executor: Any,
    calculator_jobs: dict[str, dict[str, Any]],
    calculator_job_lock: Any,
    meta_handler: Callable[..., Any],
    version_handler: Callable[..., Any],
    health_handler: Callable[..., Any],
    ready_handler: Callable[..., Any],
    ops_handler: Callable[..., Any],
    projection_response_handler: Callable[..., Any],
    projection_export_handler: Callable[..., Any],
    projection_profile_handler: Callable[..., Any],
    projection_compare_handler: Callable[..., Any],
    projection_deltas_handler: Callable[..., Any],
    calculate_request_model: type,
    calculate_export_request_model: type,
    calculate_handler: Callable[..., Any],
    calculate_export_handler: Callable[..., Any],
    calculate_job_create_handler: Callable[..., Any],
    calculate_job_read_handler: Callable[..., Any],
    calculate_job_cancel_handler: Callable[..., Any],
    calculate_authorize_handler: Callable[..., Any],
    enforce_rate_limit: Callable[..., None],
    league_fetcher: Callable[..., Any],
    player_summary_index: dict[str, Any],
    player_keys_getter: Callable[[], list[str]],
    fantrax_rate_limit_per_minute: int,
    index_path: Any,
    assets_root: Any,
    index_build_token: str,
    frontend_exists: bool,
    buttondown_api_key: str,
    stripe_secret_key: str,
    stripe_webhook_secret: str,
    stripe_monthly_price_id: str,
    stripe_annual_price_id: str,
    build_status_router_fn: Callable[..., Any],
    build_projections_router_fn: Callable[..., Any],
    build_calculate_router_fn: Callable[..., Any],
    build_fantrax_router_fn: Callable[..., Any],
    build_og_cards_router_fn: Callable[..., Any],
    build_frontend_assets_router_fn: Callable[..., Any],
    build_billing_router_fn: Callable[..., Any],
    build_newsletter_router_fn: Callable[..., Any],
) -> RuntimeCompositionArtifacts:
    app = create_app(
        title=app_config.title,
        version=app_config.version,
        app_build_id=app_config.app_build_id,
        api_no_cache_headers=app_config.api_no_cache_headers,
        cors_allow_origins=app_config.cors_allow_origins,
        environment=app_config.environment,
        refresh_data_if_needed=refresh_data_if_needed,
        current_data_version=current_data_version,
        client_identity_resolver=client_identity_resolver,
        canonical_host=app_config.canonical_host,
        enable_startup_calc_prewarm=app_config.enable_startup_calc_prewarm,
        prewarm_default_calculation_caches=prewarm_default_calculation_caches,
        calculator_job_executor=calculator_job_executor,
        calculator_jobs=calculator_jobs,
        calculator_job_lock=calculator_job_lock,
        docs_enabled=app_config.docs_enabled,
        metrics_collector=metrics_collector,
        slow_request_threshold_seconds=app_config.slow_request_threshold_seconds,
    )

    router_wiring_config = RouterWiringConfig(
        meta_handler=meta_handler,
        version_handler=version_handler,
        health_handler=health_handler,
        ready_handler=ready_handler,
        ops_handler=ops_handler,
        metrics_collector=metrics_collector,
        projection_response_handler=projection_response_handler,
        projection_export_handler=projection_export_handler,
        projection_profile_handler=projection_profile_handler,
        projection_compare_handler=projection_compare_handler,
        projection_deltas_handler=projection_deltas_handler,
        calculate_request_model=calculate_request_model,
        calculate_export_request_model=calculate_export_request_model,
        calculate_handler=calculate_handler,
        calculate_export_handler=calculate_export_handler,
        calculate_job_create_handler=calculate_job_create_handler,
        calculate_job_read_handler=calculate_job_read_handler,
        calculate_job_cancel_handler=calculate_job_cancel_handler,
        calculate_authorize_handler=calculate_authorize_handler,
        enforce_rate_limit=enforce_rate_limit,
        client_ip_resolver=client_identity_resolver,
        league_fetcher=league_fetcher,
        player_summary_getter=lambda: player_summary_index,
        fantrax_rate_limit_per_minute=fantrax_rate_limit_per_minute,
        player_summary_index=player_summary_index,
        index_path=index_path,
        assets_root=assets_root,
        app_build_id=app_config.app_build_id,
        index_build_token=index_build_token,
        player_keys_getter=player_keys_getter,
        frontend_exists=frontend_exists,
        buttondown_api_key=buttondown_api_key,
        billing_wiring=billing_wiring,
        stripe_secret_key=stripe_secret_key,
        stripe_webhook_secret=stripe_webhook_secret,
        stripe_monthly_price_id=stripe_monthly_price_id,
        stripe_annual_price_id=stripe_annual_price_id,
    )
    wire_routers(
        app,
        router_wiring_config,
        build_status_router_fn=build_status_router_fn,
        build_projections_router_fn=build_projections_router_fn,
        build_calculate_router_fn=build_calculate_router_fn,
        build_fantrax_router_fn=build_fantrax_router_fn,
        build_og_cards_router_fn=build_og_cards_router_fn,
        build_frontend_assets_router_fn=build_frontend_assets_router_fn,
        build_billing_router_fn=build_billing_router_fn,
        build_newsletter_router_fn=build_newsletter_router_fn,
    )
    return RuntimeCompositionArtifacts(
        app=app,
        router_wiring_config=router_wiring_config,
        metrics_collector=metrics_collector,
        billing_wiring=billing_wiring,
    )
