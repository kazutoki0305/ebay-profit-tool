from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from .calculations import calculate_fx_rate, now_iso, to_float

FRANKFURTER_RATE_URL = "https://api.frankfurter.dev/v2/rates"


def fetch_rate_from_frankfurter(base_currency: str, target_currency: str = "JPY") -> dict[str, Any]:
    response = requests.get(
        FRANKFURTER_RATE_URL,
        params={"base": base_currency, "quotes": target_currency},
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    if isinstance(data, list):
        rate = next((row.get("rate") for row in data if row.get("quote") == target_currency), None)
    else:
        rate = data.get("rates", {}).get(target_currency)
    if rate is None:
        raise ValueError(f"{base_currency}/{target_currency} の為替レートが取得できませんでした。")
    return {
        "base_currency": base_currency,
        "target_currency": target_currency,
        "raw_rate": float(rate),
        "source": "Frankfurter API",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def build_fx_payload(base_currency: str, target_currency: str, raw_rate: float, buffer_percent: float, source: str) -> dict[str, Any]:
    return {
        "updated_at": now_iso(),
        "base_currency": base_currency,
        "target_currency": target_currency,
        "raw_rate": to_float(raw_rate),
        "buffer_percent": to_float(buffer_percent),
        "calculation_rate": calculate_fx_rate(raw_rate, buffer_percent),
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
