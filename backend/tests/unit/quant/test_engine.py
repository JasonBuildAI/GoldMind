"""信号引擎：合成得分的归一、方向、降级与新鲜度。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from typing import Optional

from app.services.quant import engine
from app.services.quant.definitions import BENCHMARK_KEY, FACTORS, HORIZONS


def test_snapshot_covers_every_factor_and_contributions_sum_to_the_score(panel):
    factors, close = panel

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    assert snapshot.status == engine.STATUS_OK
    assert snapshot.available_factors == len(FACTORS)
    contributions = [state.contribution for state in snapshot.states if state.available]
    assert len(contributions) == len(FACTORS)
    assert sum(contributions) == pytest.approx(snapshot.score, abs=1e-12)
    assert snapshot.weight_used == pytest.approx(sum(f.weight_for(5) for f in FACTORS))


def _snapshot(*, score: float, expected_return: float,
              median_return: Optional[float] = None) -> engine.SignalSnapshot:
    return engine.SignalSnapshot(
        as_of=pd.Timestamp("2026-09-30").date(),
        horizon_days=5,
        status=engine.STATUS_OK,
        reason=None,
        base_price=4200.0,
        score=score,
        probability_up=0.5,
        expected_return=expected_return,
        uncertainty=0.02,
        target_price=4200.0 * (1.0 + expected_return),
        states=(),
        weight_used=1.0,
        median_return=expected_return if median_return is None else median_return,
    )


def test_non_finite_values_are_treated_as_missing():
    """NaN 与 ±Inf 都是「没有这个数字」，不是「一个很大的数」。

    Inf 的来源通常是除零或尺度估计退化 —— 那是「算不出来」。放它过去，
    API 会序列化出非法 JSON（`Infinity`），页面会印出 `Infinity`；
    落库那条路已经有 `stats.json_safe` 兜着，响应这条没有。

    变异验证：把 `np.isfinite` 改回 `np.isnan`，后两条断言必红。
    """
    assert engine._clean(None) is None
    assert engine._clean(float("nan")) is None
    assert engine._clean(float("inf")) is None
    assert engine._clean(float("-inf")) is None
    assert engine._clean(0.5) == 0.5


def test_direction_follows_the_calibrated_mean_and_reports_the_median():
    """方向 = sign(μ)；分布中位数作为另一个统计量一并给出。

    两次变异验证都会把本测试打红：
    ① 改回 ``"up" if score > 0`` —— 前两行红（构造的就是「得分与方向相反」）；
    ② 把方向改成 sign(中位数) —— 第三行红。后者不是洁癖：2026-10-02 用真实 20 年
    面板实测，按中位数定方向会让 60 日留出期命中率从 83.3% 掉到 78.9%
    （走查误差的位置项偏负，把三成喊单翻成看跌），所以决策口径钉在 μ 上。
    """
    assert _snapshot(score=+2.0, expected_return=-0.01).direction == "down"
    assert _snapshot(score=-2.0, expected_return=+0.01).direction == "up"
    # μ 为正、中位数为负：方向仍按 μ（两者是不同的统计量，不是一致性缺陷）
    assert _snapshot(score=+1.0, expected_return=+0.001, median_return=-0.004).direction == "up"
    assert _snapshot(score=+1.0, expected_return=+0.001, median_return=-0.004).median_return == -0.004
    # μ=0（回归样本不足，目标价=基准价）既不看涨也不看跌
    assert _snapshot(score=+2.0, expected_return=0.0).direction == "flat"


def test_expected_return_is_capped_by_what_the_market_actually_did(calendar):
    """OLS 在「得分几乎不动」的窗口里能把 β 推到 10⁴ 量级，μ 必须被封顶。

    2026-10-02 真实面板实测：2019-01-08 那天 60 日期望收益是 **+1261**（即 +126167%），
    目标价与区间一起被带飞 —— 展示这种数字等于违反红线一「不许编造数据」。
    这里用同一种病态构造（近乎恒定的得分 + 一次跳变）复现它，并钉住四条：
    μ 被夹到界内、被夹的行有标记、目标价与区间仍有限、且封顶不许吃掉正常行。

    变异验证：删掉 `.where(~capped, ...)` 那一行，本测试第一组断言必红。
    """
    rng = np.random.default_rng(11)
    n = len(calendar)
    # 前段：得分几乎恒定（分母接近 0 → β 爆炸）；末段给一次大幅跳变
    score_values = np.concatenate([1.0 + rng.normal(0.0, 1e-6, n - 5), np.full(5, 4.0)])
    score = pd.Series(score_values, index=calendar)
    returns = rng.normal(0.0, 0.006, n)
    close = pd.Series(2000.0 * np.cumprod(1.0 + returns), index=calendar)

    horizon = 20
    frame = engine.build_prediction_frame(score, close, horizon)
    realized_scale = (
        close.shift(-horizon).div(close).sub(1.0).shift(horizon).expanding(
            min_periods=engine.MIN_SCORES_FOR_SIGMA
        ).std()
    )
    bound = engine.EXPECTED_CAP_SIGMAS * realized_scale
    mu = frame["expected_return"]
    valid = mu.notna() & bound.notna()

    assert bool(frame["expected_capped"][valid].any()), "病态构造没能触发封顶，测试已经失效"
    assert bool((mu[valid].abs() <= bound[valid] + 1e-15).all()), "存在越界的期望收益"
    for column in ("target_price", "lower_return", "upper_return", "median_return"):
        assert np.isfinite(frame[column].dropna()).all(), column
    # 绝大多数行不该被夹 —— 封顶是护栏，不是把模型压平
    assert float(frame["expected_capped"][valid].mean()) < 0.2
    # 得分平稳的面板不该触发封顶（否则等于用护栏掩盖真问题）
    calm = engine.build_prediction_frame(
        pd.Series(rng.normal(0.0, 1.0, n), index=calendar), close, horizon
    )
    assert float(calm["expected_capped"][calm["expected_return"].notna()].mean()) < 0.05


def test_normal_fallback_probability_is_the_normal_tail():
    """经验样本不足时退回解析正态：p_up = Φ(μ/scale)，与兜底区间同一套尺度。

    变异验证：把兜底概率改成 ``Φ(score/σ_score)``，第一行断言必红 —— 得分为正、
    期望收益为负时那个写法大于 0.5，与方向、目标价互相矛盾。
    """
    expected = pd.Series([0.02, -0.02, 0.0])
    sigma = pd.Series([0.01, 0.01, 0.01])

    probability = engine.normal_probability_up(expected, sigma)

    assert probability.iloc[0] == pytest.approx(0.9772, abs=1e-4)  # Φ(2)
    assert probability.iloc[1] == pytest.approx(0.0228, abs=1e-4)  # Φ(−2)
    assert probability.iloc[2] == pytest.approx(0.5, abs=1e-9)
    # σ 缺失或非正时不给概率，也不退回 50%
    assert pd.isna(engine.normal_probability_up(pd.Series([0.01]), pd.Series([np.nan])).iloc[0])
    assert pd.isna(engine.normal_probability_up(pd.Series([0.01]), pd.Series([0.0])).iloc[0])


def test_probability_is_not_the_normal_tail_of_the_displayed_sigma(panel):
    """线上口径（ACI）里 p_up 必须**不是** Φ(μ/uncertainty)。

    这是本轮修掉的病症：uncertainty 是「展示区间的等效正态尺度」，曾经还被当成
    概率的分母，于是每个概率都被往 0.5 拉（Brier 技能分全线为负的机制之一）。
    同一个测试钉住自洽性：中位数与「概率是否过半」同号，否则页面会出现
    「看多 + 上行概率 47%」；并钉住情景区间嵌套在 80% 区间之内。
    """
    factors, close = panel

    for horizon in HORIZONS:
        snapshot = engine.build_snapshot(factors, close, horizon=horizon)
        assert snapshot.distribution_mode == "aci", f"h={horizon}"
        median = snapshot.median_return
        probability = snapshot.probability_up
        assert probability is not None and median is not None, f"h={horizon}"
        if median > 0:
            assert probability >= 0.5, f"h={horizon}"
        elif median < 0:
            assert probability <= 0.5, f"h={horizon}"
        assert snapshot.interval_low_return <= snapshot.scenario_low_return, f"h={horizon}"
        assert snapshot.scenario_high_return <= snapshot.interval_high_return, f"h={horizon}"
        naive = float(
            engine.normal_probability_up(
                pd.Series([snapshot.expected_return]), pd.Series([snapshot.uncertainty])
            ).iloc[0]
        )
        assert abs(probability - naive) > 1e-4, f"h={horizon} 概率仍是那条正态尾"


def test_the_band_stays_around_the_quartiles_when_alpha_saturates():
    """α 的上界不能越过 0.5：区间端点取 α/2 与 1−α/2，情景取 0.25 / 0.75。

    α/2 > 0.25 时区间下界必然**高于**情景下界（分位数单调），于是
    「情景 ⊂ 区间」这条 `scenarios.py` 声明的不变式被破坏。真实 26 年面板
    h=250 实测 1040 行 α>0.5、1036 行 `interval_low > scenario_low`。
    唯一钉这条的守卫跑在合成夹具上，而那个夹具的 α 从不 >0.5 —— 真数据上必红。

    构造：先给一段散布（把带撑宽），再给一段**窄但非退化**的散布（都落在带内）
    → α 一路升到上界；窗（750）仍含前段的散布，所以分位函数不退化。

    变异验证：把 ``ACI_ALPHA_CAP`` 改回 0.6 本测试必红。
    """
    rng = np.random.default_rng(4)
    index = pd.date_range("2020-01-01", periods=520, freq="B")
    values = np.concatenate([rng.normal(0.0, 3.0, 300), rng.normal(0.0, 0.1, 220)])
    ratio = pd.Series(values, index=index)
    flat = pd.Series(np.zeros(len(index)), index=index)

    calibration = engine.calibrate_distribution(
        ratio, flat, gamma=0.01, half_life=250, window=750, min_samples=60, issued_lag=0
    )

    saturated = calibration["alpha"] >= engine.ACI_ALPHA_CAP - 1e-9
    assert bool(saturated.any()), "构造没有把 α 推到上界，测试是空的"
    band = calibration[saturated]
    assert (band["lower"] <= band["q25"] + 1e-12).all(), "区间下界越过了情景下界"
    assert (band["q75"] <= band["upper"] + 1e-12).all(), "情景上界越过了区间上界"
    # 上界本身也必须与分位口径一致：α/2 不得超过情景的下分位点
    assert engine.ACI_ALPHA_CAP <= 2.0 * engine.QUARTILE_LOW


def test_uncertainty_is_the_walk_forward_error_not_the_fit_residual(calendar, make_panel):
    """σ 回答「模型自己错了多少」：t 时刻只用 s + h ≤ t 的已实现预测误差（spec 判据）。

    变异验证：把 uncertainty 改回回归残差 σ，第一条断言的相对误差约 23%（长尺度），必红。
    """
    horizon = 250
    factors, close = make_panel(calendar)
    signals = engine.build_signals(engine.align_factors(factors, calendar), calendar)
    score = engine.composite_score(signals, horizon=horizon)

    frame = engine.build_prediction_frame(score, close, horizon)

    forward = close.shift(-horizon) / close - 1.0
    alpha, beta, residual_sigma, calibrated = engine.expanding_ols(
        score.shift(horizon), forward.shift(horizon)
    )
    # 未校准的时段没有发布预测，它的「误差」不算数（μ 是 NaN 而不是 0）
    published = (alpha + beta * score).where(calibrated)
    errors = (forward - published).shift(horizon)
    manual_std = errors.expanding(
        min_periods=engine.MIN_ERRORS_FOR_SIGMA
    ).std()

    # uncertainty 的定义换了：它是「展示区间宽度折算成的正态尺度」，不再是乘过经验因子的 σ
    half_width = float((frame["upper_return"].iloc[-1] - frame["lower_return"].iloc[-1]) / 2.0)
    assert frame["uncertainty"].iloc[-1] == pytest.approx(
        half_width / engine.INTERVAL_Z_80, rel=1e-12
    )
    # 非对称口径下区间中点不等于 μ，所以「μ ± z80·uncertainty == 边界」只在对称口径成立；
    # 这里用对称口径钉住那条等式，别让它悄悄变成只有宽度对得上。
    symmetric_frame = engine.build_prediction_frame(score, close, horizon, interval="empirical")
    mu = float(symmetric_frame["expected_return"].iloc[-1])
    scale_display = float(symmetric_frame["uncertainty"].iloc[-1])
    assert float(symmetric_frame["lower_return"].iloc[-1]) == pytest.approx(
        mu - engine.INTERVAL_Z_80 * scale_display, rel=1e-12
    )
    assert float(symmetric_frame["upper_return"].iloc[-1]) == pytest.approx(
        mu + engine.INTERVAL_Z_80 * scale_display, rel=1e-12
    )
    # 误差口径必须大于残差口径，否则这条守卫对「换回残差 σ」的变异不敏感
    assert float(manual_std.iloc[-1]) > float(residual_sigma.iloc[-1]) * 1.1


def test_uncertainty_is_calibrated_to_the_empirical_error_quantile(calendar):
    """σ 还要按误差的实际分位校准：波动换挡时，纯正态分位的区间盖不住（spec 判据）。

    构造：前 600 个交易日日收益 ±0.04%、后 300 个 ±0.16%（波动换挡）—— 扩展窗口的
    标准差跟不上换挡，正态区间会系统性偏窄；按误差的经验 80% 分位再校准要把它推回来。
    变异验证：删掉经验校准因子，σ 就退回纯扩展标准差，第一条断言必红（两个数相等）。
    """
    horizon = 1
    rng = np.random.default_rng(2026)
    scale = np.where(np.arange(len(calendar)) < 600, 0.0004, 0.0016)
    returns = rng.normal(0.0, 1.0, len(calendar)) * scale
    close = pd.Series(2000.0 * np.cumprod(1.0 + returns), index=calendar)
    score = pd.Series(rng.normal(0.0, 1.0, len(calendar)), index=calendar)

    frame = engine.build_prediction_frame(score, close, horizon)
    forward = close.shift(-horizon) / close - 1.0
    mu, sigma = frame["expected_return"], frame["uncertainty"]
    sigma_std = (
        (forward - mu).shift(horizon).expanding(min_periods=engine.MIN_ERRORS_FOR_SIGMA).std()
    )
    # 只在两套 σ 都有值的样本上比：否则早期「兜底 σ」的行会混进来，比较就不公平
    valid = (mu.notna() & forward.notna() & sigma.notna() & sigma_std.notna()).values

    def coverage(scale_series: pd.Series) -> float:
        half = engine.INTERVAL_Z_80 * scale_series
        inside = (forward >= mu - half) & (forward <= mu + half)
        return float(inside[valid].mean())

    calibrated = coverage(sigma)
    vanilla = coverage(sigma_std)

    # 校准把覆盖推近名义值（本面板约 +1.5pp；真实数据的覆盖率见 docs/ARCHITECTURE.md 第十一节）
    assert calibrated > vanilla + 0.005
    assert calibrated > 0.60


def test_every_horizon_publishes_one_story(panel):
    """页面上的方向、目标价、概率必须自洽 —— 同一份分布出来的三个说法。"""
    factors, close = panel

    for horizon in HORIZONS:
        snapshot = engine.build_snapshot(factors, close, horizon=horizon)

        assert snapshot.status == engine.STATUS_OK
        expected = snapshot.expected_return
        assert expected is not None
        # 方向 = sign(μ)；中位数是分布的另一个统计量，只用于概率/区间的定标度
        direction = "up" if expected > 0 else "down" if expected < 0 else "flat"
        assert snapshot.direction == direction, f"h={horizon}"
        assert snapshot.median_return is not None, f"h={horizon}"
        # 目标价相对基准价的方向 = 期望收益的符号
        assert (snapshot.target_price - snapshot.base_price) * expected >= 0, f"h={horizon}"
        # 上行概率与方向同号：两者都出自同一张校准分布（中位数），不是两套口径
        assert (snapshot.probability_up - 0.5) * snapshot.median_return >= 0, f"h={horizon}"
        assert snapshot.distribution_mode in engine.INTERVAL_MODES + ("normal",), f"h={horizon}"
        # 情景区间（四分位）必须落在 80% 区间之内 —— 同一张分布的两组分位点
        assert snapshot.interval_low_return <= snapshot.scenario_low_return, f"h={horizon}"
        assert snapshot.scenario_high_return <= snapshot.interval_high_return, f"h={horizon}"


def test_change_transform_uses_the_declared_lag(calendar):
    values = pd.Series(np.arange(30, dtype="float64"), index=calendar[:30])

    changed = engine.apply_transform(values, "change_20d")

    assert changed.iloc[19] != changed.iloc[19]  # NaN
    assert changed.iloc[20] == 20.0
    # 原单位（这里是「点」），不是百分比
    assert engine.apply_transform(values, "level").iloc[0] == 0.0


def test_missing_factors_do_not_count_as_zero():
    index = pd.date_range("2026-01-01", periods=3, freq="B")
    both = pd.DataFrame({"real_yield_10y": [1.0] * 3, "vix": [2.0] * 3}, index=index)
    only_one = pd.DataFrame({"real_yield_10y": [1.0] * 3, "vix": [np.nan] * 3}, index=index)

    weight_10y = 1.0
    weight_vix = 0.4
    assert engine.composite_score(both).iloc[0] == pytest.approx(1.8 / 1.4)
    # 缺 VIX 时按剩余权重归一：得分等于 10Y 自己的信号，而不是被 VIX 的 0 拉低
    assert engine.composite_score(only_one).iloc[0] == pytest.approx(weight_10y / weight_10y)


def test_alignment_only_fills_forward_but_not_past_freshness(calendar):
    sparse = pd.Series([1.0], index=[calendar[10]])

    aligned = engine.align_factors({"vix": sparse}, calendar)["vix"]
    # 不是因子表里的序列（金价这类中间量）没有「发布节奏」可言，不受新鲜度上限约束
    unrestricted = engine.align_factors({"gold_close": sparse}, calendar)["gold_close"]

    assert np.isnan(aligned.iloc[9])
    assert aligned.iloc[10] == 1.0
    assert aligned.iloc[11] == 1.0  # 前向填充
    # VIX 的新鲜度上限是 7 天：第 20 个交易日（≈26 天后）必须已经不算数了
    assert np.isnan(aligned.iloc[20]), "陈旧值被无界前向填充继续当成了今天的观测"
    assert unrestricted.iloc[200] == 1.0


def test_observation_on_a_non_trading_day_is_not_dropped(calendar):
    """日期不在金价日历里的观测必须落到**下一个**交易日，不能被静默丢掉。

    真实 26 年面板上有 2414 条观测的日期不在 COMEX 日历内（周频 CFTC 按报告日
    +4 BDay 推、月度储备按「月末 +8 天」推、BTC 有周末报价）。旧实现用
    ``series.reindex(calendar)``：label 不匹配就整条消失，引擎只好继续用更老的一条，
    而 ``factor_states`` 读的是**原始序列** —— 页面显示 2.43（09-07），引擎吃进去
    2.42（更早那条），「展示 ≠ 计算」正是上一轮刚修好的那类分裂。

    变异验证：把 ``align_series`` 改回 ``series.reindex(calendar)`` 本测试必红。
    """
    saturday = next(
        day
        for day in pd.date_range(calendar[0], calendar[-1], freq="D")
        if day.dayofweek == 5
    )
    assert saturday not in calendar
    series = pd.Series([9.0], index=[saturday])

    aligned = engine.align_factors({"gold_close": series}, calendar)["gold_close"]

    after = calendar[calendar > saturday][0]
    assert aligned.loc[after] == 9.0, "非交易日观测被丢掉了，引擎用了更老的值"
    # 只向前填充：观测之前的日子仍是空的，不许把它回填到过去
    before = calendar[calendar < saturday]
    assert before.size > 0
    assert aligned.loc[before].isna().all()


def test_stale_data_is_marked_and_excluded(panel, calendar):
    factors, close = panel
    # VIX 的更新周期是 7 天：把最后 60 天的数据删掉，它就该被判为陈旧
    factors["vix"] = factors["vix"].iloc[:-60]

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    state = next(state for state in snapshot.states if state.key == "vix")
    assert state.status == engine.STATUS_STALE
    assert state.available is False
    assert "天前" in state.reason
    assert snapshot.available_factors == len(FACTORS) - 1
    # 陈旧必须**同时**退出计算：只看展示分支的话，得分会继续按 VIX 的老 z 贡献
    signals = engine.build_signals(engine.align_factors(factors, calendar), calendar)
    assert np.isnan(signals["vix"].iloc[-1])
    without_vix = engine.composite_score(
        signals.drop(columns=["vix"]), horizon=5
    ).iloc[-1]
    assert snapshot.score == pytest.approx(float(without_vix), rel=1e-12)
    # 对照旧行为：先无界前向填充再算，VIX 两个月前的 z 会被当成今天的贡献，得分必然不同
    stale_filled = dict(factors, vix=factors["vix"].reindex(calendar).ffill())
    stale_signals = engine.build_signals(stale_filled, calendar)
    stale_score = float(engine.composite_score(stale_signals, horizon=5).iloc[-1])
    assert not np.isnan(stale_score)
    assert snapshot.score != pytest.approx(stale_score, rel=1e-6), (
        "陈旧值仍在贡献得分"
    )


def test_factor_without_any_data_is_marked_missing(panel):
    factors, close = panel
    factors.pop("bitcoin")

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    state = next(state for state in snapshot.states if state.key == "bitcoin")
    assert state.status == engine.STATUS_MISSING
    assert state.value is None


def test_fewer_than_three_factors_refuses_to_predict(panel):
    factors, close = panel
    for factor in FACTORS[2:]:
        factors.pop(factor.key)

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    assert snapshot.status == engine.PREDICTION_UNAVAILABLE
    assert snapshot.score is None
    assert snapshot.target_price is None
    assert snapshot.direction is None
    assert "至少需要" in snapshot.reason


def test_missing_price_series_refuses_to_predict(panel):
    factors, _ = panel

    snapshot = engine.build_snapshot(factors, pd.Series(dtype="float64"), horizon=5)

    assert snapshot.status == engine.PREDICTION_UNAVAILABLE
    assert "价格" in snapshot.reason


def test_short_history_refuses_to_give_a_direction_or_target(calendar, make_panel):
    """没有校准就没有方向与目标价：给原因，而不是把「样本不足」说成「预期不变」。"""
    short = calendar[-100:]
    factors, close = make_panel(short)

    snapshot = engine.build_snapshot(factors, close, horizon=5)

    assert snapshot.status == engine.PREDICTION_UNAVAILABLE
    assert "校准" in snapshot.reason
    assert snapshot.direction is None
    assert snapshot.expected_return is None
    assert snapshot.target_price is None


def test_probability_and_uncertainty_stay_inside_their_domains(panel):
    factors, close = panel
    snapshot = engine.build_snapshot(factors, close, horizon=20)

    assert 0.0 <= snapshot.probability_up <= 1.0
    assert snapshot.uncertainty >= 0.0


def test_horizons_are_independent(panel):
    factors, close = panel
    short = engine.build_snapshot(factors, close, horizon=1)
    long = engine.build_snapshot(factors, close, horizon=20)

    assert short.horizon_days == 1
    assert long.horizon_days == 20
    assert (short.expected_return, short.target_price) != (long.expected_return, long.target_price)


def test_benchmark_is_not_a_factor():
    assert BENCHMARK_KEY not in {factor.key for factor in FACTORS}
