-- migrate:up

-- Schemas (see docs: 02_database_design.md §1)
create schema if not exists app;      -- transactional source, owned by Django migrations
create schema if not exists bronze;   -- raw, append-only
create schema if not exists silver;   -- clean, conformed
create schema if not exists gold;     -- serving tables and marts
create schema if not exists ops;      -- job queue, pipeline runs, logs, caches

-- Extensions used by search and text matching (trusted extensions, no superuser needed on PostgreSQL 13+)
create extension if not exists pg_trgm;
create extension if not exists unaccent;

-- Roles. NOLOGIN here: give the role a password and LOGIN outside version control, e.g.
--   alter role lozhka_api login password '...';
do $$
declare
  r text;
begin
  foreach r in array array[
    'lozhka_api', 'lozhka_backoffice', 'lozhka_pipeline', 'lozhka_planner', 'lozhka_report'
  ] loop
    if not exists (select 1 from pg_roles where rolname = r) then
      execute format('create role %I nologin', r);
    end if;
  end loop;
end
$$;

-- Schema usage
grant usage on schema app    to lozhka_api, lozhka_backoffice, lozhka_pipeline, lozhka_planner;
grant usage on schema bronze to lozhka_pipeline;
grant usage on schema silver to lozhka_backoffice, lozhka_pipeline;
grant usage on schema gold   to lozhka_api, lozhka_backoffice, lozhka_pipeline, lozhka_planner, lozhka_report;
grant usage on schema ops    to lozhka_api, lozhka_backoffice, lozhka_pipeline, lozhka_planner;

-- The pipeline role builds tables in silver and gold (dbt) and writes bronze
grant create on schema silver to lozhka_pipeline;
grant create on schema gold   to lozhka_pipeline;

-- Default privileges for objects created later by the migration owner (the role running this file)
alter default privileges in schema bronze grant select, insert, update, delete on tables to lozhka_pipeline;
alter default privileges in schema bronze grant usage, select on sequences to lozhka_pipeline;

alter default privileges in schema silver grant select, insert, update, delete on tables to lozhka_pipeline;
alter default privileges in schema silver grant select on tables to lozhka_backoffice;
alter default privileges in schema silver grant usage, select on sequences to lozhka_pipeline;

alter default privileges in schema gold grant select on tables to lozhka_api, lozhka_backoffice, lozhka_planner, lozhka_report;
alter default privileges in schema gold grant select, insert, update, delete on tables to lozhka_pipeline;

alter default privileges in schema ops grant select, insert, update, delete on tables to lozhka_api, lozhka_backoffice, lozhka_pipeline, lozhka_planner;
alter default privileges in schema ops grant usage, select on sequences to lozhka_api, lozhka_backoffice, lozhka_pipeline, lozhka_planner;

-- Tables that dbt (running as lozhka_pipeline) creates in silver/gold belong to that role, so
-- hand out read access on those too:
alter default privileges for role lozhka_pipeline in schema silver grant select on tables to lozhka_backoffice;
alter default privileges for role lozhka_pipeline in schema gold   grant select on tables to lozhka_api, lozhka_backoffice, lozhka_planner, lozhka_report;

-- Privileges on app tables are applied after Django has created them: db/scripts/grants_after_app.sql

-- migrate:down

drop schema if exists ops cascade;
drop schema if exists gold cascade;
drop schema if exists silver cascade;
drop schema if exists bronze cascade;
-- schema app and the roles are kept on purpose (they may hold data or be shared)
