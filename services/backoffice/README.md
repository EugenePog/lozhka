# B · Staff console (back office)

Django app (admin customisation plus purpose-built screens): products and passports, supplier upload and review, receiving, picking, route approval, content, settings. Runs as a separate process (own settings, secret key, session cookie, host name `office.*`, port 8011, no public access). Role-based: `admin` (settings, suppliers, product passports), `operator` (Orders to confirm, Orders ready for delivery, Deliveries), `storekeeper` (incoming deliveries, manual fixes of amounts). See docs 03 section 2 and 06 section 7.1.

| | |
| --- | --- |
| Phase | Phase 1 |
| Database access | reads and writes `app.*`; reads `silver.*`, `gold.*`; enqueues jobs in `ops` |
| Runs as | `lozhka-backoffice` |
| Design | `03_modules.md section 2` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.

Tables touched (v0.4): `app.delivery_template` (admin edits), `app.delivery`, `app.delivery_stop`, `app.delivery_return`, `app.return_reason`, `app.customer_flag`, `app.order_confirmation_attempt` (operator call log), order `payment_method`/`confirmed_at`/`cancel_reason`.
Every staff view needs a permission; a test must fail when a staff URL has none.
