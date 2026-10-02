"""多尺度权重：每个周期有自己的主控层，得分不能全尺度一个样。"""
from __future__ import annotations

import pandas as pd
import pytest

from app.services.quant import engine
from app.services.quant.definitions import (
    FACTORS,
    HORIZONS,
    HORIZON_SPECS,
    factor_by_key,
    horizon_spec,
)


def test_horizon_specs_cover_every_horizon_in_order():
    assert HORIZONS == (1, 5, 20, 60, 250)
    assert [spec.horizon for spec in HORIZON_SPECS] == list(HORIZONS)
    assert all(spec.label and spec.scale and spec.description for spec in HORIZON_SPECS)
    assert {spec.horizon for spec in HORIZON_SPECS} == set(horizon_spec)


def test_every_factor_declares_all_five_horizon_weights():
    for factor in FACTORS:
        declared = dict(factor.horizon_weights)
        assert set(declared) == set(HORIZONS), factor.key
        assert all(weight >= 0 for weight in declared.values()), factor.key


def test_short_horizons_lean_on_flows_and_long_horizons_on_demand():
    """方法论第一步的可执行断言：短尺度资金流主导、长尺度央行购金主导。"""
    momentum = factor_by_key["momentum"]
    cftc = factor_by_key["cftc_positioning"]
    central_bank = factor_by_key["central_bank"]

    assert momentum.weight_for(1) > momentum.weight_for(250)
    assert cftc.weight_for(1) > cftc.weight_for(250)
    assert central_bank.weight_for(250) > central_bank.weight_for(1)


def test_score_changes_when_the_horizon_changes():
    index = pd.date_range("2026-01-01", periods=1, freq="B")
    signals = pd.DataFrame(
        {
            "real_yield_10y": [1.0],
            "momentum": [-1.0],
            "central_bank": [0.5],
        },
        index=index,
    )

    short = engine.composite_score(signals, horizon=1).iloc[0]
    long = engine.composite_score(signals, horizon=250).iloc[0]

    # 短尺度动量权重 1.0 主导 → 为负；长尺度央行权重 1.0 主导 → 为正
    assert short < 0 < long


def test_direction_publication_stops_only_the_horizons_without_an_edge():
    """方向发布策略：算得出方向 ≠ 该发布方向，只停留出期拿不出优势的尺度。

    变异验证：把 250 从 NOT_PUBLISHED_DIRECTION_REASONS 里删掉（方向照发），
    本用例必红。
    """
    from app.services.quant.definitions import (
        DIRECTION_NOT_PUBLISHED,
        DIRECTION_PUBLISHED,
        NOT_PUBLISHED_DIRECTION_REASONS,
        direction_publication,
    )

    assert set(NOT_PUBLISHED_DIRECTION_REASONS) == {250}
    status, reason = direction_publication(250)
    assert status == DIRECTION_NOT_PUBLISHED
    assert reason and "预注册" in reason
    for horizon in HORIZONS:
        if horizon == 250:
            continue
        assert direction_publication(horizon) == (DIRECTION_PUBLISHED, None)


def test_weight_for_falls_back_to_the_base_weight():
    momentum = factor_by_key["momentum"]

    assert momentum.weight_for(None) == momentum.weight
    assert momentum.weight_for(3) == momentum.weight  # 未声明的尺度


def test_snapshot_states_carry_the_horizon_weight(panel):
    factors, close = panel

    short = engine.build_snapshot(factors, close, horizon=1)
    long = engine.build_snapshot(factors, close, horizon=250)

    short_momentum = next(state for state in short.states if state.key == "momentum")
    long_momentum = next(state for state in long.states if state.key == "momentum")
    assert short_momentum.weight == pytest.approx(1.0)
    assert long_momentum.weight == pytest.approx(0.2)

    assert short.weight_used == pytest.approx(
        sum(state.weight for state in short.states if state.available)
    )
    assert long.weight_used == pytest.approx(
        sum(state.weight for state in long.states if state.available)
    )
    assert short.weight_used != long.weight_used
