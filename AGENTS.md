# AGENTS.md

This is the canonical agent instruction file for Fantasy Foundry. If another tool-specific instruction file exists (for example `CLAUDE.md`), keep it as a pointer or a minimal delta only. If commands, test markers, setup requirements, or generated-artifact behavior change, update this file in the same change.

## Repo Summary

Fantasy Foundry is a dynasty fantasy baseball application with:
- FastAPI backend services in `backend/`
- pytest coverage in `tests/`
- React + Vite frontend in `frontend/`
- validation, data, and smoke scripts in `scripts/`

## Toolchain And Runtime Facts

- Python version: `3.12` from `.python-version`
- Node.js version: `22` from `.nvmrc`
- The backend serves built frontend assets from `frontend/dist` in normal app mode.
- Docker is expected to work from WSL through Docker Desktop.
- Use `./scripts/smoke_docker.sh 18000` for production-parity Docker verification instead of ad hoc container commands.

## Where To Work

- Backend app wiring and router registration: `backend/app.py`, `backend/runtime.py`, `backend/api/app_factory.py`, `backend/api/routes/`
- Backend config and shared orchestration: `backend/core/settings.py`, `backend/core/`, `backend/services/`, `backend/valuation/`
- Frontend app entrypoints: `frontend/src/main.tsx`, `frontend/src/features/projections/`, `frontend/src/hooks/useProjectionsData.ts`, `frontend/src/app_state_storage.ts`
- Tests: `tests/`
- Guardrails and helper scripts: `scripts/`

## Common Edit Paths

- New API route:
  - add or extend a router builder in `backend/api/routes/`
  - wire it through `backend/runtime.py` router config and shared endpoint wiring
  - add targeted API tests in `tests/`
- New projection column:
  - update the backend query/serialization path
  - update `frontend/src/features/projections/hooks/useProjectionColumnVisibility.ts`
  - preserve existing projections query semantics for filters, sorting, and exports
- New calculator setting:
  - update the relevant `frontend/src/dynasty_calculator*.tsx` UI
  - update persistence and share-link handling in `frontend/src/app_state_storage.ts`
  - update the backend request schema and valuation handling

## Validation Workflow

Prefer the smallest relevant validation first, then widen only as needed.

| Scenario | Command |
|---|---|
| Backend targeted check after a small backend fix | targeted `pytest` selection when obvious |
| Default backend regression lane | `make test-backend-fast` |
| Full backend suite when coverage or wider regressions matter | `pytest -q` |
| Frontend targeted check after a small frontend fix | targeted `cd frontend && npm test -- <pattern>` when obvious |
| Default frontend suite | `cd frontend && npm test` |
| Backend + frontend lint plus generated-artifact guard | `make lint` |
| Backend type-check | `make typecheck` |
| Frontend type-check | `cd frontend && npm run typecheck` |
| Security scan | `make security` |
| Full local quality gate | `make check` |
| Docker smoke | `./scripts/smoke_docker.sh 18000` |
| Generated artifact guard | `./scripts/check_generated_artifacts_untracked.sh` |
| OS metadata artifact scrub | `./scripts/check_os_metadata_artifacts.sh` |
| Frontend dist freshness guard | `./scripts/check_frontend_dist.sh` |

Useful pytest markers from `pytest.ini`:
- `full_regression`: excluded from `make test-backend-fast`
- `e2e`: browser tests that require Playwright and local app startup
- `integration`, `slow`, `valuation`: focused backend subsets

## Working Rules

- Prefer the smallest correct fix.
- Do not make unrelated edits.
- Before changing code, identify the first actual failing defect.
- After a fix, rerun only the smallest relevant validation command first.
- When validation is green, stop and report results before making further changes.
- Reuse existing repo commands and scripts instead of inventing new ones.
- Prefer updating existing files over adding new abstractions unless clearly necessary.
- Flag behavior changes explicitly.

## Repo-Specific Boundaries

- Keep `frontend/src/features/projections/container.tsx` focused on orchestration and rendering; place stateful logic in hooks under `frontend/src/features/projections/hooks/` and reusable presentation in `frontend/src/features/projections/components/`.
- Preserve local storage keys used by layout, column visibility, filter presets, and calculator/share-link state.
- Route backend env/config changes through `backend/core/settings.py`.
- Keep frontend env changes aligned with `frontend/.env.example`.
- Do not add secrets to tracked files.

## Generated And Sensitive Files

- Do not hand-edit `frontend/dist/`; rebuild it from `frontend/` when the task requires updated built assets.
- Do not hand-edit projection data files under `data/` unless the task is explicitly about data refresh or validation.
- When default dynasty-calculation behavior changes, regenerate `data/dynasty_lookup.json`; the precomputed cache now also carries a default-methodology fingerprint and should be treated as stale when either the projection data version or methodology fingerprint changes.
- Coverage outputs and caches must remain untracked, including `.coverage`, `coverage.xml`, `htmlcov/`, `frontend/coverage/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, and `.ruff_cache/`.
- OS metadata artifacts such as `*:Zone.Identifier` must not be present anywhere in the repo or built assets.
- Repo-wide searches should rely on `.rgignore` defaults unless you intentionally need `rg --no-ignore`.

## Definition Of Done

A task is done when:
1. the requested change is implemented,
2. the smallest relevant validation commands pass,
3. no unrelated files were changed,
4. any behavior changes, follow-up risks, or warnings are clearly reported.
