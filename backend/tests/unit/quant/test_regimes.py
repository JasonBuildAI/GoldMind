"""第四轮 Regime 候选与基准对照：口径守卫（先写死、再执行）。

登记的候选定义在 ``app/services/quant/regimes.py``，执行在研究台
（``scripts/quant_lab.py``）。本文件只钉三件事：

1. 状态判定只用当日及以前的数据（无前视），且窗口不足一年不产生状态；
2. 状态不成立记中性 0 分 —— 不是反向；
3. 不可达的基准必须带原因，可达的必须写清口径（含展期）。

变异验证：把 ``regime_mask`` 的滚动窗口改成 ``center=True``（引入前视），
``test_regime_mask_does_not_look_ahead` 必红；把 ``apply_regime` 的
``where(mask, 0.0)`` 改成 ``where(mask, -score)``（反向），
``test_apply_regime_zeroes_outside_the_state_instead_of_flipping` 必红。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import regimes


def _calendar(days: int = 800) -> pd.DatetimeIndex:
    return pd.date_range(end="2026-09-30", periods=days, freq="B")


@pytest.mark.unit
def test_below_median_mask_waits_for_the_minimum_window():
    """窗口不满一年不产生状态；单调上升的序列不该落在「低于中位数」里。"""
    calendar = _calendar()
    values = np.linspace(100.0, 200.0, len(calendar))
    factors = {"real_yield_10y": pd.Series(values, index=calendar)}

    mask = regimes.regime_mask("R1", factors, calendar)

    assert not mask.iloc[: regimes.REGIME_MIN_OBSERVATIONS - 1].any()
    assert not mask.iloc[-1]

    descending = {"real_yield_10y": pd.Series(values[::-1], index=calendar)}
    mask = regimes.regime_mask("R1", descending, calendar)
    assert mask.iloc[regimes.REGIME_MIN_OBSERVATIONS :].all()


@pytest.mark.unit
def test_change_positive_mask_reads_the_level_change():
    """央行储备：同比（252 个交易日）为正 → 状态成立；走低 → 不成立。"""
    calendar = _calendar()
    values = np.concatenate([np.linspace(100.0, 200.0, 400), np.linspace(200.0, 150.0, 400)])
    factors = {"central_bank": pd.Series(values, index=calendar)}

    mask = regimes.regime_mask("R3", factors, calendar)

    assert mask.iloc[300]
    assert not mask.iloc[-1]


@pytest.mark.unit
def test_a_missing_series_means_no_state_not_a_direction():
    mask = regimes.regime_mask("R2", {}, _calendar(300))

    assert not mask.any()


@pytest.mark.unit
def test_apply_regime_zeroes_outside_the_state_instead_of_flipping():
    score = pd.Series([1.0, -1.0, 2.0], index=_calendar(3))
    mask = pd.Series([True, False, False], index=score.index)

    gated = regimes.apply_regime(score, mask)

    assert gated.tolist() == [1.0, 0.0, 0.0]


@pytest.mark.unit
def test_regime_mask_matches_a_backward_only_reference_point_by_point():
    """逐点对照一个只回看、绝不用未来值的参考实现。

    为什么不用「把未来换成垃圾值」那一招：滚动**中位数**对半数以内的污染是稳健的，
    居中窗口（center=True）恰好污染一半窗口，垃圾值法测不出来。逐点参考实现
    没有这个盲区 —— 只要窗口往未来多看一眼，期望值就会对不上。

    变异验证：把 ``regime_mask`` 的 rolling 加 ``center=True``，本测试红。
    """
    calendar = _calendar(700)
    rng = np.random.default_rng(3)
    values = 100.0 + np.cumsum(rng.normal(0.0, 1.0, len(calendar)))
    factors = {"real_yield_10y": pd.Series(values, index=calendar)}

    mask = regimes.regime_mask("R1", factors, calendar)

    for position in range(len(calendar)):
        window = values[max(0, position - regimes.REGIME_WINDOW_DAYS + 1) : position + 1]
        expected = (
            len(window) >= regimes.REGIME_MIN_OBSERVATIONS
            and values[position] < float(np.median(window))
        )
        # 必须用 == 而不是 is：右侧在比较分支里是 numpy 布尔，`is` 会永远为假
        assert bool(mask.iloc[position]) == bool(expected), f"第 {position} 个观测的状态对不上"


@pytest.mark.unit
def test_benchmark_registry_marks_what_is_not_reachable():
    """不可达的基准必须带原因；生产基准必须写明含展期。"""
    production = regimes.benchmark_by_key["gold_close"]
    assert production.available
    assert "展期" in production.note

    unreachable = {item.key: item for item in regimes.BENCHMARK_CHOICES if not item.available}
    assert set(unreachable) == {"xauusd_spot", "roll_adjusted"}
    for item in unreachable.values():
        assert item.reason, f"{item.key} 标了不可达却没写原因"
        assert "未落地" in item.note
