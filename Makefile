# Gypsi Trading Agent — local dev commands
#
# Mirrors the stages in .github/workflows/main.yml so you can run the same
# checks locally before pushing, instead of finding out on GitHub.
#
# Usage: make <target>   e.g. `make test`, `make lint`, `make up`

.PHONY: help install install-backend install-worker \
        lint lint-backend \
        test test-backend test-worker \
        up down logs init-db \
        build build-backend build-worker \
        clean

help:
	@echo "Gypsi Trading Agent — available targets:"
	@echo "  make install         Install backend + worker dependencies"
	@echo "  make lint            Run backend lint (pylint + ruff), same as CI Stage 1"
	@echo "  make test            Run backend + worker unit tests, same as CI Stage 2"
	@echo "  make test-backend    Run only backend/tests/unit"
	@echo "  make test-worker     Run only worker/tests"
	@echo "  make up              Start postgres/api/worker via docker-compose"
	@echo "  make down            Stop and remove the docker-compose stack"
	@echo "  make logs            Tail logs from the docker-compose stack"
	@echo "  make init-db         Apply the trades table schema (backend/init_db.py)"
	@echo "  make build           Build backend + worker Docker images locally"
	@echo "  make clean           Remove caches (__pycache__, .pytest_cache, coverage files)"

# ----------------------------------------------------------------------
# Install
# ----------------------------------------------------------------------

install: install-backend install-worker

install-backend:
	cd backend && pip install -r requirements.txt

install-worker:
	cd worker && pip install -r requirements.txt

# ----------------------------------------------------------------------
# Lint — mirrors CI Stage 1 (Build & Lint)
# ----------------------------------------------------------------------

lint: lint-backend

lint-backend:
	cd backend && pip install pylint ruff
	cd backend && pylint --fail-under=8.0 **/*.py || true
	cd backend && ruff check . || true

# ----------------------------------------------------------------------
# Test — mirrors CI Stage 2 (Unit Tests)
# ----------------------------------------------------------------------

test: test-backend test-worker

test-backend:
	cd backend && mkdir -p tests/unit
	cd backend && touch tests/unit/__init__.py
	cd backend && pytest tests/unit --cov=. --cov-report=xml --cov-report=term || [ $$? -eq 5 ]

test-worker:
	cd worker && pytest tests -v

# ----------------------------------------------------------------------
# Local stack (postgres + api + worker via docker-compose.yml)
# ----------------------------------------------------------------------

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

init-db:
	cd backend && python init_db.py

# ----------------------------------------------------------------------
# Build — mirrors CI Stage 3 (Docker image builds), local-only (no push)
# ----------------------------------------------------------------------

build: build-backend build-worker

build-backend:
	docker build -t gypsi-backend:local -f backend/Dockerfile backend

build-worker:
	docker build -t gypsi-worker:local -f worker/Dockerfile worker

# ----------------------------------------------------------------------
# Cleanup
# ----------------------------------------------------------------------

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -f backend/coverage.xml