# Architecture Boundaries

## Dependency Direction
- Routes and HTTP adapters live under `backend/api/routes/`.
- Runtime composition lives in `backend/runtime.py` and `backend/core/runtime_composition.py`.
- Orchestration lives under `backend/core/*orchestration*` and consumes service facades.
- Service facades live under `backend/services/` and may depend on `backend/core/` and `backend/valuation/`.
- Pure calculation, export, and valuation logic should stay below the service layer.

## Runtime Rules
- `backend.app:app` remains the public FastAPI entrypoint.
- `backend/runtime.py` may expose compatibility aliases, but it should not regain direct route-registration sprawl.
- New runtime wiring should be added through `RuntimeCompositionArtifacts` or adjacent builder modules, not by expanding module-level setup inline.

## Service Rules
- `backend/services/*/service.py` is the public facade for that service package.
- Request/response models, export helpers, and package-internal adapters should move into neighboring modules when the facade starts carrying multiple concerns.
- For projections specifically, keep query/filter/export helpers in sibling modules so `ProjectionService` stays focused on cache ownership and public contract delegation.
- Service package changes must preserve API contracts and existing import surfaces unless a migration is explicit.

## Refactor Guardrails
- Prefer incremental extractions with boundary tests over large rewrites.
- Keep new decomposition modules small and typed.
- Keep common valuation orchestration on the typed `CommonYearContext` boundary instead of reintroducing anonymous `dict[str, Any]` context payloads.
- Keep `backend/dynasty_roto_values.py` as a legacy facade only; projection, minor-eligibility, aggregation, and common-math helpers should live under `backend/valuation/`.
- Add tests for every new composition/helper contract so wiring behavior stays explicit.
