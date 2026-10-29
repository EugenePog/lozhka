# A · Public API

Django project with Django Ninja endpoints under `/api/v1`, django-allauth (headless) for login. Owns every model in the `app` schema and their Django migrations.

| | |
| --- | --- |
| Phase | Phase 1 (models) and Phase 2 (endpoints) |
| Database access | reads `gold.*`; reads and writes `app.*`; inserts raw webhooks into `bronze.payment_event` |
| Runs as | `lozhka-api` |
| Design | `03_modules.md section 2` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
