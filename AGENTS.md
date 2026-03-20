# AGENTS.md

## Repository overview

Fantasy Foundry is a dynasty fantasy baseball application with:
- backend Python services in `backend/`
- tests in `tests/`
- frontend app in `frontend/`
- helper and validation scripts in `scripts/`

## Canonical validation commands

Use the repo-declared commands below instead of guessing alternatives:

- Lint backend:
  - `ruff check backend tests preprocess.py scripts`
- Lint frontend:
  - `cd frontend && npm run lint`
- Backend tests:
  - `pytest -q`
- Frontend tests:
  - `cd frontend && npm test`
- Type-check:
  - `make typecheck`
  - `cd frontend && npm run typecheck`
- Build:
  - `make docker-build`
  - `cd frontend && npm run build`
- Docker smoke test:
  - `./scripts/smoke_docker.sh 18000`

## Working rules

- Prefer the smallest correct fix.
- Do not make unrelated edits.
- Before changing code, identify the first actual failing defect.
- After a fix, rerun only the smallest relevant validation command first.
- When validation is green, stop and report results before making further changes.
- Reuse existing repo commands and scripts instead of inventing new ones.
- Prefer updating existing files over adding new abstractions unless clearly necessary.

## Docker and local environment

- Docker is expected to work from WSL through Docker Desktop.
- Use the smoke script for production-parity Docker verification instead of ad hoc container commands when possible.

## Definition of done

A task is done when:
1. the requested code change is implemented,
2. the smallest relevant validation commands pass,
3. no unrelated files were changed,
4. any follow-up risks or warnings are clearly reported.

## Review guidelines

- Keep fixes minimal and easy to review.
- Flag behavior changes explicitly.
- Do not add secrets to tracked files.
