# NavidroFM developer commands. Run `make` (or `make help`) for a summary.
#
# Everything runs against the local virtualenv in ./venv, which is what the
# Docker image simulates. No Docker required for linting/testing.

PYTHON ?= venv/bin/python
PIP ?= $(PYTHON) -m pip
IMAGE ?= aaronp18/navidrofm
TAG ?= dev
TYPE ?= csv

.DEFAULT_GOAL := help
.PHONY: help venv install install-dev lint format test test-cov check run \
        docker-build docker-build-multi docker-up docker-down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

venv: ## Create the local virtualenv in ./venv
	python3 -m venv venv

install: venv ## Install runtime dependencies into ./venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

install-dev: venv ## Install runtime + dev (lint/test) dependencies into ./venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt

lint: ## Lint the code with ruff
	$(PYTHON) -m ruff check .

format: ## Auto-fix lint issues and reformat the code
	$(PYTHON) -m ruff check . --fix
	$(PYTHON) -m ruff format .

test: ## Run the unit test suite
	$(PYTHON) -m pytest

test-cov: ## Run tests with coverage for src/
	$(PYTHON) -m pytest --cov=src --cov-report=term-missing

check: lint test ## The full gate (what CI runs)

run: ## Run locally, e.g. `make run TYPE=csv` (sources .env when present)
	@set -a; [ -f .env ] && . ./.env; set +a; $(PYTHON) -u src/app.py $(TYPE)

docker-build: ## Build the Docker image for the local platform
	docker build -t $(IMAGE):$(TAG) .

docker-build-multi: ## Build amd64 + arm64 images (no push)
	docker buildx build --platform linux/amd64,linux/arm64 -t $(IMAGE):$(TAG) .

docker-up: ## Build and start the stack with docker compose
	docker compose up -d --build

docker-down: ## Stop the docker compose stack
	docker compose down

clean: ## Remove caches and test artifacts
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find src tests -type d -name __pycache__ -exec rm -rf {} +
