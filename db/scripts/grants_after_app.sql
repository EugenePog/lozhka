-- Run after Django has created or changed the app tables (make db-grants).
-- Idempotent. Executed by the migration owner.

-- Public API and back office: full access to app tables
grant select, insert, update, delete on all tables in schema app to lozhka_api, lozhka_backoffice;
grant usage, select on all sequences in schema app to lozhka_api, lozhka_backoffice;

-- Pipelines only read app tables (they write bronze/silver/gold)
grant select on all tables in schema app to lozhka_pipeline;

-- Route planner: read everything, write delivery plans
grant select on all tables in schema app to lozhka_planner;
do $$
begin
  if to_regclass('app.delivery') is not null then
    execute 'grant insert, update, delete on app.delivery to lozhka_planner';
    execute 'grant insert, update, delete on app.delivery_stop to lozhka_planner';
    execute 'grant usage, select on all sequences in schema app to lozhka_planner';
  end if;
end
$$;

-- Tables created by Django from now on get the same grants automatically
alter default privileges in schema app grant select, insert, update, delete on tables to lozhka_api, lozhka_backoffice;
alter default privileges in schema app grant select on tables to lozhka_pipeline, lozhka_planner;
alter default privileges in schema app grant usage, select on sequences to lozhka_api, lozhka_backoffice;

-- Purchasing role: reads app, writes purchase orders
grant select on all tables in schema app to lozhka_purchasing;
do $$
begin
  if to_regclass('app.purchase_order') is not null then
    execute 'grant insert, update on app.purchase_order, app.purchase_order_line to lozhka_purchasing';
    execute 'grant usage, select on all sequences in schema app to lozhka_purchasing';
  end if;
end
$$;
alter default privileges in schema app grant select on tables to lozhka_purchasing;

-- Supplier credentials: metadata table and encrypted-secret table.
--   * only the purchasing role may read them (it also holds the decryption key in its environment)
--   * the back office may create and rotate secrets but never read them back (write-only)
--   * nobody else has any access
do $$
declare t text;
begin
  foreach t in array array['supplier_credential', 'supplier_credential_secret']
  loop
    if to_regclass('app.' || t) is not null then
      execute format('revoke all on app.%I from lozhka_api, lozhka_backoffice, lozhka_pipeline, lozhka_planner, lozhka_report', t);
      execute format('grant select on app.%I to lozhka_purchasing', t);
    end if;
  end loop;
  if to_regclass('app.supplier_credential') is not null then
    -- metadata (no secret): the back office may manage it
    execute 'grant select, insert, update on app.supplier_credential to lozhka_backoffice';
  end if;
  if to_regclass('app.supplier_credential_secret') is not null then
    -- update needs to read the key column to find the row; the secret column itself stays unreadable
    execute 'grant insert, update on app.supplier_credential_secret to lozhka_backoffice';
    execute 'grant select (credential_id, key_version, rotated_at) on app.supplier_credential_secret to lozhka_backoffice';
  end if;
end
$$;

-- Credentials never leave the API/back-office roles
do $$
declare t text;
begin
  foreach t in array array['auth_user', 'account_emailaddress', 'socialaccount_socialtoken', 'mfa_authenticator', 'otp_totp_totpdevice', 'otp_static_staticdevice', 'axes_accessattempt', 'axes_accesslog']
  loop
    if to_regclass('app.' || t) is not null then
      execute format('revoke all on app.%I from lozhka_pipeline, lozhka_planner', t);
    end if;
  end loop;
end
$$;

-- Staff console: configuration the operator/admin edit lives in app.*; only the back-office role writes it.
-- The public API role may read the time frames and slots (checkout) and read settings, never write them.
do $$
declare t text;
begin
  foreach t in array array['delivery_template', 'return_reason']
  loop
    if to_regclass('app.' || t) is not null then
      execute format('revoke all on app.%I from lozhka_api', t);
      execute format('grant select on app.%I to lozhka_api', t);
      execute format('grant select, insert, update, delete on app.%I to lozhka_backoffice', t);
    end if;
  end loop;
  -- operator call log, refusal flags and returns are written by the staff console only
  foreach t in array array['order_confirmation_attempt', 'customer_flag', 'delivery_return']
  loop
    if to_regclass('app.' || t) is not null then
      execute format('revoke all on app.%I from lozhka_api, lozhka_planner, lozhka_report', t);
      execute format('grant select, insert on app.%I to lozhka_backoffice', t);
    end if;
  end loop;
end
$$;

-- Staff-only authentication tables (authenticator devices, login-attempt log): the public API role has no access.
do $$
declare t text;
begin
  foreach t in array array['mfa_authenticator', 'otp_totp_totpdevice', 'otp_static_staticdevice', 'axes_accessattempt', 'axes_accesslog']
  loop
    if to_regclass('app.' || t) is not null then
      execute format('revoke all on app.%I from lozhka_api', t);
    end if;
  end loop;
end
$$;
