.PHONY: guard-generated-artifacts scrub-os-metadata test test-backend test-backend-quick test-backend-fast test-backend-fast-cov test-backend-full-regression test-frontend lint lint-backend lint-frontend typecheck security check format clean docker-build dev help

guard-generated-artifacts:
	./scripts/check_generated_artifacts_untracked.sh

scrub-os-metadata:
	./scripts/check_os_metadata_artifacts.sh

test: test-backend test-frontend

test-backend:
	pytest -q

test-backend-quick:
	pytest -q --no-cov -m "not slow and not integration and not valuation and not full_regression"

test-backend-fast:
	pytest -q --no-cov -m "not full_regression"

test-backend-fast-cov:
	pytest -q -m "not full_regression" --cov=backend --cov-branch --cov-report=term-missing --cov-fail-under=75

test-backend-full-regression:
	pytest -q -m "full_regression" --no-cov

test-frontend:
	cd frontend && npm test

lint: guard-generated-artifacts scrub-os-metadata lint-backend lint-frontend

lint-backend:
	python scripts/check_ruff_per_file_ignores.py
	ruff check backend tests preprocess.py scripts

lint-frontend:
	cd frontend && npm run lint

typecheck:
	mypy backend

security:
	bandit -r backend -ll --quiet

check: lint test-backend-fast-cov test-frontend typecheck security
	python scripts/check_max_file_lines.py
	cd frontend && npm run typecheck
	./scripts/check_frontend_asset_budget.sh
	./scripts/check_frontend_dist.sh

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

dev:
	docker compose -f docker-compose.dev.yml up --build

help:
	@echo "Available targets:"
	@echo "  make test                  Run all tests (backend + frontend)"
	@echo "  make test-backend          Backend full suite"
	@echo "  make test-backend-quick    Backend quick lane (skip slow/integration/valuation/full_regression)"
	@echo "  make test-backend-fast     Backend default fast lane (skip full_regression)"
	@echo "  make test-backend-fast-cov Backend fast lane with coverage"
	@echo "  make test-frontend         Frontend tests"
	@echo "  make lint                  Run all linters + artifact guards"
	@echo "  make typecheck             Run mypy type checks"
	@echo "  make security              Run Bandit SAST scan"
	@echo "  make check                 Local CI-parity quality gate"
	@echo "  make format                Auto-format backend + frontend"
	@echo "  make clean                 Remove caches and build artifacts"
	@echo "  make docker-build          Build Docker image"
	@echo "  make dev                   Start dev environment (Docker Compose)"
	@echo "  make help                  Show this help"
