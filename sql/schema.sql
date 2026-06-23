create extension if not exists "pgcrypto";

create table if not exists ebay_product_candidates (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  name text not null,
  source_url text,
  purchase_price_jpy integer not null default 0 check (purchase_price_jpy >= 0),
  domestic_shipping_jpy integer not null default 0 check (domestic_shipping_jpy >= 0),
  packaging_cost_jpy integer not null default 0 check (packaging_cost_jpy >= 0),
  item_weight_g integer not null default 0 check (item_weight_g >= 0),
  packed_weight_g integer not null default 0 check (packed_weight_g >= 0),
  length_cm numeric not null default 0 check (length_cm >= 0),
  width_cm numeric not null default 0 check (width_cm >= 0),
  height_cm numeric not null default 0 check (height_cm >= 0),
  destination_country text not null check (destination_country in ('アメリカ', 'オーストラリア')),
  sale_currency text not null check (sale_currency in ('USD', 'AUD')),
  expected_sale_price numeric not null default 0 check (expected_sale_price >= 0),
  sold_count_90d integer not null default 0 check (sold_count_90d >= 0),
  competitor_count integer not null default 0 check (competitor_count >= 0),
  category text,
  promoted_listing_percent numeric not null default 0 check (promoted_listing_percent >= 0),
  memo text,
  risk_flags jsonb not null default '{}'::jsonb,
  risk_score integer not null default 0 check (risk_score >= 0),
  calculated_fx_rate numeric,
  calculation_fx_rate numeric,
  shipping_cost_jpy integer,
  total_cost_jpy integer,
  expected_revenue_jpy integer,
  expected_profit_jpy integer,
  roi_percent numeric,
  profit_margin_percent numeric,
  grade text,
  warnings jsonb not null default '[]'::jsonb
);

create table if not exists ebay_fx_rates (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  base_currency text not null,
  target_currency text not null,
  raw_rate numeric not null check (raw_rate > 0),
  buffer_percent numeric not null default 0 check (buffer_percent >= 0),
  calculation_rate numeric not null check (calculation_rate > 0),
  source text,
  fetched_at timestamptz not null default now(),
  unique (base_currency, target_currency)
);

create table if not exists ebay_fee_settings (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  destination_country text not null check (destination_country in ('アメリカ', 'オーストラリア')),
  marketplace text,
  final_value_fee_percent numeric not null default 0 check (final_value_fee_percent >= 0),
  international_fee_percent numeric not null default 0 check (international_fee_percent >= 0),
  fixed_order_fee numeric not null default 0 check (fixed_order_fee >= 0),
  fixed_order_fee_currency text not null check (fixed_order_fee_currency in ('USD', 'AUD', 'JPY')),
  promoted_listing_default_percent numeric not null default 0 check (promoted_listing_default_percent >= 0),
  exchange_buffer_percent numeric not null default 0 check (exchange_buffer_percent >= 0),
  risk_buffer_percent numeric not null default 0 check (risk_buffer_percent >= 0),
  source_url text,
  source_note text,
  last_checked_at date,
  unique (destination_country)
);

create table if not exists ebay_shipping_rate_master (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  destination_country text not null check (destination_country in ('アメリカ', 'オーストラリア')),
  service_name text not null,
  weight_min_g integer not null check (weight_min_g >= 0),
  weight_max_g integer not null check (weight_max_g >= weight_min_g),
  shipping_cost_jpy integer not null check (shipping_cost_jpy >= 0),
  tracking boolean not null default true,
  insurance boolean not null default false,
  ddp_supported boolean not null default false,
  source_url text,
  note text,
  last_checked_at date,
  unique (destination_country, service_name, weight_min_g, weight_max_g)
);

create table if not exists ebay_grading_rules (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  destination_country text not null check (destination_country in ('アメリカ', 'オーストラリア')),
  grade_a_min_profit_jpy integer not null default 1000,
  grade_a_min_roi_percent numeric not null default 30,
  grade_a_min_sold_count integer not null default 3,
  grade_b_min_profit_jpy integer not null default 700,
  grade_b_min_roi_percent numeric not null default 20,
  grade_b_min_sold_count integer not null default 1,
  grade_d_max_profit_jpy integer not null default 500,
  grade_d_max_roi_percent numeric not null default 15,
  stale_master_warning_days integer not null default 30,
  unique (destination_country)
);

alter table ebay_product_candidates enable row level security;
alter table ebay_fx_rates enable row level security;
alter table ebay_fee_settings enable row level security;
alter table ebay_shipping_rate_master enable row level security;
alter table ebay_grading_rules enable row level security;

drop policy if exists "ebay anon read product_candidates" on ebay_product_candidates;
drop policy if exists "ebay anon insert product_candidates" on ebay_product_candidates;
drop policy if exists "ebay anon update product_candidates" on ebay_product_candidates;
drop policy if exists "ebay anon read fx_rates" on ebay_fx_rates;
drop policy if exists "ebay anon upsert fx_rates" on ebay_fx_rates;
drop policy if exists "ebay anon update fx_rates" on ebay_fx_rates;
drop policy if exists "ebay anon read fee_settings" on ebay_fee_settings;
drop policy if exists "ebay anon upsert fee_settings" on ebay_fee_settings;
drop policy if exists "ebay anon update fee_settings" on ebay_fee_settings;
drop policy if exists "ebay anon read shipping_rate_master" on ebay_shipping_rate_master;
drop policy if exists "ebay anon upsert shipping_rate_master" on ebay_shipping_rate_master;
drop policy if exists "ebay anon update shipping_rate_master" on ebay_shipping_rate_master;
drop policy if exists "ebay anon read grading_rules" on ebay_grading_rules;
drop policy if exists "ebay anon upsert grading_rules" on ebay_grading_rules;
drop policy if exists "ebay anon update grading_rules" on ebay_grading_rules;

create policy "ebay anon read product_candidates" on ebay_product_candidates for select to anon using (true);
create policy "ebay anon insert product_candidates" on ebay_product_candidates for insert to anon with check (true);
create policy "ebay anon update product_candidates" on ebay_product_candidates for update to anon using (true) with check (true);

create policy "ebay anon read fx_rates" on ebay_fx_rates for select to anon using (true);
create policy "ebay anon upsert fx_rates" on ebay_fx_rates for insert to anon with check (true);
create policy "ebay anon update fx_rates" on ebay_fx_rates for update to anon using (true) with check (true);

create policy "ebay anon read fee_settings" on ebay_fee_settings for select to anon using (true);
create policy "ebay anon upsert fee_settings" on ebay_fee_settings for insert to anon with check (true);
create policy "ebay anon update fee_settings" on ebay_fee_settings for update to anon using (true) with check (true);

create policy "ebay anon read shipping_rate_master" on ebay_shipping_rate_master for select to anon using (true);
create policy "ebay anon upsert shipping_rate_master" on ebay_shipping_rate_master for insert to anon with check (true);
create policy "ebay anon update shipping_rate_master" on ebay_shipping_rate_master for update to anon using (true) with check (true);

create policy "ebay anon read grading_rules" on ebay_grading_rules for select to anon using (true);
create policy "ebay anon upsert grading_rules" on ebay_grading_rules for insert to anon with check (true);
create policy "ebay anon update grading_rules" on ebay_grading_rules for update to anon using (true) with check (true);
