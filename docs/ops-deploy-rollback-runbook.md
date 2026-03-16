# Deploy & Rollback Runbook

Covers deployment verification, rollback procedures, and post-deploy smoke tests for Fantasy Foundry on Railway.

## Post-Deploy Smoke Tests

Run these checks immediately after every deploy to verify the service is healthy.

### 1. Health & Readiness

```bash
# Health check (returns 200 if server is up, includes queue pressure)
curl -sf https://fantasy-foundry.com/api/health | jq '.status, .queue_pressure'

# Readiness probe (returns 200 when data is loaded and ready to serve)
curl -sf https://fantasy-foundry.com/api/ready | jq '.status'
```

### 2. Data Integrity

```bash
# Verify projection metadata loaded (data version, player counts)
curl -sf https://fantasy-foundry.com/api/meta | jq '.data_version, .total_batters, .total_pitchers'

# Spot-check a projection query (limit=1 for speed)
curl -sf 'https://fantasy-foundry.com/api/projections/all?limit=1' | jq '.total_results'
```

### 3. Calculator Availability

```bash
# Status endpoint confirms calculator subsystem is operational
curl -sf https://fantasy-foundry.com/api/status | jq '.calculator'
```

### 4. Operational Metrics

```bash
# Full operational snapshot (queues, rate limits, cache stats)
curl -sf https://fantasy-foundry.com/api/ops | jq '.queues.job_pressure, .uptime_seconds'
```

## Rollback Procedure (Railway)

### Option A: Railway Dashboard

1. Go to the Railway project dashboard
2. Click on the Fantasy Foundry service
3. Navigate to **Deployments**
4. Find the last known-good deployment
5. Click the three-dot menu and select **Redeploy**

### Option B: Git Revert

If the bad deploy was triggered by a git push:

```bash
# Identify the bad commit
git log --oneline -5

# Revert the bad commit(s)
git revert <bad-commit-sha>
git push origin main
```

Railway will auto-deploy the revert.

### Post-Rollback Verification

After rollback, re-run all smoke tests above. Also check:

```bash
# Verify no calculator jobs were stranded (graceful shutdown should cancel them)
curl -sf https://fantasy-foundry.com/api/ops | jq '.queues.job_pressure.running, .queues.job_pressure.queued'
```

## Common Deploy Issues

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `/api/ready` returns 503 | Data files not loaded yet | Wait 15-30s for startup; check health endpoint |
| `/api/health` returns 503 | Server crashed during startup | Check Railway logs; likely missing env var or data file |
| Calculator jobs return 503 | Server just restarted | Jobs are auto-cancelled on restart with "Server restarting" message; users can retry |
| Projection queries return empty | Stale/missing data artifacts | Verify `data/*.json` files are committed and up to date |
