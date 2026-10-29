-- migrate:up
-- Staff console (module B): authenticator secrets and login-attempt tables must never reach Bronze.
-- Also: pay on delivery needs nothing new in ops; staff actions use ops.audit_log (already present).

create or replace function bronze.attach_change_capture_all(
  p_schema  text default 'app',
  p_exclude text[] default array[
    'django\_%', 'auth\_%', 'account\_%', 'socialaccount\_%', 'authtoken\_%', 'mfa\_%', 'usersessions\_%',
    'supplier\_credential%', 'otp\_%', 'axes\_%', 'two\_factor\_%'
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
