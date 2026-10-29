# M6 · Reporting

Scheduled exports (weekly owners' report, VAT summary, recall list). Interactive dashboards use Metabase on the `gold` schema through the read-only role.

| | |
| --- | --- |
| Phase | Phase 4 |
| Database access | reads `gold.*` only |
| Runs as | scheduled tasks in `lozhka-worker` |
| Design | `03_modules.md section 6` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
