"""情景：分位数口径、自洽性、触发条件与降级。

情景层**不再自己算分位数**：它只把 ``engine`` 校准分布给出的四分位换算成价格。
所以这里的测试盯两件事 —— 换算口径与「缺四分位就拒答」，
而不是（曾经那样的）``μ ± z·σ``：那会让情景区间与页面上的 80% 区间出自两套分布。
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from app.services.quant import engine, scenarios


def _snapshot(panel, horizon=20):
    factors, close = panel
    snapshot = engine.build_snapshot(factors, close, horizon=horizon)
    assert snapshot.status == engine.STATUS_OK
    return snapshot, close


def test_base_range_is_the_snapshot_interquartile(panel):
    snapshot, close = _snapshot(panel)

    result = scenarios.build_scenarios(snapshot, close)

    assert result.status == scenarios.STATUS_OK
    expected_low = snapshot.base_price * (1.0 + snapshot.scenario_low_return)
    expected_high = snapshot.base_price * (1.0 + snapshot.scenario_high_return)
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
    assert (
        by_key["base"].probability + by_key["bull"].probability + by_key["bear"].probability == 1.0
    )
    assert [by_key[key].probability for key in ("base", "bull", "bear")] == [0.5, 0.25, 0.25]


def test_scenarios_never_invent_a_distribution_the_snapshot_lacks(panel):
    """四分位缺失 / 顺序异常 / 基准价缺失都拒答，不退回「正态 μ ± z·σ」另算一套。"""
    snapshot, close = _snapshot(panel)

    cases = [
        ({"scenario_low_return": None}, "四分位"),
        ({"scenario_high_return": None}, "四分位"),
        ({"scenario_low_return": 0.10, "scenario_high_return": 0.02}, "顺序异常"),
        ({"base_price": None}, "基准价"),
    ]
    for changes, keyword in cases:
        result = scenarios.build_scenarios(replace(snapshot, **changes), close)
        assert result.status == scenarios.STATUS_UNAVAILABLE, changes
        assert keyword in result.reason, changes
        assert result.scenarios == ()
        assert result.range_low is None and result.range_high is None


def test_scenario_width_tracks_the_calibrated_quartile_spread(panel):
    snapshot, close = _snapshot(panel)

    narrow = scenarios.build_scenarios(snapshot, close)
    wide = scenarios.build_scenarios(
        replace(
            snapshot,
            scenario_low_return=snapshot.scenario_low_return * 2.0,
            scenario_high_return=snapshot.scenario_high_return * 2.0,
        ),
        close,
    )

    narrow_width = narrow.range_high - narrow.range_low
    wide_width = wide.range_high - wide.range_low
    expected = (
        snapshot.base_price
        * (snapshot.scenario_high_return - snapshot.scenario_low_return)
        * 2.0
    )
    assert wide_width == pytest.approx(narrow_width * 2.0, rel=1e-9)
    assert wide_width == pytest.approx(expected, rel=1e-9)


def test_price_at_return_maps_the_declared_return_onto_the_base_price():
    assert scenarios.price_at_return(2000.0, 0.0) == pytest.approx(2000.0)
    assert scenarios.price_at_return(2000.0, 0.05) == pytest.approx(2100.0)
    assert scenarios.price_at_return(2000.0, -0.05) == pytest.approx(1900.0)
    # 与目标价同一个换算口径（简单收益），不是另一种复利
    assert scenarios.price_at_return(2000.0, 0.05) == pytest.approx(2000.0 * 1.05)


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
    ],
)
def test_unavailable_prediction_carries_its_reason(panel, changes, keyword):
    snapshot, close = _snapshot(panel)

    result = scenarios.build_scenarios(replace(snapshot, **changes), close)

    assert result.status == scenarios.STATUS_UNAVAILABLE
    assert keyword in result.reason
    assert result.scenarios == ()
