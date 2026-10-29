# LOZHKA

Online shop platform for Russian and Eastern European groceries in the Netherlands: database with medallion layers, supplier-document processing, web site and mobile apps, route planning, expiry tracking, reporting and the pipelines connecting them. Mono-repo, built and run by one person.

Architecture and design documents are in the project documentation folder (`NL_online_ethnic_products_food_store/architecture/`), not in this repository. Start with its `README.md`.

## Module map

| Module | Folder | Runs as (pm2) |
| --- | --- | --- |
| M1 Database | `db/` | PostgreSQL (system service) |
| M2 Supplier documents | `services/supplier_docs/` | task in `lozhka-worker` |
| M3 Web site | `apps/web/` | `lozhka-web` |
| M3 Mobile app | `apps/mobile/` | store builds |
| A Public API | `services/api/` | `lozhka-api` |
| B Back office | `services/backoffice/` | `lozhka-backoffice` |
| M4 Route planner | `services/routing/` | `lozhka-worker-routing` |
| M5 Expiry and notifications | `services/expiry/`, `libs/lozhka_notify/` | task in `lozhka-worker` |
| M8 Forecasting and purchasing | `services/purchasing/` | forecast in `lozhka-worker`, ordering in `lozhka-worker-purchasing` |
| M6 Reporting | `services/reporting/` | task in `lozhka-worker`, Metabase |
| M7 Pipelines | `pipelines/` | tasks in `lozhka-worker` |
| Shared | `libs/`, `packages/`, `infra/` | n/a |

## Status

Phase 0 scaffold: database migrations, workspace configuration, module folders with READMEs. No application code yet (see roadmap, document 07).

## Quick start

```
cp .env.example .env        # fill in passwords
make setup                  # uv sync --all-packages, pnpm install
make db-up db-migrate       # local PostgreSQL + roles, schemas, bronze, silver, ops
make test
```

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, pnpm, [dbmate](https://github.com/amacneil/dbmate), Docker (or a local PostgreSQL 16).

## Rules

* Services import only from `libs/`, never from each other; modules cooperate through the database and the job queue.
* Only `services/api` defines `app` models. Only pipelines write to `bronze`, `silver`, `gold`.
* Secrets only in environment variables.
