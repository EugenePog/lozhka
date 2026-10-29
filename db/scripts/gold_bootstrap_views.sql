-- Stage-1 bootstrap of the Gold read models (docs 02 sections 7 and 8). Run after Django has created the
-- app tables (make db-gold-views). Idempotent: drops and re-creates the views.
--
-- WHY VIEWS: the pipelines (dbt, module M7) do not exist yet, but the public API reads Gold for browsing
-- and for the stock check at checkout. These plain views compute the same read models straight from `app`,
-- so the API already has its final read path. When the dbt models of the same names are built they replace
-- these views (dbt drops a view when it materialises a table with the same name).
--
-- Stock rules (docs 02 section 8):
--   lot_balance      = received - rejected + adjustments - picked (picked counts once the delivery is out)
--   sellable_on_hand = lots with a positive balance and best_before >= today + min_shelf_life_days_for_sale
--   reserved         = reservations that are committed, or held and not yet expired
--   available        = max(0, sellable_on_hand - reserved - safety_stock_qty)
-- "today" is the Amsterdam calendar date.

drop view if exists gold.storefront_category cascade;
drop view if exists gold.storefront_product cascade;
drop view if exists gold.stock_available cascade;
drop view if exists gold.stock_reserved cascade;
drop view if exists gold.stock_on_hand cascade;
drop view if exists gold.lot_balance cascade;
drop view if exists gold.current_price cascade;

create view gold.current_price as
select p.id as product_id,
       cur.amount_cents,
       cur.kind,
       reg.amount_cents as regular_cents,
       (cur.kind in ('offer', 'markdown')) as is_discounted
  from app.product p
  left join lateral (
        select pr.amount_cents, pr.kind
          from app.price pr
         where pr.product_id = p.id
           and pr.valid_from <= now()
           and (pr.valid_to is null or pr.valid_to > now())
         order by case pr.kind when 'markdown' then 1 when 'offer' then 2 else 3 end, pr.valid_from desc
         limit 1) cur on true
  left join lateral (
        select pr.amount_cents
          from app.price pr
         where pr.product_id = p.id and pr.kind = 'regular'
           and pr.valid_from <= now()
           and (pr.valid_to is null or pr.valid_to > now())
         order by pr.valid_from desc
         limit 1) reg on true;

create view gold.lot_balance as
select rl.id as lot_id,
       rl.product_id,
       r.supplier_id,
       rl.supplier_lot_code,
       rl.best_before,
       r.received_at,
       (rl.qty_received - rl.qty_rejected
          + coalesce(adj.qty, 0)
          - coalesce(pk.qty, 0))::numeric(12, 3) as balance
  from app.receiving_line rl
  join app.receiving r on r.id = rl.receiving_id and r.status = 'accepted'
  left join lateral (
        select sum(a.qty_delta) as qty
          from app.stock_adjustment a
         where a.receiving_line_id = rl.id) adj on true
  left join lateral (
        select sum(p.qty) as qty
          from app.pick_line p
          join app.order_line ol on ol.id = p.order_line_id
          join app."order" o on o.id = ol.order_id
          join app.delivery d on d.id = o.delivery_id
         where p.receiving_line_id = rl.id
           and d.status in ('out_for_delivery', 'completed')) pk on true;

create view gold.stock_on_hand as
select p.id as product_id,
       coalesce(sum(lb.balance) filter (where lb.balance > 0), 0)::numeric(12, 3) as total_qty,
       coalesce(sum(lb.balance) filter (
         where lb.balance > 0
           and lb.best_before >= (now() at time zone 'Europe/Amsterdam')::date + p.min_shelf_life_days_for_sale
       ), 0)::numeric(12, 3) as sellable_qty,
       min(lb.best_before) filter (where lb.balance > 0) as nearest_best_before,
       now() as as_of
  from app.product p
  left join gold.lot_balance lb on lb.product_id = p.id
 group by p.id, p.min_shelf_life_days_for_sale;

create view gold.stock_reserved as
select sr.product_id,
       sum(sr.qty)::numeric(12, 3) as reserved_qty
  from app.stock_reservation sr
 where sr.status = 'committed'
    or (sr.status = 'held' and sr.expires_at > now())
 group by sr.product_id;

create view gold.stock_available as
select p.id as product_id,
       a.available_qty,
       case when a.available_qty <= 0 then 'out_of_stock'
            when a.available_qty <= p.low_stock_threshold then 'low_stock'
            else 'in_stock' end as status,
       now() as as_of
  from app.product p
  join gold.stock_on_hand soh on soh.product_id = p.id
  left join gold.stock_reserved res on res.product_id = p.id
  cross join lateral (
        select greatest(0, soh.sellable_qty - coalesce(res.reserved_qty, 0) - p.safety_stock_qty)::numeric(12, 3)
               as available_qty) a;

-- Product card and product page in one row per product and language (falls back to English, then Dutch).
create view gold.storefront_product as
with langs(lang) as (values ('nl'), ('en'), ('ru')),
cat_path as (
  with recursive up as (
    select c.id as leaf_id, c.id, c.parent_id, 0 as depth from app.category c
    union all
    select up.leaf_id, c.id, c.parent_id, up.depth + 1 from up join app.category c on c.id = up.parent_id
  )
  select leaf_id, id as category_id, depth from up
)
select p.id as product_id,
       l.lang,
       p.sku,
       p.slug,
       coalesce(t.name, te.name, tn.name, p.sku) as name,
       coalesce(t.short_description, te.short_description, tn.short_description, '') as short_description,
       coalesce(t.description, te.description, tn.description, '') as description,
       coalesce(t.ingredients, te.ingredients, tn.ingredients, '') as ingredients,
       coalesce(t.storage_instructions, te.storage_instructions, tn.storage_instructions, '') as storage_instructions,
       b.name as brand,
       p.net_content_value,
       p.net_content_unit,
       case when p.net_content_value is null or p.net_content_unit is null then null
            else trim(trailing '.' from trim(trailing '0' from p.net_content_value::text)) || ' ' || p.net_content_unit
       end as unit_label,
       p.country_of_origin,
       p.storage_type,
       p.storage_temp_min_c,
       p.storage_temp_max_c,
       p.status,
       p.is_orderable,
       p.unit_type,
       vr.rate_pct as vat_rate_pct,
       cp.amount_cents as price_cents,
       cp.regular_cents,
       coalesce(cp.is_discounted, false) as is_discounted,
       case p.net_content_unit
            when 'g'  then round(cp.amount_cents * 1000 / nullif(p.net_content_value, 0))
            when 'kg' then round(cp.amount_cents / nullif(p.net_content_value, 0))
            when 'ml' then round(cp.amount_cents * 1000 / nullif(p.net_content_value, 0))
            when 'l'  then round(cp.amount_cents / nullif(p.net_content_value, 0))
       end::int as unit_price_cents,
       case when p.net_content_unit in ('g', 'kg') then 'kg'
            when p.net_content_unit in ('ml', 'l') then 'l' end as unit_price_per,
       p.category_id,
       c.slug as category_slug,
       (select jsonb_agg(jsonb_build_object('slug', pc.slug, 'name', coalesce(pct.name, pce.name, pc.slug))
                         order by cpath.depth desc)
          from cat_path cpath
          join app.category pc on pc.id = cpath.category_id
          left join app.category_translation pct on pct.category_id = pc.id and pct.lang = l.lang
          left join app.category_translation pce on pce.category_id = pc.id and pce.lang = 'en'
         where cpath.leaf_id = p.category_id) as category_path,
       array_remove(array[
         case when coalesce(cp.is_discounted, false) then 'offer' end,
         case when exists (select 1 from app.product_highlight h where h.product_id = p.id and h.kind = 'bestseller') then 'bestseller' end,
         case when exists (select 1 from app.product_highlight h where h.product_id = p.id and h.kind = 'new') then 'new' end,
         case when p.storage_type = 'frozen' then 'frozen' end
       ], null) as tags,
       sa.status as stock_status,
       sa.available_qty,
       coalesce((select jsonb_agg(jsonb_build_object('key', i.storage_key, 'alt', coalesce(i.alt_text ->> l.lang, i.alt_text ->> 'en', ''))
                                 order by i.sort)
                   from app.product_image i where i.product_id = p.id), '[]'::jsonb) as images,
       coalesce((select jsonb_agg(jsonb_build_object(
                          'code', pa.allergen_code, 'presence', pa.presence,
                          'name', coalesce(at.name, ate.name, pa.allergen_code))
                          order by al.sort)
                   from app.product_allergen pa
                   join app.allergen al on al.code = pa.allergen_code
                   left join app.allergen_translation at on at.allergen_id = al.id and at.lang = l.lang
                   left join app.allergen_translation ate on ate.allergen_id = al.id and ate.lang = 'en'
                  where pa.product_id = p.id), '[]'::jsonb) as allergens,
       (select to_jsonb(n) - 'id' - 'product_id' from app.product_nutrition n where n.product_id = p.id) as nutrition,
       to_tsvector('simple', unaccent(
         coalesce(t.name, te.name, '') || ' ' || coalesce(te.name, '') || ' ' || coalesce(t.search_terms, '') || ' '
         || coalesce(te.search_terms, '') || ' ' || coalesce(b.name, '') || ' ' || p.sku)) as search_vector,
       lower(unaccent(
         coalesce(t.name, te.name, '') || ' ' || coalesce(te.name, '') || ' ' || coalesce(t.search_terms, '') || ' '
         || coalesce(te.search_terms, '') || ' ' || coalesce(b.name, ''))) as search_text,
       p.created_at
  from app.product p
  cross join langs l
  join app.category c on c.id = p.category_id
  join app.vat_rate vr on vr.id = p.vat_rate_id
  left join app.brand b on b.id = p.brand_id
  left join app.product_translation t on t.product_id = p.id and t.lang = l.lang
  left join app.product_translation te on te.product_id = p.id and te.lang = 'en'
  left join app.product_translation tn on tn.product_id = p.id and tn.lang = 'nl'
  left join gold.current_price cp on cp.product_id = p.id
  left join gold.stock_available sa on sa.product_id = p.id
 where p.status = 'active' and p.archived_at is null;

create view gold.storefront_category as
with recursive tree(root_id, node_id) as (
  select c.id, c.id from app.category c
  union all
  select t.root_id, c.id from tree t join app.category c on c.parent_id = t.node_id
),
langs(lang) as (values ('nl'), ('en'), ('ru'))
select c.id as category_id,
       c.parent_id,
       pc.slug as parent_slug,
       c.slug,
       l.lang,
       coalesce(t.name, te.name, c.slug) as name,
       c.sort,
       c.is_visible,
       c.kind,
       case when c.kind = 'offers'
            then (select count(*) from app.product p join gold.current_price cp on cp.product_id = p.id
                   where p.status = 'active' and cp.is_discounted)
            else (select count(*) from tree tr join app.product p on p.category_id = tr.node_id
                   where tr.root_id = c.id and p.status = 'active' and p.archived_at is null)
       end::int as product_count
  from app.category c
  cross join langs l
  left join app.category pc on pc.id = c.parent_id
  left join app.category_translation t on t.category_id = c.id and t.lang = l.lang
  left join app.category_translation te on te.category_id = c.id and te.lang = 'en'
 where c.archived_at is null;

-- Same read access as every other Gold table (default privileges only cover objects created later).
grant select on all tables in schema gold
  to lozhka_api, lozhka_backoffice, lozhka_planner, lozhka_report, lozhka_purchasing;
