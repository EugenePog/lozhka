PG_PORT ?= 5433
# LOZHKA developer commands. Requires: uv, pnpm, dbmate, Docker (or a local PostgreSQL).
# Connection for migrations is the owner role: set LOZHKA_DATABASE_URL_OWNER in .env (loaded below).
-include .env
export

DB_URL ?= $(LOZHKA_DATABASE_URL_OWNER)

.PHONY: help setup db-up db-migrate db-rollback db-attach-cdc db-grants db-constraints api-migrate \
	pipelines-run pipelines-rebuild worker lint test

help:
	@grep -E '^[a-zA-Z_-]+:' Makefile | cut -d: -f1 | sort

setup:  ## install Python and JavaScript dependencies
	uv sync --all-packages
	pnpm install

db-up:  ## local PostgreSQL in Docker
	docker run -d --name lozhka-pg -e POSTGRES_PASSWORD=change-me -e POSTGRES_USER=lozhka_owner \
		-e POSTGRES_DB=lozhka -p $(PG_PORT):5432 postgres:16

db-migrate:  ## roles, schemas, bronze, silver (python tables), ops, change capture
	dbmate --url "$(DB_URL)" --migrations-dir db/migrations --no-dump-schema up

db-rollback:  ## undo the last migration
	dbmate --url "$(DB_URL)" --migrations-dir db/migrations --no-dump-schema rollback

db-attach-cdc:  ## attach change-capture triggers to every app table (run after Django migrate)
	psql "$(DB_URL)" -c "select bronze.attach_change_capture_all('app')"

db-grants:  ## privileges on app tables for the other roles (run after Django migrate)
	psql "$(DB_URL)" -f db/scripts/grants_after_app.sql

db-constraints:  ## rule: active delivery templates cover 24 hours (run after Django migrate)
	psql "$(DB_URL)" -f db/scripts/constraints_after_app.sql

api-migrate:  ## Django migrations for the app schema (available once services/api has its Django project)
	@echo "Phase 1: cd services/api/src && ../../../.venv/bin/python manage.py migrate"

db-gold-views:  ## stage-1 Gold read models as plain SQL views (until dbt takes over)
	psql "$$LOZHKA_DATABASE_URL_OWNER" -f db/scripts/gold_bootstrap_views.sql

seed:  ## essential reference data (natural-key CSVs in db/seeds/essential)
	cd services/api/src && ../../../.venv/bin/python manage.py seed --set essential

seed-demo:  ## essential + demo catalogue, stock, customers, orders (idempotent)
	cd services/api/src && ../../../.venv/bin/python manage.py seed --set demo

api-run:  ## public API on :8010
	cd services/api/src && DJANGO_SETTINGS_MODULE=config.settings.public ../../../.venv/bin/python -m uvicorn config.asgi:application --port 8010 --reload

backoffice-run:  ## staff console on :8011
	cd services/api/src && DJANGO_SETTINGS_MODULE=config.settings.backoffice ../../../.venv/bin/python manage.py runserver 8011

web-run:  ## customer site on :3010
	pnpm --filter @lozhka/web dev

openapi-refresh:  ## re-export the public OpenAPI schema and regenerate the typed client
	pnpm --filter @lozhka/api-client refresh

e2e:  ## browser smoke test of the customer site (API and web must be running)
	cd apps/web && node e2e/smoke.mjs

pipelines-run:  ## dbt build (Silver and Gold)
	cd pipelines/dbt && uv run --project ../.. dbt build --profiles-dir .

pipelines-rebuild:  ## full refresh of every dbt model
	cd pipelines/dbt && uv run --project ../.. dbt build --full-refresh --profiles-dir .

worker:  ## job worker in the foreground (available once services/worker has its app)
	@echo "Phase 1: uv run procrastinate --app=lozhka_worker.app.app worker"

lint:
	uv run ruff check .

test:
	uv run pytest
