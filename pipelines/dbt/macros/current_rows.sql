{#
  Latest version of every row of an app table, rebuilt from the change log.
  Deleted rows are dropped. The row is returned as jsonb in column `r`.

  Example (models/silver/catalogue/product.sql):
    select
      (r ->> 'id')::bigint  as product_id,
      r ->> 'sku'           as sku,
      r ->> 'storage_type'  as storage_type,
      changed_at            as updated_at
    from {{ current_rows('product') }}
#}
{% macro current_rows(table_name) -%}
(
  select x.row_after as r, x.change_id, x.changed_at
  from (
    select l.*,
           row_number() over (partition by l.pk order by l.change_id desc) as rn
    from {{ source('bronze', 'app_change_log') }} l
    where l.table_name = '{{ table_name }}'
  ) x
  where x.rn = 1 and x.op <> 'D'
) as current_{{ table_name }}
{%- endmacro %}
