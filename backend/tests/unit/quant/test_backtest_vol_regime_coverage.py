"""区间覆盖率的**分档**口径：整体数字合格，不代表每个风险状态下都合格。

加这条守卫的动机是本轮实测的一个缺口：线上 ACI 口径在 26 年面板上的 80% 区间
整体覆盖率随尺度恶化（5 日 0.793 → 20 日 0.762 → 60 日 0.715）。分档之后才能回答
「这是尺度没跟着风险走，还是尾部整体被低估」：实测两档之差只有 ±6pp
（5 日 0.768/0.816、20 日 0.766/0.822、60 日 0.694/0.667），
而区间宽度确实随波动率放大（20 日 0.090 → 0.150）—— 所以问题不在分档失衡，
在于**长尺度整体低估了尾部**。这一行结论要靠这个指标才看得见，故先有指标。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import backtest


def _panel(blocks: tuple[tuple[int, float], ...], seed: int = 4) -> pd.Series:
    """按 (天数, 日波动率) 的分段拼一条合成金价序列。"""
    rng = np.random.default_rng(seed)
    returns = np.concatenate([rng.normal(0.0, sigma, days) for days, sigma in blocks])
    calendar = pd.date_range("2000-01-03", periods=len(returns), freq="B")
    return pd.Series(2000.0 * np.exp(np.cumsum(returns)), index=calendar)


def _fixed_band(close: pd.Series, horizon: int, half: float = 0.01):
    """一条与波动率**无关**的固定区间 —— 专门用来暴露「不随风险缩放」这件事。"""
    forward = close.shift(-horizon) / close - 1.0
    lower = pd.Series(-half, index=close.index)
    upper = pd.Series(half, index=close.index)
    return forward, lower, upper


@pytest.mark.unit
def test_a_fixed_interval_looks_middling_overall_and_fails_where_it_matters():
    """整体覆盖率必须落在两档之间 —— 这正是「只看整体数字」会把缺口藏起来的地方。"""
    close = _panel(((600, 0.002), (600, 0.03), (600, 0.002)))
    horizon = 5
    forward, lower, upper = _fixed_band(close, horizon, half=0.02)

    out = backtest.coverage_by_vol_regime(horizon, close, forward, lower, upper)
    calm = out["buckets"]["calm"]
    turbulent = out["buckets"]["turbulent"]
    overall = backtest.interval_coverage_80(
        forward[forward.notna()], lower[forward.notna()], upper[forward.notna()]
    )

    assert calm["coverage"] is not None and calm["coverage"] > 0.9, out
    assert turbulent["coverage"] is not None and turbulent["coverage"] < 0.5, out
    assert turbulent["coverage"] < overall < calm["coverage"], (
        f"整体数字 {overall} 没有落在两档之间，分档没有揭示任何东西"
    )
    assert out["gap_turbulent_minus_calm"] < -0.4
    # 宽度也一起给：分档不看宽度就会奖励「一律放宽」这种假校准
    assert turbulent["mean_width"] == pytest.approx(0.04)


@pytest.mark.unit
def test_a_bucket_without_enough_independent_bets_reports_none_not_a_number():
    """某一档只攒了十几次独立下注时，不许把那个比例当结论。

    变异验证：把 ``len(sampled) >= MIN_NONOVERLAPPING_SAMPLES`` 的门槛删掉，
    本测试的 coverage 断言必红（十几次的比例会被当成 0.x 报出来）。
    """
    close = _panel(((950, 0.002), (100, 0.03)))
    horizon = 60  # 一年尺度的下注本来就少：1050 个交易日 ÷ 60 远不到 30 次
    forward, lower, upper = _fixed_band(close, horizon, half=0.02)

    out = backtest.coverage_by_vol_regime(horizon, close, forward, lower, upper)
    turbulent = out["buckets"]["turbulent"]
    calm = out["buckets"]["calm"]

    assert 0 < turbulent["bets"] < out["min_bets"], turbulent
    assert turbulent["coverage"] is None and calm["coverage"] is None
    assert out["gap_turbulent_minus_calm"] is None
    assert "独立下注" in out["reason"]


@pytest.mark.unit
def test_early_history_is_not_bucketed_with_thresholds_that_come_from_the_future():
    """分档阈值只能由**当时已知**的波动率分布决定。

    把动荡段放在最前面：如果用全样本分位数（事后信息），那 400 天会被认成「热闹档」；
    用 expanding 分位数就没有 —— 阈值要到第 500 天才存在，而那时动荡段早已过去。

    变异验证：把任一个 ``vol.expanding(...).quantile(...)`` 换成 ``vol.quantile(...)`` 都会红
    —— 两侧阈值的可用区间一旦错开，函数自己抛 AssertionError；只换 high_q 时
    ``turbulent["bets"] == 0`` 那条也必红。
    """
    close = _panel(((400, 0.05), (600, 0.002)))
    horizon = 5
    forward, lower, upper = _fixed_band(close, horizon, half=0.02)

    out = backtest.coverage_by_vol_regime(horizon, close, forward, lower, upper)

    # 阈值本身要攒够历史才存在：那之前的行一律不分档（两个阈值都要 expanding）
    start = 2 * backtest.VOL_REGIME_MIN_HISTORY  # 波动率攒够 250 个观测，阈值再攒 250 个
    # 第一个可用阈值出现在第 start 行（含），所以可分档的行数不会超过 len - start + 1
    assert 0 < out["eligible_rows"] <= len(close) - start + 1, out["eligible_rows"]
    assert out["buckets"]["turbulent"]["bets"] == 0, out["buckets"]["turbulent"]
    assert out["buckets"]["turbulent"]["coverage"] is None


@pytest.mark.unit
def test_a_panel_too_short_to_split_says_so_instead_of_inventing_buckets():
    close = _panel(((300, 0.002), (100, 0.03)))
    horizon = 5
    forward, lower, upper = _fixed_band(close, horizon, half=0.02)

    out = backtest.coverage_by_vol_regime(horizon, close, forward, lower, upper)

    assert out["eligible_rows"] == 0
    assert out["buckets"] == {}
    assert out["gap_turbulent_minus_calm"] is None
    assert "不给" in out["reason"] or "不足" in out["reason"]


@pytest.mark.unit
def test_evaluation_carries_the_banded_coverage_for_every_horizon(make_panel):
    """字段契约：线上评估必须真的带上这一项（否则分档只活在单元测试里）。

    变异验证：把 metrics 里的 ``interval_coverage_by_vol_regime`` 删掉，本测试红。
    """
    factors, close = make_panel(pd.date_range("2005-01-03", "2026-09-30", freq="B"))

    metrics = backtest.evaluate_horizon(factors, close, horizon=20).metrics

    banded = metrics["interval_coverage_by_vol_regime"]
    assert set(banded) >= {"buckets", "gap_turbulent_minus_calm", "window_days", "min_bets"}
    assert set(banded["buckets"]) == {"calm", "turbulent"}
    assert banded["window_days"] == backtest.VOL_REGIME_WINDOW
    for bucket in banded["buckets"].values():
        assert set(bucket) == {"bets", "coverage", "mean_width"}
        assert bucket["bets"] >= 0
