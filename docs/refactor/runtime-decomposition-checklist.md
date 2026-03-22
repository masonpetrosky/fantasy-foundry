# Runtime Decomposition Checklist

Status: Active  
Owner: Backend

## Objective
Reduce `backend/runtime.py` coupling by moving behavior into focused modules while preserving all external API contracts.

## Guardrails
- Keep FastAPI routes, request/response schemas, and query semantics unchanged.
- Keep environment variable names and runtime defaults unchanged.
- Keep wrapper compatibility tests green throughout each extraction.

## Milestone Checklist
- [x] Route registration split into dedicated `backend/api/routes/*`.
- [x] Runtime bootstrap wiring isolated in `backend/core/runtime_bootstrap.py`.
- [x] Runtime endpoint handlers isolated in `backend/core/runtime_endpoint_handlers.py`.
- [x] App/router assembly isolated in `backend/core/runtime_composition.py`, with `backend/runtime.py` consuming a typed composition artifact.
- [x] Remove transitional Ruff ignores for `backend/runtime.py` (`F821`, `F401`, `I001`) by binding aliases explicitly and preserving state-introspection imports.
- [x] Extract remaining runtime constants/config grouping into a dedicated config module (`backend/core/runtime_config.py`).
- [x] Narrow `state=sys.modules[__name__]` interfaces to typed protocol surfaces for orchestration and helper modules (`backend/core/runtime_state_protocols.py`).
- [x] Add dedicated unit coverage for alias-map contract (`required keys`, `route wiring keys`).
- [x] Move remaining shared projection utilities used only by runtime into service-owned boundaries.
- [x] Split calculator request models out of the calculator service facade to keep `backend/services/calculator/service.py` focused on orchestration.
- [x] Split projection query/profile/export orchestration out of `backend/services/projections/service.py` into focused helper modules while keeping `ProjectionService` as the stable facade.
- [x] Remove the temporary mypy ignore overrides for `backend.valuation.common_math`, `backend.valuation.replacement`, `backend.core.points_audit_review`, and `backend.dynasty_roto_values`.
- [x] Replace the common valuation year-context dict plumbing with a typed `CommonYearContext` boundary while preserving mapping-style compatibility for existing wrappers/tests.
- [x] Split the remaining `backend/dynasty_roto_values.py` helper surface into focused `backend/valuation/*` modules while keeping the legacy module as a compatibility facade.
- [x] Raise the backend fast coverage floor from 75 to 80 once the refactor stayed above the threshold.

## Acceptance Criteria
- `ruff check backend tests preprocess.py scripts` passes with no per-file ignore for `backend/runtime.py`.
- `pytest -q -m "not full_regression"` passes.
- No external API behavior change.
