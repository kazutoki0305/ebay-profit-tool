from __future__ import annotations

from typing import Any

import streamlit as st

from . import local_db
from .table_names import supabase_table_name


def get_secret_value(*names: str) -> str | None:
    try:
        for name in names:
            if "." in name:
                section, key = name.split(".", 1)
                if section in st.secrets and key in st.secrets[section]:
                    return st.secrets[section][key]
            if name in st.secrets:
                return st.secrets[name]
    except Exception:
        return None
    return None


@st.cache_resource(show_spinner=False)
def get_supabase_client() -> Any | None:
    url = get_secret_value("supabase.url", "SUPABASE_URL")
    anon_key = get_secret_value("supabase.anon_key", "SUPABASE_ANON_KEY")
    if not url or not anon_key:
        return None
    try:
        from supabase import create_client

        return create_client(url, anon_key)
    except Exception:
        return None


def supabase_is_configured() -> bool:
    return get_supabase_client() is not None


def fetch_rows(
    client: Any | None,
    table: str,
    *,
    order: str | None = None,
    desc: bool = False,
    filters: dict[str, Any] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    if client is None:
        return local_db.fetch_rows(table, order=order, desc=desc, filters=filters, limit=limit)
    physical_table = supabase_table_name(table)
    try:
        query = client.table(physical_table).select("*")
        for key, value in (filters or {}).items():
            if value is not None:
                query = query.eq(key, value)
        if order:
            query = query.order(order, desc=desc)
        if limit:
            query = query.limit(limit)
        response = query.execute()
        return response.data or []
    except Exception as exc:
        st.warning(f"{physical_table} の読み込みに失敗しました。Supabase設定とテーブルを確認してください。")
        st.session_state["last_db_error"] = str(exc)
        return []


def upsert_row(client: Any | None, table: str, payload: dict[str, Any], on_conflict: str | None = None) -> bool:
    if client is None:
        return local_db.upsert_row(table, payload, on_conflict=on_conflict)
    physical_table = supabase_table_name(table)
    try:
        query = client.table(physical_table).upsert(payload, on_conflict=on_conflict) if on_conflict else client.table(physical_table).upsert(payload)
        query.execute()
        return True
    except Exception as exc:
        st.error(f"{physical_table} の保存に失敗しました。入力値とSupabase権限を確認してください。")
        st.session_state["last_db_error"] = str(exc)
        return False


def insert_row(client: Any | None, table: str, payload: dict[str, Any]) -> bool:
    if client is None:
        return local_db.insert_row(table, payload)
    physical_table = supabase_table_name(table)
    try:
        client.table(physical_table).insert(payload).execute()
        return True
    except Exception as exc:
        st.error(f"{physical_table} への登録に失敗しました。入力値とSupabase権限を確認してください。")
        st.session_state["last_db_error"] = str(exc)
        return False


def delete_row(client: Any | None, table: str, row_id: str) -> bool:
    if client is None:
        return local_db.delete_row(table, row_id)
    physical_table = supabase_table_name(table)
    try:
        client.table(physical_table).delete().eq("id", row_id).execute()
        return True
    except Exception as exc:
        st.error(f"{physical_table} の削除に失敗しました。")
        st.session_state["last_db_error"] = str(exc)
        return False
