.PHONY: guard-generated-artifacts test test-backend test-backend-fast test-backend-full-regression test-frontend lint lint-backend lint-frontend typecheck check

guard-generated-artifacts:
	./scripts/check_generated_artifacts_untracked.sh

test: test-backend test-frontend

test-backend:
	pytest -q

test-backend-fast:
	pytest -q -m "not full_regression"

test-backend-full-regression:
	pytest -q -m "full_regression" --no-cov

test-frontend:
	cd frontend && npm test

lint: guard-generated-artifacts lint-backend lint-frontend

lint-backend:
	python scripts/check_ruff_per_file_ignores.py
	ruff check backend tests preprocess.py scripts

lint-frontend:
	cd frontend && npm run lint

typecheck:
	mypy backend/api/middleware.py backend/core/settings.py backend/core/networking.py backend/core/rate_limit.py backend/core/result_cache.py backend/core/jobs.py backend/core/data_refresh.py

check: lint test-backend-fast test-frontend typecheck
