"""回测新指标：80% 区间覆盖率与 2022 前后分段。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import numpy as np
import pytest

from app.services.quant import backtest, engine


def _series(value: float, count: int = 40) -> pd.Series:
    return pd.Series([value] * count, index=pd.RangeIndex(count))


def test_interval_band_uses_the_80_percent_quantile():
    # 1.2816×0.01 = 0.012816：0.0127 在内、0.0129 在外。
    # 若把分位点换成 1.0（或别的常数），这两条断言必翻转。
    sigma = _series(0.01)
    expected = _series(0.0)

    assert backtest.interval_coverage_80(_series(0.0127), expected, sigma) == 1.0
    assert backtest.interval_coverage_80(_series(0.0129), expected, sigma) == 0.0


def test_interval_coverage_counts_misses_exactly():
    forward = pd.Series([0.0] * 10 + [0.05] * 30, index=pd.RangeIndex(40))

    coverage = backtest.interval_coverage_80(forward, _series(0.0), _series(0.01))

    assert coverage == 10 / 40


def test_interval_coverage_is_unavailable_below_the_sample_floor():
    assert backtest.interval_coverage_80(_series(0.0, 10), _series(0.0, 10), _series(0.01, 10)) is None


def test_metrics_report_nominal_and_realized_coverage(panel):
    factors, close = panel

    evaluation = backtest.evaluate_horizon(factors, close, horizon=20)

    metrics = evaluation.metrics
    assert metrics["interval_nominal_80"] == 0.8
    assert metrics["interval_coverage_80"] is not None
    assert 0.0 <= metrics["interval_coverage_80"] <= 1.0


def test_accuracy_scores_the_calibrated_direction(make_panel):
    """回测评的就是页面上的方向 = sign(μ)；未校准的得分方向单列一份（spec 判据）。

    变异验证：把 ``direction`` 改回 ``np.sign(score[mask])``，第一条断言必红
    （最后一条断言先保证两个口径在这段数据上确实不同，否则守卫是摆设）。
    """
    horizon = 20
    factors, close = make_panel(_long_calendar())
    evaluation = backtest.evaluate_horizon(factors, close, horizon=horizon)

    calendar = close.index
    signals = engine.build_signals(engine.align_factors(factors, calendar), calendar)
    score = engine.composite_score(signals, horizon=horizon)
    frame = engine.build_prediction_frame(score, close, horizon)
    forward = close.shift(-horizon) / close - 1.0
    outcome = np.sign(forward)
    available = signals.notna().sum(axis=1) >= engine.MIN_AVAILABLE_FACTORS
    mask = (
        score.notna()
        & frame["expected_return"].notna()
        & forward.notna()
        & (outcome != 0)
        & available
    )

    realized = outcome[mask]
    calibrated = np.sign(frame["expected_return"][mask])
    raw = np.sign(score[mask])

    assert evaluation.accuracy == pytest.approx(float((calibrated == realized).mean()))
    assert evaluation.metrics["score_direction_accuracy"] == pytest.approx(
        float((raw == realized).mean())
    )
    # 两个口径必须不同，否则「换回得分符号」的变异不会变红
    assert evaluation.accuracy != pytest.approx(evaluation.metrics["score_direction_accuracy"])


def _long_calendar() -> pd.DatetimeIndex:
    return pd.date_range("2019-01-01", "2026-09-30", freq="B")


def test_regimes_split_the_accuracy_around_2022(make_panel):
    factors, close = make_panel(_long_calendar())

    evaluation = backtest.evaluate_horizon(factors, close, horizon=20)

    regimes = evaluation.metrics["regimes"]
    assert regimes["split_date"] == "2022-01-01"
    for side in ("pre", "post"):
        block = regimes[side]
        assert block["sample_size"] >= backtest.MIN_EVALUATION_SAMPLES
        assert block["accuracy"] is not None
        assert block["window_start"] and block["window_end"]
    assert pd.Timestamp(regimes["pre"]["window_end"]) < pd.Timestamp("2022-01-01")
    assert pd.Timestamp(regimes["post"]["window_start"]) >= pd.Timestamp("2022-01-01")
    assert (
        regimes["pre"]["sample_size"] + regimes["post"]["sample_size"]
        == evaluation.sample_size
    )


def test_regime_without_samples_says_so(panel):
    factors, close = panel  # 夹具日历始于 2023，全部落在 2022 年之后

    evaluation = backtest.evaluate_horizon(factors, close, horizon=20)

    pre = evaluation.metrics["regimes"]["pre"]
    assert pre["sample_size"] == 0
    assert pre["accuracy"] is None
    assert "没有可评估样本" in pre["reason"]
    assert evaluation.metrics["regimes"]["post"]["accuracy"] is not None


def test_metrics_report_confidence_and_significance(make_panel):
    factors, close = make_panel(_long_calendar())

    evaluation = backtest.evaluate_horizon(factors, close, horizon=20)
    metrics = evaluation.metrics

    lower, upper = metrics["accuracy_ci95"]
    assert lower <= evaluation.accuracy <= upper, "命中率的 95% 区间必须包住点估计"
    assert 0.0 <= metrics["p_value_vs_up"] <= 1.0
    assert metrics["p_value_vs_momentum"] is None or 0.0 <= metrics["p_value_vs_momentum"] <= 1.0
    assert metrics["effective_sample_size"] == pytest.approx(evaluation.sample_size / 20)
    assert metrics["accuracy_diff_vs_up"] == pytest.approx(
        evaluation.accuracy - evaluation.baseline_up_accuracy
    )
    assert metrics["brier_skill_score"] is not None
    assert len(metrics["reliability_bins"]) == 10
    assert sum(row["count"] for row in metrics["reliability_bins"]) <= evaluation.sample_size
    if metrics["interval_coverage_80"] is not None:
        coverage_lower, coverage_upper = metrics["interval_coverage_ci95"]
        assert coverage_lower <= metrics["interval_coverage_80"] <= coverage_upper


def test_periods_split_development_and_holdout(make_panel):
    factors, close = make_panel(_long_calendar())

    periods = backtest.evaluate_periods(factors, close, horizon=20)

    assert set(periods) == {"development", "holdout", "full"}
    development, holdout, full = periods["development"], periods["holdout"], periods["full"]
    assert development.window_end < backtest.HOLDOUT_START
    assert holdout.window_start >= backtest.HOLDOUT_START
    assert holdout.accuracy is not None, "留出期样本足够时必须给出独立的成绩"
    assert development.sample_size + holdout.sample_size == full.sample_size
    assert holdout.metrics["holdout_start"] == backtest.HOLDOUT_START.isoformat()


def test_holdout_start_is_the_preregistered_constant():
    from app.services.quant.definitions import HOLDOUT_START

    assert backtest.HOLDOUT_START == HOLDOUT_START == date(2023, 10, 2)
