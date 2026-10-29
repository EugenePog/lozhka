-- migrate:up

-- Bronze: raw, append-only copies. No foreign keys to app tables on purpose.

-- One row per uploaded supplier file. Same sha256 for the same supplier = same file.
create table bronze.supplier_file (
  file_id            bigint generated always as identity primary key,
  supplier_id        bigint not null,
  original_name      text not null,
  sha256             char(64) not null,
  size_bytes         bigint not null check (size_bytes >= 0),
  storage_key        text not null,                 -- object storage key of the untouched original
  uploaded_by        text,
  uploaded_at        timestamptz not null default now(),
  delivery_ref_hint  text,                          -- optional reference typed by staff at upload
  supersedes_file_id bigint references bronze.supplier_file (file_id),
  status             text not null default 'registered'
                       check (status in ('registered', 'extracted', 'parsed', 'failed')),
  error              text,
  unique (supplier_id, sha256)
);

-- Every cell exactly as read. cells is a JSON array of strings (nulls for empty cells).
create table bronze.supplier_file_row (
  file_id      bigint not null references bronze.supplier_file (file_id) on delete cascade,
  sheet        text not null,
  row_no       integer not null check (row_no >= 1),
  cells        jsonb not null,
  extracted_at timestamptz not null default now(),
  primary key (file_id, sheet, row_no)
);

-- Change log of every row in app.* (filled by trigger, see migration 5).
create table bronze.app_change_log (
  change_id    bigint generated always as identity primary key,
  table_schema text not null,
  table_name   text not null,
  op           char(1) not null check (op in ('I', 'U', 'D')),
  pk           jsonb not null,
  row_after    jsonb,                 -- null for deletes
  row_before   jsonb,                 -- only kept for deletes
  txid         bigint not null,
  changed_at   timestamptz not null default now()
);
create index app_change_log_table_idx on bronze.app_change_log (table_name, change_id);
create index app_change_log_changed_at_idx on bronze.app_change_log (changed_at);

-- Raw payment webhooks, stored before any processing.
create table bronze.payment_event (
  event_pk     bigint generated always as identity primary key,
  provider     text not null,
  event_id     text not null,
  received_at  timestamptz not null default now(),
  headers      jsonb,
  payload      jsonb not null,
  processed_at timestamptz,
  unique (provider, event_id)
);

-- Raw email provider events (bounces, complaints).
create table bronze.email_event (
  event_pk    bigint generated always as identity primary key,
  provider    text not null,
  event_id    text not null,
  kind        text not null,
  payload     jsonb not null,
  received_at timestamptz not null default now(),
  unique (provider, event_id)
);

-- The public API stores raw webhooks itself, so it gets insert-only access to these two tables
-- (and nothing else in bronze). Identity columns need no sequence privilege.
grant usage on schema bronze to lozhka_api;
grant insert on bronze.payment_event, bronze.email_event to lozhka_api;

-- migrate:down

drop table if exists bronze.email_event;
drop table if exists bronze.payment_event;
drop table if exists bronze.app_change_log;
drop table if exists bronze.supplier_file_row;
drop table if exists bronze.supplier_file;
