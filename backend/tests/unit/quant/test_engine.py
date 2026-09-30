"""信号引擎：合成得分的归一、方向、降级与新鲜度。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import engine
from app.services.quant.definitions import BENCHMARK_KEY, FACTORS, HORIZONS


def test_snapshot_covers_every_factor_and_contributions_sum_to_the_score(panel):
    factors, close = panel

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    assert snapshot.status == engine.STATUS_OK
    assert snapshot.available_factors == len(FACTORS)
    contributions = [state.contribution for state in snapshot.states if state.available]
    assert len(contributions) == len(FACTORS)
    assert sum(contributions) == pytest.approx(snapshot.score, abs=1e-12)
    assert snapshot.weight_used == pytest.approx(sum(f.weight_for(5) for f in FACTORS))


def _snapshot(*, score: float, expected_return: float) -> engine.SignalSnapshot:
    return engine.SignalSnapshot(
        as_of=pd.Timestamp("2026-09-30").date(),
        horizon_days=5,
        status=engine.STATUS_OK,
        reason=None,
        base_price=4200.0,
        score=score,
        probability_up=0.5,
        expected_return=expected_return,
        uncertainty=0.02,
        target_price=4200.0 * (1.0 + expected_return),
        states=(),
        weight_used=1.0,
    )


def test_direction_follows_the_calibrated_expectation():
    """方向 = sign(μ)，不是未校准的得分符号（spec 判据）。

    变异验证：把 direction 改回 ``"up" if score > 0 else "down"``，本测试必红
    —— 这里构造的正是「得分为正、期望收益为负」（页面此前会同时显示看跌与上调目标价）。
    """
    assert _snapshot(score=+2.0, expected_return=-0.01).direction == "down"
    assert _snapshot(score=-2.0, expected_return=+0.01).direction == "up"
    # μ=0（回归样本不足，目标价=基准价）既不看涨也不看跌
    assert _snapshot(score=+2.0, expected_return=0.0).direction == "flat"


def test_probability_up_comes_from_the_same_distribution():
    """p_up = Φ(μ/σ)：与目标价、区间、情景同一个分布（spec 判据）。

    变异验证：把 p_up 改回 ``Φ(score/σ_score)``，第一行断言必红 —— 得分为正、
    期望收益为负时，那个写法给出的概率大于 0.5，与方向、目标价互相矛盾。
    """
    expected = pd.Series([0.02, -0.02, 0.0])
    sigma = pd.Series([0.01, 0.01, 0.01])

    probability = engine.probability_up(expected, sigma)

    assert probability.iloc[0] == pytest.approx(0.9772, abs=1e-4)  # Φ(2)
    assert probability.iloc[1] == pytest.approx(0.0228, abs=1e-4)  # Φ(−2)
    assert probability.iloc[2] == pytest.approx(0.5, abs=1e-9)
    # σ 缺失或非正时不给概率，也不退回 50%
    assert pd.isna(engine.probability_up(pd.Series([0.01]), pd.Series([np.nan])).iloc[0])
    assert pd.isna(engine.probability_up(pd.Series([0.01]), pd.Series([0.0])).iloc[0])


def test_uncertainty_is_the_walk_forward_error_not_the_fit_residual(calendar, make_panel):
    """σ 回答「模型自己错了多少」：t 时刻只用 s + h ≤ t 的已实现预测误差（spec 判据）。

    变异验证：把 uncertainty 改回回归残差 σ，第一条断言的相对误差约 23%（长尺度），必红。
    """
    horizon = 250
    factors, close = make_panel(calendar)
    signals = engine.build_signals(engine.align_factors(factors, calendar), calendar)
    score = engine.composite_score(signals, horizon=horizon)

    frame = engine.build_prediction_frame(score, close, horizon)

    forward = close.shift(-horizon) / close - 1.0
    alpha, beta, residual_sigma, calibrated = engine.expanding_ols(
        score.shift(horizon), forward.shift(horizon)
    )
    # 未校准的时段没有发布预测，它的「误差」不算数（μ 是 NaN 而不是 0）
    published = (alpha + beta * score).where(calibrated)
    manual = ((forward - published).shift(horizon)).expanding(
        min_periods=engine.MIN_ERRORS_FOR_SIGMA
    ).std()

    assert frame["uncertainty"].iloc[-1] == pytest.approx(float(manual.iloc[-1]), rel=1e-9)
    # 误差口径必须大于残差口径，否则这条守卫对「换回残差」的变异不敏感
    assert frame["uncertainty"].iloc[-1] > float(residual_sigma.iloc[-1]) * 1.1


def test_every_horizon_publishes_one_story(panel):
    """页面上的方向、目标价、概率必须自洽 —— 同一份分布出来的三个说法。"""
    factors, close = panel

    for horizon in HORIZONS:
        snapshot = engine.build_snapshot(factors, close, horizon=horizon)

        assert snapshot.status == engine.STATUS_OK
        expected = snapshot.expected_return
        assert expected is not None
        expected_direction = "up" if expected > 0 else "down" if expected < 0 else "flat"
        assert snapshot.direction == expected_direction, f"h={horizon}"
        # 目标价相对基准价的方向 = 期望收益的符号
        assert (snapshot.target_price - snapshot.base_price) * expected >= 0, f"h={horizon}"
        # 上行概率与期望收益同号（μ=0 时正好 0.5）
        assert (snapshot.probability_up - 0.5) * expected >= 0, f"h={horizon}"


def test_change_transform_uses_the_declared_lag(calendar):
    values = pd.Series(np.arange(30, dtype="float64"), index=calendar[:30])

    changed = engine.apply_transform(values, "change_20d")

    assert changed.iloc[19] != changed.iloc[19]  # NaN
    assert changed.iloc[20] == 20.0
    # 原单位（这里是「点」），不是百分比
    assert engine.apply_transform(values, "level").iloc[0] == 0.0


def test_missing_factors_do_not_count_as_zero():
    index = pd.date_range("2026-01-01", periods=3, freq="B")
    both = pd.DataFrame({"real_yield_10y": [1.0] * 3, "vix": [2.0] * 3}, index=index)
    only_one = pd.DataFrame({"real_yield_10y": [1.0] * 3, "vix": [np.nan] * 3}, index=index)

    weight_10y = 1.0
    weight_vix = 0.4
    assert engine.composite_score(both).iloc[0] == pytest.approx(1.8 / 1.4)
    # 缺 VIX 时按剩余权重归一：得分等于 10Y 自己的信号，而不是被 VIX 的 0 拉低
    assert engine.composite_score(only_one).iloc[0] == pytest.approx(weight_10y / weight_10y)


def test_alignment_only_fills_forward(calendar):
    sparse = pd.Series([1.0], index=[calendar[10]])

    aligned = engine.align_factors({"vix": sparse}, calendar)["vix"]

    assert np.isnan(aligned.iloc[9])
    assert aligned.iloc[10] == 1.0
    assert aligned.iloc[11] == 1.0  # 前向填充


def test_stale_data_is_marked_and_excluded(panel, calendar):
    factors, close = panel
    # VIX 的更新周期是 7 天：把最后 60 天的数据删掉，它就该被判为陈旧
    factors["vix"] = factors["vix"].iloc[:-60]

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    state = next(state for state in snapshot.states if state.key == "vix")
    assert state.status == engine.STATUS_STALE
    assert state.available is False
    assert "天前" in state.reason
    assert snapshot.available_factors == len(FACTORS) - 1


def test_factor_without_any_data_is_marked_missing(panel):
    factors, close = panel
    factors.pop("bitcoin")

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    state = next(state for state in snapshot.states if state.key == "bitcoin")
    assert state.status == engine.STATUS_MISSING
    assert state.value is None


def test_fewer_than_three_factors_refuses_to_predict(panel):
    factors, close = panel
    for factor in FACTORS[2:]:
        factors.pop(factor.key)

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    assert snapshot.status == engine.PREDICTION_UNAVAILABLE
    assert snapshot.score is None
    assert snapshot.target_price is None
    assert snapshot.direction is None
    assert "至少需要" in snapshot.reason


def test_missing_price_series_refuses_to_predict(panel):
    factors, _ = panel

    snapshot = engine.build_snapshot(factors, pd.Series(dtype="float64"), horizon=5)

    assert snapshot.status == engine.PREDICTION_UNAVAILABLE
    assert "价格" in snapshot.reason


def test_short_history_refuses_to_give_a_direction_or_target(calendar, make_panel):
    """没有校准就没有方向与目标价：给原因，而不是把「样本不足」说成「预期不变」。"""
    short = calendar[-100:]
    factors, close = make_panel(short)

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    assert snapshot.status == engine.PREDICTION_UNAVAILABLE
    assert "校准" in snapshot.reason
    assert snapshot.direction is None
    assert snapshot.expected_return is None
    assert snapshot.target_price is None


def test_probability_and_uncertainty_stay_inside_their_domains(panel):
    factors, close = panel
    snapshot = engine.build_snapshot(factors, close, horizon=20)

    assert 0.0 <= snapshot.probability_up <= 1.0
    assert snapshot.uncertainty >= 0.0


def test_horizons_are_independent(panel):
    factors, close = panel
    short = engine.build_snapshot(factors, close, horizon=1)
    long = engine.build_snapshot(factors, close, horizon=20)

    assert short.horizon_days == 1
    assert long.horizon_days == 20
    assert (short.expected_return, short.target_price) != (long.expected_return, long.target_price)


def test_benchmark_is_not_a_factor():
    assert BENCHMARK_KEY not in {factor.key for factor in FACTORS}
