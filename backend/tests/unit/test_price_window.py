"""滚动价格窗口（`price_window`）的测试。

背景：统计窗口此前写死 2025-01-01，进入 2026 年后「年内涨幅」实际是
21 个月的涨幅；「波动区间」又被当成波动率展示。这里把新口径逐项钉死：

- 锚点是数据里最新的一行，不是「今天」，更不是写死的年份；
- 涨跌幅只比较窗口首末**收盘价**；
- 高低振幅 =(最高−最低)/最低，不是波动率；
- 不足 12 个月如实标注实际跨度；没有任何数据时返回 None（不造数）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pytest

from app.services.price_window import (
    WINDOW_MONTHS,
    compute_price_window,
    shift_months,
    summarize_window,
)


@dataclass
class Row:
    """满足 PriceRow 协议的最小价格行。"""

    date: date
    close_price: float
    high_price: float | None = None
    low_price: float | None = None


def _row(day: str, close: float, high: float | None = None, low: float | None = None) -> Row:
    return Row(date=date.fromisoformat(day), close_price=close, high_price=high, low_price=low)


# --------------------------------------------------------------------------- #
# shift_months：月末日期按目标月天数收敛
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_shift_months_clamps_month_end():
    assert shift_months(date(2026, 3, 31), 1) == date(2026, 2, 28)
    assert shift_months(date(2024, 3, 31), 1) == date(2024, 2, 29)  # 闰年
    assert shift_months(date(2026, 3, 30), 1) == date(2026, 2, 28)
    assert shift_months(date(2026, 1, 15), 12) == date(2025, 1, 15)


@pytest.mark.unit
def test_window_months_is_a_pinned_decision():
    """窗口长度是全局口径决策：改它必须同时更新所有消费方与测试。"""
    assert WINDOW_MONTHS == 12


# --------------------------------------------------------------------------- #
# 锚点与边界
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_anchor_is_the_latest_data_day_not_today():
    """窗口锚定数据里的最新一行；数据停在 2025-06-30 时不能按运行日算。"""
    rows = [
        _row("2024-05-01", 100),  # 比窗口更早，落在窗外
        _row("2024-07-01", 110),
        _row("2024-12-01", 120),
        _row("2025-06-30", 150),
    ]

    window = summarize_window(rows)

    assert window.window_end == date(2025, 6, 30)
    # cutoff = 2025-06-30 往前 12 个月 = 2024-06-30，第一行在窗口内的是 2024-07-01
    assert window.window_start == date(2024, 7, 1)
    assert window.full_window is True
    assert window.label == "近 12 个月"


@pytest.mark.unit
def test_change_pct_compares_first_and_last_close():
    """涨幅 = (末收盘 − 首收盘) / 首收盘；中间的暴跌暴涨不参与。"""
    rows = [
        _row("2024-07-01", 100, high=110, low=90),
        _row("2024-12-01", 60, high=130, low=50),
        _row("2025-06-30", 150, high=160, low=55),
    ]

    window = summarize_window(rows)

    assert window.change_pct == pytest.approx(50.0)
    assert window.amplitude_pct == pytest.approx((160 - 50) / 50 * 100)


@pytest.mark.unit
def test_amplitude_uses_high_and_low_not_close_and_is_named_honestly():
    """振幅用期间最高/最低，而不是收盘；它和涨跌幅是两个不同的数。"""
    rows = [
        _row("2024-07-01", 100, high=100, low=100),
        _row("2025-01-01", 101, high=200, low=99),
        _row("2025-06-30", 100, high=100, low=50),
    ]

    window = summarize_window(rows)

    assert window.change_pct == pytest.approx(0.0)
    assert window.amplitude_pct == pytest.approx(300.0)  # (200−50)/50
    assert window.high == 200
    assert window.low == 50
    assert window.high_date == date(2025, 1, 1)
    assert window.low_date == date(2025, 6, 30)


@pytest.mark.unit
def test_missing_high_low_falls_back_to_close():
    rows = [_row("2025-01-01", 100), _row("2025-06-30", 120)]

    window = summarize_window(rows)

    assert window.high == 120
    assert window.low == 100


@pytest.mark.unit
def test_partial_window_label_states_the_real_span():
    rows = [_row("2025-05-01", 100), _row("2025-06-30", 110)]

    window = summarize_window(rows)

    assert window.full_window is False
    assert "不足 12 个月" in window.label
    assert "实际约 2 个月" in window.label


@pytest.mark.unit
def test_empty_input_returns_none_instead_of_fabricating():
    assert summarize_window([]) is None


# --------------------------------------------------------------------------- #
# 数据库入口：锚点与「最早可用数据」都来自库
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_compute_price_window_uses_latest_row_as_anchor(db_session):
    from app.models.gold_price import GoldPrice

    for day, close in [("2024-06-15", 600.0), ("2024-07-01", 700.0), ("2025-06-30", 900.0)]:
        db_session.add(
            GoldPrice(date=date.fromisoformat(day), close_price=close, high_price=close + 1, low_price=close - 1)
        )
    db_session.commit()

    window = compute_price_window(db_session)

    assert window.window_end == date(2025, 6, 30)
    assert window.start_price == 700.0        # 2024-06-15 在窗口外（cutoff=2024-06-30）
    assert window.end_price == 900.0
    assert window.change_pct == pytest.approx((900 - 700) / 700 * 100)
    assert window.full_window is True          # 库里最早数据早于 cutoff


@pytest.mark.integration
def test_compute_price_window_returns_none_on_empty_db(db_session):
    assert compute_price_window(db_session) is None
