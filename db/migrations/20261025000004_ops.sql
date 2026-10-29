-- migrate:up

-- Technical tables. The job queue (Procrastinate) installs its own tables into this schema:
--   PGOPTIONS="-c search_path=ops" procrastinate --app=lozhka_worker.app.app schema --apply

-- One row per pipeline step execution.
create table ops.pipeline_run (
  run_id        bigint generated always as identity primary key,
  pipeline      text not null,                 -- e.g. P03 parse_supplier_delivery
  scope         text,                          -- e.g. file_id=12, or dbt selector
  status        text not null check (status in ('running', 'succeeded', 'failed')),
  started_at    timestamptz not null default now(),
  finished_at   timestamptz,
  rows_in       bigint,
  rows_out      bigint,
  error         text
);
create index pipeline_run_pipeline_idx on ops.pipeline_run (pipeline, started_at desc);

-- Results of data-quality checks.
create table ops.dq_result (
  result_id  bigint generated always as identity primary key,
  run_id     bigint references ops.pipeline_run (run_id),
  check_name text not null,
  target     text not null,
  status     text not null check (status in ('pass', 'warn', 'fail')),
  detail     jsonb,
  checked_at timestamptz not null default now()
);

-- Outgoing notifications (email, Telegram). dedupe_key stops repeats, e.g. 'expiry:lot=42:days=7'.
create table ops.notification (
  notification_id bigint generated always as identity primary key,
  channel         text not null check (channel in ('email', 'telegram')),
  recipient       text not null,
  topic           text not null,               -- expiry_digest, pipeline_alert, new_order, ...
  subject         text,
  body            text not null,
  dedupe_key      text,
  status          text not null default 'pending'
                    check (status in ('pending', 'sent', 'failed', 'skipped')),
  attempts        integer not null default 0,
  created_at      timestamptz not null default now(),
  sent_at         timestamptz,
  error           text
);
create unique index notification_dedupe_idx on ops.notification (channel, recipient, dedupe_key)
  where dedupe_key is not null;

-- Who did what in the back office.
create table ops.audit_log (
  audit_id   bigint generated always as identity primary key,
  actor      text not null,
  action     text not null,
  object     text,
  detail     jsonb,
  reason     text,
  at         timestamptz not null default now()
);

-- GDPR erasure record. This is the only place that documents allowed edits to bronze.
create table ops.erasure_log (
  erasure_id  bigint generated always as identity primary key,
  customer_uuid uuid not null,
  requested_at timestamptz not null default now(),
  completed_at timestamptz,
  detail      jsonb
);

-- Cached road distance/duration between rounded coordinates (route planner).
create table ops.route_matrix_cache (
  from_lat_e5  integer not null,                -- latitude  * 100000, rounded
  from_lng_e5  integer not null,
  to_lat_e5    integer not null,
  to_lng_e5    integer not null,
  profile      text not null default 'car',
  distance_m   integer not null check (distance_m >= 0),
  duration_s   integer not null check (duration_s >= 0),
  engine_version text,
  cached_at    timestamptz not null default now(),
  primary key (from_lat_e5, from_lng_e5, to_lat_e5, to_lng_e5, profile)
);

-- migrate:down

drop table if exists ops.route_matrix_cache;
drop table if exists ops.erasure_log;
drop table if exists ops.audit_log;
drop table if exists ops.notification;
drop table if exists ops.dq_result;
drop table if exists ops.pipeline_run;
