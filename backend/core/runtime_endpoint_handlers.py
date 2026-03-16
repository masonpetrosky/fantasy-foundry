"""Runtime endpoint handler adapters that compose orchestration contexts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

from fastapi import Request

from backend.core.calculator_orchestration import (
    calculate_dynasty_values as core_calculate_dynasty_values,
)
from backend.core.calculator_orchestration import (
    cancel_calculate_dynasty_job as core_cancel_calculate_dynasty_job,
)
from backend.core.calculator_orchestration import (
    create_calculate_dynasty_job as core_create_calculate_dynasty_job,
)
from backend.core.calculator_orchestration import (
    export_calculate_dynasty_values as core_export_calculate_dynasty_values,
)
from backend.core.calculator_orchestration import (
    get_calculate_dynasty_job as core_get_calculate_dynasty_job,
)
from backend.core.calculator_orchestration import (
    run_calculation_job as core_run_calculation_job,
)
from backend.core.status_orchestration import (
    build_meta_payload as core_build_meta_payload,
)
from backend.core.status_orchestration import (
    build_version_payload as core_build_version_payload,
)
from backend.core.status_orchestration import (
    dynasty_lookup_cache_health_payload as core_dynasty_lookup_cache_health_payload,
)
from backend.core.status_orchestration import (
    etag_matches as core_etag_matches,
)
from backend.core.status_orchestration import get_health as core_get_health
from backend.core.status_orchestration import get_meta as core_get_meta
from backend.core.status_orchestration import get_ops as core_get_ops
from backend.core.status_orchestration import get_ready as core_get_ready
from backend.core.status_orchestration import get_version as core_get_version
from backend.core.status_orchestration import payload_etag as core_payload_etag


@dataclass(slots=True)
class RuntimeEndpointHandlerConfig:
    status_orchestration_context_getter: Callable[[], Any]
    calculator_orchestration_context_getter: Callable[[], Any]
    projection_service_getter: Callable[[], Any]
    run_calculate_request_getter: Callable[[], Callable[..., dict]]
    enforce_rate_limit_getter: Callable[[], Callable[..., None]]
    projection_rate_limit_per_minute_getter: Callable[[], int]
    projection_export_rate_limit_per_minute_getter: Callable[[], int]


class RuntimeEndpointHandlers:
    def __init__(self, config: RuntimeEndpointHandlerConfig):
        self._config = config

    def _status_orchestration_context(self) -> Any:
        return self._config.status_orchestration_context_getter()

    def _calculator_orchestration_context(self) -> Any:
        return self._config.calculator_orchestration_context_getter()

    def meta_payload(self) -> dict[str, Any]:
        return core_build_meta_payload(ctx=self._status_orchestration_context())

    def get_meta(self, request: Request):
        return core_get_meta(request, ctx=self._status_orchestration_context())

    def version_payload(self) -> dict[str, Any]:
        return core_build_version_payload(ctx=self._status_orchestration_context())

    def payload_etag(self, payload: dict[str, Any]) -> str:
        return core_payload_etag(payload)

    def etag_matches(self, if_none_match: str | None, current_etag: str) -> bool:
        return core_etag_matches(if_none_match, current_etag)

    def get_version(self, request: Request):
        return core_get_version(request, ctx=self._status_orchestration_context())

    def dynasty_lookup_cache_health_payload(self) -> dict[str, Any]:
        return core_dynasty_lookup_cache_health_payload(ctx=self._status_orchestration_context())

    def get_health(self):
        return core_get_health(ctx=self._status_orchestration_context())

    def get_ready(self):
        return core_get_ready(ctx=self._status_orchestration_context())

    def get_ops(self):
        return core_get_ops(ctx=self._status_orchestration_context())

    def run_calculation_job(self, job_id: str, req_payload: dict) -> None:
        core_run_calculation_job(
            job_id,
            req_payload,
            ctx=self._calculator_orchestration_context(),
            run_calculate_request=self._config.run_calculate_request_getter(),
        )

    def projection_response(
        self,
        dataset: Literal["all", "bat", "pitch"],
        *,
        request: Request,
        player: str | None,
        team: str | None,
        player_keys: str | None,
        year: int | None,
        years: str | None,
        pos: str | None,
        dynasty_years: str | None,
        career_totals: bool,
        include_dynasty: bool,
        calculator_job_id: str | None,
        sort_col: str | None,
        sort_dir: Literal["asc", "desc"],
        limit: int,
        offset: int,
    ) -> dict[str, Any]:
        self._config.enforce_rate_limit_getter()(
            request,
            action="proj-read",
            limit_per_minute=self._config.projection_rate_limit_per_minute_getter(),
        )
        return self._config.projection_service_getter().projection_response(
            dataset,
            player=player,
            team=team,
            player_keys=player_keys,
            year=year,
            years=years,
            pos=pos,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            sort_col=sort_col,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

    def export_projections(
        self,
        *,
        request: Request,
        dataset: Literal["all", "bat", "pitch"],
        file_format: Literal["csv", "xlsx"] = "csv",
        player: str | None = None,
        team: str | None = None,
        player_keys: str | None = None,
        year: int | None = None,
        years: str | None = None,
        pos: str | None = None,
        dynasty_years: str | None = None,
        career_totals: bool = False,
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
        sort_col: str | None = None,
        sort_dir: Literal["asc", "desc"] = "desc",
        columns: str | None = None,
    ):
        self._config.enforce_rate_limit_getter()(
            request,
            action="proj-export",
            limit_per_minute=self._config.projection_export_rate_limit_per_minute_getter(),
        )
        return self._config.projection_service_getter().export_projections(
            dataset=dataset,
            file_format=file_format,
            player=player,
            team=team,
            player_keys=player_keys,
            year=year,
            years=years,
            pos=pos,
            dynasty_years=dynasty_years,
            career_totals=career_totals,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            sort_col=sort_col,
            sort_dir=sort_dir,
            columns=columns,
        )

    def projection_profile(
        self,
        *,
        request: Request,
        player_id: str,
        dataset: Literal["all", "bat", "pitch"] = "all",
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
    ) -> dict[str, Any]:
        self._config.enforce_rate_limit_getter()(
            request,
            action="proj-read",
            limit_per_minute=self._config.projection_rate_limit_per_minute_getter(),
        )
        return self._config.projection_service_getter().projection_profile(
            player_id=player_id,
            dataset=dataset,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
        )

    def projection_compare(
        self,
        *,
        request: Request,
        player_keys: str,
        dataset: Literal["all", "bat", "pitch"] = "all",
        include_dynasty: bool = True,
        calculator_job_id: str | None = None,
        career_totals: bool = True,
        year: int | None = None,
        years: str | None = None,
        dynasty_years: str | None = None,
    ) -> dict[str, Any]:
        self._config.enforce_rate_limit_getter()(
            request,
            action="proj-read",
            limit_per_minute=self._config.projection_rate_limit_per_minute_getter(),
        )
        return self._config.projection_service_getter().projection_compare(
            player_keys=player_keys,
            dataset=dataset,
            include_dynasty=include_dynasty,
            calculator_job_id=calculator_job_id,
            career_totals=career_totals,
            year=year,
            years=years,
            dynasty_years=dynasty_years,
        )

    def calculate_dynasty_values(self, req: Any, request: Request):
        return core_calculate_dynasty_values(
            req,
            request,
            ctx=self._calculator_orchestration_context(),
            run_calculate_request=self._config.run_calculate_request_getter(),
        )

    def export_calculate_dynasty_values(self, req: Any, request: Request):
        return core_export_calculate_dynasty_values(
            req,
            request,
            ctx=self._calculator_orchestration_context(),
            run_calculate_request=self._config.run_calculate_request_getter(),
        )

    def create_calculate_dynasty_job(self, req: Any, request: Request):
        return core_create_calculate_dynasty_job(
            req,
            request,
            ctx=self._calculator_orchestration_context(),
            run_calculation_job=self.run_calculation_job,
        )

    def get_calculate_dynasty_job(self, job_id: str, request: Request):
        return core_get_calculate_dynasty_job(
            job_id,
            request,
            ctx=self._calculator_orchestration_context(),
        )

    def cancel_calculate_dynasty_job(self, job_id: str, request: Request):
        return core_cancel_calculate_dynasty_job(
            job_id,
            request,
            ctx=self._calculator_orchestration_context(),
        )


def build_runtime_endpoint_handlers(config: RuntimeEndpointHandlerConfig) -> RuntimeEndpointHandlers:
    return RuntimeEndpointHandlers(config)


# ---------------------------------------------------------------------------
# Billing webhook wiring — extracted from runtime.py
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class BillingWiring:
    """Closures wiring Stripe webhook events to the billing service."""

    on_checkout_completed: Callable[..., Any]
    on_subscription_updated: Callable[..., Any]
    on_subscription_deleted: Callable[..., Any]
    get_subscription_status: Callable[..., Any]


def build_billing_wiring(
    *,
    stripe_module: Any,
    supabase_url: str | None,
    supabase_service_role_key: str | None,
    billing_resolve_user_id: Callable[..., Any],
    billing_upsert: Callable[..., Any],
    billing_revoke: Callable[..., Any],
    billing_get_status: Callable[..., Any],
) -> BillingWiring:
    """Build billing webhook closures that bridge Stripe events to the billing service."""
    import logging

    async def _on_checkout_completed(session: dict) -> None:
        email = str(session.get("customer_email", "")).strip()
        sub_id = str(session.get("subscription", "")).strip()
        period_end = None
        if sub_id:
            try:
                sub_obj = stripe_module.Subscription.retrieve(sub_id)
                period_end = sub_obj.get("current_period_end")
            except (OSError, ValueError, KeyError):
                logging.getLogger(__name__).warning(
                    "Could not retrieve subscription %s for period_end", sub_id, exc_info=True
                )
        user_id = await billing_resolve_user_id(
            supabase_url=supabase_url,
            supabase_service_role_key=supabase_service_role_key,
            email=email,
        )
        await billing_upsert(
            supabase_url=supabase_url,
            supabase_service_role_key=supabase_service_role_key,
            user_email=email,
            stripe_customer_id=str(session.get("customer", "")).strip(),
            stripe_subscription_id=sub_id,
            status="active",
            user_id=user_id,
            current_period_end=period_end,
        )

    async def _on_subscription_updated(subscription: dict) -> None:
        customer_id = str(subscription.get("customer", "")).strip()
        customer_email = str(subscription.get("metadata", {}).get("email", "")).strip()
        if not customer_email and customer_id:
            try:
                customer = stripe_module.Customer.retrieve(customer_id)
                customer_email = str(getattr(customer, "email", "") or "").strip()
            except (OSError, ValueError, KeyError):
                logging.getLogger(__name__).warning(
                    "Could not retrieve customer email for %s", customer_id
                )
        user_id = await billing_resolve_user_id(
            supabase_url=supabase_url,
            supabase_service_role_key=supabase_service_role_key,
            email=customer_email,
        )
        await billing_upsert(
            supabase_url=supabase_url,
            supabase_service_role_key=supabase_service_role_key,
            user_email=customer_email,
            stripe_customer_id=customer_id,
            stripe_subscription_id=str(subscription.get("id", "")).strip(),
            status=str(subscription.get("status", "")).strip(),
            user_id=user_id,
            current_period_end=subscription.get("current_period_end"),
        )

    async def _on_subscription_deleted(subscription: dict) -> None:
        await billing_revoke(
            supabase_url=supabase_url,
            supabase_service_role_key=supabase_service_role_key,
            stripe_subscription_id=str(subscription.get("id", "")).strip(),
        )

    async def _get_billing_status(email: str) -> Any:
        return await billing_get_status(
            supabase_url=supabase_url,
            supabase_service_role_key=supabase_service_role_key,
            user_email=email,
        )

    return BillingWiring(
        on_checkout_completed=_on_checkout_completed,
        on_subscription_updated=_on_subscription_updated,
        on_subscription_deleted=_on_subscription_deleted,
        get_subscription_status=_get_billing_status,
    )


# ---------------------------------------------------------------------------
# Router registration — extracted from runtime.py
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class RouterWiringConfig:
    """All dependencies needed by wire_routers to register route modules on the app."""

    # Status router
    meta_handler: Any
    version_handler: Any
    health_handler: Any
    ready_handler: Any
    ops_handler: Any
    metrics_collector: Any

    # Projections router
    projection_response_handler: Any
    projection_export_handler: Any
    projection_profile_handler: Any
    projection_compare_handler: Any
    projection_deltas_handler: Any

    # Calculate router
    calculate_request_model: Any
    calculate_export_request_model: Any
    calculate_handler: Any
    calculate_export_handler: Any
    calculate_job_create_handler: Any
    calculate_job_read_handler: Any
    calculate_job_cancel_handler: Any
    calculate_authorize_handler: Any

    # Fantrax router
    enforce_rate_limit: Any
    client_ip_resolver: Any
    league_fetcher: Any
    player_summary_getter: Callable[[], Any]
    fantrax_rate_limit_per_minute: int

    # OG cards router
    player_summary_index: Any

    # Frontend assets router (optional — only if frontend dir exists)
    index_path: Any | None = None
    assets_root: Any | None = None
    app_build_id: str | None = None
    index_build_token: str | None = None
    player_keys_getter: Callable[[], list[str]] | None = None
    frontend_exists: bool = False

    # Newsletter router (optional)
    buttondown_api_key: str | None = None
    newsletter_rate_limit_per_minute: int = 10

    # Billing router (optional)
    billing_wiring: BillingWiring | None = None
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_monthly_price_id: str | None = None
    stripe_annual_price_id: str | None = None


def wire_routers(
    app: Any,
    config: RouterWiringConfig,
    *,
    build_status_router_fn: Callable[..., Any],
    build_projections_router_fn: Callable[..., Any],
    build_calculate_router_fn: Callable[..., Any],
    build_fantrax_router_fn: Callable[..., Any],
    build_og_cards_router_fn: Callable[..., Any],
    build_frontend_assets_router_fn: Callable[..., Any],
    build_billing_router_fn: Callable[..., Any],
    build_newsletter_router_fn: Callable[..., Any],
) -> None:
    """Register all route modules on *app* using the provided config."""
    app.include_router(
        build_status_router_fn(
            meta_handler=config.meta_handler,
            version_handler=config.version_handler,
            health_handler=config.health_handler,
            ready_handler=config.ready_handler,
            ops_handler=config.ops_handler,
            metrics_collector=config.metrics_collector,
        )
    )

    app.include_router(
        build_projections_router_fn(
            projection_response_handler=config.projection_response_handler,
            projection_export_handler=config.projection_export_handler,
            projection_profile_handler=config.projection_profile_handler,
            projection_compare_handler=config.projection_compare_handler,
            projection_deltas_handler=config.projection_deltas_handler,
        )
    )

    app.include_router(
        build_calculate_router_fn(
            calculate_request_model=config.calculate_request_model,
            calculate_export_request_model=config.calculate_export_request_model,
            calculate_handler=config.calculate_handler,
            calculate_export_handler=config.calculate_export_handler,
            calculate_job_create_handler=config.calculate_job_create_handler,
            calculate_job_read_handler=config.calculate_job_read_handler,
            calculate_job_cancel_handler=config.calculate_job_cancel_handler,
            calculate_authorize_handler=config.calculate_authorize_handler,
        )
    )

    # Billing (Stripe) — conditional on credentials + wiring
    if config.billing_wiring and config.stripe_secret_key and config.stripe_webhook_secret:
        app.include_router(
            build_billing_router_fn(
                stripe_secret_key=config.stripe_secret_key,
                stripe_webhook_secret=config.stripe_webhook_secret,
                stripe_monthly_price_id=config.stripe_monthly_price_id,
                stripe_annual_price_id=config.stripe_annual_price_id,
                on_checkout_completed=config.billing_wiring.on_checkout_completed,
                on_subscription_updated=config.billing_wiring.on_subscription_updated,
                on_subscription_deleted=config.billing_wiring.on_subscription_deleted,
                get_subscription_status=config.billing_wiring.get_subscription_status,
            )
        )

    # Newsletter (Buttondown) — conditional on API key
    if config.buttondown_api_key:
        app.include_router(
            build_newsletter_router_fn(
                buttondown_api_key=config.buttondown_api_key,
                enforce_rate_limit=config.enforce_rate_limit,
                rate_limit_per_minute=config.newsletter_rate_limit_per_minute,
                client_ip_resolver=config.client_ip_resolver,
            )
        )

    # Fantrax league integration
    app.include_router(
        build_fantrax_router_fn(
            enforce_rate_limit=config.enforce_rate_limit,
            client_ip_resolver=config.client_ip_resolver,
            league_fetcher=config.league_fetcher,
            player_summary_getter=config.player_summary_getter,
            rate_limit_per_minute=config.fantrax_rate_limit_per_minute,
        )
    )

    # OG cards
    app.include_router(
        build_og_cards_router_fn(
            player_summary_index=config.player_summary_index,
        )
    )

    # Frontend assets — only if frontend dir exists
    if config.frontend_exists and config.index_path is not None:
        app.include_router(
            build_frontend_assets_router_fn(
                index_path=config.index_path,
                assets_root=config.assets_root,
                app_build_id=config.app_build_id,
                index_build_token=config.index_build_token,
                player_keys_getter=config.player_keys_getter,
                player_summary_index=config.player_summary_index,
            )
        )
