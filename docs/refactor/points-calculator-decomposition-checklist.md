# Points Calculator Decomposition Checklist

Status: Completed  
Owner: Backend

## Objective
Keep `backend/core/points_calculator.py` as the stable public entrypoint while splitting preparation, workload/replacement, and output concerns into focused internal modules.

## Guardrails
- Keep existing points calculator entrypoints and API behavior unchanged.
- Preserve current regression coverage for points-mode results and validation flows.
- Enforce file-size limits through `scripts/check_max_file_lines.py`.

## Milestone Checklist
- [x] Extract preparation/setup concerns into `backend/core/points_calculator_preparation.py`.
- [x] Extract workload and replacement allocation into `backend/core/points_calculator_usage.py`.
- [x] Extract valuation/output assembly into `backend/core/points_calculator_output.py`.
- [x] Keep `backend/core/points_calculator.py` as the public orchestration facade.
- [x] Add focused file-size guardrails for the decomposed points calculator modules.
- [x] Keep targeted points calculator and API validation regression tests green.

## Acceptance Criteria
- `python scripts/check_max_file_lines.py` passes.
- `pytest -q --no-cov tests/test_points_calculator.py tests/test_api_validation_value_penalties.py` passes.
- No external calculator contract change.
