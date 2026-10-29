# Seed data (stage 1)

CSV files that fill the tables a fresh install needs. Rows are matched by **natural keys** (code, slug, SKU, e-mail,
order number), never by numeric ids, so every file can be loaded again without creating duplicates. A foreign key
column holds the parent's natural key (`category.parent` = parent slug; composite keys use `a|b`).

`manifest.toml` lists the load order for each set:

| Set | Content | Command |
|---|---|---|
| `essential` | VAT, allergens, categories, settings, content pages, delivery zones/fees/templates, return reasons, depot, staff roles | `make seed` |
| `demo` | essential + brands, 31 products with prices, stock lots, suppliers, vehicles/drivers, 2 customers, 4 orders, staff users | `make seed-demo` |

Conventions: dates accept `+30d` / `-3d` (relative to today); empty cell = NULL/empty; JSON columns hold JSON.
Demo logins: customers `demo@lozhka.example` / `jan@lozhka.example` (password `demo1234`); staff `admin@`, `operator@`,
`store@`, `all@lozhka.example` (password `staff1234`). Change or remove the demo set before production.
