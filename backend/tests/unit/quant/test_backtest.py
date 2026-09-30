"""回测：已知答案、基准对照、样本门槛。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import backtest, engine
from app.services.quant.definitions import HORIZONS

# 三个 sign=-1、change_20d 的因子：把它们的 20 日变化做成「明日收益的镜像」，
# 合成得分的方向就与实现收益完全一致 —— 这是可复核的已知答案。
MIRROR_KEYS = ("real_yield_10y", "dollar_index", "bitcoin")
MIRROR_LOOKBACK = 20


def _mirror_series(driver: np.ndarray, index) -> pd.Series:
    """构造 y：使 change_20d(y)_t = -driver_t（t ≥ 20）。"""
    values = np.zeros(len(index), dtype="float64")
    for position in range(MIRROR_LOOKBACK, len(index)):
        values[position] = values[position - MIRROR_LOOKBACK] - driver[position]
    return pd.Series(values, index=index)


def _oracle_panel(calendar, *, seed: int = 3):
    rng = np.random.default_rng(seed)
    driver = rng.choice([-1.0, 1.0], size=len(calendar))
    # close_{t+1} = close_t × (1 + 2% × driver_t)：明日收益由今天的 driver 决定
    growth = np.concatenate([[1.0], np.cumprod(1.0 + 0.02 * driver[:-1])])
    close = pd.Series(100.0 * growth, index=calendar)
    factors = {key: _mirror_series(driver, calendar) for key in MIRROR_KEYS}
    return factors, close


@pytest.fixture()
def oracle():
    calendar = pd.date_range(end="2026-09-30", periods=400, freq="B")
    factors, close = _oracle_panel(calendar)
    return factors, close, calendar


def test_known_answer_predicts_every_realized_move(oracle):
    factors, close, _ = oracle

    evaluation = backtest.evaluate_horizon(factors, close, horizon=1)

    assert evaluation.sample_size > 250
    assert evaluation.accuracy == 1.0
    assert evaluation.metrics["per_factor"]["dollar_index"]["hit_rate"] == 1.0
    assert evaluation.brier_score == pytest.approx(0.0, abs=0.05)


def test_baselines_are_reported_alongside_the_model(oracle):
    factors, close, _ = oracle

    evaluation = backtest.evaluate_horizon(factors, close, horizon=1)

    assert evaluation.baseline_up_accuracy == pytest.approx(evaluation.metrics["up_share"])
    assert evaluation.baseline_momentum_accuracy is not None
    assert evaluation.metrics["coin_flip_accuracy"] == 0.5
    # 永远看多不可能在这段合成行情里达到 100%
    assert evaluation.baseline_up_accuracy < 1.0


def test_random_prices_leave_the_model_near_a_coin_flip(panel):
    factors, close = panel

    evaluation = backtest.evaluate_horizon(factors, close, horizon=5)

    assert 0.30 < evaluation.accuracy < 0.70


def test_too_few_factors_produces_no_evaluation(oracle):
    factors, close, _ = oracle
    factors = {key: factors[key] for key in MIRROR_KEYS[:2]}

    evaluation = backtest.evaluate_horizon(factors, close, horizon=1)

    assert evaluation.sample_size == 0
    assert evaluation.accuracy is None
    assert "样本" in evaluation.metrics["reason"]


def test_evaluate_all_covers_every_horizon(oracle):
    factors, close, _ = oracle

    evaluations = backtest.evaluate_all(factors, close)

    assert [item.horizon_days for item in evaluations] == list(HORIZONS)
    assert all(item.sample_size > 0 for item in evaluations)


def test_date_range_is_respected(oracle):
    factors, close, calendar = oracle
    start, end = calendar[200].date(), calendar[300].date()

    evaluation = backtest.evaluate_horizon(factors, close, horizon=1, start=start, end=end)

    assert evaluation.window_start >= start
    assert evaluation.window_end <= end


def test_factor_summary_is_ordered_by_weight(oracle):
    factors, close, _ = oracle
    evaluation = backtest.evaluate_horizon(factors, close, horizon=1)

    summary = backtest.factor_summary(evaluation)

    weights = [row["weight"] for row in summary]
    assert weights == sorted(weights, reverse=True)
    assert {row["key"] for row in summary} == set(MIRROR_KEYS)


def test_momentum_baseline_looks_backwards(oracle):
    """动量基准必须是「过去 60 日的方向」，不是未来。

    构造：先跌后涨的一段，且涨幅小于前期跌幅 —— 在 [110, 150] 这段里
    过去 60 日动量仍为负、而实现收益为正。用未来动量做基准会得到 100%，
    用过去动量会得到 0%，两者不可能混淆。
    """
    factors, _, calendar = oracle
    level = np.empty(len(calendar))
    level[:110] = 100.0 - 0.5 * np.arange(110)
    level[110:] = level[109] + (25.0 / (len(calendar) - 110)) * np.arange(len(calendar) - 110)
    close = pd.Series(level, index=calendar)

    past = close / close.shift(60) - 1.0
    future = close.shift(-60) / close - 1.0
    assert past.iloc[150] < 0 < future.iloc[150]

    evaluation = backtest.evaluate_horizon(
        factors, close, horizon=1, start=calendar[110].date(), end=calendar[150].date()
    )

    assert evaluation.baseline_momentum_accuracy == 0.0
