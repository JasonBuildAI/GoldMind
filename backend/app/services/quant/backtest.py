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
from statistics import NormalDist
from typing import Optional

import numpy as np
import pandas as pd

from app.services.quant import engine
from app.services.quant.definitions import FACTORS, HORIZONS, factor_by_key

# 低于这个样本数就不给命中率（避免「3 天里对了 2 天 = 67%」这种数字）
MIN_EVALUATION_SAMPLES = 30
# 逐因子命中率 / IC 的最低样本数
MIN_FACTOR_SAMPLES = 60
# 动量基准的回看长度（交易日）
MOMENTUM_LOOKBACK = 60
# 80% 名义区间的双侧分位点：Φ⁻¹(0.90)；区间 = 期望收益 ± z·不确定度
INTERVAL_Z_80 = NormalDist().inv_cdf(0.90)
INTERVAL_NOMINAL_80 = 0.80
# 「2022 年后定价函数变了」的分段口径（央行购金放量）
REGIME_SPLIT = date(2022, 1, 1)


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


def evaluate_horizon(
    factors: dict[str, pd.Series],
    close: pd.Series,
    *,
    horizon: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> HorizonEvaluation:
    """对一段区间做走查式回测。``start`` / ``end`` 为闭区间（按日期）。"""
    if close is None or close.empty:
        return _empty(horizon, "缺少黄金价格序列")

    calendar = close.index
    aligned = engine.align_factors(factors, calendar)
    signals = engine.build_signals(aligned, calendar)
    score = engine.composite_score(signals, horizon=horizon)
    frame = engine.build_prediction_frame(score, close, horizon)

    forward = close.shift(-horizon) / close - 1.0
    outcome = np.sign(forward)
    available = signals.notna().sum(axis=1) >= engine.MIN_AVAILABLE_FACTORS

    expected_return = frame["expected_return"]
    mask = (
        score.notna()
        & expected_return.notna()
        & forward.notna()
        & (outcome != 0)
        & available
    )
    if start is not None:
        mask &= calendar >= pd.Timestamp(start)
    if end is not None:
        mask &= calendar <= pd.Timestamp(end)

    samples = int(mask.sum())
    if samples < MIN_EVALUATION_SAMPLES:
        return _empty(
            horizon,
            f"可评估样本只有 {samples} 个（至少需要 {MIN_EVALUATION_SAMPLES} 个）",
            universe=int(mask.size),
        )

    # 评的就是页面上那个方向：校准后的期望收益符号（spec 判据见
    # test_backtest_metrics.py::test_accuracy_scores_the_calibrated_direction）
    direction = np.sign(expected_return[mask])
    realized = outcome[mask]
    accuracy = float((direction == realized).mean())

    # 未校准的因子偏向单独记一份成绩，与「本模型」并排展示，不混为一谈
    score_direction = np.sign(score[mask])
    score_direction_accuracy = float((score_direction == realized).mean())

    up_direction = pd.Series(1.0, index=realized.index)
    baseline_up = float((up_direction == realized).mean())

    momentum = np.sign(close / close.shift(MOMENTUM_LOOKBACK) - 1.0).reindex(realized.index)
    momentum_mask = momentum.notna()
    if momentum_mask.sum() >= MIN_EVALUATION_SAMPLES:
        baseline_momentum = float((momentum[momentum_mask] == realized[momentum_mask]).mean())
    else:
        baseline_momentum = None

    probability = frame["probability_up"][mask]
    probability_mask = probability.notna()
    brier = None
    if probability_mask.sum() >= MIN_EVALUATION_SAMPLES:
        win = (realized[probability_mask] > 0).astype("float64")
        brier = float(((probability[probability_mask] - win) ** 2).mean())

    window_start = mask[mask].index[0].date()
    window_end = mask[mask].index[-1].date()

    interval_coverage = interval_coverage_80(
        forward[mask], frame["expected_return"][mask], frame["uncertainty"][mask]
    )
    in_pre = realized.index < pd.Timestamp(REGIME_SPLIT)
    regimes = {
        "split_date": REGIME_SPLIT.isoformat(),
        "note": "以 2022-01-01 分界：2022 年后央行购金放量，定价函数可能改变",
        "pre": _regime_block("2022-01-01 之前", direction, realized, momentum, in_pre),
        "post": _regime_block("2022-01-01 起", direction, realized, momentum, ~in_pre),
    }

    metrics = {
        "coin_flip_accuracy": 0.5,
        "horizon_days": horizon,
        "score_direction_accuracy": score_direction_accuracy,
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


def interval_coverage_80(
    forward: pd.Series,
    expected: pd.Series,
    sigma: pd.Series,
) -> Optional[float]:
    """80% 名义区间的实际覆盖率：已实现收益落在 μ ± 1.2816σ 内的比例。

    样本不足时返回 None —— 覆盖率低于名义值说明不确定性被低估，
    要让页面能看见，而不是用一个数字掩盖。
    """
    frame = pd.DataFrame({"forward": forward, "expected": expected, "sigma": sigma}).dropna()
    if len(frame) < MIN_EVALUATION_SAMPLES:
        return None
    lower = frame["expected"] - INTERVAL_Z_80 * frame["sigma"]
    upper = frame["expected"] + INTERVAL_Z_80 * frame["sigma"]
    return float(((frame["forward"] >= lower) & (frame["forward"] <= upper)).mean())


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
    "HorizonEvaluation",
    "INTERVAL_NOMINAL_80",
    "REGIME_SPLIT",
    "evaluate_all",
    "evaluate_horizon",
    "factor_summary",
    "interval_coverage_80",
    "FACTORS",
]
