"""情景：分位数口径、σ 的作用、触发条件与降级。"""
from __future__ import annotations

from dataclasses import replace
from statistics import NormalDist

import pytest

from app.services.quant import engine, scenarios

# Φ⁻¹(0.25)：Base 区间来自分布分位数这条口径的锚点，硬编码以免测试与实现共用同一个错误
Z25 = -0.6744897501960817


def _snapshot(panel, horizon=20):
    factors, close = panel
    snapshot = engine.build_snapshot(factors, close, horizon=horizon)
    assert snapshot.status == engine.STATUS_OK
    return snapshot, close


def test_base_range_is_the_interquartile_of_the_prediction_distribution(panel):
    snapshot, close = _snapshot(panel)

    result = scenarios.build_scenarios(snapshot, close)

    assert result.status == scenarios.STATUS_OK
    expected_low = snapshot.base_price * (1.0 + snapshot.expected_return + snapshot.uncertainty * Z25)
    expected_high = snapshot.base_price * (1.0 + snapshot.expected_return - snapshot.uncertainty * Z25)
    by_key = {scenario.key: scenario for scenario in result.scenarios}

    assert set(by_key) == {"base", "bull", "bear"}
    assert by_key["base"].price_low == pytest.approx(expected_low, rel=1e-9)
    assert by_key["base"].price_high == pytest.approx(expected_high, rel=1e-9)
    assert result.range_low == pytest.approx(expected_low, rel=1e-9)
    assert result.range_high == pytest.approx(expected_high, rel=1e-9)
    assert by_key["bull"].price_low == pytest.approx(expected_high, rel=1e-9)
    assert by_key["bull"].price_high is None
    assert by_key["bear"].price_high == pytest.approx(expected_low, rel=1e-9)
    assert by_key["bear"].price_low is None
    assert by_key["base"].probability + by_key["bull"].probability + by_key["bear"].probability == 1.0
    assert [by_key[key].probability for key in ("base", "bull", "bear")] == [0.5, 0.25, 0.25]


def test_scenario_width_is_proportional_to_uncertainty(panel):
    snapshot, close = _snapshot(panel)

    narrow = scenarios.build_scenarios(snapshot, close)
    wide = scenarios.build_scenarios(
        replace(snapshot, uncertainty=snapshot.uncertainty * 2.0), close
    )

    narrow_width = narrow.range_high - narrow.range_low
    wide_width = wide.range_high - wide.range_low
    assert wide_width == pytest.approx(narrow_width * 2.0, rel=1e-9)


def test_triggers_name_the_dominant_factor_and_the_ma200(panel):
    snapshot, close = _snapshot(panel)
    dominant = max(
        (state for state in snapshot.states if state.available),
        key=lambda state: state.weight,
    )
    ma = close.rolling(scenarios.MA_WINDOW, min_periods=scenarios.MIN_MA_SAMPLES).mean().iloc[-1]

    result = scenarios.build_scenarios(snapshot, close)

    assert result.status == scenarios.STATUS_OK
    for scenario in result.scenarios:
        assert dominant.name in scenario.trigger, f"{scenario.key} 触发条件没有最重因子"
        assert f"{ma:,.0f}" in scenario.trigger, f"{scenario.key} 触发条件没有 200 日均线数字"
        assert dominant.name in scenario.invalidation
        assert scenario.invalidation
    by_key = {scenario.key: scenario for scenario in result.scenarios}
    # Bull 的失效条件就是 Bear 的触发条件（互补），反之亦然
    assert by_key["bull"].invalidation == by_key["bear"].trigger
    assert by_key["bear"].invalidation == by_key["bull"].trigger


def test_missing_ma_history_is_stated_not_invented(panel):
    snapshot, close = _snapshot(panel)

    result = scenarios.build_scenarios(snapshot, close.iloc[:50])

    assert result.status == scenarios.STATUS_OK
    for scenario in result.scenarios:
        assert "历史样本不足" in scenario.trigger
        assert "200 日均线" in scenario.trigger


@pytest.mark.parametrize(
    "changes, keyword",
    [
        ({"status": engine.PREDICTION_UNAVAILABLE, "reason": "可用因子只有 2 个"}, "可用因子"),
        ({"expected_return": None}, "期望收益"),
        ({"uncertainty": None}, "不确定度"),
        ({"uncertainty": 0.0}, "不确定度"),
        ({"base_price": None}, "分布"),
    ],
)
def test_undefined_distribution_is_unavailable_with_a_reason(panel, changes, keyword):
    snapshot, close = _snapshot(panel)

    result = scenarios.build_scenarios(replace(snapshot, **changes), close)

    assert result.status == scenarios.STATUS_UNAVAILABLE
    assert keyword in result.reason
    assert result.scenarios == ()
    assert result.range_low is None and result.range_high is None


def test_price_quantile_moves_with_sigma():
    low, high = 0.2, 0.4

    assert scenarios.price_at_quantile(2000.0, 0.0, high, 0.25) < scenarios.price_at_quantile(
        2000.0, 0.0, low, 0.25
    )
    assert scenarios.price_at_quantile(2000.0, 0.0, high, 0.75) > scenarios.price_at_quantile(
        2000.0, 0.0, low, 0.75
    )
    assert scenarios.price_at_quantile(2000.0, 0.0, 0.0, 0.25) == pytest.approx(2000.0)

