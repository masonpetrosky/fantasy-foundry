# ADR 003: Points Calculator Decomposition

## Status
Accepted

## Date
2026-03-22

## Context
`backend/core/points_calculator.py` had grown into a large mixed-responsibility module covering input shaping, replacement-level assignment, year-by-year usage math, and final valuation/output assembly. That size made the file trip the repository line-count guardrail and raised regression risk for points-mode changes.

## Decision
Keep `backend/core/points_calculator.py` as the stable public facade and move internal stages behind it:
- `backend/core/points_calculator_preparation.py` for context/setup and survivor-pool preparation
- `backend/core/points_calculator_usage.py` for workload and replacement allocation by year
- `backend/core/points_calculator_output.py` for valuation normalization, aggregation, and output assembly

## Scope
This ADR changes internal module boundaries only. It does not change:
- public calculator entrypoints
- API request/response contracts
- calculator result semantics

## Consequences
Positive:
- Smaller change surfaces for points-mode work
- Clearer stage boundaries for tests and future refactors
- Explicit line-count guardrails for the new module set

Tradeoffs:
- More imports across the points-calculator path
- Transitional compatibility imports for direct-script execution

## Guardrails
- Preserve the public facade in `backend/core/points_calculator.py`.
- Keep behavior identical for existing points calculator tests and API flows.
- Keep the facade, preparation, and usage modules under 500 lines, with the output module capped separately until it is split further.
