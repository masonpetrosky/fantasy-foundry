# ADR 002: Projections UI Container Split

## Status
Accepted

## Date
2026-02-21

## Context
`frontend/src/features/projections/container.tsx` has accumulated state management, async export logic, column visibility persistence, and rendering logic in one module. The file is hard to reason about and risky to modify.

## Decision
Refactor the projections feature into hook-based modules while preserving behavior:
- Extract stateful concerns into dedicated hooks under `frontend/src/features/projections/hooks/`.
- Keep `container.tsx` as orchestration + render composition.
- Preserve existing props, query params, and export behavior.

## Scope
This ADR covers feature-internal modularization only and does not change:
- endpoint URLs
- query parameter semantics
- UX copy and control behavior

## Consequences
Positive:
- Smaller, testable units for layout, export, and column visibility concerns
- Cleaner container file focused on rendering

Tradeoffs:
- More files and imports to navigate
- Need to maintain hook interfaces carefully

## Guardrails
- Keep user-visible behavior unchanged.
- Preserve storage keys and existing persisted preferences.
- New hooks/components in this area should stay under 500 lines.
