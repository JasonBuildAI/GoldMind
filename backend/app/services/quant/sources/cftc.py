"""CFTC 持仓报告（Socrata 公开 API，无需密钥）。

报告覆盖的是**周二**的持仓，周五 15:30 ET 才发布 —— 而 COMEX 黄金当天
13:30 ET 收盘，因此可用日从**下周一**开始：报告日 + 4 个工作日。
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd

from app.services.quant.sources.base import SourceError, clean_series, default_get

CFTC_URL = "https://publicreporting.cftc.gov/resource/jun7-fc8e.json"
# COMEX 黄金：market code 088691
GOLD_CONTRACT_CODE = "088691"


def parse_rows(rows: list[dict]) -> pd.Series:
    values = {}
    for row in rows or []:
        try:
            report_date = pd.Timestamp(str(row["report_date_as_yyyy_mm_dd"])[:10])
            long_position = float(row["noncomm_positions_long_all"])
            short_position = float(row["noncomm_positions_short_all"])
        except (KeyError, TypeError, ValueError):
            continue
        usable_date = report_date + pd.tseries.offsets.BDay(4)
        values[usable_date] = long_position - short_position

    if not values:
        raise SourceError("CFTC 响应里没有可解析的黄金持仓行")
    return clean_series(values, name="cftc_net")


def parse_open_interest(rows: list[dict]) -> pd.Series:
    """同一份报告里的 COMEX 黄金未平仓合约（张）；缺失时返回空序列。"""
    values = {}
    for row in rows or []:
        try:
            report_date = pd.Timestamp(str(row["report_date_as_yyyy_mm_dd"])[:10])
            open_interest = float(row["open_interest_all"])
        except (KeyError, TypeError, ValueError):
            continue
        usable_date = report_date + pd.tseries.offsets.BDay(4)
        values[usable_date] = open_interest
    if not values:
        return pd.Series(dtype="float64", name="cftc_oi")
    return clean_series(values, name="cftc_oi")


def fetch(
    start: date,
    *,
    get: Optional[Callable] = None,
    timeout: float = 30.0,
) -> dict[str, pd.Series]:
    http_get = get or default_get
    params = {
        "$limit": 2000,
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$where": (
            f"cftc_contract_market_code='{GOLD_CONTRACT_CODE}' "
            f"and report_date_as_yyyy_mm_dd >= '{start.isoformat()}T00:00:00.000'"
        ),
    }
    response = http_get(CFTC_URL, params=params, timeout=timeout)
    if getattr(response, "status_code", 200) != 200:
        raise SourceError(f"CFTC 持仓报告抓取失败：HTTP {response.status_code}")
    try:
        rows = response.json()
    except ValueError as exc:
        raise SourceError(f"CFTC 响应不是 JSON：{exc}") from exc
    if not isinstance(rows, list):
        raise SourceError("CFTC 响应不是行数组")
    result = {"cftc_net": parse_rows(rows)}
    open_interest = parse_open_interest(rows)
    if not open_interest.empty:
        result["cftc_oi"] = open_interest
    return result
