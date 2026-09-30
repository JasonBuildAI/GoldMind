"""美国财政部每日报表（DTS）的 TGA 余额（Fiscal Data，无需密钥）。

财政部把每个工作日的「Treasury General Account 期末余额」放在 Table I 的
Closing Balance 行里；该行的数值列是 ``open_today_bal``（表里的「今日余额」），
``close_today_bal`` 在这些行上恒为 null，单位百万美元。

日度现金余额在**次日**发布（16:00 ET 之后），而 COMEX 黄金 13:30 ET 收盘，
因此整体右移一个工作日才是当时可用的信息。
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd

from app.services.quant.sources.base import (
    SourceError,
    clean_series,
    default_get,
    shift_to_next_trading_day,
)

TGA_URL = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/"
    "dts/operating_cash_balance"
)
TGA_CLOSING_ACCOUNT = "Treasury General Account (TGA) Closing Balance"
PAGE_SIZE = 1000
# 10 年历史约 9 页；留足余量，同时防止分页元数据异常时无限循环
MAX_PAGES = 40


def closing_balances(payload: dict) -> dict:
    """从响应里取出 {记录日: 期末余额（百万美元）}，未右移。"""
    values: dict = {}
    for row in (payload or {}).get("data") or []:
        if str(row.get("account_type", "")) != TGA_CLOSING_ACCOUNT:
            continue
        try:
            day = pd.Timestamp(str(row["record_date"])[:10])
            value = float(row["open_today_bal"])
        except (KeyError, TypeError, ValueError):
            continue
        values[day] = value
    return values


def parse_operating_cash(payload: dict) -> pd.Series:
    values = closing_balances(payload)
    if not values:
        raise SourceError("财政部 DTS 响应里没有 TGA 期末余额行")
    return shift_to_next_trading_day(clean_series(values, name="tga"))


def fetch(
    start: date,
    end: date,
    *,
    get: Optional[Callable] = None,
    timeout: float = 30.0,
) -> dict[str, pd.Series]:
    http_get = get or default_get
    collected: dict = {}
    page = 1
    while page <= MAX_PAGES:
        response = http_get(
            TGA_URL,
            params={
                "sort": "record_date",
                "filter": f"record_date:gte:{start.isoformat()},record_date:lte:{end.isoformat()}",
                "page[size]": PAGE_SIZE,
                "page[number]": page,
            },
            timeout=timeout,
        )
        if getattr(response, "status_code", 200) != 200:
            raise SourceError(f"财政部 DTS 抓取失败：HTTP {response.status_code}")
        try:
            payload = response.json()
        except ValueError as exc:
            raise SourceError(f"财政部 DTS 响应不是 JSON：{exc}") from exc

        collected.update(closing_balances(payload))
        total_pages = int(((payload or {}).get("meta") or {}).get("total-pages") or 1)
        if page >= total_pages:
            break
        page += 1

    if not collected:
        raise SourceError(f"财政部 DTS 在 {start} ~ {end} 没有 TGA 期末余额行")
    return {"tga": shift_to_next_trading_day(clean_series(collected, name="tga"))}


__all__ = ["TGA_URL", "closing_balances", "fetch", "parse_operating_cash"]
