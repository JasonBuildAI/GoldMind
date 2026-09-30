"""美国财政部收益率曲线（名义 + 实际）。

官方 CSV，无需密钥：``daily_treasury_yield_curve`` 与
``daily_treasury_real_yield_curve``，按年分文件。收益率曲线在每天 15:30 ET
发布，而 COMEX 黄金 13:30 ET 收盘 —— 所以整体右移到下一个工作日才是
「当时可用」的信息（见 ``shift_to_next_trading_day`` 的说明）。

实际利率是图片里「最核心」的因子；通胀预期（盈亏平衡）由名义 − 实际得到。
"""
from __future__ import annotations

import io
from datetime import date
from typing import Callable, Optional

import pandas as pd

from app.services.quant.sources.base import (
    SourceError,
    clean_series,
    default_get,
    shift_to_next_trading_day,
)

NOMINAL_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)
REAL_CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_real_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)


def parse_curve_csv(text: str, column: str) -> pd.Series:
    """解析收益率曲线 CSV，取指定期限列（列名大小写不敏感）。"""
    if not text or not text.strip():
        raise SourceError("收益率曲线 CSV 为空")

    frame = pd.read_csv(io.StringIO(text))
    frame.columns = [str(col).strip() for col in frame.columns]
    date_column = frame.columns[0]

    wanted = column.strip().lower()
    matched = next((col for col in frame.columns[1:] if col.strip().lower() == wanted), None)
    if matched is None:
        raise SourceError(f"收益率曲线 CSV 里没有 {column} 列：{list(frame.columns)}")

    parsed = pd.to_datetime(frame[date_column], format="%m/%d/%Y", errors="coerce")
    values = pd.to_numeric(frame[matched], errors="coerce")
    series = clean_series(dict(zip(parsed, values)), name=f"treasury_{column}")
    if series.empty:
        raise SourceError(f"收益率曲线 {column} 列解析结果为空")
    return series


def fetch(
    years: list[int],
    *,
    get: Optional[Callable] = None,
    timeout: float = 25.0,
) -> dict[str, pd.Series]:
    """抓取若干年的名义与实际收益率曲线，返回三个原始序列。"""
    http_get = get or default_get
    nominal_2y: dict = {}
    nominal_10y: dict = {}
    real_10y: dict = {}

    for year in years:
        nominal_response = http_get(NOMINAL_CSV_URL.format(year=year), timeout=timeout)
        if getattr(nominal_response, "status_code", 200) != 200:
            raise SourceError(f"名义收益率曲线 {year} 抓取失败：HTTP {nominal_response.status_code}")
        nominal_text = nominal_response.text
        nominal_2y.update(parse_curve_csv(nominal_text, "2 Yr").to_dict())
        nominal_10y.update(parse_curve_csv(nominal_text, "10 Yr").to_dict())

        real_response = http_get(REAL_CSV_URL.format(year=year), timeout=timeout)
        if getattr(real_response, "status_code", 200) != 200:
            raise SourceError(f"实际收益率曲线 {year} 抓取失败：HTTP {real_response.status_code}")
        real_10y.update(parse_curve_csv(real_response.text, "10 YR").to_dict())

    series = {
        "ust_nominal_2y": shift_to_next_trading_day(clean_series(nominal_2y, "ust_nominal_2y")),
        "ust_nominal_10y": shift_to_next_trading_day(clean_series(nominal_10y, "ust_nominal_10y")),
        "ust_real_10y": shift_to_next_trading_day(clean_series(real_10y, "ust_real_10y")),
    }
    if series["ust_real_10y"].empty:
        raise SourceError("实际收益率曲线解析后为空")
    return series


def default_years(today: Optional[date] = None, years: int = 10) -> list[int]:
    today = today or date.today()
    return list(range(today.year - years, today.year + 1))
