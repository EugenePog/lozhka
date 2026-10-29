-- migrate:up

-- Silver tables written by Python (module M2 and the geocoder). Tables built by dbt are NOT defined here.

-- One row per delivery version. A corrected re-upload creates version + 1.
create table silver.supplier_delivery (
  delivery_id    bigint generated always as identity primary key,
  supplier_id    bigint not null,
  delivery_ref   text not null,
  version        integer not null check (version >= 1),
  source_file_id bigint not null references bronze.supplier_file (file_id),
  expected_date  date,
  status         text not null default 'parsed'
                   check (status in ('parsed', 'needs_review', 'ready', 'received', 'cancelled')),
  line_count     integer not null default 0,
  total_cost_cents bigint,
  parsed_at      timestamptz not null default now(),
  profile_version integer,
  unique (supplier_id, delivery_ref, version)
);

create table silver.supplier_delivery_line (
  delivery_id       bigint not null references silver.supplier_delivery (delivery_id) on delete cascade,
  line_no           integer not null check (line_no >= 1),
  line_key          text not null,           -- stable key used by app.delivery_line_fix (SKU, or SKU|lot)
  source_sheet      text,
  source_row_no     integer,
  supplier_sku      text,
  gtin              text,
  raw_description   text,
  product_id        bigint,                  -- matched app.product id, null if unmatched
  match_method      text check (match_method in ('supplier_sku', 'gtin', 'fuzzy', 'manual')),
  qty_packs         numeric(12, 3),
  pack_size         numeric(12, 3),
  qty_units         numeric(12, 3),
  unit_cost_cents   bigint,
  best_before       date,
  lot_code          text,
  fixed_fields      jsonb not null default '{}'::jsonb,   -- which fields were overridden by manual fixes
  validation_status text not null default 'ok'
                      check (validation_status in ('ok', 'warning', 'error')),
  primary key (delivery_id, line_no)
);
create index supplier_delivery_line_key_idx on silver.supplier_delivery_line (delivery_id, line_key);

create table silver.supplier_delivery_issue (
  issue_id    bigint generated always as identity primary key,
  delivery_id bigint not null references silver.supplier_delivery (delivery_id) on delete cascade,
  line_no     integer,                        -- null for delivery-level issues
  severity    text not null check (severity in ('error', 'warning')),
  code        text not null,                  -- UNKNOWN_SKU, BAD_NUMBER, EXPIRED, QTY_MISMATCH, ...
  message     text not null,
  created_at  timestamptz not null default now()
);
create index supplier_delivery_issue_delivery_idx on silver.supplier_delivery_issue (delivery_id);

-- Coordinates for addresses that arrived without them (guest checkouts, edited addresses).
create table silver.address_geocode (
  address_hash text primary key,              -- hash of normalised postcode + house number + addition
  lat          double precision not null check (lat between -90 and 90),
  lng          double precision not null check (lng between -180 and 180),
  bag_id       text,
  source       text not null default 'pdok',
  geocoded_at  timestamptz not null default now()
);

-- migrate:down

drop table if exists silver.address_geocode;
drop table if exists silver.supplier_delivery_issue;
drop table if exists silver.supplier_delivery_line;
drop table if exists silver.supplier_delivery;
