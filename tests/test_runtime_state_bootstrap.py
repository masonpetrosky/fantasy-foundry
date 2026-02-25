from __future__ import annotations

from pathlib import Path

from backend.core.runtime_startup import build_runtime_startup_artifacts
from backend.core.runtime_state import build_runtime_state


def test_build_runtime_state_initializes_mutable_containers() -> None:
    redis_state = object()
    state = build_runtime_state(
        calculator_job_workers=1,
        redis_client_state_factory=lambda: redis_state,
    )

    assert state.data_source_signature is None
    assert state.data_content_version == ""
    assert state.calculator_jobs == {}
    assert state.calc_result_cache == {}
    assert list(state.calc_result_cache_order) == []
    assert state.request_rate_limit_last_sweep_ts == 0.0
    assert state.redis_client_state is redis_state

    bucket_key = ("limit", "127.0.0.1")
    state.request_rate_limit_buckets[bucket_key].append(1.0)
    assert list(state.request_rate_limit_buckets[bucket_key]) == [1.0]

    state.calculator_job_executor.shutdown(wait=True)


def test_build_runtime_startup_artifacts_delegates_signature_and_state_bootstrap() -> None:
    calls: dict[str, tuple[Path, ...]] = {}
    redis_state = object()
    paths = (Path("data/meta.json"), Path("data/bat.json"))

    def fake_compute_signature(in_paths: tuple[Path, ...]) -> tuple[tuple[str, int | None, int | None], ...]:
        calls["signature"] = in_paths
        return (("data/meta.json", 1, 2),)

    def fake_compute_content_version(in_paths: tuple[Path, ...]) -> str:
        calls["content"] = in_paths
        return "v-test"

    artifacts = build_runtime_startup_artifacts(
        data_refresh_paths=paths,
        compute_data_signature_fn=fake_compute_signature,
        compute_content_data_version_fn=fake_compute_content_version,
        calculator_job_workers=1,
        redis_client_state_factory=lambda: redis_state,
    )

    assert calls["signature"] == paths
    assert calls["content"] == paths
    assert artifacts.data_source_signature == (("data/meta.json", 1, 2),)
    assert artifacts.data_content_version == "v-test"
    assert artifacts.runtime_state.redis_client_state is redis_state

    artifacts.runtime_state.calculator_job_executor.shutdown(wait=True)
