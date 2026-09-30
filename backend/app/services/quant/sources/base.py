"""数据源的公共类型与工具。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Callable, Optional

import pandas as pd
import requests

from app.utils import timeutil

_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


class SourceError(RuntimeError):
    """某个数据源不可用（网络、格式、内容为空）。消息会如实出现在 API 与界面里。"""


@dataclass
class SourceResult:
    """一个源一轮抓取的结果。``ok=False`` 时 ``series`` 为空、``error`` 有值。"""

    name: str
    series: dict[str, pd.Series] = field(default_factory=dict)
    fetched_at: datetime = field(default_factory=timeutil.now_naive)
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.error is None


def default_get(url: str, *, params: Optional[dict] = None, timeout: float = 20.0):
    """默认 HTTP 客户端（``requests``）。测试通过参数注入假实现。"""
    return requests.get(url, params=params, timeout=timeout, headers={"User-Agent": _USER_AGENT})


def clean_series(values: dict[Any, Any], name: str) -> pd.Series:
    """把 {日期: 值} 整理成规范序列：DatetimeIndex、float、升序、去重、去 NaN。"""
    if not values:
        return pd.Series(dtype="float64", name=name)

    series = pd.Series(values, name=name)
    series.index = pd.to_datetime(series.index)
    series = pd.to_numeric(series, errors="coerce")
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series.dropna().astype("float64")


def shift_to_next_trading_day(series: pd.Series, days: int = 1) -> pd.Series:
    """整体右移 N 个工作日。

    用途：数据在**黄金收盘之后**才发布（美国财政部收益率曲线 15:30 ET、
    CFTC 报告 15:30 ET、纽约联储 EFFR 次日上午）。用当天的值去预测当天收盘
    属于前视；右移一天才是当时真正可用的信息。
    """
    if series.empty:
        return series
    offset = pd.tseries.offsets.BDay(days)
    shifted = series.copy()
    shifted.index = shifted.index + offset
    return shifted


def business_day_on_or_after(day: date, offset_days: int) -> date:
    """从 ``day + offset_days`` 起找到第一个工作日（用于月度数据的发布日）。"""
    candidate = pd.Timestamp(day) + pd.Timedelta(days=offset_days)
    return (candidate + pd.tseries.offsets.BDay(0)).date()
