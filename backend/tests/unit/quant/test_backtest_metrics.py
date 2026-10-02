"""回测新指标：80% 区间覆盖率与 2022 前后分段。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import numpy as np
import pytest

from app.services.quant import backtest, engine


def test_horizon_evaluation_to_dict_never_emits_nan():
    """API 响应与落库共用 to_dict；NaN 不许从这里出去（MySQL 的 JSON 列会拒收）。"""
    import json

    evaluation = backtest.HorizonEvaluation(
        horizon_days=250,
        window_start=date(2023, 10, 2),
        window_end=date(2026, 10, 1),
        sample_size=506,
        accuracy=0.6736,
        baseline_up_accuracy=0.6736,
        baseline_momentum_accuracy=float("nan"),
        brier_score=float("inf"),
        metrics={"p_value_vs_up": float("nan"), "reason": "样本重叠"},
    )

    payload = evaluation.to_dict()

    assert payload["metrics"]["p_value_vs_up"] is None
    assert payload["baseline_momentum_accuracy"] is None
    assert payload["brier_score"] is None
    assert payload["accuracy"] == 0.6736
    json.dumps(payload, allow_nan=False)


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
    calibrated = np.sign(frame["expected_return"][mask])
    raw = np.sign(score[mask])

    assert evaluation.accuracy == pytest.approx(float((calibrated == realized).mean()))
    assert evaluation.metrics["score_direction_accuracy"] == pytest.approx(
        float((raw == realized).mean())
    )
    # 两个口径必须不同，否则「换回得分符号」的变异不会变红
    assert evaluation.accuracy != pytest.approx(evaluation.metrics["score_direction_accuracy"])
    # 方向必须是「校准后的 μ」而不是未校准的得分符号（上一条断言已区分两者）


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

    assert set(periods) == {"development", "holdout", "forward", "full"}
    development = periods["development"]
    holdout = periods["holdout"]
    full = periods["full"]
    assert development.window_end < backtest.HOLDOUT_START
    assert holdout.window_start >= backtest.HOLDOUT_START
    assert holdout.window_end < backtest.ACTIVE_HOLDOUT_START
    assert holdout.accuracy is not None, "留出期样本足够时必须给出独立的成绩"
    assert development.sample_size + holdout.sample_size == full.sample_size
    assert holdout.metrics["holdout_start"] == backtest.HOLDOUT_START.isoformat()


def test_holdout_start_is_the_preregistered_constant():
    from app.services.quant.definitions import HOLDOUT_START

    assert backtest.HOLDOUT_START == HOLDOUT_START == date(2023, 10, 2)


def test_forward_slice_is_the_only_deciding_window(make_panel):
    """前向留出期必须自成一列、且只覆盖封板日之后的观测。

    变异验证：把 forward 的掩码改回 `>= HOLDOUT_START`（拿历史那段顶替）、
    或把 holdout 的上界删掉，本用例必红 —— 那正是「窗口纪律变成装饰」的改法。
    """
    calendar = pd.date_range("2019-01-01", "2027-06-30", freq="B")
    factors, close = make_panel(calendar)

    periods = backtest.evaluate_periods(factors, close, horizon=5)

    development = periods["development"]
    holdout = periods["holdout"]
    forward = periods["forward"]
    assert development.window_end < backtest.HOLDOUT_START
    assert holdout.window_start >= backtest.HOLDOUT_START
    assert holdout.window_end < backtest.ACTIVE_HOLDOUT_START
    assert forward.window_start >= backtest.ACTIVE_HOLDOUT_START
    assert forward.sample_size > 0, "面板跨过封板日后裁决窗口必须有观测"
    # 三段互不重叠、合起来等于全样本 —— 有重叠就说明切片口径错了
    assert (
        development.sample_size + holdout.sample_size + forward.sample_size
        == periods["full"].sample_size
    )


def test_forward_slice_stays_empty_and_says_so_before_the_window_fills(make_panel):
    """窗口还没到/刚开：前向那一列如实空着，不给数字、也不借历史那段。

    变异验证：把 forward 掩码退回 `>= HOLDOUT_START`，forward.sample_size 会变成
    一大段历史样本，本用例必红。
    """
    factors, close = make_panel(_long_calendar())  # 止于 2026-09-30，还没到封板日

    periods = backtest.evaluate_periods(factors, close, horizon=20)

    forward = periods["forward"]
    assert forward.sample_size == 0
    assert forward.accuracy is None
    assert forward.window_start is None
    assert forward.metrics["reason"], "空窗口必须给出原因，不能静默"


def test_forward_window_readiness_counts_bets_and_shortfall():
    from app.services.quant import preregistered

    empty = pd.date_range("2026-09-01", "2026-10-01", freq="B")
    readiness = preregistered.forward_window_readiness(empty, 20)

    assert readiness["window_start"] == "2026-10-02"
    assert readiness["observations"] == 0
    assert readiness["independent_bets"] == 0
    assert readiness["decidable"] is False
    assert readiness["shortfall_bets"] == preregistered.MIN_EFFECTIVE_SAMPLES
    assert readiness["approx_trading_days_needed"] == preregistered.MIN_EFFECTIVE_SAMPLES * 20

    # 400 个交易日 = 20 注（stride = 20）刚好够判，缺口归零
    filled = pd.date_range("2026-10-05", periods=400, freq="B")
    ready = preregistered.forward_window_readiness(filled, 20)

    assert ready["observations"] == 400
    assert ready["independent_bets"] == 20
    assert ready["decidable"] is True
    assert ready["shortfall_bets"] == 0
    assert ready["approx_trading_days_needed"] == 0

    # 差一注就不能判 —— 门槛是 ≥ 而不是 ≥ 之前的某个数
    almost = preregistered.forward_window_readiness(
        pd.date_range("2026-10-05", periods=399, freq="B"), 20
    )
    assert almost["decidable"] is False
    assert almost["approx_trading_days_needed"] == 1


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
    direction = np.sign(prepared["frame"]["expected_return"][mask])
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

def test_per_factor_alignment_uses_hac_not_the_naive_standard_error(make_panel):
    """重叠前瞻样本会抬高逐因子 t 值：表里给的是 HAC 那一个，并露出被抬高了多久。

    构造「完全预知」的因子：z 就等于 h 日前瞻收益本身。此时
    `z × forward = forward²` 均值为正、且因相邻窗口共享 59 天信息而强自相关，
    理论上 HAC 标准误必须大于 iid 标准误，于是 |t_HAC| < |t_naive|。
    变异验证：把 `_per_factor_metrics` 里的 `lags=lags` 改成 `lags=0`，第二条断言必红；
    把 `alternative` 从 greater 改成 two-sided，第三条断言必红（p 值翻倍）。
    """
    calendar = pd.date_range("2015-01-01", "2026-09-30", freq="B")
    rng = np.random.default_rng(7)
    daily = pd.Series(rng.normal(0.0002, 0.006, len(calendar)), index=calendar)
    forward = daily.rolling(60).sum().shift(-60).dropna()
    horizon = 60

    perfect = backtest._per_factor_metrics(
        pd.DataFrame({"vix": forward}, index=forward.index),
        forward,
        pd.Series(True, index=forward.index),
        horizon=horizon,
    )["vix"]
    assert perfect["alignment"] > 0
    assert perfect["alignment_t"] < perfect["alignment_naive_t"], "HAC 没有把重叠样本的虚高压下去"
    assert perfect["alignment_p_value"] < 0.5 * perfect["alignment_naive_p_value"] + 1e-9

    # 真实面板上的字段契约：滞后 = h−1，缺样本的因子给 None 而不是 0
    evaluation = backtest.evaluate_horizon(*make_panel(calendar), horizon=horizon)
    rows = evaluation.metrics["per_factor"]
    for name, row in rows.items():
        assert row["hac_lags"] == horizon - 1, name
        if row["alignment"] is None:
            assert row["alignment_t"] is None and row["alignment_naive_t"] is None, name


def test_long_horizon_reports_the_normal_fallback_share(make_panel):
    """必须报告「这一行用的是经验分布还是正态兜底」的占比。

    `bet` 校准档在 250 日尺度上永远凑不满 60 注（20 年面板最多 21 注），于是
    **每一行**都退回解析正态 —— 候选标签写着「每注经验校准」，成绩其实来自纯正态。
    报告里不写这个占比，候选之间的比较就没有意义（这正是第三轮 C1/C2 裁决的盲区）。

    变异验证：把这两个指标从 metrics 里删掉，本测试第一条断言必红。
    """
    calendar = pd.date_range("2006-01-02", "2026-09-30", freq="B")
    factors, close = make_panel(calendar)

    # 线上口径（逐行取样）：绝大多数行用经验分布
    row_mode = backtest.evaluate_horizon(factors, close, horizon=20)
    assert row_mode.metrics["distribution_normal_share"] is not None
    assert row_mode.metrics["distribution_empirical_share"] is not None
    assert row_mode.metrics["distribution_normal_share"] < 0.5

    # bet 档 + 250 日：注数凑不够 60 → 全部退回正态
    bet_mode = backtest.evaluate_horizon(
        factors, close, horizon=250, calibration_mode=engine.CALIBRATION_BET
    )
    assert bet_mode.metrics["distribution_normal_share"] == pytest.approx(1.0)
    assert bet_mode.metrics["distribution_empirical_share"] == pytest.approx(0.0)



def test_normal_crps_matches_the_cdf_integral_definition():
    # 闭式解 vs 定义式 CRPS = ∫ (F(z) − 1{z ≥ y})² dz 的数值积分。
    # 变异验证：把 2·φ(z) 的系数改掉或把符号翻掉，本用例必红。
    grid = np.linspace(-12.0, 12.0, 400001)
    pdf = np.exp(-0.5 * grid * grid) / np.sqrt(2.0 * np.pi)
    cdf = np.cumsum(pdf) * (grid[1] - grid[0])

    for outcome in (-3.0, -0.5, 0.0, 0.5, 2.5):
        indicator = (grid >= outcome).astype("float64")
        integral = float(np.sum((cdf - indicator) ** 2) * (grid[1] - grid[0]))
        assert engine.normal_crps(outcome) == pytest.approx(integral, abs=1e-4)


def test_weighted_empirical_crps_matches_brute_force_cdf_integration():
    values = np.array([-1.2, -0.3, 0.1, 0.4, 2.0])
    weights = np.array([0.1, 0.2, 0.4, 0.2, 0.1])

    grid = np.linspace(-3.0, 4.0, 140001)
    step = grid[1] - grid[0]
    cdf = np.array([float(weights[values <= point].sum()) for point in grid])

    for outcome in (-0.9, 0.1, 1.5):
        indicator = (grid >= outcome).astype("float64")
        integral = float(np.sum((cdf - indicator) ** 2) * step)
        scored = engine._weighted_empirical_crps(
            values, weights, float(weights.sum()), outcome
        )
        assert scored == pytest.approx(integral, abs=1e-3)



def test_calibrate_distribution_scores_crps_with_the_outcomes_it_is_given():
    # 逐行 wiring：crps 必须配 outcome、crps_flat 配 outcome_flat；把两者抄混
    # （例如都给 outcome_z_flat）时，第一条近似断言必红。
    ratio = pd.Series([-1.0, 0.0, 1.0, -1.0, 0.0, 1.0, -0.5])
    flat_z = pd.Series(np.zeros(len(ratio)))
    model = pd.Series([np.nan, np.nan, np.nan, 0.5, -0.5, 0.25, 0.75])
    flat = pd.Series([np.nan, np.nan, np.nan, 2.0, -2.0, 1.0, 3.0])

    frame = engine.calibrate_distribution(
        ratio,
        flat_z,
        outcome=model,
        outcome_flat=flat,
        min_samples=3,
        gamma=0.0,
        half_life=None,
        window=None,
    )

    for position in range(3, len(ratio)):
        sample = np.sort(ratio.to_numpy()[:position])
        weights = np.ones(position)
        assert frame["crps"][position] == pytest.approx(
            engine._weighted_empirical_crps(
                sample, weights, float(position), model[position]
            )
        )
        assert frame["crps_flat"][position] == pytest.approx(
            engine._weighted_empirical_crps(
                sample, weights, float(position), flat[position]
            )
        )
    # 两个 outcome 不同 → 两列必须不同（同抄一列时这条也红）
    assert frame["crps"][3] != pytest.approx(frame["crps_flat"][3])


def test_crps_is_lowest_when_the_distribution_sits_on_the_outcome():
    # N(0,1) 的 CRPS 在 ω=0 处全局最小、关于 0 对称：完美预测 < 偏差 1σ < 偏差 3σ。
    assert engine.normal_crps(0.0) < engine.normal_crps(1.0) < engine.normal_crps(3.0)
    assert engine.normal_crps(-2.0) == pytest.approx(engine.normal_crps(2.0))

    sample = np.linspace(-2.0, 2.0, 9)
    weights = np.ones(9)
    on_center = engine._weighted_empirical_crps(sample, weights, 9.0, 0.0)
    far_out = engine._weighted_empirical_crps(sample, weights, 9.0, 6.0)
    assert on_center < far_out


def test_prediction_frame_scores_the_distribution_it_issues(make_panel):
    # crps / crps_flat：同一张分布（模型 μ 对零漂移）对实现收益的评分。
    # 变异验证：把 outcome_z 换成 outcome_z_flat（或反向），最后一条断言必红。
    factors, close = make_panel(_long_calendar())
    horizon = 20
    calendar = close.index
    signals = engine.build_signals(engine.align_factors(factors, calendar), calendar)
    score = engine.composite_score(signals, horizon=horizon)

    frame = engine.build_prediction_frame(score, close, horizon)

    assert "crps" in frame.columns and "crps_flat" in frame.columns
    realized = frame["crps"].notna()
    assert int(realized.sum()) > 100
    assert frame["crps"].iloc[-horizon:].isna().all(), "最后 h 行没有实现收益，不许给分布评分"
    assert (frame.loc[realized, "crps"] > 0.0).all()
    # 模型分布与零漂移基准不是同一张分布：经验行两列必须出现不同（把 outcome_z
    # 误传成 outcome_z_flat 时，经验行两列将逐行相同 → 这条必红）
    empirical = realized & (frame["distribution_mode"] != "normal")
    assert int(empirical.sum()) > 100
    assert (frame.loc[empirical, "crps"] != frame.loc[empirical, "crps_flat"]).any()

    # 正态口径下有闭式解：crps = σ·g((r − μ)/σ)，σ 就是该行的 uncertainty
    normal_frame = engine.build_prediction_frame(score, close, horizon, interval="normal")
    forward = close.shift(-horizon) / close - 1.0
    omega = (forward - normal_frame["expected_return"]) / normal_frame["uncertainty"]
    manual = normal_frame["uncertainty"] * engine.normal_crps(omega)
    mask = normal_frame["crps"].notna()
    assert int(mask.sum()) > 0
    assert np.allclose(normal_frame.loc[mask, "crps"], manual[mask], rtol=1e-9, atol=1e-12)


def test_backtest_reports_crps_and_its_skill_against_the_flat_benchmark(make_panel):
    # metrics 的 mean_crps / crps_skill_vs_flat 必须与逐行 frame 的口径一致。
    # 变异验证：把技能分改成 1 − flat/model，第一条近似断言必红。
    factors, close = make_panel(_long_calendar())

    evaluation = backtest.evaluate_horizon(factors, close, horizon=20)
    metrics = evaluation.metrics

    assert metrics["mean_crps"] is not None and metrics["mean_crps"] > 0.0
    assert metrics["mean_crps_flat"] is not None and metrics["mean_crps_flat"] > 0.0
    assert metrics["crps_samples"] >= backtest.MIN_EVALUATION_SAMPLES
    assert metrics["crps_skill_vs_flat"] == pytest.approx(
        1.0 - metrics["mean_crps"] / metrics["mean_crps_flat"]
    )
