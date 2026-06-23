LOGICAL_TO_SUPABASE_TABLE = {
    "product_candidates": "ebay_product_candidates",
    "fx_rates": "ebay_fx_rates",
    "fee_settings": "ebay_fee_settings",
    "shipping_rate_master": "ebay_shipping_rate_master",
    "grading_rules": "ebay_grading_rules",
}


def supabase_table_name(logical_name: str) -> str:
    return LOGICAL_TO_SUPABASE_TABLE.get(logical_name, logical_name)

