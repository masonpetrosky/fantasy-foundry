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
- [x] Remove transitional Ruff ignores for `backend/runtime.py` (`F821`, `F401`, `I001`) by binding aliases explicitly and preserving state-introspection imports.
- [ ] Extract remaining runtime constants/config grouping into a dedicated config module.
- [ ] Narrow `state=sys.modules[__name__]` interfaces to typed protocol surfaces for orchestration and infra helpers.
- [ ] Add dedicated unit coverage for alias-map contract (`required keys`, `route wiring keys`).
- [ ] Move remaining shared projection utilities used only by runtime into service-owned boundaries.

## Acceptance Criteria
- `ruff check backend tests preprocess.py scripts` passes with no per-file ignore for `backend/runtime.py`.
- `pytest -q -m "not full_regression"` passes.
- No external API behavior change.

