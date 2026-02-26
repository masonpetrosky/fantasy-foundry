# Queue Pressure Runbook

Use this runbook when calculator throughput degrades or `/api/calculate/jobs` starts returning queue-related `429` errors.

## Quick Checks

1. Fetch a live operational snapshot:

```bash
curl -s http://127.0.0.1:8000/api/ops | jq '.queues.job_pressure'
```

2. Fetch a lightweight health probe snapshot:

```bash
curl -s http://127.0.0.1:8000/api/health | jq '.queue_pressure'
```

## Fields To Watch

- `queues.job_pressure.utilization_ratio`: queued+running load divided by `FF_CALC_MAX_ACTIVE_JOBS_TOTAL`.
- `queues.job_pressure.at_capacity`: `true` means new async jobs may be rejected.
- `queues.job_pressure.queued_oldest_age_seconds`: rising values indicate backlog growth.
- `queues.job_pressure.running_longest_runtime_seconds`: high values indicate slow or stuck workers.
- `queues.job_pressure.alerts.queue_wait_exceeds_request_timeout`: queue wait exceeded `FF_CALC_REQUEST_TIMEOUT_SECONDS`.
- `queues.job_pressure.alerts.runtime_exceeds_request_timeout`: running job duration exceeded `FF_CALC_REQUEST_TIMEOUT_SECONDS`.
- `queues.rate_limit_activity.totals.blocked`: request throttling pressure across endpoints.

## Triage Heuristics

- `at_capacity=true` and `queued_oldest_age_seconds` climbing:
  - Likely worker saturation. Scale workers or reduce incoming load.
- `runtime_exceeds_request_timeout=true` with low queue depth:
  - Likely expensive or stuck job execution; inspect calculator logs for long-running requests.
- `rate_limit_activity.totals.blocked` spike with normal queue utilization:
  - Likely client burst traffic; validate rate-limit configs and client retry behavior.

## Immediate Mitigations

- Temporarily increase `FF_CALC_MAX_ACTIVE_JOBS_TOTAL` if CPU/memory headroom exists.
- Temporarily increase `FF_CALC_JOB_WORKERS` if CPU headroom exists and lock contention is acceptable.
- Tighten caller retry/backoff behavior for `429` responses.
- If queue wait is breaching timeout alerts, reduce user-facing async job fan-out until pressure recovers.

## Recovery Verification

Use the same `/api/ops` query and confirm:

- `utilization_ratio` trending down.
- `at_capacity=false`.
- `queued_oldest_age_seconds` returning to near-zero.
- alert flags clearing.
