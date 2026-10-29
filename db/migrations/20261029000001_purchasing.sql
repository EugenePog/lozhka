-- migrate:up

-- M8 · Demand forecasting and purchasing (docs: 03_modules.md section 8, 02_database_design.md section 4.6)

-- Role that prepares and sends purchase orders. It is the only role besides the owner that may read
-- supplier credentials. Set its password outside version control.
do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'lozhka_purchasing') then
    create role lozhka_purchasing nologin;
  end if;
end
$$;
grant usage on schema app  to lozhka_purchasing;
grant usage on schema gold to lozhka_purchasing;
grant usage on schema ops  to lozhka_purchasing;
alter default privileges in schema gold grant select on tables to lozhka_purchasing;
alter default privileges for role lozhka_pipeline in schema gold grant select on tables to lozhka_purchasing;
alter default privileges in schema ops grant select, insert, update, delete on tables to lozhka_purchasing;
alter default privileges in schema ops grant usage, select on sequences to lozhka_purchasing;
-- privileges on app tables (purchase orders, credentials) are applied by db/scripts/grants_after_app.sql

-- Forecast runs and results are written by Python (role lozhka_pipeline), so they are defined here, not in dbt.
create table silver.forecast_run (
  run_id        bigint generated always as identity primary key,
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  status        text not null default 'running' check (status in ('running', 'succeeded', 'failed')),
  horizon_days  integer not null check (horizon_days >= 1),
  history_days  integer,                       -- length of sales history used
  parameters    jsonb not null default '{}'::jsonb,
  metrics       jsonb,                         -- e.g. {"wape": 0.31, "bias": -0.02} from the rolling backtest
  products      integer,
  error         text
);

-- One row per product and future day. p50 = expected units sold, p80/p90 = upper quantiles used for safety stock.
create table silver.demand_forecast (
  run_id        bigint not null references silver.forecast_run (run_id) on delete cascade,
  product_id    bigint not null,
  forecast_date date not null,
  p50           numeric(12, 3) not null check (p50 >= 0),
  p80           numeric(12, 3) check (p80 is null or p80 >= p50),
  p90           numeric(12, 3) check (p90 is null or p90 >= p50),
  method        text not null,                 -- par_level, moving_average, ets, croston_tsb, gradient_boosting, manual
  primary key (run_id, product_id, forecast_date)
);
create index demand_forecast_product_idx on silver.demand_forecast (product_id, forecast_date);

-- Forecast versus what really sold, to monitor accuracy and bias per product and per method.
create table silver.forecast_accuracy (
  run_id        bigint not null references silver.forecast_run (run_id) on delete cascade,
  product_id    bigint not null,
  window_start  date not null,
  window_end    date not null,
  method        text not null,
  forecast_units numeric(12, 3) not null,
  actual_units  numeric(12, 3) not null,
  abs_error     numeric(12, 3) not null,
  primary key (run_id, product_id, window_start, method)
);

-- Link a parsed supplier delivery to the purchase order it fulfils (matched by PO number in the document, or by hand).
alter table silver.supplier_delivery add column po_number text;
alter table silver.supplier_delivery add column po_id bigint;   -- app.purchase_order id, no foreign key across schemas

-- Supplier credentials must never be copied to bronze: extend the exclusion list of the change-capture helper.
create or replace function bronze.attach_change_capture_all(
  p_schema  text default 'app',
  p_exclude text[] default array[
    'django\_%', 'auth\_%', 'account\_%', 'socialaccount\_%', 'authtoken\_%', 'mfa\_%', 'usersessions\_%',
    'supplier\_credential%'
  ]
)
returns integer
language plpgsql
as $$
declare
  t record;
  n integer := 0;
begin
  for t in
    select c.relname
      from pg_class c
      join pg_namespace s on s.oid = c.relnamespace
     where s.nspname = p_schema
       and c.relkind in ('r', 'p')
       and not exists (select 1 from unnest(p_exclude) as ex where c.relname like ex)
  loop
    perform bronze.attach_change_capture(p_schema, t.relname);
    n := n + 1;
  end loop;
  return n;
end
$$;

-- migrate:down

alter table silver.supplier_delivery drop column if exists po_id;
alter table silver.supplier_delivery drop column if exists po_number;
drop table if exists silver.forecast_accuracy;
drop table if exists silver.demand_forecast;
drop table if exists silver.forecast_run;

create or replace function bronze.attach_change_capture_all(
  p_schema  text default 'app',
  p_exclude text[] default array[
    'django\_%', 'auth\_%', 'account\_%', 'socialaccount\_%', 'authtoken\_%', 'mfa\_%', 'usersessions\_%'
  ]
)
returns integer
language plpgsql
as $$
declare
  t record;
  n integer := 0;
begin
  for t in
    select c.relname
      from pg_class c
      join pg_namespace s on s.oid = c.relnamespace
     where s.nspname = p_schema
       and c.relkind in ('r', 'p')
       and not exists (select 1 from unnest(p_exclude) as ex where c.relname like ex)
  loop
    perform bronze.attach_change_capture(p_schema, t.relname);
    n := n + 1;
  end loop;
  return n;
end
$$;
-- role lozhka_purchasing is kept on purpose (it may own grants)
