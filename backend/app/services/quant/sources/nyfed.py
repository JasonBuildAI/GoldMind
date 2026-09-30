"""纽约联储参考利率（EFFR / SOFR）—— 政策利率的官方口径。"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd

from app.services.quant.sources.base import SourceError, clean_series, default_get, shift_to_next_trading_day

EFFR_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"


def parse_rates(payload: dict, rate_type: str = "EFFR") -> pd.Series:
    rates = (payload or {}).get("refRates") or []
    values = {}
    for row in rates:
        if str(row.get("type", "")).upper() != rate_type:
            continue
        try:
            values[pd.Timestamp(row["effectiveDate"])] = float(row["percentRate"])
        except (KeyError, TypeError, ValueError):
            continue
    if not values:
        raise SourceError(f"纽约联储响应里没有 {rate_type} 数据")
    return clean_series(values, name="effr")


def fetch(
    start: date,
    end: date,
    *,
    get: Optional[Callable] = None,
    timeout: float = 30.0,
) -> dict[str, pd.Series]:
    http_get = get or default_get
    response = http_get(
        EFFR_URL,
        params={"startDate": start.isoformat(), "endDate": end.isoformat()},
        timeout=timeout,
    )
    if getattr(response, "status_code", 200) != 200:
        raise SourceError(f"纽约联储 EFFR 抓取失败：HTTP {response.status_code}")

    try:
        payload = response.json()
    except ValueError as exc:  # 非 JSON
        raise SourceError(f"纽约联储 EFFR 响应不是 JSON：{exc}") from exc

    # EFFR 是次日发布的（上午 9 点 ET），右移一天使用。
    return {"effr": shift_to_next_trading_day(parse_rates(payload))}
