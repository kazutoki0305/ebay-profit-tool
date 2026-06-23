from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from .calculations import now_iso

DB_PATH = Path.cwd() / "data" / "local_app.db"

JSON_COLUMNS = {"risk_flags", "warnings"}
BOOL_COLUMNS = {"tracking", "insurance", "ddp_supported"}

TABLE_COLUMNS = {
    "product_candidates": [
        "id",
        "created_at",
        "updated_at",
        "name",
        "source_url",
        "purchase_price_jpy",
        "domestic_shipping_jpy",
        "packaging_cost_jpy",
        "item_weight_g",
        "packed_weight_g",
        "length_cm",
        "width_cm",
        "height_cm",
        "destination_country",
        "sale_currency",
        "expected_sale_price",
        "sold_count_90d",
        "competitor_count",
        "category",
        "promoted_listing_percent",
        "memo",
        "risk_flags",
        "risk_score",
        "calculated_fx_rate",
        "calculation_fx_rate",
        "shipping_cost_jpy",
        "total_cost_jpy",
        "expected_revenue_jpy",
        "expected_profit_jpy",
        "roi_percent",
        "profit_margin_percent",
        "grade",
        "warnings",
    ],
    "fx_rates": [
        "id",
        "created_at",
        "updated_at",
        "base_currency",
        "target_currency",
        "raw_rate",
        "buffer_percent",
        "calculation_rate",
        "source",
        "fetched_at",
    ],
    "fee_settings": [
        "id",
        "created_at",
        "updated_at",
        "destination_country",
        "marketplace",
        "final_value_fee_percent",
        "international_fee_percent",
        "fixed_order_fee",
        "fixed_order_fee_currency",
        "promoted_listing_default_percent",
        "exchange_buffer_percent",
        "risk_buffer_percent",
        "source_url",
        "source_note",
        "last_checked_at",
    ],
    "shipping_rate_master": [
        "id",
        "created_at",
        "updated_at",
        "destination_country",
        "service_name",
        "weight_min_g",
        "weight_max_g",
        "shipping_cost_jpy",
        "tracking",
        "insurance",
        "ddp_supported",
        "source_url",
        "note",
        "last_checked_at",
    ],
    "grading_rules": [
        "id",
        "created_at",
        "updated_at",
        "destination_country",
        "grade_a_min_profit_jpy",
        "grade_a_min_roi_percent",
        "grade_a_min_sold_count",
        "grade_b_min_profit_jpy",
        "grade_b_min_roi_percent",
        "grade_b_min_sold_count",
        "grade_d_max_profit_jpy",
        "grade_d_max_roi_percent",
        "stale_master_warning_days",
    ],
}


def get_db_path() -> Path:
    return DB_PATH


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists product_candidates (
          id text primary key,
          created_at text not null,
          updated_at text not null,
          name text not null,
          source_url text,
          purchase_price_jpy integer,
          domestic_shipping_jpy integer,
          packaging_cost_jpy integer,
          item_weight_g integer,
          packed_weight_g integer,
          length_cm real,
          width_cm real,
          height_cm real,
          destination_country text,
          sale_currency text,
          expected_sale_price real,
          sold_count_90d integer,
          competitor_count integer,
          category text,
          promoted_listing_percent real,
          memo text,
          risk_flags text,
          risk_score integer,
          calculated_fx_rate real,
          calculation_fx_rate real,
          shipping_cost_jpy integer,
          total_cost_jpy integer,
          expected_revenue_jpy integer,
          expected_profit_jpy integer,
          roi_percent real,
          profit_margin_percent real,
          grade text,
          warnings text
        );

        create table if not exists fx_rates (
          id text primary key,
          created_at text not null,
          updated_at text not null,
          base_currency text not null,
          target_currency text not null,
          raw_rate real not null,
          buffer_percent real not null,
          calculation_rate real not null,
          source text,
          fetched_at text,
          unique (base_currency, target_currency)
        );

        create table if not exists fee_settings (
          id text primary key,
          created_at text not null,
          updated_at text not null,
          destination_country text not null unique,
          marketplace text,
          final_value_fee_percent real,
          international_fee_percent real,
          fixed_order_fee real,
          fixed_order_fee_currency text,
          promoted_listing_default_percent real,
          exchange_buffer_percent real,
          risk_buffer_percent real,
          source_url text,
          source_note text,
          last_checked_at text
        );

        create table if not exists shipping_rate_master (
          id text primary key,
          created_at text not null,
          updated_at text not null,
          destination_country text not null,
          service_name text not null,
          weight_min_g integer not null,
          weight_max_g integer not null,
          shipping_cost_jpy integer not null,
          tracking integer,
          insurance integer,
          ddp_supported integer,
          source_url text,
          note text,
          last_checked_at text,
          unique (destination_country, service_name, weight_min_g, weight_max_g)
        );

        create table if not exists grading_rules (
          id text primary key,
          created_at text not null,
          updated_at text not null,
          destination_country text not null unique,
          grade_a_min_profit_jpy integer,
          grade_a_min_roi_percent real,
          grade_a_min_sold_count integer,
          grade_b_min_profit_jpy integer,
          grade_b_min_roi_percent real,
          grade_b_min_sold_count integer,
          grade_d_max_profit_jpy integer,
          grade_d_max_roi_percent real,
          stale_master_warning_days integer
        );
        """
    )
    conn.commit()


def normalize_payload(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    now = now_iso()
    allowed = set(TABLE_COLUMNS[table])
    normalized = {key: value for key, value in payload.items() if key in allowed}
    normalized.setdefault("id", str(uuid.uuid4()))
    normalized.setdefault("created_at", now)
    normalized.setdefault("updated_at", now)
    for key in JSON_COLUMNS:
        if key in normalized and not isinstance(normalized[key], str):
            normalized[key] = json.dumps(normalized[key], ensure_ascii=False)
    for key in BOOL_COLUMNS:
        if key in normalized:
            normalized[key] = 1 if normalized[key] else 0
    return normalized


def decode_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    for key in JSON_COLUMNS:
        if key in data and isinstance(data[key], str):
            try:
                data[key] = json.loads(data[key])
            except json.JSONDecodeError:
                data[key] = {} if key == "risk_flags" else []
    for key in BOOL_COLUMNS:
        if key in data and data[key] is not None:
            data[key] = bool(data[key])
    return data


def fetch_rows(
    table: str,
    *,
    order: str | None = None,
    desc: bool = False,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if table not in TABLE_COLUMNS:
        return []
    columns = TABLE_COLUMNS[table]
    sql = f"select {', '.join(columns)} from {table}"
    params: list[Any] = []
    conditions = []
    for key, value in (filters or {}).items():
        if key in columns and value is not None:
            conditions.append(f"{key} = ?")
            params.append(value)
    if conditions:
        sql += " where " + " and ".join(conditions)
    if order and order in columns:
        sql += f" order by {order} {'desc' if desc else 'asc'}"
    if limit:
        sql += " limit ?"
        params.append(limit)
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [decode_row(row) for row in rows]


def insert_row(table: str, payload: dict[str, Any]) -> bool:
    if table not in TABLE_COLUMNS:
        return False
    row = normalize_payload(table, payload)
    keys = list(row.keys())
    placeholders = ", ".join("?" for _ in keys)
    sql = f"insert into {table} ({', '.join(keys)}) values ({placeholders})"
    with connect() as conn:
        conn.execute(sql, [row[key] for key in keys])
        conn.commit()
    return True


def upsert_row(table: str, payload: dict[str, Any], on_conflict: str | None = None) -> bool:
    if table not in TABLE_COLUMNS:
        return False
    row = normalize_payload(table, payload)
    keys = list(row.keys())
    conflict_cols = [col.strip() for col in (on_conflict or "id").split(",") if col.strip()]
    conflict_cols = [col for col in conflict_cols if col in TABLE_COLUMNS[table]]
    if not conflict_cols:
        conflict_cols = ["id"]
    update_cols = [key for key in keys if key not in conflict_cols and key != "created_at"]
    updates = ", ".join(f"{key} = excluded.{key}" for key in update_cols)
    placeholders = ", ".join("?" for _ in keys)
    sql = (
        f"insert into {table} ({', '.join(keys)}) values ({placeholders}) "
        f"on conflict ({', '.join(conflict_cols)}) do update set {updates}"
    )
    with connect() as conn:
        conn.execute(sql, [row[key] for key in keys])
        conn.commit()
    return True


def delete_row(table: str, row_id: str) -> bool:
    if table not in TABLE_COLUMNS:
        return False
    with connect() as conn:
        conn.execute(f"delete from {table} where id = ?", [row_id])
        conn.commit()
    return True

