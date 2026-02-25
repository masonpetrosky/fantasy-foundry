# Fantasy Foundry — Claude Code Guide

## What This Is

Production MLB dynasty fantasy baseball app with 20-year projections (2026–2045), a Monte Carlo dynasty valuation calculator, and optional cloud sync (Supabase). Live at https://fantasy-foundry.com.

**Stack:** React (Vite) frontend + FastAPI backend, deployed on Railway via Docker.

---

## Dev Commands

```bash
# Full test suite (backend + frontend)
make test

# Backend only (fast, excludes full_regression)
make test-backend-fast          # pytest -q -m "not full_regression"
make test-backend               # pytest -q (includes coverage enforcement)

# Frontend only
make test-frontend              # cd frontend && npm test

# Lint (Ruff + ESLint + generated artifact check)
make lint

# Type check (mypy on specific modules)
make typecheck

# All quality gates
make check
```

**Frontend dev server:**
```bash
cd frontend && npm run dev
```

**Coverage:**
- Backend enforces ≥75% (pytest-cov)
- Frontend thresholds in `frontend/vite.config.js` (lines/statements: 50%, functions/branches: 70%)

---

## Architecture

### Backend (`backend/`)

| Path | Purpose |
|---|---|
| `app.py` | FastAPI entrypoint |
| `runtime.py` | App wiring (startup, middleware) |
| `api/routes/` | Route modules: `projections.py`, `calculate.py`, `status.py` |
| `core/` | Shared orchestration helpers (settings, caching, jobs, rate limits) |
| `core/settings.py` | Typed env/config loader (mypy'd) |
| `domain/constants.py` | Shared domain constants |
| `services/projections/` | Projection query pipeline + runtime boundaries |
| `services/valuation/` | Service boundary around valuation entry points |
| `dynasty_roto_values.py` | Legacy re-export facade for valuation + CLI |
| `valuation/` | Core math: models, positions, assignment, common/league math |

**To add a new route:** create a handler function in `backend/core/`, register the route in the appropriate `backend/api/routes/*.py` router, and wire the router in `backend/runtime.py` via `build_*_router()`.

**To add a new valuation stat/slot:** `backend/valuation/models.py` (schema), `backend/valuation/common_math.py` (math), `backend/api/routes/calculate.py` (request model).

### Frontend (`frontend/src/`)

| Path | Purpose |
|---|---|
| `features/projections/` | Projections explorer — container, hooks, components |
| `features/projections/hooks/` | Extracted state hooks (column visibility, filter presets, export, etc.) |
| `features/projections/components/` | UI components (FilterBar, ComparisonPanel, ResultsShell, etc.) |
| `dynasty_calculator*.jsx` | Calculator sidebar, categories, slots, results |
| `hooks/useProjectionsData.js` | Core data fetch hook |
| `app_state_storage.js` | localStorage persistence + preset serialization |
| `analytics.js` | Analytics event tracking |
| `styles/` | CSS: `app.css`, `projections.css`, `responsive.css`, `calculator.css` |

**To add a new projection column:** update `useProjectionColumnVisibility.js` catalog and the backend query.

**To add a new calculator setting:** `dynasty_calculator_sidebar_categories.jsx` or `_slots.jsx` → `app_state_storage.js` preset serialization → `backend/api/routes/calculate.py` request schema → `backend/valuation/`.

---

## Code Quality Gates

- **Ruff:** `ruff check backend tests preprocess.py scripts` — zero per-file ignores allowed (enforced by `scripts/check_ruff_per_file_ignores.py`)
- **mypy:** runs on `backend/api/middleware.py`, `backend/core/settings.py`, `backend/core/networking.py`, `backend/core/rate_limit.py`, `backend/core/result_cache.py`, `backend/core/jobs.py`, `backend/core/data_refresh.py`
- **ESLint:** `cd frontend && npm run lint`
- **Generated artifacts:** `scripts/check_generated_artifacts_untracked.sh` (run before lint)

---

## Large / Sensitive Files — Avoid Bloating

- `backend/dynasty_roto_values.py` — 900+ line legacy facade; add new logic to `backend/valuation/` submodules instead
- `backend/valuation/common_math.py` — 1100+ lines; surgical edits only
- `backend/valuation/league_math.py` — 1000+ lines
- `frontend/src/features/projections/container.jsx` — orchestration only; new logic belongs in hooks or components
- `data/` — large JSON projection files; do not modify by hand

---

## Key Conventions

- **Re-exports in `dynasty_roto_values.py`** use `from X import Y as Y` syntax (signals intentional re-export to Ruff)
- **`try/except ImportError`** pattern in `dynasty_roto_values.py` supports both `backend.*` import path and direct script execution
- **URL preset sharing:** calculator settings are serialized to/from URL query params via `app_state_storage.js`
- **Data version tracking:** `dataVersion` prop threads through the app to invalidate stale calculator overlays
- **Rate limiting:** projection queries and calculator jobs are rate-limited; see `backend/core/rate_limit.py`
- **React components** use `React.memo` + extracted hooks; avoid adding logic directly to `container.jsx`
