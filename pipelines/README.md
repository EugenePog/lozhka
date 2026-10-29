# M7 · Data pipelines

`dbt/` holds the SQL models (Silver and Gold), tests, macros and seeds. `src/lozhka_pipelines/` holds the Python loaders and the task wiring that runs dbt with selectors.

| | |
| --- | --- |
| Phase | Phase 1 onward |
| Database access | reads `app.*`, `bronze.*`; writes `bronze.*`, `silver.*`, `gold.*`, `ops.pipeline_run` |
| Runs as | tasks in `lozhka-worker` |
| Design | `04_pipelines.md` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
