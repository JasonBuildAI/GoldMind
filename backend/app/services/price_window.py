"""价格统计窗口的**唯一**实现：以最新数据日为锚的滚动 12 个月。

背景：投资建议、多空因子、市场总结与统计接口此前各自写了一份
「2025 年至今」的统计，年份写死。进入 2026 年后，这些「年内涨幅」
实际变成了「最近 21 个月涨幅」，而且各服务窗口与口径互不一致。

这里收敛成一处，约定三件事：

1. **滚动窗口**：锚点是数据里最新的一条价格，往前推 ``WINDOW_MONTHS`` 个月；
   跨年不失效，也不再有任何写死的年份。
2. **两个口径分名**：
   - 涨跌幅 = (窗口末收盘 − 窗口首收盘) / 窗口首收盘；
   - 高低振幅 = (窗口最高 − 窗口最低) / 窗口最低 —— **不是波动率**，
     展示与提示词里不许再叫「波动区间 / 波动率」。
3. **不足 12 个月如实说**：数据覆盖不满窗口时 ``full_window=False``，
   ``label`` 写明实际可得长度，不假装满窗。
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional, Protocol

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.gold_price import GoldPrice

# 窗口长度（月）。改它等于改所有消费方的口径，测试会逐值钉住。
WINDOW_MONTHS = 12


class PriceRow(Protocol):
    """窗口计算需要的最小字段集（ORM 行与测试用轻量对象都满足）。"""

    date: date
    close_price: float
    high_price: Optional[float]
    low_price: Optional[float]


@dataclass(frozen=True)
class PriceWindow:
    """一段滚动窗口的统计结果。所有百分比都是「百分数」而不是小数。"""

    window_start: date
    window_end: date
    start_price: float
    end_price: float
    change_pct: float
    high: float
    low: float
    high_date: date
    low_date: date
    amplitude_pct: float
    full_window: bool
    label: str


def shift_months(anchor: date, months: int) -> date:
    """把日期往前推 ``months`` 个月；月末日期按目标月的实际天数收敛。"""

    total = anchor.year * 12 + (anchor.month - 1) - months
    year, month_index = divmod(total, 12)
    month = month_index + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _row_high(row: PriceRow) -> float:
    return float(row.high_price) if row.high_price else float(row.close_price)


def _row_low(row: PriceRow) -> float:
    return float(row.low_price) if row.low_price else float(row.close_price)


def summarize_window(
    rows: Iterable[PriceRow],
    *,
    months: int = WINDOW_MONTHS,
    earliest_available: Optional[date] = None,
) -> Optional[PriceWindow]:
    """按行计算窗口统计；没有任何行时返回 None（不造数）。

    ``rows`` 需要能按日期排序的价格行；``earliest_available`` 给出「库里最早
    有哪些数据」（用于判断窗口是否满），缺省时用 ``rows`` 里的最早日期。
    """

    ordered = sorted(rows, key=lambda item: item.date)
    if not ordered:
        return None

    window_end = ordered[-1].date
    cutoff = shift_months(window_end, months)
    in_window = [row for row in ordered if row.date >= cutoff]
    if not in_window:
        in_window = [ordered[-1]]

    start_row = in_window[0]
    end_row = in_window[-1]
    high_row = max(in_window, key=_row_high)
    low_row = min(in_window, key=_row_low)

    start_price = float(start_row.close_price)
    end_price = float(end_row.close_price)
    change_pct = (end_price - start_price) / start_price * 100 if start_price else 0.0
    high = _row_high(high_row)
    low = _row_low(low_row)
    amplitude_pct = (high - low) / low * 100 if low else 0.0

    earliest = earliest_available or ordered[0].date
    full_window = earliest <= cutoff
    if full_window:
        label = f"近 {months} 个月"
    else:
        span_days = max((window_end - earliest).days, 1)
        span_months = max(1, round(span_days / 30.44))
        label = f"全部可得数据（不足 {months} 个月，实际约 {span_months} 个月）"

    return PriceWindow(
        window_start=start_row.date,
        window_end=end_row.date,
        start_price=start_price,
        end_price=end_price,
        change_pct=change_pct,
        high=high,
        low=low,
        high_date=high_row.date,
        low_date=low_row.date,
        amplitude_pct=amplitude_pct,
        full_window=full_window,
        label=label,
    )


def compute_price_window(
    db: Session,
    *,
    months: int = WINDOW_MONTHS,
    end: Optional[date] = None,
) -> Optional[PriceWindow]:
    """从数据库取数并计算滚动窗口；没有任何价格数据时返回 None。"""

    query = db.query(GoldPrice)
    if end is not None:
        query = query.filter(GoldPrice.date <= end)
    rows = query.order_by(GoldPrice.date.asc()).all()
    if not rows:
        return None
    earliest = db.query(func.min(GoldPrice.date)).scalar()
    return summarize_window(rows, months=months, earliest_available=earliest)
