from __future__ import annotations

from datetime import date, datetime, timezone
from html import escape
from typing import Any

import streamlit as st

from ebay_tool import local_db
from ebay_tool.calculations import (
    build_product_payload,
    calculate_fx_rate,
    calculate_profit,
    now_iso,
    serialize_date,
    to_float,
    to_int,
)
from ebay_tool.constants import (
    COUNTRY_CONFIG,
    COUNTRY_OPTIONS,
    DEFAULT_FEE_SETTINGS,
    DEFAULT_GRADING_RULES,
    DEFAULT_SHIPPING_RATES,
)
from ebay_tool.db import fetch_rows, get_supabase_client, insert_row, update_row, upsert_row
from ebay_tool.fx import build_fx_payload, fetch_rate_from_frankfurter


COUNTRY_AU = "オーストラリア"
COUNTRY_US = "アメリカ"
COMPARISON_META_KEY = "_country_comparison"
DEFAULT_PACKAGING_COST_JPY = 150
DEFAULT_COMPARISON_WEIGHT_G = 500
STORE_CHECK_NOTICE = (
    "店頭チェック：偽物・非公式・素材不明・食品・液体・香り付き・電池入り・"
    "植物/動物/木竹素材・重い/大きい/壊れやすい商品は保留。判断に迷うものは仕入れない。"
)

RISK_GUIDE_SECTIONS = [
    {
        "title": "権利・ブランドリスク",
        "red": [
            "偽物、コピー品、レプリカ、非公式グッズに見える",
            "メーカー名、JAN、型番、販売元表記がないキャラクター商品",
            "「〇〇風」「〇〇タイプ」「互換」「パロディ」表記がある",
            "海賊版ゲーム、改造ROM、コピーソフト、ダウンロードコード、アカウント商品",
        ],
        "yellow": [
            "ディズニー、ジブリ、ポケモン、マリオ、サンリオなどの有名IP公式品",
            "非売品、ノベルティ、キャンペーン品",
            "中古ゲーム、中古DVDなど、動作・地域・言語説明が必要な商品",
        ],
    },
    {
        "title": "素材リスク",
        "red": [
            "食品、飲料、茶葉、粉末、サプリ、種、木の実",
            "ドライフラワー、押し花、植物片、葉、枝、苔",
            "木、竹、藁、籐、コルク、未加工っぽい自然素材",
            "革、毛皮、羽、骨、角、貝殻など動物由来素材",
            "香水、液体、スプレー、アルコール類",
            "リチウム電池、磁石入り",
            "中古でカビ、虫、強い臭い、汚れがある",
        ],
        "yellow": [
            "素材表示がない",
            "「天然素材」「自然素材」とだけ書かれている",
            "革風、木製風、ウール、絹など素材が曖昧",
            "和紙や紙製品に、植物片・木・竹・革風の飾りがある",
            "匂い付き文具、香り付きカード、アロマ系雑貨",
        ],
    },
    {
        "title": "店頭で見える配送・検疫リスク",
        "red": [
            "片手で持って明らかに重い、または外箱が大きい",
            "ガラス、陶器、鏡、薄いプラスチックなど壊れやすい",
            "液漏れ、粉漏れ、破裂の可能性がある",
            "箱が潰れている、開封済み、テープ跡がある",
            "英語の商品名・素材を簡単に説明できない",
            "中身が外から判断できない、または検品漏れが起きそう",
            "鋭利な金属、刃物、工具、針状パーツがある",
        ],
        "yellow": [
            "梱包すると厚み・重さがかなり増えそう",
            "角潰れ・箱潰れでクレームになりそう",
            "パーツ数が多く、欠品確認が面倒",
            "説明書や表示が日本語だけで、海外購入者が誤解しそう",
            "オーストラリア向けで、植物・動物・木竹素材に少しでも見える",
            "アメリカ向けで、食品・液体・電池・電子部品に少しでも見える",
        ],
    },
]

COUNTRY_RISK_NOTES = {
    COUNTRY_AU: "オーストラリア向け補足：植物・動物・木竹素材に見えるものは保留。紙・綿・プラスチック・金属とはっきり分かる軽量品を優先。",
    COUNTRY_US: "アメリカ向け補足：食品・液体・電池入り・重い商品は保留。品名と素材を簡単に説明できる軽量品を優先。",
}


st.set_page_config(
    page_title="eBay仕入れ判定・利益計算",
    layout="centered",
    initial_sidebar_state="collapsed",
)


def apply_mobile_css() -> None:
    st.markdown(
        """
        <style>
        .block-container { padding: 1rem 0.8rem 2rem; max-width: 760px; }
        div.stButton > button, div.stDownloadButton > button {
            width: 100%;
            min-height: 3rem;
            font-weight: 700;
        }
        [data-testid="stMetricValue"] { font-size: 1.7rem; }
        .small-note { color: #666; font-size: 0.86rem; }
        .card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 0.9rem;
            margin: 0.75rem 0;
            background: #fff;
        }
        .grade-A, .grade-B, .grade-C, .grade-D, .grade-送料未登録, .grade-未計算 {
            border-radius: 8px;
            padding: 0.7rem 0.9rem;
            font-size: 1.25rem;
            font-weight: 800;
            text-align: center;
            margin: 0.6rem 0;
        }
        .grade-A { background: #e6f4ea; color: #0d652d; border: 1px solid #b7dfc2; }
        .grade-B { background: #eef7e1; color: #3b6b02; border: 1px solid #cbe6a1; }
        .grade-C { background: #fff7d6; color: #795000; border: 1px solid #f0d36a; }
        .grade-D, .grade-送料未登録, .grade-未計算 { background: #fde8e7; color: #a50e0e; border: 1px solid #f6b4b1; }
        .warn { background: #fff7d6; border-left: 5px solid #d9a400; padding: 0.7rem; border-radius: 6px; margin: 0.4rem 0; }
        .danger { background: #fde8e7; border-left: 5px solid #d93025; padding: 0.7rem; border-radius: 6px; margin: 0.4rem 0; }
        .ok { background: #e6f4ea; border-left: 5px solid #188038; padding: 0.7rem; border-radius: 6px; margin: 0.4rem 0; }
        .summary-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 0.85rem;
            margin: 0.5rem 0;
            background: #fff;
        }
        .summary-label { color: #666; font-size: 0.85rem; margin-bottom: 0.15rem; }
        .summary-value { font-size: 1.35rem; font-weight: 800; line-height: 1.25; }
        .risk-guide ul { margin: 0.35rem 0 0 1.1rem; padding: 0; }
        .risk-guide li { margin: 0.28rem 0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def yen(value: Any) -> str:
    if value is None:
        return "-"
    return f"{to_int(value):,}円"


def pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{to_float(value):.1f}%"


def fx_calculation_rate(contexts: dict[str, dict[str, Any]], country: str) -> float:
    fx_rate = (contexts.get(country) or {}).get("fx_rate") or {}
    return to_float(fx_rate.get("calculation_rate"))


def sale_price_in_currency(expected_sale_price_jpy: Any, country: str, contexts: dict[str, dict[str, Any]]) -> float:
    rate = fx_calculation_rate(contexts, country)
    if rate <= 0:
        return 0.0
    return round(to_float(expected_sale_price_jpy) / rate, 2)


def converted_sale_price_text(expected_sale_price_jpy: Any, country: str, contexts: dict[str, dict[str, Any]]) -> str:
    currency = COUNTRY_CONFIG[country]["currency"]
    converted = sale_price_in_currency(expected_sale_price_jpy, country, contexts)
    rate = fx_calculation_rate(contexts, country)
    if rate <= 0:
        return f"{currency}: 為替未取得"
    return f"{converted:,.2f} {currency}"


def guide_box(label: str, items: list[str], css_class: str) -> None:
    bullet_items = "".join(f"<li>{escape(item)}</li>" for item in items)
    st.markdown(
        f"""
        <div class="risk-guide {css_class}">
            <strong>{escape(label)}</strong>
            <ul>{bullet_items}</ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_store_check_guide(country: str) -> None:
    for section in RISK_GUIDE_SECTIONS:
        with st.expander(section["title"], expanded=False):
            guide_box("赤信号：原則仕入れない", section["red"], "danger")
            guide_box("黄信号：その場では保留", section["yellow"], "warn")
            if section.get("note"):
                st.info(section["note"])
            if section["title"] == "店頭で見える配送・検疫リスク":
                st.info(COUNTRY_RISK_NOTES.get(country, COUNTRY_RISK_NOTES[COUNTRY_AU]))


def risk_guide_prompt_text(country: str) -> str:
    lines = [STORE_CHECK_NOTICE, ""]
    for section in RISK_GUIDE_SECTIONS:
        lines.append(f"■ {section['title']}")
        lines.append("赤信号：原則仕入れない")
        lines.extend(f"- {item}" for item in section["red"])
        lines.append("黄信号：その場では保留")
        lines.extend(f"- {item}" for item in section["yellow"])
        if section.get("note"):
            lines.append(f"補足: {section['note']}")
        if section["title"] == "店頭で見える配送・検疫リスク":
            lines.append(f"販売国別補足: {COUNTRY_RISK_NOTES.get(country, COUNTRY_RISK_NOTES[COUNTRY_AU])}")
        lines.append("")
    return "\n".join(lines).strip()


def normalize_fee_setting(row: dict[str, Any] | None, country: str) -> dict[str, Any]:
    setting = DEFAULT_FEE_SETTINGS[country].copy()
    if row:
        setting.update({k: v for k, v in row.items() if v is not None})
    return setting


def normalize_grading_rule(row: dict[str, Any] | None, country: str) -> dict[str, Any]:
    rule = DEFAULT_GRADING_RULES.copy()
    rule["destination_country"] = country
    if row:
        rule.update({k: v for k, v in row.items() if v is not None})
    return rule


def load_fee_setting(client: Any | None, country: str) -> dict[str, Any]:
    rows = fetch_rows(client, "fee_settings", filters={"destination_country": country}, limit=1)
    return normalize_fee_setting(rows[0] if rows else None, country)


def load_grading_rule(client: Any | None, country: str) -> dict[str, Any]:
    rows = fetch_rows(client, "grading_rules", filters={"destination_country": country}, limit=1)
    return normalize_grading_rule(rows[0] if rows else None, country)


def load_shipping_rates(client: Any | None, country: str) -> list[dict[str, Any]]:
    rows = fetch_rows(client, "shipping_rate_master", filters={"destination_country": country}, order="weight_min_g")
    if rows:
        return rows
    if client is None:
        return [row for row in DEFAULT_SHIPPING_RATES if row["destination_country"] == country]
    return []


def load_fx_rate(client: Any | None, base_currency: str, target_currency: str, fee_setting: dict[str, Any]) -> dict[str, Any] | None:
    rows = fetch_rows(
        client,
        "fx_rates",
        filters={"base_currency": base_currency, "target_currency": target_currency},
        order="fetched_at",
        desc=True,
        limit=1,
    )
    if rows:
        return rows[0]
    session_key = f"fx_{base_currency}_{target_currency}"
    if session_key in st.session_state:
        return st.session_state[session_key]
    return None


def load_products(client: Any | None) -> list[dict[str, Any]]:
    return fetch_rows(client, "product_candidates", order="updated_at", desc=True)


def parse_date_value(value: Any) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(value)
            except ValueError:
                return date.today()
    return date.today()


def stale_days(value: Any) -> int | None:
    if not value:
        return None
    checked = parse_date_value(value)
    return (date.today() - checked).days


def show_master_warnings(fee_setting: dict[str, Any], shipping_rates: list[dict[str, Any]], grading_rule: dict[str, Any]) -> None:
    warning_days = to_int(grading_rule.get("stale_master_warning_days"), 30)
    fee_age = stale_days(fee_setting.get("last_checked_at"))
    if fee_age is None:
        st.warning("手数料マスタの最終確認日が未登録です。")
    elif fee_age > warning_days:
        st.warning(f"手数料マスタが{fee_age}日更新されていません。公式情報を確認してください。")

    if not shipping_rates:
        st.error("送料マスタが未登録です。利益計算は完了できません。")
        return
    shipping_dates = [stale_days(row.get("last_checked_at")) for row in shipping_rates]
    valid_ages = [age for age in shipping_dates if age is not None]
    if not valid_ages:
        st.warning("送料マスタの最終確認日が未登録です。")
    elif max(valid_ages) > warning_days:
        st.warning(f"送料マスタに{max(valid_ages)}日以上未確認の行があります。公式料金を確認してください。")


def grade_badge(grade: str) -> None:
    safe_grade = grade or "未計算"
    st.markdown(f'<div class="grade-{safe_grade}">判定: {safe_grade}</div>', unsafe_allow_html=True)


def show_result_card(calculation: dict[str, Any]) -> None:
    st.subheader("利益計算結果")
    grade_badge(calculation.get("grade", "未計算"))
    st.caption(calculation.get("judge_comment", ""))

    col1, col2 = st.columns(2)
    col1.metric("想定利益", yen(calculation.get("expected_profit_jpy")))
    col2.metric("ROI", pct(calculation.get("roi_percent")))
    col1.metric("利益率", pct(calculation.get("profit_margin_percent")))
    col2.metric("リスク", calculation.get("risk_level_label", "-"))

    with st.expander("内訳", expanded=True):
        st.write(f"売上JPY: {yen(calculation.get('expected_revenue_jpy'))}")
        st.write(f"総コスト: {yen(calculation.get('total_cost_jpy'))}")
        st.write(f"送料: {yen(calculation.get('shipping_cost_jpy'))}")
        st.write(f"eBay手数料合計: {yen(calculation.get('ebay_fee_total_jpy'))}")
        st.write(f"広告費: {yen(calculation.get('promoted_listing_fee_jpy'))}")
        st.write(f"返品・未着バッファ: {yen(calculation.get('risk_buffer_jpy'))}")
        if calculation.get("calculation_fx_rate"):
            st.write(f"為替: 実レート {calculation.get('raw_fx_rate'):.4f} / 計算用 {calculation.get('calculation_fx_rate'):.4f}")
        shipping = calculation.get("shipping_rate")
        if shipping:
            st.write(f"配送方法: {shipping.get('service_name')} ({shipping.get('weight_min_g')}g〜{shipping.get('weight_max_g')}g)")

    warnings = calculation.get("warnings") or []
    if warnings:
        st.markdown("#### 警告・確認事項")
        for warning in warnings:
            css = "danger" if "未登録" in warning or "高リスク" in warning or "不可" in warning else "warn"
            st.markdown(f'<div class="{css}">{warning}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="ok">現時点の入力では大きな警告はありません。ただし最終判断前に公式情報を確認してください。</div>', unsafe_allow_html=True)


def load_country_contexts(client: Any | None) -> dict[str, dict[str, Any]]:
    contexts: dict[str, dict[str, Any]] = {}
    for country in [COUNTRY_AU, COUNTRY_US]:
        config = COUNTRY_CONFIG[country]
        fee_setting = load_fee_setting(client, country)
        fx_rate = load_fx_rate(client, config["fx_base"], config["fx_target"], fee_setting)
        if fx_rate:
            expected_rate = calculate_fx_rate(to_float(fx_rate.get("raw_rate")), to_float(fee_setting.get("exchange_buffer_percent")))
            if abs(expected_rate - to_float(fx_rate.get("calculation_rate"))) > 0.0001:
                fx_rate = fx_rate.copy()
                fx_rate["buffer_percent"] = to_float(fee_setting.get("exchange_buffer_percent"))
                fx_rate["calculation_rate"] = expected_rate
        contexts[country] = {
            "config": config,
            "fee_setting": fee_setting,
            "grading_rule": load_grading_rule(client, country),
            "shipping_rates": load_shipping_rates(client, country),
            "fx_rate": fx_rate,
        }
    return contexts


def candidate_meta(row: dict[str, Any] | None) -> dict[str, Any]:
    flags = (row or {}).get("risk_flags") or {}
    meta = flags.get(COMPARISON_META_KEY) if isinstance(flags, dict) else None
    meta = meta.copy() if isinstance(meta, dict) else {}
    if row:
        sale_currency = row.get("sale_currency")
        if "expected_sale_price_jpy" not in meta:
            meta["expected_sale_price_jpy"] = to_int(row.get("expected_revenue_jpy"))
        if "expected_sale_price_aud" not in meta:
            meta["expected_sale_price_aud"] = to_float(row.get("expected_sale_price")) if sale_currency == "AUD" else 0.0
        if "expected_sale_price_usd" not in meta:
            meta["expected_sale_price_usd"] = to_float(row.get("expected_sale_price")) if sale_currency == "USD" else 0.0
    meta.setdefault("expected_sale_price_jpy", 0)
    meta.setdefault("expected_sale_price_aud", 0.0)
    meta.setdefault("expected_sale_price_usd", 0.0)
    meta.setdefault("deleted", False)
    return meta


def risk_flags_with_meta(row: dict[str, Any] | None, meta: dict[str, Any]) -> dict[str, Any]:
    flags = ((row or {}).get("risk_flags") or {}).copy()
    flags[COMPARISON_META_KEY] = meta
    return flags


def is_deleted_candidate(row: dict[str, Any]) -> bool:
    return bool(candidate_meta(row).get("deleted"))


def visible_products(client: Any | None) -> list[dict[str, Any]]:
    return [row for row in load_products(client) if not is_deleted_candidate(row)]


def simple_candidate_base(values: dict[str, Any], country: str, sale_price: float, contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fee_setting = contexts[country]["fee_setting"]
    return {
        "name": values.get("name", ""),
        "source_url": "",
        "purchase_price_jpy": to_int(values.get("purchase_price_jpy")),
        "domestic_shipping_jpy": to_int(values.get("domestic_shipping_jpy")),
        "packaging_cost_jpy": to_int(values.get("packaging_cost_jpy")),
        "item_weight_g": 0,
        "packed_weight_g": DEFAULT_COMPARISON_WEIGHT_G,
        "length_cm": 0,
        "width_cm": 0,
        "height_cm": 0,
        "destination_country": country,
        "expected_sale_price": to_float(sale_price),
        "sold_count_90d": 0,
        "competitor_count": 0,
        "promoted_listing_percent": to_float(fee_setting.get("promoted_listing_default_percent")),
        "category": "",
        "memo": values.get("memo", ""),
        "risk_flags": {},
    }


def calculate_country_comparison(values: dict[str, Any], contexts: dict[str, dict[str, Any]]) -> dict[str, Any]:
    expected_sale_price_jpy = values.get("expected_sale_price_jpy")
    au_sale_price = sale_price_in_currency(expected_sale_price_jpy, COUNTRY_AU, contexts)
    us_sale_price = sale_price_in_currency(expected_sale_price_jpy, COUNTRY_US, contexts)
    au_candidate = simple_candidate_base(values, COUNTRY_AU, au_sale_price, contexts)
    us_candidate = simple_candidate_base(values, COUNTRY_US, us_sale_price, contexts)
    au_calc = calculate_profit(
        au_candidate,
        contexts[COUNTRY_AU]["fee_setting"],
        contexts[COUNTRY_AU]["fx_rate"],
        contexts[COUNTRY_AU]["shipping_rates"],
        contexts[COUNTRY_AU]["grading_rule"],
    )
    us_calc = calculate_profit(
        us_candidate,
        contexts[COUNTRY_US]["fee_setting"],
        contexts[COUNTRY_US]["fx_rate"],
        contexts[COUNTRY_US]["shipping_rates"],
        contexts[COUNTRY_US]["grading_rule"],
    )
    au_profit = to_int(au_calc.get("expected_profit_jpy"), -10**9)
    us_profit = to_int(us_calc.get("expected_profit_jpy"), -10**9)
    both_d = au_calc.get("grade") == "D" and us_calc.get("grade") == "D"
    recommended_country = COUNTRY_AU if au_profit >= us_profit else COUNTRY_US
    recommended_calc = au_calc if recommended_country == COUNTRY_AU else us_calc
    recommended_candidate = au_candidate if recommended_country == COUNTRY_AU else us_candidate
    recommendation = "仕入れ非推奨" if both_d else recommended_country
    return {
        "au_candidate": au_candidate,
        "us_candidate": us_candidate,
        "au": au_calc,
        "us": us_calc,
        "recommended_country": recommended_country,
        "recommended_label": recommendation,
        "recommended_calc": recommended_calc,
        "recommended_candidate": recommended_candidate,
        "profit_difference": abs(au_profit - us_profit) if au_profit > -10**8 and us_profit > -10**8 else None,
    }


def values_from_row(row: dict[str, Any]) -> dict[str, Any]:
    meta = candidate_meta(row)
    return {
        "name": row.get("name", ""),
        "purchase_price_jpy": to_int(row.get("purchase_price_jpy")),
        "domestic_shipping_jpy": to_int(row.get("domestic_shipping_jpy")),
        "packaging_cost_jpy": to_int(row.get("packaging_cost_jpy"), DEFAULT_PACKAGING_COST_JPY),
        "expected_sale_price_jpy": to_int(meta.get("expected_sale_price_jpy"), to_int(row.get("expected_revenue_jpy"))),
        "memo": row.get("memo", "") or "",
    }


def meta_from_values(values: dict[str, Any], comparison: dict[str, Any], deleted: bool = False) -> dict[str, Any]:
    return {
        "expected_sale_price_jpy": to_int(values.get("expected_sale_price_jpy")),
        "expected_sale_price_aud": to_float(comparison["au_candidate"].get("expected_sale_price")),
        "expected_sale_price_usd": to_float(comparison["us_candidate"].get("expected_sale_price")),
        "recommended_label": comparison.get("recommended_label"),
        "au_profit_jpy": comparison["au"].get("expected_profit_jpy"),
        "us_profit_jpy": comparison["us"].get("expected_profit_jpy"),
        "au_roi_percent": comparison["au"].get("roi_percent"),
        "us_roi_percent": comparison["us"].get("roi_percent"),
        "au_grade": comparison["au"].get("grade"),
        "us_grade": comparison["us"].get("grade"),
        "profit_difference_jpy": comparison.get("profit_difference"),
        "deleted": deleted,
    }


def product_payload_from_values(values: dict[str, Any], comparison: dict[str, Any], existing: dict[str, Any] | None = None) -> dict[str, Any]:
    candidate = comparison["recommended_candidate"].copy()
    candidate["memo"] = values.get("memo", "")
    payload = build_product_payload(candidate, comparison["recommended_calc"])
    meta = meta_from_values(values, comparison, deleted=False)
    payload["risk_flags"] = risk_flags_with_meta(existing, meta)
    payload["grade"] = comparison["recommended_calc"].get("grade")
    if comparison.get("recommended_label") == "仕入れ非推奨":
        payload["grade"] = "D"
    return payload


def summary_value(label: str, value: str) -> None:
    st.markdown(
        f'<div class="summary-card"><div class="summary-label">{label}</div><div class="summary-value">{value}</div></div>',
        unsafe_allow_html=True,
    )


def show_comparison_summary(comparison: dict[str, Any]) -> None:
    st.subheader("判定結果")
    summary_value("推奨販売国", str(comparison.get("recommended_label") or "-"))
    col1, col2 = st.columns(2)
    with col1:
        summary_value("オーストラリア利益", yen(comparison["au"].get("expected_profit_jpy")))
        summary_value("AU判定 / ROI", f"{comparison['au'].get('grade', '-')} / {pct(comparison['au'].get('roi_percent'))}")
    with col2:
        summary_value("アメリカ利益", yen(comparison["us"].get("expected_profit_jpy")))
        summary_value("US判定 / ROI", f"{comparison['us'].get('grade', '-')} / {pct(comparison['us'].get('roi_percent'))}")
    summary_value("利益差", yen(comparison.get("profit_difference")))


def show_comparison_details(comparison: dict[str, Any]) -> None:
    with st.expander("詳細な計算内訳", expanded=False):
        st.markdown("#### オーストラリア")
        show_result_card(comparison["au"])
        st.markdown("#### アメリカ")
        show_result_card(comparison["us"])


def build_comparison_prompt(values: dict[str, Any], comparison: dict[str, Any], country: str) -> str:
    return f"""以下の商品を、eBay輸出初心者が少量仕入れしてよいか、利益・リスク・販売国の観点から厳しく判定してください。

商品情報:
- 商品名: {values.get("name", "")}
- 仕入れ価格: {to_int(values.get("purchase_price_jpy")):,}円
- 国内送料: {to_int(values.get("domestic_shipping_jpy")):,}円
- 梱包費: {to_int(values.get("packaging_cost_jpy")):,}円
- 想定販売価格: {to_int(values.get("expected_sale_price_jpy")):,}円
- AUD換算: {comparison["au_candidate"].get("expected_sale_price")} AUD
- USD換算: {comparison["us_candidate"].get("expected_sale_price")} USD

利益比較:
- オーストラリア向け想定利益: {yen(comparison["au"].get("expected_profit_jpy"))}
- オーストラリア向けROI: {pct(comparison["au"].get("roi_percent"))}
- オーストラリア向け判定: {comparison["au"].get("grade", "-")}
- アメリカ向け想定利益: {yen(comparison["us"].get("expected_profit_jpy"))}
- アメリカ向けROI: {pct(comparison["us"].get("roi_percent"))}
- アメリカ向け判定: {comparison["us"].get("grade", "-")}
- 推奨販売国: {comparison.get("recommended_label") or "-"}
- 利益差: {yen(comparison.get("profit_difference"))}

店頭リスク確認ガイド:
{risk_guide_prompt_text(country)}

メモ:
{values.get("memo") or "未記入"}

依頼:
この商品を初心者が少量仕入れしてよいか、利益・リスク・販売国の観点から厳しく判定してください。見送るべき条件と、確認すべき公式情報も具体的に挙げてください。
"""


def render_candidate_form(
    client: Any | None,
    contexts: dict[str, dict[str, Any]],
    *,
    existing: dict[str, Any] | None = None,
    key_prefix: str = "new",
) -> None:
    base = values_from_row(existing) if existing else {
        "name": "",
        "purchase_price_jpy": 0,
        "domestic_shipping_jpy": 0,
        "packaging_cost_jpy": to_int(st.session_state.get("default_packaging_cost_jpy"), DEFAULT_PACKAGING_COST_JPY),
        "expected_sale_price_jpy": 0,
        "memo": "",
    }

    st.markdown("#### 入力")
    name = st.text_input("商品名", value=base["name"], key=f"{key_prefix}_name")
    purchase_price_jpy = st.number_input("仕入れ価格（円）", min_value=0, step=100, value=to_int(base["purchase_price_jpy"]), key=f"{key_prefix}_purchase")
    domestic_shipping_jpy = st.number_input("国内送料（円）", min_value=0, step=100, value=to_int(base["domestic_shipping_jpy"]), key=f"{key_prefix}_domestic")
    price_col, conversion_col = st.columns([2, 1])
    with price_col:
        expected_sale_price_jpy = st.number_input(
            "想定販売価格（円）",
            min_value=0,
            step=100,
            value=to_int(base["expected_sale_price_jpy"]),
            key=f"{key_prefix}_sale_jpy",
        )
    with conversion_col:
        st.metric("AUD換算", converted_sale_price_text(expected_sale_price_jpy, COUNTRY_AU, contexts))
        st.metric("USD換算", converted_sale_price_text(expected_sale_price_jpy, COUNTRY_US, contexts))
    packaging_cost_jpy = st.number_input("梱包費（円）", min_value=0, step=50, value=to_int(base["packaging_cost_jpy"], DEFAULT_PACKAGING_COST_JPY), key=f"{key_prefix}_packaging")
    memo = st.text_area("メモ", value=base["memo"], key=f"{key_prefix}_memo")

    values = {
        "name": name,
        "purchase_price_jpy": purchase_price_jpy,
        "domestic_shipping_jpy": domestic_shipping_jpy,
        "packaging_cost_jpy": packaging_cost_jpy,
        "expected_sale_price_jpy": expected_sale_price_jpy,
        "memo": memo,
    }
    comparison = calculate_country_comparison(values, contexts)
    show_comparison_summary(comparison)
    show_comparison_details(comparison)

    button_label = "変更を保存" if existing else "この候補を保存"
    if st.button(button_label, type="primary", key=f"{key_prefix}_save"):
        if not name.strip():
            st.error("商品名を入力してください。")
            return
        payload = product_payload_from_values(values, comparison, existing)
        if existing:
            payload["updated_at"] = now_iso()
            ok = update_row(client, "product_candidates", str(existing.get("id")), payload)
        else:
            ok = insert_row(client, "product_candidates", payload)
        if ok:
            st.success("商品候補を保存しました。")
            st.session_state.pop("editing_candidate_id", None)
            st.rerun()


def product_judgment_page(client: Any | None, contexts: dict[str, dict[str, Any]], country: str) -> None:
    st.header("商品判定")
    render_store_check_guide(country)
    render_candidate_form(client, contexts, key_prefix="new")


def card_updated_label(row: dict[str, Any]) -> str:
    value = row.get("updated_at") or row.get("created_at") or ""
    return str(value).split("T")[0] if value else "-"


def render_candidate_detail(row: dict[str, Any], values: dict[str, Any], comparison: dict[str, Any], country: str) -> None:
    show_comparison_summary(comparison)
    st.markdown("#### 補足メモ")
    st.write(f"メモ: {values.get('memo') or '未記入'}")
    render_store_check_guide(country)
    show_comparison_details(comparison)


def products_page(client: Any | None, contexts: dict[str, dict[str, Any]], country: str) -> None:
    st.header("候補一覧")
    products = visible_products(client)
    if not products:
        st.info("保存済みの商品候補がありません。")
        return

    sort_by = st.selectbox("並び替え", ["優先度順", "利益差順", "更新日順"])
    prepared = []
    for row in products:
        values = values_from_row(row)
        comparison = calculate_country_comparison(values, contexts)
        prepared.append((row, values, comparison))
    if sort_by == "優先度順":
        prepared.sort(key=lambda item: max(to_int(item[2]["au"].get("expected_profit_jpy")), to_int(item[2]["us"].get("expected_profit_jpy"))), reverse=True)
    elif sort_by == "利益差順":
        prepared.sort(key=lambda item: to_int(item[2].get("profit_difference")), reverse=True)
    else:
        prepared.sort(key=lambda item: item[0].get("updated_at") or item[0].get("created_at") or "", reverse=True)

    st.caption(f"{len(prepared)}件表示")
    for row, values, comparison in prepared:
        row_id = str(row.get("id"))
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown(f"### {values.get('name') or '名称未設定'}")
        st.write(f"仕入れ価格: {yen(values.get('purchase_price_jpy'))}")
        st.write(f"推奨販売国: {comparison.get('recommended_label')}")
        st.write(f"オーストラリア利益: {yen(comparison['au'].get('expected_profit_jpy'))} / 判定 {comparison['au'].get('grade', '-')}")
        st.write(f"アメリカ利益: {yen(comparison['us'].get('expected_profit_jpy'))} / 判定 {comparison['us'].get('grade', '-')}")
        st.write(f"更新日: {card_updated_label(row)}")
        col1, col2 = st.columns(2)
        if col1.button("詳細", key=f"detail_{row_id}"):
            st.session_state["detail_candidate_id"] = row_id
        if col2.button("編集", key=f"edit_{row_id}"):
            st.session_state["editing_candidate_id"] = row_id
        col3, col4 = st.columns(2)
        if col3.button("削除", key=f"delete_{row_id}"):
            st.session_state["delete_candidate_id"] = row_id
        if col4.button("ChatGPT精査プロンプト", key=f"prompt_{row_id}"):
            st.session_state["prompt_candidate_id"] = row_id
        st.markdown("</div>", unsafe_allow_html=True)

        if st.session_state.get("detail_candidate_id") == row_id:
            render_candidate_detail(row, values, comparison, country)
        if st.session_state.get("prompt_candidate_id") == row_id:
            st.text_area("コピー用プロンプト", value=build_comparison_prompt(values, comparison, country), height=420, key=f"prompt_text_{row_id}")
        if st.session_state.get("delete_candidate_id") == row_id:
            st.warning("この候補を削除しますか？")
            dcol1, dcol2 = st.columns(2)
            if dcol1.button("削除する", key=f"confirm_delete_{row_id}", type="primary"):
                meta = candidate_meta(row)
                meta["deleted"] = True
                if update_row(client, "product_candidates", row_id, {"updated_at": now_iso(), "risk_flags": risk_flags_with_meta(row, meta)}):
                    st.success("候補を削除しました。")
                    st.session_state.pop("delete_candidate_id", None)
                    st.rerun()
            if dcol2.button("キャンセル", key=f"cancel_delete_{row_id}"):
                st.session_state.pop("delete_candidate_id", None)
                st.rerun()
        if st.session_state.get("editing_candidate_id") == row_id:
            st.markdown("#### 編集")
            render_candidate_form(client, contexts, existing=row, key_prefix=f"edit_{row_id}")


def fx_page(client: Any | None, country: str, fee_setting: dict[str, Any], fx_rate: dict[str, Any] | None) -> None:
    st.header("為替更新")
    st.caption("無料・APIキー不要のFrankfurter APIからUSD/JPYとAUD/JPYを取得します。失敗時は保存済みレートを使います。")

    pairs = [("USD", "JPY", "アメリカ"), ("AUD", "JPY", "オーストラリア")]
    for base, target, pair_country in pairs:
        pair_fee = load_fee_setting(client, pair_country)
        current = load_fx_rate(client, base, target, pair_fee)
        st.markdown(f"#### {base}/{target}")
        if current:
            st.write(f"実レート: {to_float(current.get('raw_rate')):.4f}")
            st.write(f"為替バッファ: {to_float(current.get('buffer_percent')):.1f}%")
            st.write(f"計算用レート: {to_float(current.get('calculation_rate')):.4f}")
            st.caption(f"最終取得: {current.get('fetched_at') or '未取得'}")
        else:
            st.warning("まだ為替レートがありません。")

    if st.button("為替を更新", type="primary"):
        errors = []
        for base, target, pair_country in pairs:
            try:
                pair_fee = load_fee_setting(client, pair_country)
                fetched = fetch_rate_from_frankfurter(base, target)
                payload = build_fx_payload(
                    base,
                    target,
                    fetched["raw_rate"],
                    to_float(pair_fee.get("exchange_buffer_percent")),
                    fetched["source"],
                )
                session_key = f"fx_{base}_{target}"
                st.session_state[session_key] = payload
                if client is not None:
                    upsert_row(client, "fx_rates", payload, on_conflict="base_currency,target_currency")
            except Exception:
                errors.append(f"{base}/{target}")
        if errors:
            st.warning("取得に失敗した通貨があります。保存済みレートを使ってください: " + ", ".join(errors))
        else:
            st.success("為替レートを更新しました。")
        st.rerun()


def fee_master_form(client: Any | None, country: str, fee_setting: dict[str, Any]) -> None:
    st.markdown("### 手数料マスタ")
    with st.form("fee_master_form"):
        marketplace = st.text_input("marketplace", value=fee_setting.get("marketplace", COUNTRY_CONFIG[country]["marketplace"]))
        final_value_fee_percent = st.number_input("final_value_fee_percent", min_value=0.0, max_value=100.0, step=0.05, value=to_float(fee_setting.get("final_value_fee_percent")))
        international_fee_percent = st.number_input("international_fee_percent", min_value=0.0, max_value=100.0, step=0.05, value=to_float(fee_setting.get("international_fee_percent")))
        fixed_order_fee = st.number_input("fixed_order_fee", min_value=0.0, step=0.01, value=to_float(fee_setting.get("fixed_order_fee")))
        fixed_order_fee_currency = st.selectbox("fixed_order_fee_currency", ["USD", "AUD", "JPY"], index=["USD", "AUD", "JPY"].index(fee_setting.get("fixed_order_fee_currency", COUNTRY_CONFIG[country]["currency"])))
        promoted_listing_default_percent = st.number_input("promoted_listing_default_percent", min_value=0.0, max_value=100.0, step=0.5, value=to_float(fee_setting.get("promoted_listing_default_percent")))
        exchange_buffer_percent = st.number_input("exchange_buffer_percent", min_value=0.0, max_value=30.0, step=0.5, value=to_float(fee_setting.get("exchange_buffer_percent")))
        risk_buffer_percent = st.number_input("risk_buffer_percent", min_value=0.0, max_value=50.0, step=0.5, value=to_float(fee_setting.get("risk_buffer_percent")))
        source_url = st.text_input("source_url", value=fee_setting.get("source_url", "") or "")
        source_note = st.text_area("source_note", value=fee_setting.get("source_note", "") or "")
        last_checked_at = st.date_input("last_checked_at", value=parse_date_value(fee_setting.get("last_checked_at")))
        submitted = st.form_submit_button("手数料マスタを保存", type="primary")
    if submitted:
        payload = {
            "updated_at": now_iso(),
            "destination_country": country,
            "marketplace": marketplace,
            "final_value_fee_percent": final_value_fee_percent,
            "international_fee_percent": international_fee_percent,
            "fixed_order_fee": fixed_order_fee,
            "fixed_order_fee_currency": fixed_order_fee_currency,
            "promoted_listing_default_percent": promoted_listing_default_percent,
            "exchange_buffer_percent": exchange_buffer_percent,
            "risk_buffer_percent": risk_buffer_percent,
            "source_url": source_url,
            "source_note": source_note,
            "last_checked_at": serialize_date(last_checked_at),
        }
        if upsert_row(client, "fee_settings", payload, on_conflict="destination_country"):
            st.success("手数料マスタを保存しました。")
            st.rerun()


def shipping_master_form(client: Any | None, country: str, shipping_rates: list[dict[str, Any]]) -> None:
    st.markdown("### 送料マスタ")
    if shipping_rates:
        for row in shipping_rates:
            st.markdown(
                f"- {row.get('service_name')} / {row.get('weight_min_g')}〜{row.get('weight_max_g')}g / {yen(row.get('shipping_cost_jpy'))} / 最終確認: {row.get('last_checked_at') or '未登録'}"
            )
    else:
        st.warning("この販売国の送料マスタが未登録です。")

    with st.form("shipping_master_form"):
        service_name = st.text_input("配送方法", placeholder="例: EMS 小型")
        weight_min_g = st.number_input("weight_min_g", min_value=0, step=50, value=0)
        weight_max_g = st.number_input("weight_max_g", min_value=0, step=50, value=500)
        shipping_cost_jpy = st.number_input("shipping_cost_jpy", min_value=0, step=100, value=0)
        tracking = st.checkbox("tracking", value=True)
        insurance = st.checkbox("insurance", value=False)
        ddp_supported = st.checkbox("ddp_supported", value=False)
        source_url = st.text_input("source_url", key="shipping_source_url")
        note = st.text_area("note", key="shipping_note")
        last_checked_at = st.date_input("last_checked_at", value=date.today(), key="shipping_last_checked")
        submitted = st.form_submit_button("送料マスタを追加・更新", type="primary")
    if submitted:
        if not service_name.strip() or weight_max_g < weight_min_g:
            st.error("配送方法名と重量範囲を確認してください。")
        else:
            payload = {
                "updated_at": now_iso(),
                "destination_country": country,
                "service_name": service_name.strip(),
                "weight_min_g": weight_min_g,
                "weight_max_g": weight_max_g,
                "shipping_cost_jpy": shipping_cost_jpy,
                "tracking": tracking,
                "insurance": insurance,
                "ddp_supported": ddp_supported,
                "source_url": source_url,
                "note": note,
                "last_checked_at": serialize_date(last_checked_at),
            }
            if upsert_row(client, "shipping_rate_master", payload, on_conflict="destination_country,service_name,weight_min_g,weight_max_g"):
                st.success("送料マスタを保存しました。")
                st.rerun()


def grading_master_form(client: Any | None, country: str, grading_rule: dict[str, Any]) -> None:
    st.markdown("### 判定基準マスタ")
    with st.form("grading_master_form"):
        grade_a_min_profit_jpy = st.number_input("A利益基準", min_value=0, step=100, value=to_int(grading_rule.get("grade_a_min_profit_jpy")))
        grade_a_min_roi_percent = st.number_input("A ROI基準", min_value=0.0, step=1.0, value=to_float(grading_rule.get("grade_a_min_roi_percent")))
        grade_a_min_sold_count = st.number_input("A Sold基準", min_value=0, step=1, value=to_int(grading_rule.get("grade_a_min_sold_count")))
        grade_b_min_profit_jpy = st.number_input("B利益基準", min_value=0, step=100, value=to_int(grading_rule.get("grade_b_min_profit_jpy")))
        grade_b_min_roi_percent = st.number_input("B ROI基準", min_value=0.0, step=1.0, value=to_float(grading_rule.get("grade_b_min_roi_percent")))
        grade_b_min_sold_count = st.number_input("B Sold基準", min_value=0, step=1, value=to_int(grading_rule.get("grade_b_min_sold_count")))
        grade_d_max_profit_jpy = st.number_input("D除外利益基準", min_value=0, step=100, value=to_int(grading_rule.get("grade_d_max_profit_jpy")))
        grade_d_max_roi_percent = st.number_input("D除外ROI基準", min_value=0.0, step=1.0, value=to_float(grading_rule.get("grade_d_max_roi_percent")))
        stale_master_warning_days = st.number_input("マスタ警告日数", min_value=1, step=1, value=to_int(grading_rule.get("stale_master_warning_days")))
        submitted = st.form_submit_button("判定基準を保存", type="primary")
    if submitted:
        payload = {
            "updated_at": now_iso(),
            "destination_country": country,
            "grade_a_min_profit_jpy": grade_a_min_profit_jpy,
            "grade_a_min_roi_percent": grade_a_min_roi_percent,
            "grade_a_min_sold_count": grade_a_min_sold_count,
            "grade_b_min_profit_jpy": grade_b_min_profit_jpy,
            "grade_b_min_roi_percent": grade_b_min_roi_percent,
            "grade_b_min_sold_count": grade_b_min_sold_count,
            "grade_d_max_profit_jpy": grade_d_max_profit_jpy,
            "grade_d_max_roi_percent": grade_d_max_roi_percent,
            "stale_master_warning_days": stale_master_warning_days,
        }
        if upsert_row(client, "grading_rules", payload, on_conflict="destination_country"):
            st.success("判定基準を保存しました。")
            st.rerun()


def settings_page(client: Any | None, country: str, contexts: dict[str, dict[str, Any]]) -> None:
    st.header("設定")
    st.caption("通常の仕入れ判断では触らなくてよい項目です。公式情報を確認したときだけ更新してください。")
    context = contexts[country]

    with st.expander("注意書き・マスタ最終更新日", expanded=True):
        st.warning("このツールは利益予測用です。最終判断前にeBay公式手数料、配送会社公式料金、配送可否、関税、DDP、検疫、規約適合性を確認してください。")
        st.write(f"設定対象国: {country}")
        st.write(f"手数料マスタ最終確認日: {context['fee_setting'].get('last_checked_at') or '未登録'}")
        last_shipping_checked = max([row.get("last_checked_at") or "" for row in context["shipping_rates"]], default="")
        st.write(f"送料マスタ最終確認日: {last_shipping_checked or '未登録'}")
        st.write(f"為替最終取得日時: {(context['fx_rate'] or {}).get('fetched_at') or '未取得'}")
        show_master_warnings(context["fee_setting"], context["shipping_rates"], context["grading_rule"])

    with st.expander("梱包費デフォルト設定", expanded=False):
        st.session_state["default_packaging_cost_jpy"] = st.number_input(
            "新規登録時の梱包費（円）",
            min_value=0,
            step=50,
            value=to_int(st.session_state.get("default_packaging_cost_jpy"), DEFAULT_PACKAGING_COST_JPY),
        )

    with st.expander("為替更新", expanded=False):
        fx_page(client, country, context["fee_setting"], context["fx_rate"])

    with st.expander("手数料マスタ", expanded=False):
        fee_master_form(client, country, context["fee_setting"])

    with st.expander("送料マスタ", expanded=False):
        shipping_master_form(client, country, context["shipping_rates"])

    with st.expander("判定基準", expanded=False):
        st.caption("現在の判定は利益額のみを使います。ROIとSold数は判定に使いません。C判定の下限はD除外利益基準です。")
        grading_master_form(client, country, context["grading_rule"])


def main() -> None:
    apply_mobile_css()

    st.title("eBay仕入れ判定・利益計算")
    st.warning("このツールは利益予測用です。最終判断前にeBay公式手数料、配送会社公式料金、配送可否、関税、DDP、検疫、規約適合性を確認してください。")

    client = get_supabase_client()
    if client is None:
        st.info(f"Supabase未設定のため、このPC内に保存します。保存先: {local_db.get_db_path()}")

    country = st.selectbox(
        "基準販売国",
        COUNTRY_OPTIONS,
        index=COUNTRY_OPTIONS.index(COUNTRY_AU),
        key="destination_country",
    )
    config = COUNTRY_CONFIG[country]
    st.caption(f"基準表示: {country} / {config['currency']} / {config['fx_base']}/{config['fx_target']}")
    contexts = load_country_contexts(client)

    page = st.selectbox(
        "画面",
        ["商品判定", "候補一覧", "設定"],
    )

    if page == "商品判定":
        product_judgment_page(client, contexts, country)
    elif page == "候補一覧":
        products_page(client, contexts, country)
    elif page == "設定":
        settings_page(client, country, contexts)


if __name__ == "__main__":
    main()
