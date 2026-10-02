"""回测新指标：80% 区间覆盖率与 2022 前后分段。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import numpy as np
import pytest

from app.services.quant import backtest, engine


def _series(value: float, count: int = 40) -> pd.Series:
    return pd.Series([value] * count, index=pd.RangeIndex(count))


def test_interval_band_uses_the_calibrated_bounds():
    # 边界是显式传入的校准分位：0.0127 在内、0.0129 在外。
    lower = _series(-0.012816)
    upper = _series(0.012816)

    assert backtest.interval_coverage_80(_series(0.0127), lower, upper) == 1.0
    assert backtest.interval_coverage_80(_series(0.0129), lower, upper) == 0.0


def test_interval_coverage_counts_misses_exactly():
    forward = pd.Series([0.0] * 10 + [0.05] * 30, index=pd.RangeIndex(40))

    coverage = backtest.interval_coverage_80(forward, _series(-0.01), _series(0.01))

    assert coverage == 10 / 40


def test_interval_coverage_is_unavailable_below_the_sample_floor():
    assert backtest.interval_coverage_80(_series(0.0, 10), _series(-0.01, 10), _series(0.01, 10)) is None


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
    calibrated = np.sign(frame["median_return"][mask])
    mean_sign = np.sign(frame["expected_return"][mask])
    raw = np.sign(score[mask])

    assert evaluation.accuracy == pytest.approx(float((calibrated == realized).mean()))
    assert evaluation.metrics["score_direction_accuracy"] == pytest.approx(
        float((raw == realized).mean())
    )
    # 两个口径必须不同，否则「换回得分符号」的变异不会变红
    assert evaluation.accuracy != pytest.approx(evaluation.metrics["score_direction_accuracy"])
    # 中位数与 μ 的符号必须真的会分开，否则这条守卫对「方向退回 sign(μ)」的变异不敏感
    assert not bool((calibrated == mean_sign).all())


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


def test_backtest_coverage_uses_the_calibrated_bounds(make_panel):
    """回测覆盖率必须来自校准后的非对称边界，而不是 σ 的正态区间。

    变异验证：把 evaluate_horizon 的覆盖计算换回 μ ± 1.2816σ，本用例必红。
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

    calibrated = backtest.interval_coverage_80(
        forward[mask], frame["lower_return"][mask], frame["upper_return"][mask]
    )
    symmetric = backtest.interval_coverage_80(
        forward[mask],
        frame["expected_return"][mask] - backtest.INTERVAL_Z_80 * frame["uncertainty"][mask],
        frame["expected_return"][mask] + backtest.INTERVAL_Z_80 * frame["uncertainty"][mask],
    )

    assert evaluation.metrics["interval_coverage_80"] == pytest.approx(calibrated)
    assert calibrated != pytest.approx(symmetric), "两者必须不同，否则守卫对「换回正态区间」的变异不敏感"


def test_long_horizon_reports_how_many_independent_bets_it_really_is(make_panel):
    """非重叠口径：长尺度独立样本不足时只报样本数、不报成绩。

    这正是 250 日「覆盖率 24.1% 未达标」那条结论的问题所在：506 个重叠样本
    折算下来是 2 次独立下注，任何校准方案都无法在这个尺度上被验证。
    变异验证：把 stride 写成 1（永远不抽稀）→ 第二条断言红；
    把门槛从 30 改成 1 → 第一条断言红（会给出一个由 2 个观测算出的「成绩」）。
    """
    calendar = pd.date_range("2008-01-01", "2026-09-30", freq="B")
    factors, close = make_panel(calendar)

    long_run = backtest.evaluate_horizon(factors, close, horizon=250)
    short_run = backtest.evaluate_horizon(factors, close, horizon=1)

    metrics = long_run.metrics
    assert metrics["nonoverlapping_stride"] == 250
    assert metrics["nonoverlapping_samples"] < backtest.MIN_NONOVERLAPPING_SAMPLES
    assert metrics["accuracy_nonoverlapping"] is None
    assert metrics["interval_coverage_80_nonoverlapping"] is None
    assert short_run.metrics["nonoverlapping_samples"] == short_run.sample_size
    assert short_run.metrics["accuracy_nonoverlapping"] == pytest.approx(
        short_run.accuracy, rel=1e-12
    )


def test_timing_increment_metrics_refuse_to_score_an_untested_claim(make_panel):
    """单边上涨行情里，「相对永远看多的增量」必须是**可证伪**的那几个数。

    绝对方向命中率在牛市里天然被基准压死（2023-10 起的留出期五个尺度全是 +0.0pp），
    所以这里单列三件有账可算的东西：敢不敢喊跌（次数与命中率）、幅度技能、区间锐度。
    喊跌次数不足 30 次时命中率给 None —— 「从没喊过跌」不等于「喊跌全对」。

    变异验证：把 ``down_call_accuracy`` 的样本门槛去掉（空集也算均值）→ 第二条断言红；
    把 ``magnitude_skill_vs_flat`` 写成 ``1 - flat/model``（分子分母反了）→ 第三条断言红。
    """
    calendar = pd.date_range("2012-01-01", "2026-09-30", freq="B")
    factors, close = make_panel(calendar)

    evaluation = backtest.evaluate_horizon(factors, close, horizon=20)
    metrics = evaluation.metrics
    prepared = backtest.prepare_evaluation(factors, close, horizon=20)
    mask = backtest._base_mask(prepared)
    direction = np.sign(prepared["frame"]["median_return"][mask])
    forward = prepared["forward"][mask]

    assert metrics["down_calls"] == int((direction < 0).sum())
    if metrics["down_calls"] < backtest.MIN_EVALUATION_SAMPLES:
        assert metrics["down_call_accuracy"] is None
    else:
        assert metrics["down_call_accuracy"] == pytest.approx(
            float((forward[direction < 0] < 0).mean()), rel=1e-12
        )

    model_mape = float((prepared["frame"]["expected_return"][mask] - forward).abs().mean())
    flat_mape = float(forward.abs().mean())
    assert metrics["magnitude_mape"] == pytest.approx(model_mape, rel=1e-12)
    assert metrics["magnitude_skill_vs_flat"] == pytest.approx(
        1.0 - model_mape / flat_mape, rel=1e-12
    )
    assert metrics["interval_sharpness_80"] == pytest.approx(
        float(
            (
                prepared["frame"]["upper_return"][mask]
                - prepared["frame"]["lower_return"][mask]
            ).mean()
        ),
        rel=1e-12,
    )


def test_a_market_that_never_called_down_reports_no_bets_not_a_perfect_score(make_panel):
    """单边行情里「从没喊过跌」必须显示成「没有可评估的下注」。

    这条守的是留出期真正的形状：2023-10 起黄金单边上涨，模型 5 个尺度的方向与
    「永远看多」逐日一致（+0.0pp），此时绝对方向命中率既不能证明有能力，
    也不能反过来把「一次都没看空」读成「看空全对」。
    """
    calendar = pd.date_range("2012-01-01", "2026-09-30", freq="B")
    rng = np.random.default_rng(3)
    factors, _ = make_panel(calendar)
    close = pd.Series(
        2000.0 * np.cumprod(1.0 + 0.0009 + rng.normal(0, 0.0006, len(calendar))), index=calendar
    )
    trending = {
        key: pd.Series(np.cumsum(rng.normal(0.02, 0.01, len(calendar))), index=calendar)
        for key in factors
    }

    for horizon in (1, 20, 250):
        metrics = backtest.evaluate_horizon(trending, close, horizon=horizon).metrics
        assert metrics["down_calls"] == 0, f"h={horizon}"
        assert metrics["down_call_accuracy"] is None, f"h={horizon}"
        assert metrics["up_share"] > 0.9, f"h={horizon}"
        # 幅度那一侧仍然有账可算：预测趋势优于预测「原地不动」
        assert 0.0 < metrics["magnitude_skill_vs_flat"] < 1.0, f"h={horizon}"
