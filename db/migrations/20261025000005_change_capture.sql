-- migrate:up

-- Trigger-based change capture: every insert/update/delete on an app table is copied to
-- bronze.app_change_log. SECURITY DEFINER lets the API and back-office roles trigger the copy
-- without having any privilege on the bronze schema.

create or replace function bronze.capture_change()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, bronze
as $$
declare
  rec jsonb;
  pk  jsonb := '{}'::jsonb;
  col text;
begin
  if tg_op = 'DELETE' then
    rec := to_jsonb(old);
  else
    rec := to_jsonb(new);
  end if;

  -- trigger arguments carry the primary-key column names
  foreach col in array tg_argv loop
    pk := pk || jsonb_build_object(col, rec -> col);
  end loop;

  insert into bronze.app_change_log (table_schema, table_name, op, pk, row_after, row_before, txid)
  values (
    tg_table_schema,
    tg_table_name,
    left(tg_op, 1),
    pk,
    case when tg_op = 'DELETE' then null else rec end,
    case when tg_op = 'DELETE' then rec else null end,
    txid_current()
  );
  return null;  -- AFTER trigger, return value ignored
end
$$;

-- Attach (or re-attach) the trigger to one table. Idempotent.
create or replace function bronze.attach_change_capture(p_schema text, p_table text)
returns void
language plpgsql
as $$
declare
  pk_cols text[];
  args    text;
begin
  select array_agg(a.attname order by k.ord)
    into pk_cols
    from pg_index i
    cross join lateral unnest(i.indkey) with ordinality as k(attnum, ord)
    join pg_attribute a on a.attrelid = i.indrelid and a.attnum = k.attnum
   where i.indrelid = format('%I.%I', p_schema, p_table)::regclass
     and i.indisprimary;

  if pk_cols is null then
    raise exception 'table %.% has no primary key, cannot capture changes', p_schema, p_table;
  end if;

  select string_agg(quote_literal(c), ', ') into args from unnest(pk_cols) as c;

  execute format('drop trigger if exists zz_capture_change on %I.%I', p_schema, p_table);
  execute format(
    'create trigger zz_capture_change after insert or update or delete on %I.%I '
    'for each row execute function bronze.capture_change(%s)',
    p_schema, p_table, args
  );
end
$$;

-- Attach to every base table of a schema except technical and credential tables.
-- Django internals, login credentials and social-login tokens must never reach bronze.
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

-- migrate:down

drop function if exists bronze.attach_change_capture_all(text, text[]);
drop function if exists bronze.attach_change_capture(text, text);
drop function if exists bronze.capture_change() cascade;  -- cascade also removes the triggers on app tables
