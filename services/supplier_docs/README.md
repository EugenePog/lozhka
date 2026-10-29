# M2 · Supplier document processing

Register, extract, parse, match, validate and apply manual fixes for supplier Excel/CSV files. Layouts are described by `app.supplier_import_profile` rows, not code. Put anonymised real files in `tests/fixtures/`.

| | |
| --- | --- |
| Phase | Phase 1 |
| Database access | reads `app.supplier_import_profile`, `app.supplier_product`, `app.delivery_line_fix`; writes `bronze.supplier_*`, `silver.supplier_delivery*` |
| Runs as | tasks in `lozhka-worker` |
| Design | `03_modules.md section 1` in the documentation folder |

Rules: import only from `libs/`, never from another service. Document new tables touched and new settings here.
