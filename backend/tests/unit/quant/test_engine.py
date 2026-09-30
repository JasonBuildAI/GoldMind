"""信号引擎：合成得分的归一、方向、降级与新鲜度。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import engine
from app.services.quant.definitions import BENCHMARK_KEY, FACTORS


def test_snapshot_covers_every_factor_and_contributions_sum_to_the_score(panel):
    factors, close = panel

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    assert snapshot.status == engine.STATUS_OK
    assert snapshot.available_factors == len(FACTORS)
    contributions = [state.contribution for state in snapshot.states if state.available]
    assert len(contributions) == len(FACTORS)
    assert sum(contributions) == pytest.approx(snapshot.score, abs=1e-12)
    assert snapshot.weight_used == pytest.approx(sum(f.weight_for(5) for f in FACTORS))


def test_direction_follows_the_sign_of_the_score(panel):
    factors, close = panel
    snapshot = engine.build_snapshot(factors, close, horizon=1)

    assert snapshot.direction == ("up" if snapshot.score > 0 else "down")


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


def test_short_history_falls_back_to_the_base_price(calendar, make_panel):
    """回归样本不足时 β=0：目标价 = 基准价，而不是编出来的数字。"""
    short = calendar[-100:]
    factors, close = make_panel(short)

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    assert snapshot.status == engine.STATUS_OK
    assert snapshot.expected_return == 0.0
    assert snapshot.target_price == pytest.approx(snapshot.base_price)


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
