COUNTRY_CONFIG = {
    "アメリカ": {
        "code": "US",
        "marketplace": "eBay US",
        "currency": "USD",
        "fx_base": "USD",
        "fx_target": "JPY",
        "fixed_fee_currency": "USD",
        "risk_notice": "DDP、未着、返品、商標・ブランド表記を公式情報で確認してください。",
    },
    "オーストラリア": {
        "code": "AU",
        "marketplace": "eBay Australia",
        "currency": "AUD",
        "fx_base": "AUD",
        "fx_target": "JPY",
        "fixed_fee_currency": "AUD",
        "risk_notice": "検疫、素材、木材・植物・動物由来素材、DDP可否を公式情報で確認してください。",
    },
}

COUNTRY_OPTIONS = list(COUNTRY_CONFIG.keys())

DEFAULT_FEE_SETTINGS = {
    "アメリカ": {
        "destination_country": "アメリカ",
        "marketplace": "eBay US",
        "final_value_fee_percent": 13.25,
        "international_fee_percent": 1.65,
        "fixed_order_fee": 0.40,
        "fixed_order_fee_currency": "USD",
        "promoted_listing_default_percent": 2.0,
        "exchange_buffer_percent": 3.0,
        "risk_buffer_percent": 3.0,
        "source_url": "",
        "source_note": "初期サンプル値です。必ず公式情報で確認してください。",
        "last_checked_at": None,
    },
    "オーストラリア": {
        "destination_country": "オーストラリア",
        "marketplace": "eBay Australia",
        "final_value_fee_percent": 13.25,
        "international_fee_percent": 1.65,
        "fixed_order_fee": 0.40,
        "fixed_order_fee_currency": "AUD",
        "promoted_listing_default_percent": 2.0,
        "exchange_buffer_percent": 3.0,
        "risk_buffer_percent": 4.0,
        "source_url": "",
        "source_note": "初期サンプル値です。必ず公式情報で確認してください。",
        "last_checked_at": None,
    },
}

DEFAULT_GRADING_RULES = {
    "destination_country": "",
    "grade_a_min_profit_jpy": 1000,
    "grade_a_min_roi_percent": 30.0,
    "grade_a_min_sold_count": 3,
    "grade_b_min_profit_jpy": 700,
    "grade_b_min_roi_percent": 20.0,
    "grade_b_min_sold_count": 1,
    "grade_d_max_profit_jpy": 500,
    "grade_d_max_roi_percent": 15.0,
    "stale_master_warning_days": 30,
}

DEFAULT_SHIPPING_RATES = [
    {
        "destination_country": "アメリカ",
        "service_name": "サンプル小型便",
        "weight_min_g": 0,
        "weight_max_g": 500,
        "shipping_cost_jpy": 1800,
        "tracking": True,
        "insurance": False,
        "ddp_supported": False,
        "source_url": "",
        "note": "デモ用サンプル。実運用前に公式料金へ更新してください。",
        "last_checked_at": None,
    },
    {
        "destination_country": "アメリカ",
        "service_name": "サンプル標準便",
        "weight_min_g": 501,
        "weight_max_g": 1000,
        "shipping_cost_jpy": 2800,
        "tracking": True,
        "insurance": False,
        "ddp_supported": False,
        "source_url": "",
        "note": "デモ用サンプル。実運用前に公式料金へ更新してください。",
        "last_checked_at": None,
    },
    {
        "destination_country": "オーストラリア",
        "service_name": "サンプル小型便",
        "weight_min_g": 0,
        "weight_max_g": 500,
        "shipping_cost_jpy": 1900,
        "tracking": True,
        "insurance": False,
        "ddp_supported": False,
        "source_url": "",
        "note": "デモ用サンプル。実運用前に公式料金へ更新してください。",
        "last_checked_at": None,
    },
    {
        "destination_country": "オーストラリア",
        "service_name": "サンプル標準便",
        "weight_min_g": 501,
        "weight_max_g": 1000,
        "shipping_cost_jpy": 3000,
        "tracking": True,
        "insurance": False,
        "ddp_supported": False,
        "source_url": "",
        "note": "デモ用サンプル。実運用前に公式料金へ更新してください。",
        "last_checked_at": None,
    },
]

RISK_FLAGS = [
    {"key": "character_pattern", "label": "キャラクター柄", "category": "権利・ブランド", "points": 3, "severity": "medium"},
    {"key": "brand_logo", "label": "ブランドロゴ", "category": "権利・ブランド", "points": 4, "severity": "high"},
    {"key": "trademark_risk", "label": "商標リスクあり", "category": "権利・ブランド", "points": 5, "severity": "high"},
    {"key": "authenticity_needed", "label": "真贋確認が必要", "category": "権利・ブランド", "points": 5, "severity": "high"},
    {"key": "liquid", "label": "液体", "category": "配送・検疫", "points": 5, "severity": "high"},
    {"key": "food", "label": "食品", "category": "配送・検疫", "points": 5, "severity": "high"},
    {"key": "battery", "label": "電池", "category": "配送・検疫", "points": 5, "severity": "high"},
    {"key": "magnet", "label": "磁石", "category": "配送・検疫", "points": 3, "severity": "medium"},
    {"key": "knife", "label": "刃物", "category": "配送・検疫", "points": 5, "severity": "high"},
    {"key": "fragile", "label": "割れ物", "category": "配送・検疫", "points": 3, "severity": "medium"},
    {"key": "plant_piece", "label": "植物片", "category": "配送・検疫", "points": 5, "severity": "high"},
    {"key": "pressed_flower", "label": "押し花", "category": "配送・検疫", "points": 5, "severity": "high"},
    {"key": "wood", "label": "木材", "category": "配送・検疫", "points": 5, "severity": "high"},
    {"key": "leather", "label": "革", "category": "素材", "points": 3, "severity": "medium"},
    {"key": "wool", "label": "ウール", "category": "素材", "points": 3, "severity": "medium"},
    {"key": "animal_origin", "label": "動物由来素材", "category": "素材", "points": 5, "severity": "high"},
    {"key": "used_item", "label": "中古品", "category": "状態", "points": 1, "severity": "low"},
    {"key": "odor_mold_stain", "label": "臭い・カビ・汚れリスク", "category": "状態", "points": 3, "severity": "medium"},
    {"key": "large_size", "label": "サイズが大きい", "category": "サイズ・重量", "points": 4, "severity": "high"},
    {"key": "heavy_weight", "label": "重量が重い", "category": "サイズ・重量", "points": 4, "severity": "high"},
    {"key": "unknown_material", "label": "素材不明", "category": "素材", "points": 4, "severity": "high"},
    {"key": "no_made_in_japan", "label": "日本製表記なし", "category": "表示", "points": 2, "severity": "low"},
]

HIGH_RISK_KEYS = {item["key"] for item in RISK_FLAGS if item["severity"] == "high"}
SEVERE_D_KEYS = {
    "trademark_risk",
    "brand_logo",
    "authenticity_needed",
    "liquid",
    "food",
    "battery",
    "knife",
    "plant_piece",
    "pressed_flower",
    "wood",
    "animal_origin",
}

RISK_LEVEL_LABELS = {
    "low": "低",
    "medium": "中",
    "high": "高",
}

GRADE_ORDER = {"A": 1, "B": 2, "C": 3, "D": 4, "送料未登録": 5, "未計算": 6}

