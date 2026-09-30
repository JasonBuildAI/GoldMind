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
    # 900 个交易日：最长尺度（250 日）也要有「250 日 + 60 组校准样本」的评估窗口
    calendar = pd.date_range(end="2026-09-30", periods=900, freq="B")
    factors, close = _oracle_panel(calendar)
    return factors, close, calendar


def test_known_answer_predicts_every_realized_move(oracle):
    factors, close, _ = oracle

    evaluation = backtest.evaluate_horizon(factors, close, horizon=1)

    assert evaluation.sample_size > 250
    # 已知答案：因子偏向（未校准）100% 命中；校准后的方向继承它
    assert evaluation.metrics["score_direction_accuracy"] == 1.0
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

    构造：先跌 200 日（-0.5/日）再慢涨（+0.02/日）—— 价格要涨 25 倍才回到
    60 日前的水平，所以恢复到第 60 天（t=259）之前「过去 60 日动量」一直是负的。
    评估窗口取在涨势的头 51 天：每天的实现收益都是正的、动量却全为负。
    于是「永远看多」= 100%、「过去 60 日动量」= 0%，两者不可能混淆。
    """
    factors, _, calendar = oracle
    level = np.empty(len(calendar))
    level[:200] = 200.0 - 0.5 * np.arange(200)
    level[200:] = level[199] + 0.02 * np.arange(len(calendar) - 200)
    close = pd.Series(level, index=calendar)

    past = close / close.shift(60) - 1.0
    one_day = close.shift(-1) / close - 1.0
    window = slice(200, 251)
    assert (past.iloc[window] < 0).all()
    assert (one_day.iloc[window] > 0).all()

    evaluation = backtest.evaluate_horizon(
        factors, close, horizon=1, start=calendar[200].date(), end=calendar[250].date()
    )

    assert evaluation.sample_size >= 45
    assert evaluation.baseline_up_accuracy == 1.0
    assert evaluation.baseline_momentum_accuracy == 0.0
