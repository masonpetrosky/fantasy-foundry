# Projections Container Decomposition Checklist

Status: Active  
Owner: Frontend

## Objective
Continue reducing `frontend/src/features/projections/container.jsx` to orchestration/render composition while preserving current behavior.

## Guardrails
- Keep endpoint URLs and query parameter semantics unchanged.
- Keep persisted storage keys unchanged.
- Keep current UX controls, defaults, and copy unchanged unless explicitly scoped.

## Milestone Checklist
- [x] Core view state moved to `frontend/src/features/projections/view_state.js`.
- [x] Hook module surface established under `frontend/src/features/projections/hooks/`.
- [x] Component module surface established under `frontend/src/features/projections/components/`.
- [x] Extract remaining export pipeline state/actions into hook-only module.
- [x] Extract remaining watchlist/comparison overlay wiring into dedicated composition hooks.
- [x] Limit container responsibilities to:
  - screen-level orchestration
  - composition of hooks/components
  - top-level side-effect coordination
- [x] Add focused tests for each extracted hook:
  - column visibility persistence
  - layout state behavior
  - filter preset behavior
  - export request assembly

## Acceptance Criteria
- `cd frontend && npm test` passes.
- `cd frontend && npm run lint` passes.
- Existing projections user flows remain behaviorally equivalent.
