select
  table_schema,
  table_name
from information_schema.tables
where table_schema = 'public'
  and table_name in (
    'ebay_product_candidates',
    'ebay_fx_rates',
    'ebay_fee_settings',
    'ebay_shipping_rate_master',
    'ebay_grading_rules'
  )
order by table_name;

