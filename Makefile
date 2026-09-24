# neutrino-database — developer Makefile (slim, inaugural version).
#
# Mirrors the relevant subset of neutrino-gateway/Makefile. Full
# lint/format/CI parity is tracked as task #29 — left out here so this
# inaugural test-infra commit stays focused on what's required to run
# pytest. Uses the same conda-env-per-repo convention from
# `our-engineering-standards.md` §8.
#
# Quick start:
#   make install              # creates conda env + installs deps
#   conda activate $(ENV_NAME)
#   make setup-test-db        # one-time: creates the test DB
#   make test                 # runs pytest
#
# CI-friendly targets (run inside an already-activated env):
#   make install-deps         # pip install only
#   make test                 # pytest
#
# Test database management requires `psql` / `createdb` / `dropdb` on
# PATH and PGPASSWORD set in the environment.

.PHONY: help install install-deps test test-verbose \
        setup-test-db drop-test-db recreate-test-db clean \
        db-upgrade backfill-authz-store migrate-fga migrate

ENV_NAME       := neutrino-db
PYTHON_VERSION := 3.12

# OpenFGA endpoint for the FGA model migrator. Override via env in deploy.
OPENFGA_API_URL ?= http://localhost:8080

# Test database (used by pytest). Override via env if your local
# Postgres differs.
TEST_DB_NAME   ?= neutrino_database_test_db
TEST_DB_HOST   ?= localhost
TEST_DB_PORT   ?= 5432
TEST_DB_USER   ?= postgres

help:
	@echo "Setup:"
	@echo "  install              Create conda env '$(ENV_NAME)' and install all deps"
	@echo "  install-deps         pip install runtime + dev deps (run inside activated env)"
	@echo ""
	@echo "Test database (real Postgres):"
	@echo "  setup-test-db        Create '$(TEST_DB_NAME)' if it doesn't exist (needs PGPASSWORD)"
	@echo "  drop-test-db         Drop '$(TEST_DB_NAME)' (needs PGPASSWORD)"
	@echo "  recreate-test-db     Drop + setup (fresh schema)"
	@echo ""
	@echo "Test:"
	@echo "  test                 Run pytest (needs TEST_DATABASE_URL set)"
	@echo "  test-verbose         Run pytest -v"
	@echo "  clean                Remove __pycache__ + .pytest_cache"
	@echo ""
	@echo "Migrations (run on deploy, in this order):"
	@echo "  db-upgrade           alembic upgrade head (Postgres schema)"
	@echo "  backfill-authz-store Map pre-existing OpenFGA doc-ACL stores onto workspace_authz_store"
	@echo "  migrate-fga          Converge every OpenFGA store to the canonical model"
	@echo "  migrate              the full deploy step"

install:
	conda create -n $(ENV_NAME) python=$(PYTHON_VERSION) -y
	conda run -n $(ENV_NAME) --no-capture-output pip install -r requirements.txt -r requirements-dev.txt
	conda run -n $(ENV_NAME) --no-capture-output pip install -e .
	@echo ""
	@echo "Conda env '$(ENV_NAME)' is ready. Activate it:"
	@echo "  conda activate $(ENV_NAME)"

install-deps:
	pip install -r requirements.txt -r requirements-dev.txt

test:
	pytest tests/

test-verbose:
	pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true

# ------------------------------------------------------------------
# Deploy-time migrations. neutrino_database owns ALL schema migrations —
# Postgres (alembic) and OpenFGA. Run `make migrate` after deploying new
# code, BEFORE the services start serving. Both steps are idempotent.
#
#   DATABASE_URL    — Postgres, for alembic (db-upgrade)
#   OPENFGA_API_URL — OpenFGA endpoint, for the FGA migrator (migrate-fga)
# ------------------------------------------------------------------

db-upgrade:
	alembic upgrade head

# Idempotent — safe on every deploy; an already-mapped workspace is left alone.
backfill-authz-store:
	OPENFGA_API_URL=$(OPENFGA_API_URL) python -m neutrino_database.fga.backfill_workspace_authz_store

migrate-fga:
	OPENFGA_API_URL=$(OPENFGA_API_URL) python -m neutrino_database.fga.migrate

migrate: db-upgrade backfill-authz-store migrate-fga

# ------------------------------------------------------------------
# Test-database management. Mirrors gateway/Makefile.
# ------------------------------------------------------------------

setup-test-db:
	@echo "Ensuring database '$(TEST_DB_NAME)' exists on $(TEST_DB_HOST):$(TEST_DB_PORT)..."
	@psql -h $(TEST_DB_HOST) -p $(TEST_DB_PORT) -U $(TEST_DB_USER) -d postgres -tc \
		"SELECT 1 FROM pg_database WHERE datname='$(TEST_DB_NAME)'" | grep -q 1 \
		|| createdb -h $(TEST_DB_HOST) -p $(TEST_DB_PORT) -U $(TEST_DB_USER) $(TEST_DB_NAME)
	@echo "✓ Database '$(TEST_DB_NAME)' is ready."
	@echo "  Schema is created automatically by the pytest session-scope fixture."

drop-test-db:
	@echo "Dropping database '$(TEST_DB_NAME)'..."
	@dropdb -h $(TEST_DB_HOST) -p $(TEST_DB_PORT) -U $(TEST_DB_USER) --if-exists $(TEST_DB_NAME)
	@echo "✓ Dropped (if it existed)."

recreate-test-db: drop-test-db setup-test-db
