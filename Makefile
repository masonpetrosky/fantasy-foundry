.PHONY: test test-backend test-frontend lint lint-backend lint-frontend check

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

check: lint test
