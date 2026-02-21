# ADR 001: Backend Runtime Decomposition

## Status
Accepted

## Date
2026-02-21

## Context
`backend/runtime.py` and `backend/dynasty_roto_values.py` are oversized legacy modules. They currently mix orchestration, adapters, and utility concerns in single files, which slows changes and increases regression risk.

## Decision
Adopt an incremental decomposition strategy that preserves external behavior:
- Keep the public FastAPI entrypoint (`backend/runtime.py`) stable.
- Extract internal utility/adaptor concerns into focused modules (for example `backend/valuation/cli_args.py` and runtime helper modules) without changing API contracts.
- Keep legacy files as temporary compatibility shells while moving logic behind stable interfaces.

## Scope
This ADR governs internal module boundaries only. It does not change:
- API routes/paths
- Request/response payload contracts
- Runtime environment variable names

## Consequences
Positive:
- Lower cognitive load per module
- Easier targeted test additions
- Safer future refactors because concerns are isolated

Tradeoffs:
- Transitional period with mixed old/new structure
- Extra imports/indirection while decomposition is in progress

## Guardrails
- No externally visible behavior changes during decomposition PRs.
- Existing tests must pass before and after each extraction step.
- New modules in decomposition areas should stay under 500 lines.
