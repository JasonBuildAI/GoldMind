"""无前视守卫（spec 判据测试）。

判据：把 t 之后的数据换成垃圾值，t 时刻的信号必须**逐位不变**。

变异验证（必须做一次，证明这条守卫不是摆设）：把 ``engine.rolling_z`` 里的
``.shift(1)`` 去掉，本文件必须变红。做法与结果记录在 commit message 里。
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.services.quant import engine
from app.services.quant.definitions import HORIZONS


def _snapshot_fields(snapshot: engine.SignalSnapshot) -> tuple:
    """快照里**每一个**对外数字都要参与比对。

    只比 8 个字段是不够的：区间端点、情景区间、中位数、名义水平与分布来源都是
    用户看得见的数字，任何一条偷偷用上全样本分位，旧的字段表都发现不了。
    加字段的代价是零，漏字段的代价是「守卫看着在守、其实没守那条路径」。
    """
    return (
        snapshot.status,
        snapshot.score,
        snapshot.probability_up,
        snapshot.expected_return,
        snapshot.uncertainty,
        snapshot.target_price,
        snapshot.base_price,
        snapshot.weight_used,
        snapshot.interval_low_return,
        snapshot.interval_high_return,
        snapshot.scenario_low_return,
        snapshot.scenario_high_return,
        snapshot.median_return,
        snapshot.distribution_mode,
        snapshot.interval_alpha,
        snapshot.expected_capped,
    )


def _state_fields(snapshot: engine.SignalSnapshot) -> tuple:
    return tuple(
        (state.key, state.value, state.obs_date, state.z, state.signed_z, state.contribution, state.status)
        for state in snapshot.states
    )


def _sabotage(series: pd.Series, cutoff: pd.Timestamp) -> pd.Series:
    """把 t 之后的数据换成垃圾值：交错的正负超大数 + 跳变。"""
    sabotaged = series.copy()
    future = sabotaged.index > cutoff
    if future.any():
        positions = range(int(future.sum()))
        sabotaged.loc[future] = [1e9 if index % 2 else -1e9 for index in positions]
    return sabotaged


@pytest.mark.parametrize("horizon", HORIZONS)
def test_snapshot_at_t_ignores_everything_after_t(calendar, make_panel, horizon):
    factors, close = make_panel(calendar)

    for position in (700, 899):
        cutoff = calendar[position]
        reference = engine.build_snapshot(factors, close, horizon=horizon, as_of=cutoff.date())

        sabotaged_factors = {key: _sabotage(series, cutoff) for key, series in factors.items()}
        sabotaged_close = _sabotage(close, cutoff)
        sabotaged = engine.build_snapshot(
            sabotaged_factors, sabotaged_close, horizon=horizon, as_of=cutoff.date()
        )

        assert _snapshot_fields(sabotaged) == _snapshot_fields(reference), f"t={cutoff}"
        assert _state_fields(sabotaged) == _state_fields(reference), f"t={cutoff}"


def test_snapshot_at_t_does_not_change_when_future_rows_are_dropped(calendar, make_panel):
    factors, close = make_panel(calendar)
    cutoff = calendar[820]

    reference = engine.build_snapshot(factors, close, horizon=5, as_of=cutoff.date())
    truncated_factors = {key: series.loc[:cutoff] for key, series in factors.items()}
    truncated = engine.build_snapshot(
        truncated_factors, close.loc[:cutoff], horizon=5, as_of=cutoff.date()
    )

    assert _snapshot_fields(truncated) == _snapshot_fields(reference)
    assert _state_fields(truncated) == _state_fields(reference)


def test_backtest_style_walk_forward_matches_the_single_snapshot(calendar, make_panel):
    """逐日推进得到的 t 时刻信号，必须与只喂到 t 的单独计算一致。"""
    factors, close = make_panel(calendar)
    cutoff = calendar[850]

    single = engine.build_snapshot(factors, close, horizon=1, as_of=cutoff.date())
    truncated = engine.build_snapshot(
        {key: series.loc[:cutoff] for key, series in factors.items()},
        close.loc[:cutoff],
        horizon=1,
        as_of=cutoff.date(),
    )

    assert single.score == truncated.score


def test_sparse_sources_never_pull_a_future_observation_backwards(calendar, make_sparse_panel):
    """周度 / 月度 / 单点快照类因子：对齐时只能向前填充。

    这条用例的存在理由：合成面板若每个因子都每天更新，``ffill`` 与 ``bfill``
    没有区别，前一条守卫会一直是绿的 —— 而真实数据里 CFTC 是周度、央行储备是
    月度、ETF 份额只有采集日之后的数据。
    """
    factors, close = make_sparse_panel(calendar)

    # 843 / 857 都不是周度（每 5 天）与月度（每 21 天）序列的观测日：
    # 只有「向前填充」才会在 t 时刻用上一次已发布的数，向后填充会用到未来的报告。
    for position in (843, 857):
        cutoff = calendar[position]
        reference = engine.build_snapshot(factors, close, horizon=5, as_of=cutoff.date())

        sabotaged_factors = {key: _sabotage(series, cutoff) for key, series in factors.items()}
        sabotaged = engine.build_snapshot(
            sabotaged_factors, _sabotage(close, cutoff), horizon=5, as_of=cutoff.date()
        )

        assert _snapshot_fields(sabotaged) == _snapshot_fields(reference), f"t={cutoff}"
        assert _state_fields(sabotaged) == _state_fields(reference), f"t={cutoff}"
