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
│   ├── app.py                          # FastAPI application
│   ├── api/routes/                     # Route registration modules (status/projections/calculate)
│   ├── dynasty_roto_values.py          # Main valuation workflow + CLI facade
│   └── valuation/                      # Shared valuation modules (models/positions/assignment)
├── frontend/
│   ├── index.html                      # Vite entry HTML (with inline styles)
│   ├── src/                            # React source modules
│   │   ├── main.jsx                    # App composition root + primary screens
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
- Python 3.10+
- Node.js 20+ (for frontend build)

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
# Backend unit/integration suite
pytest -q

# Frontend unit tests
cd frontend
npm test
```

### CI Parity Check (Frontend Dist Freshness)
```bash
cd frontend
npm ci
npm run build
cd ..
git diff --exit-code -- frontend/dist
```

`git diff` should be clean. If it is not, commit the regenerated `frontend/dist` output.

### CI Parity Check (Source File Size Guardrail)
```bash
python scripts/check_max_file_lines.py
```

This guardrail keeps new backend/frontend source files under the configured line threshold while allowing known legacy hotspots during incremental refactors.

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

### Optional: Proxy + Rate Limit Identity Settings

The API rate limiter and async-job IP guardrails can be configured for proxy deployments:

- `FF_TRUST_X_FORWARDED_FOR` (default: `0`)  
  - `0`/`false`: use direct socket client IP (`request.client.host`) unless trusted proxy CIDRs are configured.
  - `1`/`true`: trust `X-Forwarded-For` even without CIDR allow-list (only recommended behind a trusted proxy chain).
- `FF_TRUSTED_PROXY_CIDRS` (default: empty)  
  - Comma-separated IP/CIDR allow-list for trusted proxy hops (example: `10.0.0.0/8,172.16.0.0/12`).
  - When set, `X-Forwarded-For` is only honored if the direct peer is in this allow-list.
- `FF_RATE_LIMIT_BUCKET_CLEANUP_INTERVAL_SECONDS` (default: `60`)  
  - Periodic cleanup interval for stale in-memory rate-limit buckets.
- `FF_REQUIRE_PRECOMPUTED_DYNASTY_LOOKUP` (default: `1`)  
  - `1`/`true`: require a valid precomputed `data/dynasty_lookup.json`; projections return HTTP 503 if missing/stale/invalid.
  - `0`/`false`: allow runtime fallback generation (slower cold-start projections responses).

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Runtime health summary (projection row counts, cache/job stats) |
| GET | `/api/version` | Build metadata (`build_id`, commit SHA, build timestamp) |
| GET | `/api/meta` | Filter options (teams, years, positions) |
| GET | `/api/projections/all` | Combined hitter+pitcher rows (query params: player, team, player_keys, year, years, pos, dynasty_years, career_totals, include_dynasty, sort_col, sort_dir, limit, offset) |
| GET | `/api/projections/bat` | Hitter projections (query params: player, team, player_keys, year, years, pos, dynasty_years, career_totals, include_dynasty, sort_col, sort_dir, limit, offset) |
| GET | `/api/projections/pitch` | Pitcher projections (same query params as `/api/projections/bat`) |
| GET | `/api/projections/export/{dataset}` | Export filtered projections as CSV/XLSX (`dataset`: `all`, `bat`, `pitch`; query param: `format`) |
| POST | `/api/calculate` | Run dynasty value calculator (JSON body with league settings) |
| POST | `/api/calculate/export` | Export calculator output as CSV/XLSX (`format`, optional `include_explanations`) |
| POST | `/api/calculate/jobs` | Create async calculator job (returns `job_id` and queue status) |
| GET | `/api/calculate/jobs/{job_id}` | Poll async calculator job status/result |
| DELETE | `/api/calculate/jobs/{job_id}` | Cancel queued/running async calculator job |

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
- **Points mode**: Rules-based valuation where each event is weighted by custom points settings.
- **IP cap**: Maximum innings for pitching value calculations; extra innings above the cap do not add value.
- **PlayerKey**: Normalized player identifier derived from name (can collide for same-name players).
- **PlayerEntityKey**: Disambiguated player identifier (used to separate same-name players by context such as team).
- **DynastyMatchStatus**: Join status for attaching dynasty values to projection rows: `matched`, `no_unique_match`, or `missing`.
- **Two-way player**: A player with both hitter and pitcher projections that may be merged/handled specially in valuation views.
- **Calculation job**: Async calculator run created via `/api/calculate/jobs` and polled by `job_id` until completion/failure/cancellation.

## Next Steps

Some ideas for future development:

- **Player profile pages** — individual player pages with year-by-year projection charts
- **Comparison tool** — side-by-side player comparisons
- **League mode** — add the full custom league settings (SP/RP/P slots, OPS, SVH categories)
- **Export** — download rankings as CSV or Excel
- **Projection freshness indicators** — show when each player's projection was last updated
- **Mobile optimization** — responsive improvements for phone-sized screens
