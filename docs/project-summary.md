# Fantasy Foundry — Comprehensive Project Summary

_For resume tailoring. Feed this to Claude Chat alongside your resume and target job description._

---

## Elevator Pitch

**Fantasy Foundry** is a production SaaS web application for MLB dynasty fantasy baseball, live at fantasy-foundry.com. It provides 20-year player projections (2026–2045) for 800+ players and a Monte Carlo dynasty valuation calculator that lets users generate fully customizable dynasty rankings. It features a freemium business model with Stripe billing, Supabase authentication, and cloud sync. Solo-built and maintained end-to-end: product design, full-stack engineering, data pipeline, infrastructure, CI/CD, analytics, SEO, and monetization.

---

## Technical Architecture

### Backend (Python / FastAPI)
- **FastAPI** REST API (20+ endpoints) serving projections, dynasty valuations, billing, newsletter, and operational health routes
- **Router factory pattern**: each route module exposes a `build_*_router()` factory that accepts handler dependencies as arguments — fully decoupled from business logic, independently testable
- **Service layer architecture**: domain logic behind service boundaries (`ProjectionService`, `CalculatorService`, `ValuationService`); route files are pure HTTP wiring
- **Pydantic request models** with field-level validation (type, range, max_length) on all API inputs
- **Three-layer caching**: in-process LRU query cache (invalidated on data refresh), calculator result cache (in-memory + optional Redis, TTL-based, content-hash keyed), and precomputed file-based dynasty lookup cache
- **Rate limiting**: sliding-window (1-minute buckets), per-IP per-endpoint-type, with separate anonymous and authenticated tiers; in-memory or Redis-backed for multi-instance deployments
- **Async job system**: CPU-intensive calculator runs submitted to a `ThreadPoolExecutor` (configurable worker count), returning `202 Accepted` with job polling and cancellation endpoints; concurrency guards (max 1 active job per IP, 24 total)
- **Hot data reload**: file-watcher detects source data changes by mtime/size, acquires a lock, hot-reloads all JSON, recomputes content hashes, and clears all LRU caches — zero-downtime data updates
- **Structured JSON logging** in production via custom logging module
- **Sentry error tracking** with configurable sample rate
- **Security**: non-root Docker user, CORS whitelist, canonical host redirect, Cloudflare trusted proxy CIDR validation for real client IP resolution, gzip response compression

### Frontend (React / TypeScript / Vite)
- **React 19 SPA** with React Router v6, code-split via `React.lazy` for calculator and methodology sections
- **Strict TypeScript** — full migration from JavaScript completed across ~120 source files with zero `any` types
- **Custom hook architecture**: 14+ extracted hooks in the projections feature alone (`useProjectionsData`, `useProjectionColumnVisibility`, `useProjectionFilterPresets`, `useProjectionExportPipeline`, `useProjectionComparisonComposition`, etc.); container component is orchestration-only
- **`React.memo`** on performance-critical components (filter bar, mobile sheet)
- **LRU page cache** in the data-fetching hook (80 entries, keyed by data version + filter params) with speculative next-page prefetching and AbortController-based request cancellation
- **Custom analytics system**: event buffer (up to 400 events, localStorage-persisted), session ID via `crypto.getRandomValues`, GA4/GTM integration, debug bridge on `window.ffAnalytics` with activation funnel analysis
- **Supabase auth**: lazy-loaded client, `onAuthStateChange` listener, cloud preference sync (calculator presets + watchlists) with 900ms debounced writes and local-wins merge strategy
- **No external UI libraries or chart libraries** — all visualizations (sparklines, fairness meters) are hand-rolled inline SVG

### Data Pipeline
- **Source**: Excel workbook with 20-year projection data for 800+ MLB players (hitters and pitchers)
- **Preprocessing** (`preprocess.py`, 537 lines): validates 47+ required columns, normalizes aliases, computes deterministic player identity keys, re-derives rate stats from components (mathematically correct averaging, not naive), snapshots previous data for delta computation, outputs JSON + precomputed dynasty lookup cache
- **Automated refresh**: GitHub Actions workflow runs every Monday and Thursday, re-processes data, auto-commits if changes detected
- **Delta tracking**: previous-week snapshots enable week-over-week projection change detection with composite z-score normalization

---

## Core Algorithms & Mathematical Complexity

### Monte Carlo SGP (Standings Gain Points) Simulation
- Simulates N fantasy league universes (default 200, configurable up to 5,000) per roto category
- In each simulation: randomly shuffles player-to-team assignments within each roster slot type, computes team-level category totals, estimates SGP denominator as mean adjacent rank gap
- Two estimator modes: **classic** (simple mean) and **robust** (Winsorized with configurable percentiles + epsilon floors for ratio stats)
- Runs independently for hitters (up to 12 categories: R/RBI/HR/SB/AVG/OBP/SLG/OPS/H/BB/2B/TB) and pitchers (up to 8: W/K/SV/ERA/WHIP/QS/QA3/SVH)

### Linear Programming: Optimal Roster Assignment
- **Hungarian algorithm** (via `scipy.optimize.linear_sum_assignment`) for globally optimal player-to-slot assignment respecting positional eligibility constraints across 9 hitter slots (C/1B/2B/3B/SS/CI/MI/OF/UT) and 3 pitcher slots (SP/RP/P)
- Greedy fallback for environments without SciPy
- Vacancy row insertion when player pool can't fill all slots

### Two-Pass Valuation Architecture
- **Pass 1 (Average-Starter)**: For each of 20 projection years — compute positional assignments, run SGP Monte Carlo, compute per-player year values vs average starter at their best slot; pivot to Player × Year value matrix; apply discount rate and stash rules; select which players get rostered (MLB spots, bench, minors)
- **Pass 2 (Replacement-Level)**: Compute replacement baselines from the free agent pool; optionally freeze baselines from start year to prevent late-horizon inflation; recompute all per-year values as marginal SGP above replacement; compute final dynasty values as NPV of future year values with configurable discount factor

### Points Mode: Min-Cost Flow Optimization
- Flow-network-based optimal slot assignment for points-based leagues using a custom `_FlowEdge` dataclass and heapq-driven shortest path algorithm
- Per-stat scoring with 18 configurable point values

### Additional Modeling
- **Piecewise linear aging curves**: position-specific (hitters peak 29, pitchers 28, catchers 27) with exponential decay for 31+ players
- **Playing-time reliability guard**: adjusts projections based on confidence in playing time estimates
- **Replacement baseline blending**: configurable alpha between frozen and in-year baselines
- **NPV dynasty valuation**: discounted present value with optimal drop decisions (negative-value years can be stashed at configurable penalty rates)
- **Auction dollar conversion**: translates SGP-based values to dollar amounts given a configurable budget

---

## Product Features

### Projections Explorer
- Browse 20-year projections for 800+ players with filtering by name, team, position, year
- Career totals aggregation (sum/weighted-average across all projection years)
- Sortable by any column, paginated (100 rows/page), configurable column visibility
- Dynasty value overlay: calculator results merge into the projection table by player key
- CSV and XLSX export with selectable column subsets (premium)
- Week-over-week projection change tracking ("movers" — risers and fallers with composite delta scoring)

### Dynasty Calculator
- Two scoring modes: **Roto** (SGP-based) and **Points** (per-stat scoring rules)
- 30+ configurable parameters: teams (2–30), simulation count (1–5,000), horizon (1–20 years), discount rate, all roster slots, IP caps, two-way player handling, SGP estimator mode, aging adjustments, replacement blending
- Configurable roto categories (any subset of 12 hitting + 8 pitching stats)
- Preset system with save/load/delete, cloud sync via Supabase, URL-shareable via base64-encoded query params
- Quick-start onboarding: one-click standard 12-team 5x5 roto or points setup with immediate run
- Sync and async execution paths (async with job polling for large simulations)

### Player Profiles
- Modal with year-by-year stat projections and hand-drawn SVG sparkline of dynasty value trajectory
- Keyboard accessible (focus trap, Escape to close)

### Comparison Tool
- Side-by-side comparison of up to 4 players
- URL-shareable via `?compare=key1,key2,...`

### Trade Analyzer (Premium)
- Two-side player search with up to 6 players per side
- Fairness meter visualization based on dynasty value differential
- URL-shareable trade proposals

### Keeper Calculator (Premium)
- Add players with editable cost (round/dollar)
- Surplus calculation and keep/neutral/cut recommendations
- Sorted by surplus value

### Watchlist
- Per-player watch toggle, persisted locally and cloud-synced
- Watchlist panel with CSV export

---

## Monetization & Business

- **Freemium SaaS model**: free tier with capped simulations (300), premium unlocks full simulations (5,000), points mode, custom categories, export, trade analyzer, keeper calculator, cloud sync
- **Stripe integration** (live mode): monthly ($4.99) and annual ($29.99) billing via Stripe Checkout
- **Webhook-driven subscription lifecycle**: handles `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted` events
- **Supabase backend**: `subscriptions` table for billing state, `user_preferences` table (RLS-protected) for cloud sync
- **Buttondown newsletter** integration with rate limiting

---

## Infrastructure & DevOps

### Deployment
- **Railway** (Docker-based PaaS) — auto-deploys on push to `main`
- **Multi-stage Dockerfile**: Stage 1 (Node 22) builds React frontend with build-time env vars baked in; Stage 2 (Python 3.12) runs FastAPI with non-root user, health check, and production env defaults
- **Cloudflare CDN** in front of Railway
- **UptimeRobot** monitoring with HEAD request support

### CI/CD (7 GitHub Actions Jobs)
1. **Path-filtered change detection** — downstream jobs only run if relevant paths changed
2. **Backend quality**: Ruff lint (zero per-file ignores enforced) → file size guardrails → mypy (9 modules) → pip-audit (direct deps) → pytest with 75% coverage enforcement → data artifact freshness check
3. **Frontend quality**: Vitest with coverage thresholds → ESLint → Vite build → JS/CSS asset budget enforcement (400KB JS, 170KB CSS) → committed dist parity check → npm audit (direct deps) → analytics contract validation
4. **Docker build** validation
5. **E2E smoke** (Playwright Chromium)
6. **Full regression** (push to main / daily schedule)
7. **Full E2E** (manual dispatch)
- **CodeQL** security scanning (weekly, Python + JavaScript)
- **Automated data refresh** (Mon/Thu via GitHub Actions)

### Code Quality
- **~950 tests** across backend (62 files) and frontend (~130 test files)
- **Backend**: 75% coverage enforced, Ruff lint with zero per-file ignores, mypy strict on core modules, file size guardrails (1,200 lines default, 500 for hotspot dirs), pip-audit on direct dependencies
- **Frontend**: Vitest coverage thresholds (lines:30, branches:65, functions:69), ESLint zero warnings, TypeScript strict, asset budget enforcement, npm audit on direct dependencies
- **Architectural Decision Records** (ADRs) documenting key design choices
- **Ops runbooks** for production incident response (queue pressure, data ingest)

### Observability
- **Sentry** error tracking (backend + frontend) with configurable trace sampling
- **GA4** analytics with custom activation funnel tracking
- **Custom analytics debug bridge** (`window.ffAnalytics`) with CSV export and funnel visualization
- **Activation rollout framework**: gate scripts, checkpoint readouts, decision memo generation

---

## Mobile Experience
- **Responsive design** with breakpoints at 1024px, 900px, 768px (primary mobile), 560px, 360px
- **Collapsible filter drawer** on mobile with discovery pulse animation
- **Bottom sheet calculator** with drag-to-dismiss (40% threshold), body scroll lock, focus trap
- **Card view toggle** as alternative to table on small screens
- **Sticky table headers + frozen columns** with CSS scroll-snap and gradient scroll affordance indicators
- **44px minimum touch targets** throughout

---

## Key Technical Decisions & Patterns
- **No global state library** — all state managed via React hooks + localStorage + URL params + Supabase cloud
- **No external UI or chart libraries** — all UI hand-built for minimal bundle size
- **Precomputed dynasty lookup cache**: production requires a fresh precomputed file (503 if missing), preventing cold-start OOM from concurrent calculations
- **Frozen replacement baselines**: prevents late-horizon replacement value inflation in 20-year projections
- **Content-hash cache keys**: calculator results cached by SHA-256 of serialized settings, enabling instant deduplication
- **Router factory pattern**: complete decoupling of HTTP routing from business logic
- **Committed frontend dist**: CI rebuilds and diffs to catch stale artifacts, eliminates Node.js from production Docker stage

---

## Scale & Scope
- **~280 source files** (148 Python + 130 TypeScript)
- **~950 tests** with multi-tier coverage enforcement
- **20+ API endpoints** with rate limiting, caching, and async job support
- **3 completed product roadmaps** (19/19 items delivered)
- **Full TypeScript migration** completed across 9 batches (~120 files)
- **Solo-built**: product design, full-stack development, data pipeline, infrastructure, CI/CD, analytics, SEO, and monetization
- **Live production SaaS** with real Stripe billing, Supabase auth, Cloudflare CDN, Sentry monitoring

---

## Technologies Used

| Category | Technologies |
|---|---|
| **Backend** | Python 3.12, FastAPI, Uvicorn, Pandas, NumPy, SciPy, Pydantic |
| **Frontend** | React 19, TypeScript (strict), Vite, React Router v6 |
| **Testing** | pytest, Vitest, Playwright, pytest-cov |
| **Database/Auth** | Supabase (PostgreSQL + Auth + RLS), Redis (optional) |
| **Payments** | Stripe (Checkout, Webhooks, Subscriptions) |
| **Infrastructure** | Docker (multi-stage), Railway, Cloudflare CDN, GitHub Actions |
| **Monitoring** | Sentry, GA4, UptimeRobot, custom analytics |
| **Code Quality** | Ruff, mypy, ESLint, TypeScript strict, pip-audit, npm audit, CodeQL |
| **Math/Algorithms** | Monte Carlo simulation, Hungarian algorithm (linear programming), min-cost flow optimization, NPV discounting, piecewise aging curves, z-score normalization |
| **Email** | Buttondown API |
| **SEO** | Dynamic OG images (Pillow), JSON-LD schema, Google Search Console, sitemap |
