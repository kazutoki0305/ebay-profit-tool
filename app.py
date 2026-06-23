from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pandas as pd
import streamlit as st

from ebay_tool import local_db
from ebay_tool.calculations import (
    build_chatgpt_prompt,
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
    GRADE_ORDER,
    RISK_FLAGS,
)
from ebay_tool.db import fetch_rows, get_secret_value, get_supabase_client, insert_row, upsert_row
from ebay_tool.fx import build_fx_payload, fetch_rate_from_frankfurter


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
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_login_if_needed() -> None:
    password = get_secret_value("APP_LOGIN_PASSWORD", "app.login_password")
    if not password:
        return
    if st.session_state.get("authenticated"):
        return
    st.title("ログイン")
    entered = st.text_input("パスワード", type="password")
    if st.button("ログイン"):
        if entered == password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが違います。")
    st.stop()


def yen(value: Any) -> str:
    if value is None:
        return "-"
    return f"{to_int(value):,}円"


def pct(value: Any) -> str:
    if value is None:
        return "-"
    return f"{to_float(value):.1f}%"


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


def product_input_page(client: Any | None, country: str, fee_setting: dict[str, Any], shipping_rates: list[dict[str, Any]], grading_rule: dict[str, Any], fx_rate: dict[str, Any] | None) -> None:
    st.header("商品候補登録")
    st.caption("URLは保存するだけで、自動アクセスはしません。入力中に概算利益を表示します。")

    name = st.text_input("商品名", placeholder="例: 和柄 小皿 5枚セット")
    source_url = st.text_input("仕入れURL", placeholder="https://...")
    purchase_price_jpy = st.number_input("仕入れ価格（円）", min_value=0, step=100, value=0)
    domestic_shipping_jpy = st.number_input("国内送料（円）", min_value=0, step=100, value=0)
    packaging_cost_jpy = st.number_input("梱包費（円）", min_value=0, step=50, value=100)
    item_weight_g = st.number_input("商品重量（g）", min_value=0, step=10, value=0)
    packed_weight_g = st.number_input("梱包後重量（g）", min_value=0, step=10, value=0)
    length_cm = st.number_input("縦（cm）", min_value=0.0, step=0.5, value=0.0)
    width_cm = st.number_input("横（cm）", min_value=0.0, step=0.5, value=0.0)
    height_cm = st.number_input("高さ（cm）", min_value=0.0, step=0.5, value=0.0)
    currency = COUNTRY_CONFIG[country]["currency"]
    expected_sale_price = st.number_input(f"想定販売価格（{currency}）", min_value=0.0, step=1.0, value=0.0)
    sold_count_90d = st.number_input("想定Sold数（90日）", min_value=0, step=1, value=0)
    competitor_count = st.number_input("競合数", min_value=0, step=1, value=0)
    promoted_default = to_float(fee_setting.get("promoted_listing_default_percent"))
    promoted_listing_percent = st.number_input("Promoted Listings率（%）", min_value=0.0, max_value=100.0, step=0.5, value=promoted_default)
    category = st.text_input("商品カテゴリ", placeholder="例: Collectibles / Kitchen")

    risk_flags: dict[str, bool] = {}
    st.markdown("#### リスクチェック")
    categories = sorted({item["category"] for item in RISK_FLAGS})
    for risk_category in categories:
        with st.expander(risk_category, expanded=False):
            for item in [risk for risk in RISK_FLAGS if risk["category"] == risk_category]:
                risk_flags[item["key"]] = st.checkbox(item["label"], key=f"risk_{item['key']}")

    memo = st.text_area("メモ", placeholder="目視で確認したSold状況、状態、注意点など")

    candidate = {
        "name": name,
        "source_url": source_url,
        "purchase_price_jpy": purchase_price_jpy,
        "domestic_shipping_jpy": domestic_shipping_jpy,
        "packaging_cost_jpy": packaging_cost_jpy,
        "item_weight_g": item_weight_g,
        "packed_weight_g": packed_weight_g,
        "length_cm": length_cm,
        "width_cm": width_cm,
        "height_cm": height_cm,
        "destination_country": country,
        "expected_sale_price": expected_sale_price,
        "sold_count_90d": sold_count_90d,
        "competitor_count": competitor_count,
        "promoted_listing_percent": promoted_listing_percent,
        "category": category,
        "memo": memo,
        "risk_flags": risk_flags,
    }
    calculation = calculate_profit(candidate, fee_setting, fx_rate, shipping_rates, grading_rule)
    show_result_card(calculation)

    if st.button("この候補を保存", type="primary"):
        if not name.strip():
            st.error("商品名を入力してください。")
        else:
            payload = build_product_payload(candidate, calculation)
            payload["created_at"] = now_iso()
            if insert_row(client, "product_candidates", payload):
                st.success("商品候補を保存しました。")
                st.rerun()


def dashboard_page(client: Any | None, country: str, fee_setting: dict[str, Any], shipping_rates: list[dict[str, Any]], grading_rule: dict[str, Any], fx_rate: dict[str, Any] | None) -> None:
    st.header("ダッシュボード")
    products = load_products(client)
    country_products = [row for row in products if row.get("destination_country") == country]

    col1, col2 = st.columns(2)
    col1.metric("登録候補数", len(country_products))
    for grade in ["A", "B", "C", "D"]:
        col = col1 if grade in {"A", "C"} else col2
        col.metric(f"{grade}判定数", sum(1 for row in country_products if row.get("grade") == grade))

    valid_profit = [row for row in country_products if row.get("expected_profit_jpy") is not None]
    if valid_profit:
        best_profit = max(valid_profit, key=lambda row: to_int(row.get("expected_profit_jpy")))
        best_roi = max(valid_profit, key=lambda row: to_float(row.get("roi_percent")))
        st.markdown("#### 注目候補")
        st.write(f"最高利益候補: {best_profit.get('name')} / {yen(best_profit.get('expected_profit_jpy'))}")
        st.write(f"最高ROI候補: {best_roi.get('name')} / {pct(best_roi.get('roi_percent'))}")
    else:
        st.info("まだ利益計算済みの商品候補がありません。")

    st.markdown("#### マスタ・為替")
    st.write(f"手数料マスタ最終確認日: {fee_setting.get('last_checked_at') or '未登録'}")
    last_shipping_checked = max([row.get("last_checked_at") or "" for row in shipping_rates], default="")
    st.write(f"送料マスタ最終確認日: {last_shipping_checked or '未登録'}")
    st.write(f"為替最終取得日時: {(fx_rate or {}).get('fetched_at') or '未取得'}")
    show_master_warnings(fee_setting, shipping_rates, grading_rule)


def products_page(client: Any | None, country: str) -> None:
    st.header("候補一覧")
    products = load_products(client)
    if not products:
        st.info("保存済みの商品候補がありません。")
        return

    country_filter = st.selectbox("販売国で絞り込み", ["すべて", "アメリカ", "オーストラリア"], index=COUNTRY_OPTIONS.index(country) + 1)
    grade_filter = st.selectbox("判定で絞り込み", ["すべて", "Aのみ", "B以上", "C以下", "高リスク除外"])
    sort_by = st.selectbox("並び替え", ["判定順", "利益順", "ROI順", "登録日順", "リスク低い順"])

    filtered = products
    if country_filter != "すべて":
        filtered = [row for row in filtered if row.get("destination_country") == country_filter]
    if grade_filter == "Aのみ":
        filtered = [row for row in filtered if row.get("grade") == "A"]
    elif grade_filter == "B以上":
        filtered = [row for row in filtered if row.get("grade") in {"A", "B"}]
    elif grade_filter == "C以下":
        filtered = [row for row in filtered if row.get("grade") in {"C", "D", "送料未登録", "未計算"}]
    elif grade_filter == "高リスク除外":
        filtered = [row for row in filtered if to_int(row.get("risk_score")) <= 8]

    if sort_by == "判定順":
        filtered = sorted(filtered, key=lambda row: GRADE_ORDER.get(row.get("grade"), 99))
    elif sort_by == "利益順":
        filtered = sorted(filtered, key=lambda row: to_int(row.get("expected_profit_jpy")), reverse=True)
    elif sort_by == "ROI順":
        filtered = sorted(filtered, key=lambda row: to_float(row.get("roi_percent")), reverse=True)
    elif sort_by == "登録日順":
        filtered = sorted(filtered, key=lambda row: row.get("created_at") or "", reverse=True)
    elif sort_by == "リスク低い順":
        filtered = sorted(filtered, key=lambda row: to_int(row.get("risk_score")))

    st.caption(f"{len(filtered)}件表示")
    for row in filtered:
        with st.container():
            st.markdown('<div class="card">', unsafe_allow_html=True)
            st.markdown(f"### {row.get('name') or '名称未設定'}")
            grade_badge(row.get("grade", "未計算"))
            st.write(f"販売国: {row.get('destination_country')}")
            st.write(f"想定利益: {yen(row.get('expected_profit_jpy'))} / ROI: {pct(row.get('roi_percent'))}")
            st.write(f"仕入れ価格: {yen(row.get('purchase_price_jpy'))} / 想定販売価格: {row.get('expected_sale_price')} {row.get('sale_currency')}")
            st.write(f"リスクスコア: {row.get('risk_score', 0)} / 更新日: {row.get('updated_at') or row.get('created_at')}")
            warnings = row.get("warnings") or []
            if warnings:
                st.caption("警告: " + " / ".join(warnings[:2]))
            st.markdown("</div>", unsafe_allow_html=True)


def result_page(client: Any | None) -> None:
    st.header("利益計算結果")
    products = load_products(client)
    if not products:
        st.info("保存済みの商品候補がありません。商品候補登録画面で入力すると、入力中の概算結果も表示されます。")
        return

    labels = [f"{row.get('name') or '名称未設定'} / {row.get('destination_country')} / {row.get('grade')}" for row in products]
    selected_index = st.selectbox("商品候補を選択", range(len(products)), format_func=lambda idx: labels[idx])
    product = products[selected_index]
    product_country = product.get("destination_country") or "アメリカ"
    product_config = COUNTRY_CONFIG[product_country]
    fee_setting = load_fee_setting(client, product_country)
    grading_rule = load_grading_rule(client, product_country)
    shipping_rates = load_shipping_rates(client, product_country)
    fx_rate = load_fx_rate(client, product_config["fx_base"], product_config["fx_target"], fee_setting)
    calculation = calculate_profit(product, fee_setting, fx_rate, shipping_rates, grading_rule)
    show_result_card(calculation)


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


def master_page(client: Any | None, country: str, fee_setting: dict[str, Any], shipping_rates: list[dict[str, Any]], grading_rule: dict[str, Any]) -> None:
    st.header("マスタ管理")
    st.caption("手数料・送料・判定基準は自動更新しません。公式情報を確認した日付を保存してください。")
    fee_master_form(client, country, fee_setting)
    shipping_master_form(client, country, shipping_rates)
    grading_master_form(client, country, grading_rule)


def prompt_page(client: Any | None) -> None:
    st.header("ChatGPT精査プロンプト生成")
    products = load_products(client)
    if not products:
        st.info("保存済みの商品候補がありません。先に商品候補を保存してください。")
        return
    labels = [f"{row.get('name') or '名称未設定'} / {row.get('destination_country')} / {row.get('grade')}" for row in products]
    selected_index = st.selectbox("商品候補を選択", range(len(products)), format_func=lambda idx: labels[idx])
    prompt = build_chatgpt_prompt(products[selected_index])
    st.text_area("コピー用プロンプト", value=prompt, height=520)


def main() -> None:
    apply_mobile_css()
    require_login_if_needed()

    st.title("eBay仕入れ判定・利益計算")
    st.warning("このツールは利益予測用です。最終判断前にeBay公式手数料、配送会社公式料金、配送可否、関税、DDP、検疫、規約適合性を確認してください。")

    client = get_supabase_client()
    if client is None:
        st.info(f"Supabase未設定のため、このPC内に保存します。保存先: {local_db.get_db_path()}")

    country = st.selectbox("販売国", COUNTRY_OPTIONS, key="destination_country")
    config = COUNTRY_CONFIG[country]
    st.caption(f"販売通貨: {config['currency']} / 使用為替: {config['fx_base']}/{config['fx_target']} / 注意: {config['risk_notice']}")

    fee_setting = load_fee_setting(client, country)
    grading_rule = load_grading_rule(client, country)
    shipping_rates = load_shipping_rates(client, country)
    fx_rate = load_fx_rate(client, config["fx_base"], config["fx_target"], fee_setting)

    if fx_rate:
        expected_rate = calculate_fx_rate(to_float(fx_rate.get("raw_rate")), to_float(fee_setting.get("exchange_buffer_percent")))
        if abs(expected_rate - to_float(fx_rate.get("calculation_rate"))) > 0.0001:
            fx_rate = fx_rate.copy()
            fx_rate["buffer_percent"] = to_float(fee_setting.get("exchange_buffer_percent"))
            fx_rate["calculation_rate"] = expected_rate

    page = st.selectbox(
        "画面",
        ["ダッシュボード", "商品候補登録", "利益計算結果", "候補一覧", "マスタ管理", "為替更新", "ChatGPT精査プロンプト生成"],
    )

    if page == "ダッシュボード":
        dashboard_page(client, country, fee_setting, shipping_rates, grading_rule, fx_rate)
    elif page == "商品候補登録":
        product_input_page(client, country, fee_setting, shipping_rates, grading_rule, fx_rate)
    elif page == "利益計算結果":
        result_page(client)
    elif page == "候補一覧":
        products_page(client, country)
    elif page == "マスタ管理":
        master_page(client, country, fee_setting, shipping_rates, grading_rule)
    elif page == "為替更新":
        fx_page(client, country, fee_setting, fx_rate)
    elif page == "ChatGPT精査プロンプト生成":
        prompt_page(client)


if __name__ == "__main__":
    main()
