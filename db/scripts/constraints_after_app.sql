-- Run after Django has created the app tables (make db-constraints). Idempotent.
-- Rule: the collection ranges of the ACTIVE delivery templates must cover the 24 hours exactly:
-- every minute of the day belongs to exactly one active template (no gap, no overlap).
-- Range convention: [collect_from, collect_to) in local time; if collect_to <= collect_from the range runs through midnight
-- (12:00 -> 00:00 means 12:00 to 24:00; equal start and end means the whole day). Zero active templates is allowed (nothing is delivered).
-- Required columns on app.delivery_template: collect_from time, collect_to time, is_active boolean.

create or replace function app.check_delivery_template_coverage()
returns trigger
language plpgsql
as $$
declare
  n_active integer;
  bad_minutes integer;
begin
  select count(*) into n_active from app.delivery_template where is_active;
  if n_active = 0 then
    return null;
  end if;

  -- start minute s and length len of each range (equal start and end = the whole day)
  with r as (
    select (extract(hour from collect_from) * 60 + extract(minute from collect_from))::int as s,
           case when collect_to = collect_from then 1440
                else ((extract(hour from collect_to) * 60 + extract(minute from collect_to)
                     - extract(hour from collect_from) * 60 - extract(minute from collect_from))::int + 1440) % 1440
           end as len
      from app.delivery_template
     where is_active
  )
  select count(*) into bad_minutes
    from generate_series(0, 1439) as m
   where (select count(*) from r where ((m - r.s) % 1440 + 1440) % 1440 < r.len) <> 1;

  if bad_minutes > 0 then
    raise exception 'delivery_template: collection ranges of active templates must cover 24 hours with no gap or overlap (% minutes violate it)', bad_minutes
      using errcode = 'check_violation';
  end if;
  return null;
end
$$;

do $$
begin
  if to_regclass('app.delivery_template') is not null then
    execute 'drop trigger if exists zz_delivery_template_coverage on app.delivery_template';
    execute 'create constraint trigger zz_delivery_template_coverage
               after insert or update or delete on app.delivery_template
               deferrable initially deferred
               for each row execute function app.check_delivery_template_coverage()';
  end if;
end
$$;
