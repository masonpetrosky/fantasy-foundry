"""Startup assembly helpers for backend.runtime mutable state."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from backend.core.runtime_state import RuntimeMutableState, build_runtime_state


@dataclass(slots=True)
class RuntimeStartupArtifacts:
    data_source_signature: tuple[tuple[str, int | None, int | None], ...] | None
    data_content_version: str
    runtime_state: RuntimeMutableState


def build_runtime_startup_artifacts(
    *,
    data_refresh_paths: tuple[Path, ...],
    compute_data_signature_fn: Callable[[tuple[Path, ...]], tuple[tuple[str, int | None, int | None], ...]],
    compute_content_data_version_fn: Callable[[tuple[Path, ...]], str],
    calculator_job_workers: int,
    redis_client_state_factory: Callable[[], Any],
) -> RuntimeStartupArtifacts:
    data_source_signature = compute_data_signature_fn(data_refresh_paths)
    data_content_version = compute_content_data_version_fn(data_refresh_paths)
    runtime_state = build_runtime_state(
        calculator_job_workers=calculator_job_workers,
        redis_client_state_factory=redis_client_state_factory,
    )
    return RuntimeStartupArtifacts(
        data_source_signature=data_source_signature,
        data_content_version=data_content_version,
        runtime_state=runtime_state,
    )
