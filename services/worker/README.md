# Job worker

Procrastinate application that registers tasks from all modules (parsing, pipelines, notifications, planning) and runs the periodic schedule.

| | |
| --- | --- |
| Phase | Phase 1 |
| Database access | reads and writes `ops.*` (job queue); each task uses its module's database role |
| Runs as | `lozhka-worker`, `lozhka-worker-routing` |
| Design | `04_pipelines.md section 4` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
