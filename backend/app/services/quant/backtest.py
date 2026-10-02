"""走查式回测：同一套信号，与三个基准对照。

**为什么是向量化的走查**：``engine`` 的每一行只用该行之前的数据（由
``tests/unit/quant/test_no_lookahead.py`` 逐位钉住），所以在整段历史上一次算完
再逐行读取，与「每天重新算一遍」的结果完全一致 —— 后者要跑 2500 次快照，
产出却一模一样。这条等价关系本身也有测试（截断到 t 的结果与整段一致）。

三条基准（写进 ``model_evaluations``，页面上并排展示）：

- ``baseline_up_accuracy``：永远看多。牛市里它天然很高，不拿它对照，
  「命中率 60%」就没有意义。
- ``baseline_momentum_accuracy``：动量（过去 60 个交易日收益的方向）。
- ``coin_flip_accuracy``：0.5，理论值，写在 metrics 里。

样本不足、当日可用因子不足 3 个、或该日之后还没有实现收益的，一律不计入 ——
不补齐、不插值、不当成「猜错了」。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from app.services.quant import engine, stats
from app.services.quant.definitions import FACTORS, HOLDOUT_START, HORIZONS, factor_by_key

# 低于这个样本数就不给命中率（避免「3 天里对了 2 天 = 67%」这种数字）
MIN_EVALUATION_SAMPLES = 30
# 逐因子命中率 / IC 的最低样本数
MIN_FACTOR_SAMPLES = 60
# 非重叠口径的最低独立下注次数：低于它就只报样本数、不报成绩
# （11 次的命中率 ±15pp，当成结论就是把噪声读成能力）
MIN_NONOVERLAPPING_SAMPLES = 30
# 动量基准的回看长度（交易日）
MOMENTUM_LOOKBACK = 60
# 80% 名义区间的双侧分位点：区间 = 期望收益 ± z·不确定度（口径定义在 engine 一处）
INTERVAL_Z_80 = engine.INTERVAL_Z_80
INTERVAL_NOMINAL_80 = 0.80
# 「2022 年后定价函数变了」的分段口径（央行购金放量）
REGIME_SPLIT = date(2022, 1, 1)
# 置信区间/覆盖率自助的重采样次数（种子固定 → 同一输入产出同一条区间）
BOOTSTRAP_DRAWS = 1000


@dataclass(frozen=True)
class HorizonEvaluation:
    horizon_days: int
    window_start: Optional[date]
    window_end: Optional[date]
    sample_size: int
    accuracy: Optional[float]
    baseline_up_accuracy: Optional[float]
    baseline_momentum_accuracy: Optional[float]
    brier_score: Optional[float]
    metrics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "horizon_days": self.horizon_days,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "sample_size": self.sample_size,
            "accuracy": self.accuracy,
            "baseline_up_accuracy": self.baseline_up_accuracy,
            "baseline_momentum_accuracy": self.baseline_momentum_accuracy,
            "brier_score": self.brier_score,
            "metrics": self.metrics,
        }


def prepare_evaluation(
    factors: dict[str, pd.Series],
    close: pd.Series,
    *,
    horizon: int,
    score_mode: str = "weighted",
    include: Optional[tuple[str, ...]] = None,
    regression_window: Optional[int] = None,
    interval: str = "aci",
    score: Optional[pd.Series] = None,
) -> dict:
    """把因子面板算成一次评估所需的全部序列。

    研究台（``scripts/quant_lab.py``）的预注册候选在这里落地：``score_mode``
    见 ``engine.SCORE_MODES``、``interval`` 见 ``engine.INTERVAL_MODES``、
    ``include`` 限定因子子集、``regression_window`` 指定滚动回归窗口。
    计算量最大的一段（信号、回归、区间校准）只做一次，
    ``evaluate_periods`` 在开发期 / 留出期 / 全样本三个切片上复用同一结果。

    ``score`` 直接给定时忽略 ``score_mode`` 的合成部分（集成候选的得分由
    调用方先平均好）；可用因子数仍按 ``include`` 统计。
    """
    calendar = close.index
    aligned = engine.align_factors(factors, calendar)
    signals = engine.build_signals(aligned, calendar)
    if score is None:
        score = engine.composite_score(
            signals, horizon=horizon, mode=score_mode, include=include
        )
    frame = engine.build_prediction_frame(
        score, close, horizon, regression_window=regression_window, interval=interval
    )
    forward = close.shift(-horizon) / close - 1.0
    outcome = np.sign(forward)
    available_signals = signals
    if include is not None:
        available_signals = signals[
            [key for key in signals.columns if key in set(include)]
        ]
    available = available_signals.notna().sum(axis=1) >= engine.MIN_AVAILABLE_FACTORS
    return {
        "close": close,
        "signals": signals,
        "score": score,
        "frame": frame,
        "forward": forward,
        "outcome": outcome,
        "available": available,
    }


def _base_mask(prepared: dict) -> pd.Series:
    """「这一行可以计入评估」的统一口径（预测可用、收益已实现、因子够用）。"""
    return (
        prepared["score"].notna()
        & prepared["frame"]["expected_return"].notna()
        & prepared["forward"].notna()
        & (prepared["outcome"] != 0)
        & prepared["available"]
    )


def evaluate_horizon(
    factors: dict[str, pd.Series],
    close: pd.Series,
    *,
    horizon: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
    score_mode: str = "weighted",
    include: Optional[tuple[str, ...]] = None,
    regression_window: Optional[int] = None,
    interval: str = "aci",
    score: Optional[pd.Series] = None,
) -> HorizonEvaluation:
    """对一段区间做走查式回测。``start`` / ``end`` 为闭区间（按日期）。

    其余关键字参数是研究台的候选变体（口径见 ``prepare_evaluation``）；
    缺省值即线上 ``quant-v4`` 口径。
    """
    if close is None or close.empty:
        return _empty(horizon, "缺少黄金价格序列")

    prepared = prepare_evaluation(
        factors,
        close,
        horizon=horizon,
        score_mode=score_mode,
        include=include,
        regression_window=regression_window,
        interval=interval,
        score=score,
    )
    mask = _base_mask(prepared)
    calendar = close.index
    if start is not None:
        mask &= calendar >= pd.Timestamp(start)
    if end is not None:
        mask &= calendar <= pd.Timestamp(end)

    return _evaluate(horizon, prepared, mask, universe=int(mask.size))


def _evaluate(
    horizon: int,
    prepared: dict,
    mask: pd.Series,
    *,
    universe: int,
) -> HorizonEvaluation:
    """在一段掩码上计算全部指标（三个样本期的唯一实现）。"""
    close = prepared["close"]
    signals = prepared["signals"]
    score = prepared["score"]
    frame = prepared["frame"]
    forward = prepared["forward"]
    outcome = prepared["outcome"]
    expected_return = frame["expected_return"]

    samples = int(mask.sum())
    if samples < MIN_EVALUATION_SAMPLES:
        return _empty(
            horizon,
            f"可评估样本只有 {samples} 个（至少需要 {MIN_EVALUATION_SAMPLES} 个）",
            universe=universe,
        )

    # 评的就是页面上那个方向：校准后的期望收益 μ 的符号（spec 判据见
    # test_backtest_metrics.py::test_accuracy_scores_the_calibrated_direction）。
    # 中位数只用于概率定标度 —— 用它定方向在真实面板上更差，见 engine.SignalSnapshot.direction。
    direction = np.sign(expected_return[mask])
    realized = outcome[mask]
    correct = direction == realized
    accuracy = float(correct.mean())

    # 未校准的因子偏向单独记一份成绩，与「本模型」并排展示，不混为一谈
    score_direction = np.sign(score[mask])
    score_direction_accuracy = float((score_direction == realized).mean())

    up_direction = pd.Series(1.0, index=realized.index)
    up_correct = up_direction == realized
    baseline_up = float(up_correct.mean())

    momentum = np.sign(close / close.shift(MOMENTUM_LOOKBACK) - 1.0).reindex(realized.index)
    momentum_mask = momentum.notna()
    if momentum_mask.sum() >= MIN_EVALUATION_SAMPLES:
        baseline_momentum = float((momentum[momentum_mask] == realized[momentum_mask]).mean())
    else:
        baseline_momentum = None

    probability = frame["probability_up"][mask]
    probability_mask = probability.notna()
    brier = None
    brier_skill = None
    brier_skill_p_value = None
    reliability = None
    if probability_mask.sum() >= MIN_EVALUATION_SAMPLES:
        win = (realized[probability_mask] > 0).astype("float64")
        usable_probability = probability[probability_mask]
        squared_error = (usable_probability - win) ** 2
        brier = float(squared_error.mean())
        brier_skill = stats.brier_skill_score(usable_probability, win)
        # 「Brier 技能分显著为正」的正式检验：模型平方误差 vs 常数基准率，
        # 重叠样本用 HAC —— 与研究台预注册规则 ② 是同一口径。
        skill_test = stats.diebold_mariano(
            squared_error,
            (float(win.mean()) - win) ** 2,
            lags=horizon - 1 if horizon > 1 else None,
            alternative="less",
        )
        brier_skill_p_value = skill_test["p_value"]
        reliability = stats.reliability_bins(usable_probability, win, bins=10)

    window_start = mask[mask].index[0].date()
    window_end = mask[mask].index[-1].date()

    coverage_indicator = interval_coverage_indicator(
        forward[mask], frame["lower_return"][mask], frame["upper_return"][mask]
    )
    interval_coverage = float(coverage_indicator.mean()) if coverage_indicator is not None else None
    in_pre = realized.index < pd.Timestamp(REGIME_SPLIT)
    regimes = {
        "split_date": REGIME_SPLIT.isoformat(),
        "note": "以 2022-01-01 分界：2022 年后央行购金放量，定价函数可能改变",
        "pre": _regime_block("2022-01-01 之前", direction, realized, momentum, in_pre),
        "post": _regime_block("2022-01-01 起", direction, realized, momentum, ~in_pre),
    }

    # 显著性：重叠样本用 HAC（滞后 = h−1），「优于基准」用单尾。
    lags = horizon - 1 if horizon > 1 else None
    accuracy_ci = stats.block_bootstrap_ci(
        correct.astype("float64"), block=max(1, horizon), n=BOOTSTRAP_DRAWS
    )
    vs_up = stats.hac_t_statistic(
        correct.astype("float64") - up_correct.astype("float64"),
        lags=lags,
        alternative="greater",
    )
    momentum_correct = (momentum == realized).astype("float64").where(momentum.notna())
    p_value_vs_momentum = None
    if int(momentum_correct.notna().sum()) >= MIN_EVALUATION_SAMPLES:
        usable = momentum_correct.notna()
        p_value_vs_momentum = stats.hac_t_statistic(
            correct[usable].astype("float64") - momentum_correct[usable],
            lags=lags,
            alternative="greater",
        )["p_value"]
    coverage_ci = None
    if coverage_indicator is not None:
        coverage_ci = stats.block_bootstrap_ci(
            coverage_indicator, block=max(1, horizon), n=BOOTSTRAP_DRAWS
        )

    # 非重叠口径（stride = h）：重叠样本回答「模型每天面对的那串预测成绩如何」，
    # 这一列回答「把这些年当成互不相干的 k 次下注，成绩还剩多少可信度」。
    # 长尺度上两者差别巨大（250 日留出期 506 个重叠样本 = 2 次独立下注），
    # 所以这里宁可返回 None 并如实给出样本数，也不把 2 个观测的覆盖率当结论。
    nonoverlap_correct = stats.nonoverlapping(correct.astype("float64"), horizon)
    nonoverlap_coverage = (
        stats.nonoverlapping(coverage_indicator, horizon) if coverage_indicator is not None else None
    )
    accuracy_nonoverlapping = (
        float(nonoverlap_correct.mean())
        if len(nonoverlap_correct) >= MIN_NONOVERLAPPING_SAMPLES
        else None
    )
    coverage_nonoverlapping = (
        float(nonoverlap_coverage.mean())
        if nonoverlap_coverage is not None and len(nonoverlap_coverage) >= MIN_NONOVERLAPPING_SAMPLES
        else None
    )

    # 「相对永远看多的增量」：单边牛市里绝对方向被基准压死（路线图 §四.3 点到的目标定义问题）。
    # 唯一还能证伪的说法是「模型敢在看空的时候看空」，所以单列看空喊话的次数与命中率：
    # 次数为 0 就是「没有可评估的下注」，必须给 None，不许把「从没喊过跌」算成「喊跌全对」。
    down_mask = direction < 0
    down_calls = int(down_mask.sum())
    down_call_accuracy = (
        float((realized[down_mask] < 0).mean()) if down_calls >= MIN_EVALUATION_SAMPLES else None
    )
    # 幅度技能：把「目标价偏离基准价多少」与「实际偏离多少」放在一起看 ——
    # 基准是「永远回答基准价」（预测不动）。它在方向上完全无从证伪，但在幅度上是有账可算的。
    model_mape = float((expected_return[mask] - forward[mask]).abs().mean())
    flat_mape = float(forward[mask].abs().mean())
    magnitude_mape = model_mape if samples >= MIN_EVALUATION_SAMPLES else None
    magnitude_skill_vs_flat = (
        1.0 - model_mape / flat_mape if flat_mape > 0.0 and samples >= MIN_EVALUATION_SAMPLES else None
    )
    width = frame["upper_return"][mask] - frame["lower_return"][mask]
    sharpness_80 = float(width.mean()) if int(width.notna().sum()) >= MIN_EVALUATION_SAMPLES else None

    metrics = {
        "coin_flip_accuracy": 0.5,
        "horizon_days": horizon,
        "score_direction_accuracy": score_direction_accuracy,
        "accuracy_ci95": [accuracy_ci[0], accuracy_ci[1]],
        "accuracy_diff_vs_up": float(correct.mean() - up_correct.mean()),
        "p_value_vs_up": vs_up["p_value"],
        "p_value_vs_momentum": p_value_vs_momentum,
        "effective_sample_size": stats.effective_sample_size(samples, horizon),
        "down_calls": down_calls,
        "down_call_accuracy": down_call_accuracy,
        "magnitude_mape": magnitude_mape,
        "magnitude_skill_vs_flat": magnitude_skill_vs_flat,
        "interval_sharpness_80": sharpness_80,
        # 「模型原本想报更夸张的数」被封顶拦住的比例：封顶不是美化，是把不可信的幅度
        # 关回市场真的动过的那个量级里，比例本身是要给用户看的健康度指标。
        "expected_cap_rate": float(frame["expected_capped"][mask].mean()),
        "expected_cap_sigmas": engine.EXPECTED_CAP_SIGMAS,
        "nonoverlapping_stride": horizon,
        "nonoverlapping_samples": int(len(nonoverlap_correct)),
        "accuracy_nonoverlapping": accuracy_nonoverlapping,
        "interval_coverage_80_nonoverlapping": coverage_nonoverlapping,
        "nonoverlapping_min_samples": MIN_NONOVERLAPPING_SAMPLES,
        "hac_lags": lags,
        "brier_skill_score": brier_skill,
        "brier_skill_p_value": brier_skill_p_value,
        "reliability_bins": reliability,
        "interval_coverage_ci95": list(coverage_ci) if coverage_ci is not None else None,
        "holdout_start": HOLDOUT_START.isoformat(),
        "up_share": float((realized > 0).mean()),
        "mean_score": float(score[mask].mean()),
        "mean_absolute_score": float(score[mask].abs().mean()),
        "momentum_lookback": MOMENTUM_LOOKBACK,
        "probability_coverage": float(probability_mask.mean()),
        "interval_nominal_80": INTERVAL_NOMINAL_80,
        "interval_coverage_80": interval_coverage,
        "regimes": regimes,
        "per_factor": _per_factor_metrics(signals, forward, mask),
    }

    return HorizonEvaluation(
        horizon_days=horizon,
        window_start=window_start,
        window_end=window_end,
        sample_size=samples,
        accuracy=accuracy,
        baseline_up_accuracy=baseline_up,
        baseline_momentum_accuracy=baseline_momentum,
        brier_score=brier,
        metrics=metrics,
    )


def _per_factor_metrics(
    signals: pd.DataFrame,
    forward: pd.Series,
    mask: pd.Series,
) -> dict:
    """逐因子：单独命中率与 IC（Pearson + Spearman）。

    这是「权重是否失效」的唯一证据来源：某个因子长期命中率低于 0.5，
    说明它的方向先验与实际相反，页面照实展示，不藏。
    """
    result = {}
    for key in signals.columns:
        definition = factor_by_key.get(key)
        if definition is None:
            continue
        column = signals[key]
        usable = mask & column.notna() & forward.notna()
        samples = int(usable.sum())
        if samples < MIN_FACTOR_SAMPLES:
            result[key] = {
                "name": definition.name,
                "category": definition.category,
                "weight": definition.weight,
                "sign": definition.sign,
                "samples": samples,
                "hit_rate": None,
                "ic": None,
                "rank_ic": None,
            }
            continue
        direction = np.sign(column[usable])
        hit_rate = float((direction == np.sign(forward[usable])).mean())
        result[key] = {
            "name": definition.name,
            "category": definition.category,
            "weight": definition.weight,
            "sign": definition.sign,
            "samples": samples,
            "hit_rate": hit_rate,
            "ic": _safe_corr(column[usable], forward[usable]),
            "rank_ic": _safe_corr(column[usable], forward[usable], method="spearman"),
        }
    return result


def interval_coverage_indicator(
    forward: pd.Series,
    lower: pd.Series,
    upper: pd.Series,
) -> Optional[pd.Series]:
    """已实现收益是否落在 [lower, upper] 内的 0/1 序列（区间口径只在这里定义）。

    边界由 ``engine`` 的非对称经验分位 + ACI 给出；样本不足时返回 None ——
    覆盖率低于名义值说明不确定性被低估，要让页面能看见，而不是用一个数字掩盖。
    """
    frame = pd.DataFrame({"forward": forward, "lower": lower, "upper": upper}).dropna()
    if len(frame) < MIN_EVALUATION_SAMPLES:
        return None
    return ((frame["forward"] >= frame["lower"]) & (frame["forward"] <= frame["upper"])).astype(
        "float64"
    )


def interval_coverage_80(
    forward: pd.Series,
    lower: pd.Series,
    upper: pd.Series,
) -> Optional[float]:
    """80% 名义区间的实际覆盖率（区间定义见 ``interval_coverage_indicator``）。"""
    indicator = interval_coverage_indicator(forward, lower, upper)
    if indicator is None:
        return None
    return float(indicator.mean())


def _regime_block(
    label: str,
    direction: pd.Series,
    realized: pd.Series,
    momentum: pd.Series,
    segment,
) -> dict:
    """一个分段的命中率与基准；样本不足时只给样本数与原因。"""
    count = int(segment.sum())
    block = {
        "label": label,
        "window_start": None,
        "window_end": None,
        "sample_size": count,
        "accuracy": None,
        "baseline_up_accuracy": None,
        "baseline_momentum_accuracy": None,
        "reason": None,
    }
    if count == 0:
        block["reason"] = "该区间没有可评估样本"
        return block
    block["window_start"] = realized.index[segment][0].date().isoformat()
    block["window_end"] = realized.index[segment][-1].date().isoformat()
    if count < MIN_EVALUATION_SAMPLES:
        block["reason"] = f"可评估样本只有 {count} 个（至少需要 {MIN_EVALUATION_SAMPLES} 个）"
        return block

    segment_direction = direction[segment]
    segment_realized = realized[segment]
    block["accuracy"] = float((segment_direction == segment_realized).mean())
    block["baseline_up_accuracy"] = float((segment_realized > 0).mean())

    segment_momentum = momentum[segment]
    momentum_mask = segment_momentum.notna()
    if int(momentum_mask.sum()) >= MIN_EVALUATION_SAMPLES:
        block["baseline_momentum_accuracy"] = float(
            (np.sign(segment_momentum[momentum_mask]) == segment_realized[momentum_mask]).mean()
        )
    return block


def _safe_corr(left: pd.Series, right: pd.Series, *, method: str = "pearson") -> Optional[float]:
    correlation = left.corr(right, method=method)
    if correlation is None or pd.isna(correlation):
        return None
    return float(correlation)


def evaluate_all(
    factors: dict[str, pd.Series],
    close: pd.Series,
    *,
    horizons: tuple[int, ...] = HORIZONS,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> list[HorizonEvaluation]:
    return [
        evaluate_horizon(factors, close, horizon=horizon, start=start, end=end)
        for horizon in horizons
    ]


def evaluate_periods(
    factors: dict[str, pd.Series],
    close: pd.Series,
    *,
    horizon: int,
    holdout_start: date = HOLDOUT_START,
    score_mode: str = "weighted",
    include: Optional[tuple[str, ...]] = None,
    regression_window: Optional[int] = None,
    interval: str = "aci",
    score: Optional[pd.Series] = None,
) -> dict[str, HorizonEvaluation]:
    """开发期 / 留出期 / 全样本三列。

    留出期（``HOLDOUT_START`` 起）只用于汇报与预注册裁决，不参与任何调参 ——
    否则「样本外」就不再是样本外。三个切片共用一次预计算（见
    ``prepare_evaluation``），不会对整段历史把同一候选算三遍。
    """
    if close is None or close.empty:
        empty = _empty(horizon, "缺少黄金价格序列")
        return {"development": empty, "holdout": empty, "full": empty}

    prepared = prepare_evaluation(
        factors,
        close,
        horizon=horizon,
        score_mode=score_mode,
        include=include,
        regression_window=regression_window,
        interval=interval,
        score=score,
    )
    base = _base_mask(prepared)
    calendar = close.index
    development = base & (calendar < pd.Timestamp(holdout_start))
    holdout = base & (calendar >= pd.Timestamp(holdout_start))
    return {
        "development": _evaluate(
            horizon, prepared, development, universe=int(development.size)
        ),
        "holdout": _evaluate(horizon, prepared, holdout, universe=int(holdout.size)),
        "full": _evaluate(horizon, prepared, base, universe=int(base.size)),
    }


def _empty(horizon: int, reason: str, *, universe: int = 0) -> HorizonEvaluation:
    return HorizonEvaluation(
        horizon_days=horizon,
        window_start=None,
        window_end=None,
        sample_size=0,
        accuracy=None,
        baseline_up_accuracy=None,
        baseline_momentum_accuracy=None,
        brier_score=None,
        metrics={"reason": reason, "universe_days": universe, "per_factor": {}},
    )


def factor_summary(evaluation: HorizonEvaluation) -> list[dict]:
    """把逐因子指标摊平成列表（给页面用，按权重从大到小）。"""
    rows = []
    for key, item in (evaluation.metrics.get("per_factor") or {}).items():
        rows.append({"key": key, **item})
    rows.sort(key=lambda row: row.get("weight") or 0.0, reverse=True)
    return rows


__all__ = [
    "BOOTSTRAP_DRAWS",
    "HorizonEvaluation",
    "HOLDOUT_START",
    "INTERVAL_NOMINAL_80",
    "REGIME_SPLIT",
    "evaluate_all",
    "evaluate_horizon",
    "evaluate_periods",
    "factor_summary",
    "interval_coverage_80",
    "interval_coverage_indicator",
    "prepare_evaluation",
    "FACTORS",
]
