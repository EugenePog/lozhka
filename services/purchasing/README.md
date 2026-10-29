# M8 · Demand forecasting and purchasing

Predicts daily demand per product, turns it into order proposals per supplier (pack sizes, minimum quantities, minimum order value, order cut-offs), prepares draft purchase orders for staff to approve, and sends them (Excel/CSV by email first, supplier API or EDI later).

| | |
| --- | --- |
| Phase | 4b (level 1 rules from day one; statistical models after 8-12 weeks of sales) |
| Database access | forecast task (role `lozhka_pipeline`): reads `gold.demand_history`, `app.demand_override`; writes `silver.forecast_run`, `silver.demand_forecast`, `silver.forecast_accuracy`. Ordering tasks (role `lozhka_purchasing`): reads `gold.reorder_suggestion`, `app.supplier*`; writes `app.purchase_order`, `app.purchase_order_line`; the only reader of `app.supplier_credential*` |
| Runs as | forecast: task in `lozhka-worker`; ordering: `lozhka-worker-purchasing` (queue `purchasing`) |
| Design | `03_modules.md` section 8 and `02_database_design.md` section 4.6 in the documentation folder |

Credential rules: secrets are encrypted before storage, the key (`SUPPLIER_SECRET_KEYS`) exists only in the environment of `lozhka-worker-purchasing`, jobs carry credential ids never secrets, nothing secret is logged, rotation is write-only from the back office. Decrypt in memory for one task, write an `ops.audit_log` row, discard.

Layout to follow: `forecast/` (baselines, statistical models, backtest), `ordering/` (net requirement, rounding, supplier choice, PO drafting), `channels/` (email file, API), `credentials.py` (the only module that decrypts), `tasks.py`.
