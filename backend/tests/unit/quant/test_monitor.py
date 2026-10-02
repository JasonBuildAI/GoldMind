"""监测仪表盘：逐行信号规则、数值口径与降级。"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.services.quant import monitor, storage


def _series(values, *, periods=None, end="2026-09-30") -> pd.Series:
    if periods is None:
        periods = len(values)
    return pd.Series(values, index=pd.date_range(end=end, periods=periods, freq="B"), dtype="float64")


@pytest.mark.parametrize(
    "key, bull_values, bear_values",
    [
        ("real_yield_10y", [2.0] * 6 + [1.7], [2.0] * 6 + [2.3]),
        ("inflation_expectation", [2.0] * 6 + [2.3], [2.0] * 6 + [1.7]),
        ("dollar_index", [100.0] * 6 + [98.0], [100.0] * 6 + [102.0]),
        ("policy_expectation", [1.0] * 6 + [0.7], [1.0] * 6 + [1.3]),
        ("central_bank", [7600.0, 7610.0], [7600.0, 7590.0]),
        ("etf_shares", [260_000_000.0, 261_000_000.0], [260_000_000.0, 259_000_000.0]),
        ("vix", [18.0] * 6 + [30.0], [18.0] * 6 + [12.0]),
        ("credit_appetite", [0.0] * 6 + [-3.0], [0.0] * 6 + [3.0]),
        ("tga", [900_000.0] * 21 + [840_000.0], [900_000.0] * 21 + [960_000.0]),
        ("rrp", [300.0] * 21 + [240.0], [300.0] * 21 + [380.0]),
    ],
)
def test_threshold_rules_flip_with_constructed_data(key, bull_values, bear_values):
    bull_signal, _ = monitor._rule(key, _series(bull_values))
    bear_signal, _ = monitor._rule(key, _series(bear_values))

    assert bull_signal == monitor.SIGNAL_BULL, f"{key} 的看涨方向判反了"
    assert bear_signal == monitor.SIGNAL_BEAR, f"{key} 的看跌方向判反了"


def test_cftc_crowding_is_contrarian():
    calm = [100.0, 101.0] * 30

    crowded_long, _ = monitor._rule("cftc_positioning", _series(calm + [140.0]))
    crowded_short, _ = monitor._rule("cftc_positioning", _series(calm + [60.0]))
    balanced, _ = monitor._rule("cftc_positioning", _series(calm + [100.5]))

    assert crowded_long == monitor.SIGNAL_BEAR, "多头拥挤应当看跌"
    assert crowded_short == monitor.SIGNAL_BULL, "空头拥挤应当看涨"
    assert balanced == monitor.SIGNAL_NEUTRAL


def test_info_rows_never_get_a_direction():
    for key in ("usdcny", "cny_gold", "cftc_oi"):
        signal, change = monitor._rule(key, _series([7.0] * 10))
        assert signal is None, f"{key} 是信息行，不应该有多空信号"
        assert change is not None


def test_monitor_reports_values_changes_and_dates(db_session):
    calendar = pd.date_range(end="2026-09-30", periods=200, freq="B")
    gold = pd.Series(np.linspace(2000.0, 2400.0, len(calendar)), index=calendar)
    storage.upsert_series(db_session, "gold_close", gold, source="测试夹具")
    yields = pd.Series([2.0] * 199 + [1.7], index=calendar)
    storage.upsert_series(db_session, "real_yield_10y", yields, source="测试夹具")

    result = monitor.build_monitor(db_session)

    rows = {row["key"]: row for row in result["rows"]}
    assert len(result["rows"]) >= 10
    assert rows["real_yield_10y"]["signal"] == "bull"
    assert rows["real_yield_10y"]["value"] == pytest.approx(1.7)
    assert rows["real_yield_10y"]["change"] == pytest.approx(-0.3)
    assert rows["real_yield_10y"]["obs_date"] == "2026-09-30"
    assert rows["ma200"]["status"] == "ok"
    expected_ma = gold.rolling(200, min_periods=120).mean().iloc[-1]
    assert rows["ma200"]["value"] == pytest.approx(expected_ma)
    assert rows["ma200"]["change"] == pytest.approx((gold.iloc[-1] / expected_ma - 1) * 100)
    assert result["as_of"] == date(2026, 9, 30)

    for row in result["rows"]:
        assert row["status"] in ("ok", "unavailable", "stale")
        if row["status"] == "unavailable":
            assert row["reason"], f"{row['key']} 不可用却没有原因"
            assert row["value"] is None
        else:
            assert row["value"] is not None
            assert row["obs_date"] is not None


def test_empty_database_marks_every_row_unavailable_with_reason(db_session):
    result = monitor.build_monitor(db_session)

    assert result["rows"]
    for row in result["rows"]:
        assert row["status"] == "unavailable"
        assert row["reason"]
        assert row["signal"] is None
        assert row["signal_label"] == "不可用"


def test_shanghai_premium_is_honestly_unavailable(db_session):
    result = monitor.build_monitor(db_session)

    row = next(item for item in result["rows"] if item["key"] == "shanghai_premium")
    assert row["status"] == "unavailable"
    assert "不编数" in row["reason"]


def test_ma200_without_enough_history_is_unavailable(db_session):
    short = _series([2000.0] * 50, periods=50)
    storage.upsert_series(db_session, "gold_close", short, source="测试夹具")

    result = monitor.build_monitor(db_session)

    row = next(item for item in result["rows"] if item["key"] == "ma200")
    assert row["status"] == "unavailable"
    assert "历史样本不足" in row["reason"]


def test_stale_rows_keep_the_number_but_lose_the_signal(db_session):
    """仪表盘按声明的更新节奏判陈旧：数值与观测日照示，但不再给多空方向。

    变异验证：把 `_freshness` 的 `age > budget` 改成恒 False（等于不判陈旧），
    本测试第一条断言必红。陈旧分支在算信号之前就返回，所以「带着方向显示陈旧值」
    这条路在结构上不存在 —— 断言 `signal is None` 是把这个结构钉住，防止以后
    有人把返回顺序挪到 `_rule` 之后。
    """
    calendar = pd.date_range(end="2026-09-30", periods=200, freq="B")
    gold = pd.Series(np.linspace(2000.0, 2400.0, len(calendar)), index=calendar)
    storage.upsert_series(db_session, "gold_close", gold, source="测试夹具")

    # 周频序列（cftc_positioning，上限 14 天）最后一次观测停在 40 天前
    weekly = pd.Series(
        [100.0, 101.0] * 20, index=pd.date_range(end="2026-08-21", periods=40, freq="W-FRI")
    )
    storage.upsert_series(db_session, "cftc_positioning", weekly, source="测试夹具")
    # 日频序列照常更新 —— 用来证明判定不是「一律陈旧」
    vix = pd.Series([18.0] * 199 + [30.0], index=calendar)
    storage.upsert_series(db_session, "vix", vix, source="测试夹具")

    rows = {row["key"]: row for row in monitor.build_monitor(db_session)["rows"]}

    stale = rows["cftc_positioning"]
    assert stale["status"] == monitor.STATUS_STALE
    assert stale["signal"] is None and stale["signal_label"] == "陈旧"
    assert stale["value"] == pytest.approx(101.0)
    assert stale["obs_date"] == "2026-08-21"
    assert "40 天" in stale["reason"]
    # 参照系是金价日历（红线五），不是服务器时间
    assert rows["vix"]["status"] == "ok" and rows["vix"]["signal"] == "bull"
