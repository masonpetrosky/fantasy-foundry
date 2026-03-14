# Dynasty Baseball Projections — Web App

A web application for browsing 20-year MLB dynasty baseball projections (2026–2045) and generating personalized dynasty rankings with custom league settings.

## Production

- Live site: https://fantasy-foundry.com
- Hosting: Railway (Docker deploy from this repository)

## Features

- **Projections Explorer** — Browse, search, filter, sort, and paginate hitter/pitcher/combined projections across 20 seasons (default view is rest-of-career totals)
- **Dynasty Value Calculator** — Configure your league settings (teams, roster, categories, IP caps) and generate Monte Carlo–based dynasty rankings
- **Dual scoring workflows** — Switch between roto-focused and points-focused setups, including editable custom points scoring rules
- **Explainability panel** — Inspect per-year value contributions and detailed stat-to-points breakdowns in points mode
- **Preset + sharing workflow** — Save named calculator presets locally and share full settings through URL links
- **Optional account sync** — Sign up/sign in to sync presets and watchlist across devices via Supabase Auth + Postgres
- **Data export** — Export projections and calculator rankings to CSV/XLSX
- **Efficient large-result loading** — Projection responses are gzip-compressed by the API, and the UI cancels stale in-flight requests during rapid filter changes
- **Free & ad-free** — No paywalls

## Architecture

```
dynasty-site/
├── backend/
│   ├── app.py                          # FastAPI compatibility entrypoint
│   ├── runtime.py                      # FastAPI runtime wiring + app internals
│   ├── api/routes/                     # Route registration modules (status/projections/calculate/billing/fantrax/newsletter/og_cards/frontend_assets)
│   ├── core/settings.py                # Typed env/config loader
│   ├── core/calculator_orchestration.py # Calculator endpoint/job orchestration helpers
│   ├── core/status_orchestration.py    # Status/health/version/readiness endpoint helpers
│   ├── core/dynasty_lookup_orchestration.py # Dynasty lookup attach/year-filter helpers
│   ├── core/projection_preprocessing.py # Projection data identity/date averaging helpers
│   ├── core/projection_utils.py        # Projection utility/parsing helpers
│   ├── core/points_calculator.py       # Points scoring and replacement-level calculation helpers
│   ├── core/calculator_helpers.py      # Category parsing, guardrails, and explanation helpers
│   ├── core/common_calculator.py       # Cached common roto calculator orchestration helper
│   ├── core/export_utils.py            # CSV/XLSX export and record serialization helpers
│   ├── core/result_cache.py            # Local/Redis calculator result and job snapshot cache helpers
│   ├── core/data_refresh.py            # Data refresh/content-version/cache-inspection helpers
│   ├── core/runtime_config.py          # Shared runtime constants + build metadata helpers
│   ├── core/runtime_state_protocols.py # Typed protocol surfaces for state-driven runtime helpers
│   ├── domain/constants.py             # Shared domain constants
│   ├── services/projections/           # Projection service pipeline + runtime boundary helpers
│   ├── services/valuation/             # Service boundary around legacy valuation entrypoints
│   ├── services/calculator/            # Calculator job orchestration service
│   ├── services/billing.py             # Stripe billing service
│   ├── services/fantrax/               # Fantrax league integration service
│   ├── dynasty_roto_values.py          # Main valuation workflow + CLI facade
│   └── valuation/                      # Shared valuation modules (models/positions/assignment)
├── frontend/
│   ├── index.html                      # Vite entry HTML (with inline styles)
│   ├── src/                            # React source modules
│   │   ├── main.jsx                    # App composition root + primary screens
│   │   ├── hooks/useProjectionsData.js # Projections query/filter/cache hook
│   │   ├── features/projections/       # Projections explorer feature container/modules
│   │   ├── app_state_storage.js        # Local/cloud preference persistence helpers
│   │   ├── request_helpers.js          # API error/response/debounce helper utilities
│   │   ├── account_panel.jsx           # Account sync/auth UI
│   │   └── methodology_section.jsx     # Methodology + glossary + FAQ content block
│   ├── dist/                           # Built frontend assets (served by backend)
│   └── package.json                    # Frontend build scripts/deps
├── data/
│   ├── Dynasty Baseball Projections.xlsx
│   ├── bat.json                        # Pre-processed hitter data
│   ├── pitch.json                      # Pre-processed pitcher data
│   ├── meta.json                       # Filter options metadata
│   └── dynasty_lookup.json             # Precomputed default dynasty lookup cache
├── Dockerfile
├── supabase/
│   └── user_preferences.sql             # Auth/RLS table setup for cloud-synced user prefs
├── requirements.txt
└── README.md
```

## Local Development

### Prerequisites
- Python 3.12+
- Node.js 22+ (for frontend build)

Version pins are included in `.python-version` and `.nvmrc` for local parity with CI.

### Setup
```bash
# Install dependencies
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..

# Run the dev server
uvicorn backend.app:app --reload --port 8000
```

Then open http://localhost:8000

### Frontend-Only Dev (optional)
```bash
cd frontend
npm run dev
```

Vite serves the UI at http://localhost:5173 and proxies API calls to `localhost:8000` via existing frontend API-base detection.
FastAPI serves `frontend/dist` in normal app mode, so rebuild (`npm run build`) after frontend source changes.

### Optional: Account Login + Cloud Sync (Supabase)

The app now supports optional user accounts that sync calculator presets and watchlists across visits/devices.

1. Create a Supabase project.
2. In Supabase SQL Editor, run `supabase/user_preferences.sql`.
3. Configure frontend env vars (copy from `frontend/.env.example`):

```bash
cd frontend
cp .env.example .env
# then set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
```

`VITE_*` variables are compiled into frontend assets at build time, so set them before `npm run build` (or before Docker build in deployment).

4. Rebuild frontend assets:

```bash
cd frontend
npm run build
```

Without these env vars, the site continues to work with local-only browser storage.

### Running Tests
```bash
# Backend full suite
pytest -q

# Backend fast suite (matches required PR CI lane)
pytest -q -m "not full_regression"

# Backend high-cost regression lane (scheduled + manual CI)
pytest -q -m "full_regression" --no-cov

# Frontend unit tests
cd frontend
npm test

# Frontend unit tests + coverage thresholds
cd frontend
npm run test:coverage
```

Coverage outputs (`.coverage`, `coverage.xml`, `htmlcov/`, `frontend/coverage/`) are generated locally and must remain untracked:

```bash
./scripts/check_generated_artifacts_untracked.sh
```

### Linting
```bash
# Enforce backend Ruff per-file-ignore allowlist
python scripts/check_ruff_per_file_ignores.py

# Enforce generated coverage artifacts remain untracked
./scripts/check_generated_artifacts_untracked.sh

# Backend lint
ruff check backend tests preprocess.py scripts

# Frontend lint
cd frontend
npm run lint
```

### Type Checking
```bash
# Full mypy check across all typed modules (see Makefile for complete file list)
make typecheck
```

### Repository Search Hygiene
Fast repo-wide searches should ignore generated/vendor directories by default.
`rg` picks this up automatically through `.rgignore`.

If you need to include ignored paths in a one-off search, run:

```bash
rg --no-ignore <pattern>
```

### Unified Local Check
```bash
# Runs lint + backend fast suite + frontend tests + backend type checks
make check
```

### Dependency Audit Checks
```bash
# Python direct dependency vulnerability gate (requires pip-audit installed)
python scripts/check_pip_audit_direct.py

# Frontend direct dependency gate (high/critical only)
cd frontend
node ../scripts/check_npm_audit_direct.mjs
```

### CI Parity Check (Frontend Dist Freshness)
```bash
./scripts/check_frontend_dist.sh
```

If the check fails, commit the added/modified/deleted files under `frontend/dist`.
On GitHub, keep `CI / frontend-dist` as a required pull-request check before merge to `main`.

Quick local check when frontend dependencies are already installed:

```bash
cd frontend
npm run build:check
npm run check:asset-budget
```

### CI Parity Check (Source File Size Guardrail)
```bash
python scripts/check_max_file_lines.py
```

This guardrail keeps new backend/frontend source files under the configured line threshold while allowing known legacy hotspots during incremental refactors.

### CI Parity Check (Ruff Per-File Ignore Allowlist)
```bash
python scripts/check_ruff_per_file_ignores.py
```

This guardrail prevents silent growth of temporary Ruff per-file ignores during incremental refactors.

### Activation Rollout Readout
After shipping activation-funnel changes, validate event contract coverage and KPI/guardrail deltas:

```bash
python scripts/activation_readout.py \
  --input tmp/activation_current.csv \
  --baseline tmp/activation_baseline.csv \
  --strict-contract
```

Recommended one-command execution (includes decision memo generation):

```bash
scripts/run_activation_readout.sh \
  --current tmp/activation_current.csv \
  --baseline tmp/activation_baseline.csv \
  --date 2026-02-25 \
  --owner "Analytics Team"
```

Recommended two-checkpoint execution (24h + 48h + final gate):

```bash
scripts/run_activation_readout_checkpoints.sh \
  --current-24h tmp/activation_current_24h.csv \
  --baseline-24h tmp/activation_baseline_24h.csv \
  --date-24h 2026-02-26 \
  --current-48h tmp/activation_current_48h.csv \
  --baseline-48h tmp/activation_baseline_48h.csv \
  --date-48h 2026-02-27 \
  --owner "Analytics Team"
```

This generates per-checkpoint readouts and memos plus:

- `tmp/activation_rollout_gate_<date-48h>.json`
- `docs/activation-rollout-final-decision-<date-48h>.md`

See [`docs/activation-rollout-validation.md`](docs/activation-rollout-validation.md) for expected columns, thresholds, and rollout decision rules.

### Local Activation Diagnostics (Browser)
The app stores a capped local analytics buffer (`ff:analytics-events:v1`) and exposes a debug bridge on `window.ffAnalytics`:

```js
window.ffAnalytics.summary()      // quick-start funnel summary
window.ffAnalytics.events(200)    // last N events
window.ffAnalytics.exportCsv()    // download local events as CSV
window.ffAnalytics.clear()        // clear local buffer
```

The diagnostics panel also provides a `Command Center` modal with:
- `Copy Readout Cmd` for `scripts/run_activation_readout.sh`
- `Copy Checkpoint Cmd` for `scripts/run_activation_readout_checkpoints.sh`
- Date presets (`Use Today`, `Use Tomorrow`) and editable owner/path fields
- Live runtime card sourced from `/api/ops` (queue utilization, oldest queued job age, and rate-limit block count), auto-refreshing every 30 seconds

Enable the in-app diagnostics panel with either:

- `VITE_FF_ACTIVATION_DIAGNOSTICS_PANEL_V1=1` at build time, or
- `?activation_debug=1` in the browser URL.

This is useful for owner-operator validation in staging/prod when vendor analytics exports are delayed.

CI also enforces cross-stack compatibility for this export path:

```bash
python scripts/check_activation_browser_csv_contract.py
```

### Running Browser E2E Tests (Playwright)
```bash
# Install app + dev test dependencies
pip install -r requirements-dev.txt

# Install Playwright Chromium once
python -m playwright install chromium

# Run browser integration tests (opt-in under pytest)
FF_RUN_E2E=1 pytest -q tests/test_e2e_projections_pagination.py tests/test_e2e_calculator_smoke.py
```

`test_e2e_projections_pagination.py` launches the app locally and verifies:
- the projections view loads in `Rest of Career Totals` mode
- forcing an invalid empty year selection keeps the view in `Rest of Career Totals` mode
- the browser issued paginated API requests against `/api/projections/all`

`test_e2e_calculator_smoke.py` launches the app locally and validates a lightweight calculator UX smoke flow on desktop and mobile:
- switch to points-focused setup
- run rankings and verify result-count format
- exercise reset filters and column chooser controls
- verify row selection surfaces the explainability panel

### Updating Projections

Single-player manual ingest workflow (GPT-generated projections):
- Quick guide: [`docs/projection-ingest-runbook.md`](docs/projection-ingest-runbook.md)
- Prompt template: [`docs/templates/gpt-single-player-projection-prompt.md`](docs/templates/gpt-single-player-projection-prompt.md)
- Quick path:
  1. Fill `[Player]`, `[Position]`, and `[Team]` in the prompt template and run it in GPT.
  2. Download the generated `.xlsx` and append the 2026-2045 rows into `data/Dynasty Baseball Projections.xlsx` (`Bat`/`Pitch` sheets).
  3. Manually fill `Minor`, `Fantrax Roster`/`Roster`, and `Date` for the appended rows.
  4. Run `python preprocess.py`.

When you update the Excel file, re-run the preprocessing to regenerate the JSON data files:

```bash
python preprocess.py
```

`preprocess.py` now also builds `data/dynasty_lookup.json` by default so the first projections request does not need to recompute default dynasty values at runtime.
If cache generation fails, `preprocess.py` exits non-zero so deploys do not silently ship without the precomputed lookup.

If you need a faster preprocess run and are okay with a slower first projections load, you can skip cache generation:

```bash
python preprocess.py --skip-dynasty-cache
```

Strict ingest validation defaults to the 2026-2045 projection window. Override only when intentionally shifting the projection horizon:

```bash
python preprocess.py --min-year 2026 --max-year 2045
```

Optional quality report output:

```bash
python preprocess.py --quality-report tmp/projection_quality_report.json
python scripts/check_projection_quality_report.py --report tmp/projection_quality_report.json
```

Production deployments enforce the precomputed cache by default (`FF_REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP=1`), so skipping cache generation will cause projections endpoints to return HTTP 503 until a valid `data/dynasty_lookup.json` is deployed.

## Deployment

### Docker
```bash
docker build -t dynasty-projections .
docker run -p 8000:8000 dynasty-projections
```

### Railway / Render / Fly.io
All three support Dockerfiles out of the box:

1. Push this repo to GitHub
2. Connect the repo to your hosting provider
3. It will auto-detect the Dockerfile and deploy

**Railway** (recommended for simplicity):
- Free tier: 500 hours/month, 512 MB RAM — plenty for this app
- Just connect your GitHub repo and deploy
- Current production custom domain: https://fantasy-foundry.com

This Docker image sets these production-friendly runtime defaults:
- `FF_ENV=production` and explicit `FF_CORS_ALLOW_ORIGINS=https://fantasy-foundry.com`.
- `FF_PREWARM_DEFAULT_CALC=0` so post-deploy first projections loads are not delayed by calculator prewarm work.
- `FF_REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP=1` so projections never fall back to expensive runtime dynasty lookup generation.
- Tightened public rate limits and queue caps:
  - `FF_CALC_SYNC_RATE_LIMIT_PER_MINUTE=20`
  - `FF_CALC_SYNC_AUTH_RATE_LIMIT_PER_MINUTE=60`
  - `FF_CALC_JOB_CREATE_RATE_LIMIT_PER_MINUTE=10`
  - `FF_CALC_JOB_CREATE_AUTH_RATE_LIMIT_PER_MINUTE=30`
  - `FF_CALC_JOB_STATUS_RATE_LIMIT_PER_MINUTE=180`
  - `FF_CALC_JOB_STATUS_AUTH_RATE_LIMIT_PER_MINUTE=360`
  - `FF_PROJ_RATE_LIMIT_PER_MINUTE=90`
  - `FF_EXPORT_RATE_LIMIT_PER_MINUTE=20`
  - `FF_CALC_MAX_ACTIVE_JOBS_PER_IP=1`
  - `FF_CALC_MAX_ACTIVE_JOBS_TOTAL=24`

If you set Railway service variables manually, keep these defaults unless you intentionally want the opposite tradeoff.

### Backend `FF_*` Runtime Settings

| Variable | Default | Description |
| --- | --- | --- |
| `FF_ENV` | `development` | Runtime mode (`development` or `production`). Production mode enforces stricter startup safety checks. |
| `FF_CALC_JOB_TTL_SECONDS` | `1800` | Retention window for completed/failed/cancelled async calculator jobs. |
| `FF_CALC_JOB_MAX_ENTRIES` | `256` | Max in-memory async job records retained before pruning. |
| `FF_CALC_JOB_WORKERS` | `2` | Thread pool size for async calculator jobs. |
| `FF_PREWARM_DEFAULT_CALC` | `1` | Prewarm default calculator caches on startup (`Dockerfile` overrides this to `0`). |
| `FF_CALC_REQUEST_TIMEOUT_SECONDS` | `600` | Calculator request timeout metadata used in guardrails/status payloads. |
| `FF_CALC_SYNC_RATE_LIMIT_PER_MINUTE` | `30` | Sync calculator request limit per identity per minute. |
| `FF_CALC_SYNC_AUTH_RATE_LIMIT_PER_MINUTE` | `max(base,60)` | Sync calculator request limit for authenticated API-key callers per minute. |
| `FF_CALC_JOB_CREATE_RATE_LIMIT_PER_MINUTE` | `15` | Async calculator job-create limit per identity per minute. |
| `FF_CALC_JOB_CREATE_AUTH_RATE_LIMIT_PER_MINUTE` | `max(base,30)` | Async calculator job-create limit for authenticated API-key callers per minute. |
| `FF_CALC_JOB_STATUS_RATE_LIMIT_PER_MINUTE` | `240` | Async calculator job status/cancel limit per identity per minute. |
| `FF_CALC_JOB_STATUS_AUTH_RATE_LIMIT_PER_MINUTE` | `max(base,360)` | Async calculator job status/cancel limit for authenticated API-key callers per minute. |
| `FF_PROJ_RATE_LIMIT_PER_MINUTE` | `120` | Projections read endpoint limit per identity per minute. |
| `FF_EXPORT_RATE_LIMIT_PER_MINUTE` | `30` | Projections export endpoint limit per identity per minute. |
| `FF_CALC_MAX_ACTIVE_JOBS_PER_IP` | `2` | Max queued/running async jobs per client IP. |
| `FF_CALC_MAX_ACTIVE_JOBS_TOTAL` | `24` | Max queued/running async jobs across one app instance before queue rejection. |
| `FF_CALC_RESULT_CACHE_TTL_SECONDS` | `1800` | TTL for calculator result cache entries. |
| `FF_CALC_RESULT_CACHE_MAX_ENTRIES` | `256` | Max local calculator result cache entries before LRU pruning. |
| `FF_REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP` | `1` | Require a valid `data/dynasty_lookup.json` (otherwise projections return 503). |
| `FF_TRUST_X_FORWARDED_FOR` | `0` | Trust `X-Forwarded-For` chain when resolving client identity. |
| `FF_TRUSTED_PROXY_CIDRS` | `""` | Comma-separated trusted proxy CIDRs for forwarded IP handling. |
| `FF_REDIS_URL` | `""` | Optional Redis URL; enables shared calculator result cache, shared rate limiting, shared cancellation markers, and shared active-job tracking across workers/pods. |
| `FF_REQUIRE_CALCULATE_AUTH` | `0` | Require API keys on `/api/calculate*` endpoints. |
| `FF_CALCULATE_API_KEYS` | `""` | Comma/space-separated calculator API keys accepted via `X-API-Key` or `Authorization: Bearer ...`. |
| `FF_CANONICAL_HOST` | `""` | Optional canonical host; when set, requests for `www.<host>` are redirected to `<host>` with HTTP `308`. |
| `FF_RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS` | `60` | Cleanup interval for local in-memory rate-limit buckets (used when Redis limiter is unavailable). |
| `FF_CORS_ALLOW_ORIGINS` | `*` | Comma-separated CORS origins (`*` by default; use explicit origins in production). |

When `FF_REQUIRE_CALCULATE_AUTH=1`, calculate routes return:
- HTTP `401` for missing/invalid API keys
- HTTP `503` if auth is required but `FF_CALCULATE_API_KEYS` is not configured

When `FF_ENV=production`, startup fails fast for unsafe config combinations:
- wildcard CORS (`FF_CORS_ALLOW_ORIGINS=*`)
- trusted forwarded-chain mode without explicit trusted proxies (`FF_TRUST_X_FORWARDED_FOR=1` and empty `FF_TRUSTED_PROXY_CIDRS`)
- required calculator auth without configured API keys (`FF_REQUIRE_CALCULATE_AUTH=1` and empty `FF_CALCULATE_API_KEYS`)

Post-deploy sanity checks for projection startup latency:
- `GET /api/ops` should report `data.dynasty_lookup_cache.status = "ready"` and matching expected/found versions.
- `GET /api/ops` should expose `queues.rate_limit_activity.totals` so throttling pressure is visible during rollout.
- `GET /api/ops` should expose `queues.job_pressure` so queue saturation and oldest-job age are visible before timeouts spike.
- `GET /api/health` should expose `queue_pressure` with `active_jobs`/`at_capacity` for lightweight capacity probes.
- `GET /api/health` should show calculator prewarm idle/off when `FF_PREWARM_DEFAULT_CALC=0`.

Operational response guide: [`docs/ops-queue-pressure-runbook.md`](docs/ops-queue-pressure-runbook.md)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Runtime health summary (projection row counts, cache/job stats, lightweight queue-pressure capacity signal) |
| GET | `/api/ready` | Readiness probe (returns HTTP 503 when required startup prerequisites are not ready; includes current queue-capacity context) |
| GET | `/api/ops` | Operational diagnostics (runtime mode, limiter/cache posture, queue/cache stats, queue-pressure telemetry, live rate-limit activity counters, and non-secret config flags) |
| GET | `/api/version` | Build metadata (`build_id`, commit SHA, build timestamp) |
| GET | `/api/meta` | Filter options (teams, years, positions) |
| GET | `/api/projections/all` | Combined hitter+pitcher rows (query params: player, team, player_keys, year, years, pos, dynasty_years, career_totals, include_dynasty, sort_col, sort_dir, limit, offset) |
| GET | `/api/projections/bat` | Hitter projections (query params: player, team, player_keys, year, years, pos, dynasty_years, career_totals, include_dynasty, sort_col, sort_dir, limit, offset) |
| GET | `/api/projections/pitch` | Pitcher projections (same query params as `/api/projections/bat`) |
| GET | `/api/projections/profile/{player_id}` | Player profile payload (`dataset`, yearly series rows, career totals rows, matched identity metadata) |
| GET | `/api/projections/compare` | Compare payload for at least two `player_keys` (`dataset`, optional `career_totals/year/years/dynasty_years`, matched keys, and projection rows) |
| GET | `/api/projections/export/{dataset}` | Export filtered projections as CSV/XLSX (`dataset`: `all`, `bat`, `pitch`; query param: `format`) |
| POST | `/api/calculate` | Run dynasty value calculator (JSON body with league settings) |
| POST | `/api/calculate/export` | Export calculator output as CSV/XLSX (`format`, optional `include_explanations`) |
| POST | `/api/calculate/jobs` | Create async calculator job (returns `job_id` and queue status) |
| GET | `/api/calculate/jobs/{job_id}` | Poll async calculator job status/result |
| DELETE | `/api/calculate/jobs/{job_id}` | Cancel queued/running async calculator job |

Calculator auth note:
- If `FF_REQUIRE_CALCULATE_AUTH=1`, include `X-API-Key: <key>` or `Authorization: Bearer <key>` on all `/api/calculate*` requests.

`years` accepts comma-separated years and inclusive ranges, for example `2026,2028-2030`.
If both `year` and `years` are provided, results use the intersection.
`player_keys` accepts comma/space-separated `PlayerEntityKey` or `PlayerKey` values to fetch specific tracked players.
`dynasty_years` accepts comma-separated years and inclusive ranges, for example `2026,2028-2030`.
`career_totals=true` collapses each player to a single rest-of-career totals row across the selected years.
`pos` accepts one or more exact position tokens (comma, slash, or space separated), for example `SP,RP` or `1B/OF`.
`sort_dir` supports `asc` or `desc` and is applied server-side before pagination.
`sort_col` is validated server-side and returns HTTP 422 when unsupported for that endpoint.

For `/api/projections/all`, stat collisions are explicit:
- `H`, `HR`, `BB` are hitter stats
- `PitH`, `PitHR`, `PitBB` are pitcher stats

Identity fields are included end-to-end:
- `PlayerKey`: deterministic normalized player key
- `PlayerEntityKey`: disambiguated key for same-name collisions
- `DynastyMatchStatus`: `matched`, `no_unique_match`, or `missing` when dynasty values are attached

## Glossary

- **Dynasty league**: A long-term fantasy format where player value spans multiple future seasons instead of a single year.
- **Projection horizon**: The future window used for valuation (this app supports 2026-2045 projections).
- **Rest of Career Totals**: A single aggregated row per player across selected years (`career_totals=true`).
- **Dynasty Value**: The app's long-horizon value metric, built from discounted per-year production and centered around replacement-level roster value.
- **SGP (Standings Gain Points)**: A roto scoring conversion that estimates how much of each stat moves a team by one standings point.
- **Replacement level**: The expected production from the best readily available unrostered players at each slot.
- **Monte Carlo simulation**: Repeated randomized league outcomes used to estimate SGP/stat denominators and stabilize valuation.
- **Roto mode**: Category-based valuation (e.g., AVG/HR/RBI for hitters; ERA/WHIP/K for pitchers).
- **Points mode**: Rules-based deterministic valuation where each event is weighted by custom points settings (no Monte Carlo or IP min/max constraints).
- **IP cap**: Maximum innings for pitching value calculations; extra innings above the cap do not add value.
- **PlayerKey**: Normalized player identifier derived from name (can collide for same-name players).
- **PlayerEntityKey**: Disambiguated player identifier (used to separate same-name players by context such as team).
- **DynastyMatchStatus**: Join status for attaching dynasty values to projection rows: `matched`, `no_unique_match`, or `missing`.
- **Two-way player**: A player with both hitter and pitcher projections that may be merged/handled specially in valuation views.
- **Calculation job**: Async calculator run created via `/api/calculate/jobs` and polled by `job_id` until completion/failure/cancellation.

## Next Steps

Some ideas for future development:

- **Projection freshness indicators** — show when each player's projection was last updated
