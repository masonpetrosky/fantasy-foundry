"""Async calculator job-state helpers."""

from __future__ import annotations

import time
from typing import Any


def active_jobs_for_ip(calculator_jobs: dict[str, dict], client_ip: str) -> int:
    count = 0
    for job in calculator_jobs.values():
        if str(job.get("client_ip") or "") != client_ip:
            continue
        status = str(job.get("status") or "").lower()
        if status in {"queued", "running"}:
            count += 1
    return count


def mark_job_cancelled_locked(
    job: dict,
    *,
    now: str,
    cancelled_status: str,
    cancelled_error: dict[str, Any],
) -> None:
    job["status"] = cancelled_status
    job["cancel_requested"] = True
    job["result"] = None
    job["error"] = dict(cancelled_error)
    job["completed_at"] = job.get("completed_at") or now
    job["updated_at"] = now


def cleanup_calculation_jobs(
    calculator_jobs: dict[str, dict],
    *,
    now_ts: float | None,
    job_ttl_seconds: int,
    job_max_entries: int,
    cancelled_status: str,
) -> None:
    current = time.time() if now_ts is None else now_ts
    expired_ids: list[str] = []
    completed: list[tuple[str, float]] = []

    for job_id, job in calculator_jobs.items():
        status = str(job.get("status") or "").lower()
        created_ts = float(job.get("created_ts") or current)
        age = current - created_ts
        if status in {"completed", "failed", cancelled_status} and age > job_ttl_seconds:
            expired_ids.append(job_id)
        elif status in {"completed", "failed", cancelled_status}:
            completed.append((job_id, created_ts))

    for job_id in expired_ids:
        calculator_jobs.pop(job_id, None)

    if len(calculator_jobs) <= job_max_entries:
        return

    completed.sort(key=lambda item: item[1])
    while len(calculator_jobs) > job_max_entries and completed:
        job_id, _ = completed.pop(0)
        calculator_jobs.pop(job_id, None)


def calculation_job_public_payload(
    job: dict,
    *,
    calculator_jobs: dict[str, dict],
    cancelled_status: str,
) -> dict:
    status = str(job.get("status") or "").lower()
    payload = {
        "job_id": job["job_id"],
        "status": status,
        "created_at": job["created_at"],
        "started_at": job.get("started_at"),
        "completed_at": job.get("completed_at"),
        "settings": job.get("settings"),
    }
    if status == "completed":
        payload["result"] = job.get("result")
    elif status in {"failed", cancelled_status}:
        payload["error"] = job.get("error")
    elif status == "queued":
        queued_jobs = [
            candidate
            for candidate in calculator_jobs.values()
            if str(candidate.get("status") or "").lower() == "queued"
        ]
        queued_jobs.sort(key=lambda candidate: float(candidate.get("created_ts") or 0.0))
        payload["queued_jobs"] = len(queued_jobs)
        payload["running_jobs"] = sum(
            1
            for candidate in calculator_jobs.values()
            if str(candidate.get("status") or "").lower() == "running"
        )
        payload["queue_position"] = None
        for idx, candidate in enumerate(queued_jobs, start=1):
            if str(candidate.get("job_id") or "") == str(job.get("job_id") or ""):
                payload["queue_position"] = idx
                break
    return payload
