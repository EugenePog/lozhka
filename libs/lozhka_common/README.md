# lozhka_common

Settings (environment variables with the `LOZHKA_` prefix), database connection helper, logging. No business logic.

| | |
| --- | --- |
| Phase | Phase 0 |
| Database access | none |
| Runs as | library |
| Design | `06_repo_deployment.md section 2` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
