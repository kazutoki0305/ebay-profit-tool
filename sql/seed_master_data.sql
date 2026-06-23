insert into ebay_fee_settings (
  destination_country,
  marketplace,
  final_value_fee_percent,
  international_fee_percent,
  fixed_order_fee,
  fixed_order_fee_currency,
  promoted_listing_default_percent,
  exchange_buffer_percent,
  risk_buffer_percent,
  source_url,
  source_note,
  last_checked_at
) values
  ('アメリカ', 'eBay US', 13.25, 1.65, 0.40, 'USD', 2.0, 3.0, 3.0, '', '初期サンプル値。実運用前にeBay公式情報で確認してください。', current_date),
  ('オーストラリア', 'eBay Australia', 13.25, 1.65, 0.40, 'AUD', 2.0, 3.0, 4.0, '', '初期サンプル値。実運用前にeBay公式情報で確認してください。', current_date)
on conflict (destination_country) do update set
  marketplace = excluded.marketplace,
  final_value_fee_percent = excluded.final_value_fee_percent,
  international_fee_percent = excluded.international_fee_percent,
  fixed_order_fee = excluded.fixed_order_fee,
  fixed_order_fee_currency = excluded.fixed_order_fee_currency,
  promoted_listing_default_percent = excluded.promoted_listing_default_percent,
  exchange_buffer_percent = excluded.exchange_buffer_percent,
  risk_buffer_percent = excluded.risk_buffer_percent,
  source_url = excluded.source_url,
  source_note = excluded.source_note,
  last_checked_at = excluded.last_checked_at,
  updated_at = now();

insert into ebay_shipping_rate_master (
  destination_country,
  service_name,
  weight_min_g,
  weight_max_g,
  shipping_cost_jpy,
  tracking,
  insurance,
  ddp_supported,
  source_url,
  note,
  last_checked_at
) values
  ('アメリカ', 'サンプル小型便', 0, 500, 1800, true, false, false, '', '初期サンプル値。公式料金に置き換えてください。', current_date),
  ('アメリカ', 'サンプル標準便', 501, 1000, 2800, true, false, false, '', '初期サンプル値。公式料金に置き換えてください。', current_date),
  ('アメリカ', 'サンプル大型便', 1001, 2000, 5200, true, false, false, '', '初期サンプル値。公式料金に置き換えてください。', current_date),
  ('オーストラリア', 'サンプル小型便', 0, 500, 1900, true, false, false, '', '初期サンプル値。公式料金に置き換えてください。', current_date),
  ('オーストラリア', 'サンプル標準便', 501, 1000, 3000, true, false, false, '', '初期サンプル値。公式料金に置き換えてください。', current_date),
  ('オーストラリア', 'サンプル大型便', 1001, 2000, 5600, true, false, false, '', '初期サンプル値。公式料金に置き換えてください。', current_date)
on conflict (destination_country, service_name, weight_min_g, weight_max_g) do update set
  shipping_cost_jpy = excluded.shipping_cost_jpy,
  tracking = excluded.tracking,
  insurance = excluded.insurance,
  ddp_supported = excluded.ddp_supported,
  source_url = excluded.source_url,
  note = excluded.note,
  last_checked_at = excluded.last_checked_at,
  updated_at = now();

insert into ebay_grading_rules (
  destination_country,
  grade_a_min_profit_jpy,
  grade_a_min_roi_percent,
  grade_a_min_sold_count,
  grade_b_min_profit_jpy,
  grade_b_min_roi_percent,
  grade_b_min_sold_count,
  grade_d_max_profit_jpy,
  grade_d_max_roi_percent,
  stale_master_warning_days
) values
  ('アメリカ', 1000, 30, 3, 700, 20, 1, 500, 15, 30),
  ('オーストラリア', 1000, 30, 3, 700, 20, 1, 500, 15, 30)
on conflict (destination_country) do update set
  grade_a_min_profit_jpy = excluded.grade_a_min_profit_jpy,
  grade_a_min_roi_percent = excluded.grade_a_min_roi_percent,
  grade_a_min_sold_count = excluded.grade_a_min_sold_count,
  grade_b_min_profit_jpy = excluded.grade_b_min_profit_jpy,
  grade_b_min_roi_percent = excluded.grade_b_min_roi_percent,
  grade_b_min_sold_count = excluded.grade_b_min_sold_count,
  grade_d_max_profit_jpy = excluded.grade_d_max_profit_jpy,
  grade_d_max_roi_percent = excluded.grade_d_max_roi_percent,
  stale_master_warning_days = excluded.stale_master_warning_days,
  updated_at = now();
