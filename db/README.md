# M1 · Database

PostgreSQL 16+, one database `lozhka`, schemas `app`, `bronze`, `silver`, `gold`, `ops`. Design: `02_database_design.md` in the documentation folder.

| Path | Content |
| --- | --- |
| `migrations/` | dbmate SQL files: roles and schemas, bronze, silver tables written by Python, ops, change capture |
| `scripts/constraints_after_app.sql` | Rule that active delivery templates cover 24 hours without gap or overlap; run after Django migrations (`make db-constraints`) |
| `scripts/grants_after_app.sql` | Privileges on `app` tables; run after Django migrations (`make db-grants`) |
| `tests/` | SQL tests (permission and trigger checks) |

Ownership: `app` tables = Django migrations. Everything created here = SQL migrations. Silver and Gold tables built by dbt are defined in `pipelines/dbt`, not here.

```
make db-up db-migrate          # local database
make db-rollback               # undo the last migration
make api-migrate db-attach-cdc db-grants db-constraints   # after Django exists
```

Supplier credentials (`app.supplier_credential*`, module M8) are excluded from change capture and readable only by role `lozhka_purchasing`; see `scripts/grants_after_app.sql` and migration `20261029000001_purchasing.sql`.

Passwords for the roles are set outside version control: `alter role lozhka_api login password '...';`
