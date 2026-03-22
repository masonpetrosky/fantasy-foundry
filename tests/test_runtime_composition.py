from __future__ import annotations

from backend.core import runtime_composition


def test_build_runtime_composition_creates_app_and_wires_routes(monkeypatch) -> None:
    calls: dict[str, object] = {}
    app_sentinel = object()
    metrics_sentinel = object()
    billing_sentinel = object()
    player_summary_index = {"slug": {"player": "A"}}

    def fake_create_app(**kwargs):
        calls["create_app_kwargs"] = kwargs
        return app_sentinel

    def fake_wire_routers(app, config, **kwargs):
        calls["wire_app"] = app
        calls["wire_config"] = config
        calls["wire_kwargs"] = kwargs

    monkeypatch.setattr(runtime_composition, "create_app", fake_create_app)
    monkeypatch.setattr(runtime_composition, "wire_routers", fake_wire_routers)

    app_config = runtime_composition.RuntimeAppConfig(
        title="Dynasty Baseball Projections",
        version="1.0.0",
        app_build_id="build-123",
        api_no_cache_headers={"Cache-Control": "no-store"},
        cors_allow_origins=("https://fantasy-foundry.com",),
        environment="production",
        canonical_host="fantasy-foundry.com",
        enable_startup_calc_prewarm=True,
        docs_enabled=False,
        slow_request_threshold_seconds=2.5,
    )
    handler = lambda *args, **kwargs: {"ok": True}

    artifacts = runtime_composition.build_runtime_composition(
        app_config=app_config,
        metrics_collector=metrics_sentinel,
        billing_wiring=billing_sentinel,
        refresh_data_if_needed=lambda: None,
        current_data_version=lambda: "v1",
        client_identity_resolver=lambda _request=None: "127.0.0.1",
        prewarm_default_calculation_caches=lambda: None,
        calculator_job_executor=object(),
        calculator_jobs={},
        calculator_job_lock=object(),
        meta_handler=handler,
        version_handler=handler,
        health_handler=handler,
        ready_handler=handler,
        ops_handler=handler,
        projection_response_handler=handler,
        projection_export_handler=handler,
        projection_profile_handler=handler,
        projection_compare_handler=handler,
        projection_deltas_handler=handler,
        calculate_request_model=type("CalculateRequest", (), {}),
        calculate_export_request_model=type("CalculateExportRequest", (), {}),
        calculate_handler=handler,
        calculate_export_handler=handler,
        calculate_job_create_handler=handler,
        calculate_job_read_handler=handler,
        calculate_job_cancel_handler=handler,
        calculate_authorize_handler=handler,
        enforce_rate_limit=lambda *args, **kwargs: None,
        league_fetcher=lambda *args, **kwargs: {"league": True},
        player_summary_index=player_summary_index,
        player_keys_getter=lambda: ["player-1"],
        fantrax_rate_limit_per_minute=10,
        index_path="index.html",
        assets_root="assets",
        index_build_token="index-token",
        frontend_exists=True,
        buttondown_api_key="buttondown-key",
        stripe_secret_key="stripe-secret",
        stripe_webhook_secret="stripe-webhook",
        stripe_monthly_price_id="monthly",
        stripe_annual_price_id="annual",
        build_status_router_fn=lambda *args, **kwargs: "status-router",
        build_projections_router_fn=lambda *args, **kwargs: "projections-router",
        build_calculate_router_fn=lambda *args, **kwargs: "calculate-router",
        build_fantrax_router_fn=lambda *args, **kwargs: "fantrax-router",
        build_og_cards_router_fn=lambda *args, **kwargs: "og-router",
        build_frontend_assets_router_fn=lambda *args, **kwargs: "frontend-router",
        build_billing_router_fn=lambda *args, **kwargs: "billing-router",
        build_newsletter_router_fn=lambda *args, **kwargs: "newsletter-router",
    )

    create_app_kwargs = calls["create_app_kwargs"]
    assert create_app_kwargs["title"] == "Dynasty Baseball Projections"
    assert create_app_kwargs["app_build_id"] == "build-123"
    assert create_app_kwargs["metrics_collector"] is metrics_sentinel
    assert create_app_kwargs["docs_enabled"] is False

    assert calls["wire_app"] is app_sentinel
    router_config = calls["wire_config"]
    assert router_config.metrics_collector is metrics_sentinel
    assert router_config.player_summary_index is player_summary_index
    assert router_config.billing_wiring is billing_sentinel
    assert router_config.player_summary_getter() is player_summary_index
    assert router_config.player_keys_getter() == ["player-1"]
    assert calls["wire_kwargs"]["build_billing_router_fn"]() == "billing-router"

    assert artifacts.app is app_sentinel
    assert artifacts.router_wiring_config is router_config
    assert artifacts.metrics_collector is metrics_sentinel
    assert artifacts.billing_wiring is billing_sentinel
