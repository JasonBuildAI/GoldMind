"""纽约联储：参考利率（EFFR / SOFR）与隔夜逆回购（RRP）结果。

EFFR 是政策利率的官方口径；RRP 余额是货币市场流动性的近端水位 ——
余额回升代表资金被抽回美联储（利空黄金流动性），回落代表资金回到市场。
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd

from app.services.quant.sources.base import SourceError, clean_series, default_get, shift_to_next_trading_day

EFFR_URL = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"
RRP_URL = "https://markets.newyorkfed.org/api/rp/reverserepo/all/results/last/{count}.json"
# 一次取最近约两年的操作结果（每天一条左右），增量同步不需要更长的历史
RRP_COUNT = 500


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


def parse_reverserepo(payload: dict) -> pd.Series:
    """按日汇总逆回购成交额（美元 → 亿美元）。"""
    operations = ((payload or {}).get("repo") or {}).get("operations") or []
    totals: dict = {}
    for op in operations:
        if str(op.get("operationType", "")) != "Reverse Repo":
            continue
        try:
            day = pd.Timestamp(str(op["operationDate"])[:10])
            amount = float(op["totalAmtAccepted"])
        except (KeyError, TypeError, ValueError):
            continue
        totals[day] = totals.get(day, 0.0) + amount

    if not totals:
        raise SourceError("纽约联储逆回购响应里没有结果行")
    # 结果 13:15 ET 公布、黄金 13:30 ET 收盘；保守起见仍右移一个工作日
    scaled = {day: amount / 1e8 for day, amount in totals.items()}
    return shift_to_next_trading_day(clean_series(scaled, name="rrp"))


def fetch_reverserepo(
    *,
    get: Optional[Callable] = None,
    count: int = RRP_COUNT,
    timeout: float = 30.0,
) -> dict[str, pd.Series]:
    http_get = get or default_get
    response = http_get(RRP_URL.format(count=count), timeout=timeout)
    if getattr(response, "status_code", 200) != 200:
        raise SourceError(f"纽约联储逆回购抓取失败：HTTP {response.status_code}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceError(f"纽约联储逆回购响应不是 JSON：{exc}") from exc
    return {"rrp": parse_reverserepo(payload)}


__all__ = ["EFFR_URL", "fetch", "fetch_reverserepo", "parse_rates", "parse_reverserepo"]
