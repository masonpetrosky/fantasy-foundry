.PHONY: test test-backend test-frontend lint lint-backend lint-frontend typecheck check

test: test-backend test-frontend

test-backend:
	pytest -q

test-frontend:
	cd frontend && npm test

lint: lint-backend lint-frontend

lint-backend:
	ruff check backend tests preprocess.py scripts

lint-frontend:
	cd frontend && npm run lint

typecheck:
	mypy backend/api/middleware.py backend/core/settings.py backend/core/networking.py backend/core/rate_limit.py backend/core/result_cache.py backend/core/jobs.py backend/core/data_refresh.py

check: lint test typecheck
