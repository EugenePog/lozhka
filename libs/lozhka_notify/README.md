# lozhka_notify

Notification channels with one small interface (`Channel.send`). Email and Telegram implementations arrive with the expiry module.

| | |
| --- | --- |
| Phase | Phase 4 (interfaces now) |
| Database access | writes `ops.notification` through the caller |
| Runs as | library |
| Design | `03_modules.md section 5` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
