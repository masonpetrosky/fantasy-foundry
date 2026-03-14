.PHONY: guard-generated-artifacts test test-backend test-backend-fast test-backend-full-regression test-frontend lint lint-backend lint-frontend typecheck security check format clean docker-build help

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
	mypy backend/api/middleware.py backend/api/models.py backend/api/error_handlers.py backend/api/routes/status.py backend/core/settings.py backend/core/networking.py backend/core/rate_limit.py backend/core/result_cache.py backend/core/jobs.py backend/core/data_refresh.py backend/core/structured_logging.py backend/core/runtime_config.py backend/core/runtime_state_protocols.py backend/core/exceptions.py backend/core/status_orchestration.py backend/valuation/models.py backend/valuation/positions.py backend/valuation/assignment.py backend/valuation/team_stats.py backend/valuation/credit_guards.py backend/valuation/sgp_math.py backend/valuation/projection_identity.py backend/valuation/projection_averaging.py backend/valuation/minor_eligibility.py backend/valuation/xlsx_formatting.py backend/valuation/cli.py backend/valuation/cli_args.py backend/services/calculator/service.py backend/services/projections/service.py backend/services/projections/delta.py backend/services/projections/runtime_boundaries.py backend/services/valuation/service.py backend/services/billing.py backend/services/fantrax/service.py backend/services/fantrax/models.py backend/services/fantrax/mapping.py

security:
	bandit -r backend -ll --quiet

check: lint test-backend-fast test-frontend typecheck

format:
	ruff format backend tests preprocess.py scripts
	ruff check --fix backend tests preprocess.py scripts
	cd frontend && npx eslint src --fix --max-warnings=0

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/node_modules/.vite 2>/dev/null || true

docker-build:
	docker build -t fantasy-foundry .

help:
	@echo "Available targets:"
	@echo "  make test                  Run all tests (backend + frontend)"
	@echo "  make test-backend          Backend tests with coverage"
	@echo "  make test-backend-fast     Backend tests (skip full_regression)"
	@echo "  make test-frontend         Frontend tests"
	@echo "  make lint                  Run all linters"
	@echo "  make typecheck             Run mypy type checks"
	@echo "  make security              Run Bandit SAST scan"
	@echo "  make check                 All quality gates"
	@echo "  make format                Auto-format backend + frontend"
	@echo "  make clean                 Remove caches and build artifacts"
	@echo "  make docker-build          Build Docker image"
	@echo "  make help                  Show this help"
