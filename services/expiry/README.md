# M5 · Expiry tracking

Daily scan of `gold.expiry_watch`, severity grouping, digest messages through `lozhka_notify` (email, Telegram), de-duplicated by threshold.

| | |
| --- | --- |
| Phase | Phase 4 |
| Database access | reads `gold.expiry_watch`, `app.expiry_rule`, `app.notification_recipient`; writes `ops.notification` |
| Runs as | scheduled tasks in `lozhka-worker` |
| Design | `03_modules.md section 5` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
