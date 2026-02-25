"""Builders for runtime status/calculator orchestration contexts."""

from __future__ import annotations

from dataclasses import dataclass

from backend.api.dependencies import (
    build_calculator_orchestration_context,
    build_status_orchestration_context,
)
from backend.core.calculator_orchestration import CalculatorOrchestrationContext
from backend.core.runtime_state_protocols import RuntimeOrchestrationState
from backend.core.status_orchestration import StatusOrchestrationContext


@dataclass(slots=True)
class RuntimeOrchestrationHelpers:
    state: RuntimeOrchestrationState

    def status_orchestration_context(self) -> StatusOrchestrationContext:
        state = self.state
        return build_status_orchestration_context(
            refresh_data_if_needed=state._refresh_data_if_needed,
            meta_getter=lambda: state.META,
            calculator_guardrails_payload=state._calculator_guardrails_payload,
            projection_freshness_getter=lambda: state.PROJECTION_FRESHNESS,
            environment=state.APP_ENVIRONMENT,
            cors_allow_origins=tuple(state.CORS_ALLOW_ORIGINS),
            trust_x_forwarded_for=state.TRUST_X_FORWARDED_FOR,
            trusted_proxy_cidrs=tuple(str(network) for network in state.TRUSTED_PROXY_NETWORKS),
            canonical_host=state.CANONICAL_HOST,
            require_calculate_auth=state.REQUIRE_CALCULATE_AUTH,
            calculate_api_keys_configured=bool(state.CALCULATE_API_KEY_IDENTITIES),
            calculator_prewarm_lock=state.CALCULATOR_PREWARM_LOCK,
            calculator_prewarm_state=state.CALCULATOR_PREWARM_STATE,
            api_no_cache_headers=state.API_NO_CACHE_HEADERS,
            current_data_version=state._current_data_version,
            app_build_id=state.APP_BUILD_ID,
            deploy_commit_sha=state.DEPLOY_COMMIT_SHA,
            app_build_at=state.APP_BUILD_AT,
            inspect_precomputed_default_dynasty_lookup=state._inspect_precomputed_default_dynasty_lookup,
            require_precomputed_dynasty_lookup=state.REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP,
            index_path=state.INDEX_PATH,
            calculator_job_lock=state.CALCULATOR_JOB_LOCK,
            cleanup_calculation_jobs=state._cleanup_calculation_jobs,
            calculator_jobs=state.CALCULATOR_JOBS,
            calc_job_cancelled_status=state.CALC_JOB_CANCELLED_STATUS,
            calc_result_cache_lock=state.CALC_RESULT_CACHE_LOCK,
            cleanup_local_result_cache=state._cleanup_local_result_cache,
            calc_result_cache=state.CALC_RESULT_CACHE,
            rate_limit_bucket_count_getter=state._rate_limit_bucket_count,
            calculator_sync_rate_limit_per_minute=state.CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
            calculator_job_create_rate_limit_per_minute=state.CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
            calculator_job_status_rate_limit_per_minute=state.CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
            projection_rate_limit_per_minute=state.PROJECTION_RATE_LIMITS.read_per_minute,
            projection_export_rate_limit_per_minute=state.PROJECTION_RATE_LIMITS.export_per_minute,
            redis_url=state.REDIS_URL,
            bat_data_getter=lambda: state.BAT_DATA,
            pit_data_getter=lambda: state.PIT_DATA,
            calculator_worker_available=lambda: not getattr(state.CALCULATOR_JOB_EXECUTOR, "_shutdown", False),
            iso_now=state._iso_now,
        )

    def calculator_orchestration_context(self) -> CalculatorOrchestrationContext:
        state = self.state
        return build_calculator_orchestration_context(
            calculate_request_model=state.CalculateRequest,
            enforce_rate_limit=state._enforce_rate_limit,
            sync_rate_limit_per_minute=state.CALCULATOR_SYNC_RATE_LIMIT_PER_MINUTE,
            job_create_rate_limit_per_minute=state.CALCULATOR_JOB_CREATE_RATE_LIMIT_PER_MINUTE,
            job_status_rate_limit_per_minute=state.CALCULATOR_JOB_STATUS_RATE_LIMIT_PER_MINUTE,
            flatten_explanations_for_export=state._flatten_explanations_for_export,
            tabular_export_response=state._tabular_export_response,
            default_calculator_export_columns=state._default_calculator_export_columns,
            export_internal_column_blocklist=state.EXPORT_INTERNAL_COLUMN_BLOCKLIST,
            calc_result_cache_key=state._calc_result_cache_key,
            result_cache_get=state._result_cache_get,
            client_ip=state._client_ip,
            iso_now=state._iso_now,
            active_jobs_for_ip=state._active_jobs_for_ip,
            calculator_max_active_jobs_per_ip=state.CALCULATOR_MAX_ACTIVE_JOBS_PER_IP,
            calculator_job_lock=state.CALCULATOR_JOB_LOCK,
            calculator_jobs=state.CALCULATOR_JOBS,
            cleanup_calculation_jobs=state._cleanup_calculation_jobs,
            cache_calculation_job_snapshot=state._cache_calculation_job_snapshot,
            cached_calculation_job_snapshot=state._cached_calculation_job_snapshot,
            calculation_job_public_payload=state._calculation_job_public_payload,
            mark_job_cancelled_locked=state._mark_job_cancelled_locked,
            calculator_job_executor=state.CALCULATOR_JOB_EXECUTOR,
            calc_job_cancelled_status=state.CALC_JOB_CANCELLED_STATUS,
            calc_logger=state.CALC_LOGGER,
            track_active_job=state._track_active_job,
            untrack_active_job=state._untrack_active_job,
            set_job_cancel_requested=state._set_job_cancel_requested,
            clear_job_cancel_requested=state._clear_job_cancel_requested,
            job_cancel_requested=state._job_cancel_requested,
        )


def build_runtime_orchestration_helpers(*, state: RuntimeOrchestrationState) -> RuntimeOrchestrationHelpers:
    return RuntimeOrchestrationHelpers(state=state)
