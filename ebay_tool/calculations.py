from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from .constants import (
    COUNTRY_CONFIG,
    DEFAULT_GRADING_RULES,
    HIGH_RISK_KEYS,
    RISK_FLAGS,
    RISK_LEVEL_LABELS,
    SEVERE_D_KEYS,
)


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialize_date(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def calculate_fx_rate(raw_rate: float, buffer_percent: float) -> float:
    """円高側に倒した計算用レートを返す."""
    raw_rate = to_float(raw_rate)
    buffer_percent = max(0.0, to_float(buffer_percent))
    return round(raw_rate * (1 - buffer_percent / 100), 4)


def risk_flag_labels(risk_flags: dict[str, bool]) -> list[str]:
    labels = []
    for item in RISK_FLAGS:
        if risk_flags.get(item["key"]):
            labels.append(item["label"])
    return labels


def calculate_risk(
    risk_flags: dict[str, bool],
    destination_country: str,
    packed_weight_g: int,
    length_cm: float,
    width_cm: float,
    height_cm: float,
) -> dict[str, Any]:
    score = 0
    warnings: list[str] = []
    checked_high_risk: list[str] = []
    checked_severe_risk: list[str] = []

    by_key = {item["key"]: item for item in RISK_FLAGS}
    for key, checked in risk_flags.items():
        if not checked or key not in by_key:
            continue
        item = by_key[key]
        score += to_int(item["points"])
        if item["severity"] == "high":
            checked_high_risk.append(item["label"])
        if key in SEVERE_D_KEYS:
            checked_severe_risk.append(item["label"])

    if packed_weight_g >= 2000 and not risk_flags.get("heavy_weight"):
        score += 2
        warnings.append("梱包後重量が2kg以上です。送料・破損・返品リスクを追加確認してください。")

    longest_side = max(to_float(length_cm), to_float(width_cm), to_float(height_cm))
    total_size = to_float(length_cm) + to_float(width_cm) + to_float(height_cm)
    if (longest_side >= 60 or total_size >= 120) and not risk_flags.get("large_size"):
        score += 2
        warnings.append("サイズが大きめです。送料マスタと配送可否を公式情報で確認してください。")

    if destination_country == "オーストラリア":
        quarantine_keys = {"food", "plant_piece", "pressed_flower", "wood", "leather", "wool", "animal_origin"}
        if any(risk_flags.get(key) for key in quarantine_keys):
            warnings.append("オーストラリア向けは検疫・素材制限の確認が必要です。")

    if destination_country == "アメリカ":
        warnings.append("アメリカ向けはDDP、未着、返品、商標表記を最終確認してください。")

    if score <= 3:
        level = "low"
    elif score <= 8:
        level = "medium"
    else:
        level = "high"

    return {
        "risk_score": score,
        "risk_level": level,
        "risk_level_label": RISK_LEVEL_LABELS[level],
        "high_risk_labels": checked_high_risk,
        "severe_risk_labels": checked_severe_risk,
        "warnings": warnings,
    }


def select_shipping_rate(
    destination_country: str,
    packed_weight_g: int,
    shipping_rates: list[dict[str, Any]],
) -> dict[str, Any] | None:
    matched = []
    for rate in shipping_rates:
        if rate.get("destination_country") != destination_country:
            continue
        min_g = to_int(rate.get("weight_min_g"))
        max_g = to_int(rate.get("weight_max_g"))
        if min_g <= packed_weight_g <= max_g:
            matched.append(rate)
    if not matched:
        return None
    return sorted(matched, key=lambda row: to_int(row.get("shipping_cost_jpy")))[0]


def normalize_rules(raw_rules: dict[str, Any] | None, destination_country: str) -> dict[str, Any]:
    rules = DEFAULT_GRADING_RULES.copy()
    if raw_rules:
        rules.update({k: v for k, v in raw_rules.items() if v is not None})
    rules["destination_country"] = destination_country
    return rules


def grade_candidate(
    *,
    expected_profit_jpy: int,
    roi_percent: float,
    sold_count_90d: int,
    risk_level: str,
    severe_risk_labels: list[str],
    high_risk_labels: list[str],
    packed_weight_g: int,
    rules: dict[str, Any],
) -> tuple[str, str]:
    d_profit = to_int(rules.get("grade_d_max_profit_jpy"), 500)
    d_roi = to_float(rules.get("grade_d_max_roi_percent"), 15)

    if expected_profit_jpy < 0:
        return "D", "想定赤字のため仕入れ不可です。"
    if expected_profit_jpy < d_profit:
        return "D", f"利益が{d_profit:,}円未満のため安全側でD判定です。"
    if roi_percent < d_roi:
        return "D", f"ROIが{d_roi:.1f}%未満のため安全側でD判定です。"
    if severe_risk_labels:
        return "D", "高リスク項目があるため、利益が出てもD判定です。"
    if risk_level == "high" or high_risk_labels:
        return "C", "高めのリスクがあるため追加調査が必要です。"

    a_profit = to_int(rules.get("grade_a_min_profit_jpy"), 1000)
    a_roi = to_float(rules.get("grade_a_min_roi_percent"), 30)
    a_sold = to_int(rules.get("grade_a_min_sold_count"), 3)
    b_profit = to_int(rules.get("grade_b_min_profit_jpy"), 700)
    b_roi = to_float(rules.get("grade_b_min_roi_percent"), 20)
    b_sold = to_int(rules.get("grade_b_min_sold_count"), 1)

    if (
        expected_profit_jpy >= a_profit
        and roi_percent >= a_roi
        and sold_count_90d >= a_sold
        and risk_level == "low"
        and packed_weight_g <= 1000
    ):
        return "A", "利益・ROI・Sold実績・リスクが揃っています。小ロット仕入れ候補です。"

    if expected_profit_jpy >= b_profit and roi_percent >= b_roi and sold_count_90d >= b_sold and risk_level in {"low", "medium"}:
        return "B", "少量で検証するなら候補になります。公式情報と実Soldの目視確認をしてください。"

    return "C", "利益、ROI、Sold実績、またはリスクに弱い点があります。追加調査が必要です。"


def calculate_profit(
    candidate: dict[str, Any],
    fee_setting: dict[str, Any],
    fx_rate: dict[str, Any] | None,
    shipping_rates: list[dict[str, Any]],
    grading_rules: dict[str, Any] | None,
) -> dict[str, Any]:
    destination_country = candidate.get("destination_country") or "アメリカ"
    config = COUNTRY_CONFIG[destination_country]
    warnings: list[str] = []

    purchase_price_jpy = to_int(candidate.get("purchase_price_jpy"))
    domestic_shipping_jpy = to_int(candidate.get("domestic_shipping_jpy"))
    packaging_cost_jpy = to_int(candidate.get("packaging_cost_jpy"))
    packed_weight_g = to_int(candidate.get("packed_weight_g"))
    expected_sale_price = to_float(candidate.get("expected_sale_price"))
    sold_count_90d = to_int(candidate.get("sold_count_90d"))
    promoted_percent = candidate.get("promoted_listing_percent")
    if promoted_percent is None:
        promoted_percent = fee_setting.get("promoted_listing_default_percent", 0)
    promoted_percent = to_float(promoted_percent)

    purchase_total_jpy = purchase_price_jpy + domestic_shipping_jpy

    if purchase_total_jpy <= 0:
        warnings.append("仕入れ総額が0円です。仕入れ価格と国内送料を確認してください。")
    if expected_sale_price <= 0:
        warnings.append("想定販売価格が未入力です。")
    if packed_weight_g <= 0:
        warnings.append("梱包後重量が未入力です。送料判定ができません。")

    risk = calculate_risk(
        candidate.get("risk_flags") or {},
        destination_country,
        packed_weight_g,
        to_float(candidate.get("length_cm")),
        to_float(candidate.get("width_cm")),
        to_float(candidate.get("height_cm")),
    )
    warnings.extend(risk["warnings"])

    selected_shipping = select_shipping_rate(destination_country, packed_weight_g, shipping_rates)
    if not selected_shipping:
        warnings.append("送料未登録です。販売国と梱包後重量に合う送料マスタを登録してください。")
        return {
            "calculation_complete": False,
            "grade": "送料未登録",
            "judge_comment": "送料が未登録のため、利益計算を完了できません。",
            "warnings": warnings,
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "risk_level_label": risk["risk_level_label"],
            "high_risk_labels": risk["high_risk_labels"],
            "severe_risk_labels": risk["severe_risk_labels"],
            "shipping_rate": None,
            "shipping_cost_jpy": None,
        }

    if not fx_rate:
        warnings.append("為替レートが未取得です。為替更新を実行してください。")
        return {
            "calculation_complete": False,
            "grade": "未計算",
            "judge_comment": "為替レートがないため、利益計算を完了できません。",
            "warnings": warnings,
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "risk_level_label": risk["risk_level_label"],
            "high_risk_labels": risk["high_risk_labels"],
            "severe_risk_labels": risk["severe_risk_labels"],
            "shipping_rate": selected_shipping,
            "shipping_cost_jpy": to_int(selected_shipping.get("shipping_cost_jpy")),
        }

    raw_rate = to_float(fx_rate.get("raw_rate"))
    calculation_rate = to_float(fx_rate.get("calculation_rate"))
    if calculation_rate <= 0:
        calculation_rate = calculate_fx_rate(raw_rate, to_float(fee_setting.get("exchange_buffer_percent")))

    sale_currency = config["currency"]
    expected_revenue_jpy = round(expected_sale_price * calculation_rate)
    shipping_cost_jpy = to_int(selected_shipping.get("shipping_cost_jpy"))

    final_value_fee_jpy = round(expected_revenue_jpy * to_float(fee_setting.get("final_value_fee_percent")) / 100)
    international_fee_jpy = round(expected_revenue_jpy * to_float(fee_setting.get("international_fee_percent")) / 100)
    fixed_fee_currency = fee_setting.get("fixed_order_fee_currency") or sale_currency
    if fixed_fee_currency == "JPY":
        fixed_order_fee_jpy = round(to_float(fee_setting.get("fixed_order_fee")))
    else:
        fixed_order_fee_jpy = round(to_float(fee_setting.get("fixed_order_fee")) * calculation_rate)

    promoted_listing_fee_jpy = round(expected_revenue_jpy * promoted_percent / 100)
    risk_buffer_jpy = round(expected_revenue_jpy * to_float(fee_setting.get("risk_buffer_percent")) / 100)

    ebay_fee_total_jpy = final_value_fee_jpy + international_fee_jpy + fixed_order_fee_jpy
    total_cost_jpy = (
        purchase_total_jpy
        + shipping_cost_jpy
        + packaging_cost_jpy
        + ebay_fee_total_jpy
        + promoted_listing_fee_jpy
        + risk_buffer_jpy
    )
    expected_profit_jpy = expected_revenue_jpy - total_cost_jpy
    roi_percent = round((expected_profit_jpy / purchase_total_jpy * 100), 1) if purchase_total_jpy > 0 else 0.0
    profit_margin_percent = round((expected_profit_jpy / expected_revenue_jpy * 100), 1) if expected_revenue_jpy > 0 else 0.0

    if not selected_shipping.get("tracking"):
        warnings.append("追跡なしの配送です。未着リスクを高めに見てください。")
    if not selected_shipping.get("ddp_supported") and destination_country == "アメリカ":
        warnings.append("DDP非対応の配送です。購入者負担や返品リスクを確認してください。")

    rules = normalize_rules(grading_rules, destination_country)
    grade, judge_comment = grade_candidate(
        expected_profit_jpy=expected_profit_jpy,
        roi_percent=roi_percent,
        sold_count_90d=sold_count_90d,
        risk_level=risk["risk_level"],
        severe_risk_labels=risk["severe_risk_labels"],
        high_risk_labels=risk["high_risk_labels"],
        packed_weight_g=packed_weight_g,
        rules=rules,
    )

    return {
        "calculation_complete": True,
        "sale_currency": sale_currency,
        "purchase_total_jpy": purchase_total_jpy,
        "expected_revenue_jpy": expected_revenue_jpy,
        "shipping_cost_jpy": shipping_cost_jpy,
        "shipping_rate": selected_shipping,
        "final_value_fee_jpy": final_value_fee_jpy,
        "international_fee_jpy": international_fee_jpy,
        "fixed_order_fee_jpy": fixed_order_fee_jpy,
        "ebay_fee_total_jpy": ebay_fee_total_jpy,
        "promoted_listing_fee_jpy": promoted_listing_fee_jpy,
        "risk_buffer_jpy": risk_buffer_jpy,
        "total_cost_jpy": total_cost_jpy,
        "expected_profit_jpy": expected_profit_jpy,
        "roi_percent": roi_percent,
        "profit_margin_percent": profit_margin_percent,
        "raw_fx_rate": raw_rate,
        "calculation_fx_rate": calculation_rate,
        "risk_score": risk["risk_score"],
        "risk_level": risk["risk_level"],
        "risk_level_label": risk["risk_level_label"],
        "high_risk_labels": risk["high_risk_labels"],
        "severe_risk_labels": risk["severe_risk_labels"],
        "grade": grade,
        "judge_comment": judge_comment,
        "warnings": warnings,
    }


def build_product_payload(candidate: dict[str, Any], calculation: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "updated_at": now_iso(),
        "name": candidate.get("name", "").strip(),
        "source_url": candidate.get("source_url", "").strip(),
        "purchase_price_jpy": to_int(candidate.get("purchase_price_jpy")),
        "domestic_shipping_jpy": to_int(candidate.get("domestic_shipping_jpy")),
        "packaging_cost_jpy": to_int(candidate.get("packaging_cost_jpy")),
        "item_weight_g": to_int(candidate.get("item_weight_g")),
        "packed_weight_g": to_int(candidate.get("packed_weight_g")),
        "length_cm": to_float(candidate.get("length_cm")),
        "width_cm": to_float(candidate.get("width_cm")),
        "height_cm": to_float(candidate.get("height_cm")),
        "destination_country": candidate.get("destination_country"),
        "sale_currency": calculation.get("sale_currency") or COUNTRY_CONFIG[candidate.get("destination_country")]["currency"],
        "expected_sale_price": to_float(candidate.get("expected_sale_price")),
        "sold_count_90d": to_int(candidate.get("sold_count_90d")),
        "competitor_count": to_int(candidate.get("competitor_count")),
        "category": candidate.get("category", "").strip(),
        "promoted_listing_percent": to_float(candidate.get("promoted_listing_percent")),
        "memo": candidate.get("memo", "").strip(),
        "risk_flags": candidate.get("risk_flags") or {},
        "risk_score": to_int(calculation.get("risk_score")),
        "calculated_fx_rate": calculation.get("raw_fx_rate"),
        "calculation_fx_rate": calculation.get("calculation_fx_rate"),
        "shipping_cost_jpy": calculation.get("shipping_cost_jpy"),
        "total_cost_jpy": calculation.get("total_cost_jpy"),
        "expected_revenue_jpy": calculation.get("expected_revenue_jpy"),
        "expected_profit_jpy": calculation.get("expected_profit_jpy"),
        "roi_percent": calculation.get("roi_percent"),
        "profit_margin_percent": calculation.get("profit_margin_percent"),
        "grade": calculation.get("grade"),
        "warnings": calculation.get("warnings") or [],
    }
    return payload


def build_chatgpt_prompt(product: dict[str, Any]) -> str:
    risk_flags = product.get("risk_flags") or {}
    warning_lines = product.get("warnings") or []
    risk_labels = risk_flag_labels(risk_flags)
    sale_currency = product.get("sale_currency") or COUNTRY_CONFIG[product.get("destination_country", "アメリカ")]["currency"]

    return f"""以下の商品を、eBay輸出初心者が少量仕入れしてよいか厳密に検証してください。

前提:
- スクレイピングや自動出品は使わず、公式情報と目視確認を前提にしてください。
- 利益が基準ギリギリ、送料・手数料・配送可否・規約適合性に不確実性がある場合は安全側に判断してください。
- 最終判断前にeBay公式手数料、配送会社の公式料金、禁制品・検疫・DDP・商標リスクを確認する前提です。

商品情報:
- 商品名: {product.get("name", "")}
- 仕入れURL: {product.get("source_url", "")}
- 仕入れ価格: {product.get("purchase_price_jpy", 0):,}円
- 国内送料: {product.get("domestic_shipping_jpy", 0):,}円
- 梱包費: {product.get("packaging_cost_jpy", 0):,}円
- 想定販売国: {product.get("destination_country", "")}
- 想定販売価格: {product.get("expected_sale_price", 0)} {sale_currency}
- 商品重量: {product.get("item_weight_g", 0)}g
- 梱包後重量: {product.get("packed_weight_g", 0)}g
- サイズ: {product.get("length_cm", 0)} x {product.get("width_cm", 0)} x {product.get("height_cm", 0)} cm
- Sold実績: {product.get("sold_count_90d", 0)}件
- 競合数: {product.get("competitor_count", 0)}件
- カテゴリ: {product.get("category", "")}
- リスクチェック: {", ".join(risk_labels) if risk_labels else "該当なし"}

計算結果:
- 判定: {product.get("grade", "")}
- 売上JPY: {product.get("expected_revenue_jpy") or 0:,}円
- 送料: {product.get("shipping_cost_jpy") or 0:,}円
- 総コスト: {product.get("total_cost_jpy") or 0:,}円
- 想定利益: {product.get("expected_profit_jpy") or 0:,}円
- ROI: {product.get("roi_percent") or 0}%
- 利益率: {product.get("profit_margin_percent") or 0}%
- リスクスコア: {product.get("risk_score") or 0}
- 警告: {", ".join(warning_lines) if warning_lines else "なし"}

依頼:
1. この商品を初心者が少量仕入れしてよいか、A/B/C/Dで再判定してください。
2. 利益計算で見落としやすい費用を指摘してください。
3. 配送・検疫・商標・真贋・返品のリスクを確認してください。
4. 仕入れる場合の最大仕入れ価格と、見送るべき条件を具体的に出してください。
"""

