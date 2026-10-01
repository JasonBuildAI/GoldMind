"""统计工具：诚实评估所需的置信区间与显著性检验。

回测样本是**重叠的** —— h 日前瞻收益每天取一个，相邻样本共享 h−1 天的信息。
把 n 个重叠样本当独立样本，置信区间会过窄、p 值会过小。这里的工具按
「保守近似」处理，不假定 iid：

- :func:`newey_west_se` —— Newey–West HAC 标准误（Bartlett 核，滞后阶数默认按
  ``4·(n/100)^(2/9)`` 的经验规则；前瞻重叠时显式传入 ``lags≥h``）。
- :func:`block_bootstrap_ci` —— 圆周分块自助的百分位区间（块长 ≥ h 才能保留重叠结构）。
- :func:`hac_t_statistic` / :func:`diebold_mariano` —— 均值的 HAC t 检验 /
  两个损失序列的 Diebold–Mariano 检验（双尾，正态近似）。
- :func:`brier_skill_score` / :func:`reliability_bins` —— 概率预测的技能分与可靠性分桶。
- :func:`effective_sample_size` —— 重叠样本的保守折算 ``n/h``。

没有 scipy：正态尾概率用 ``math.erfc`` 直接算，不引入新依赖。
"""
from __future__ import annotations

import math
from typing import Callable, Optional, Sequence

import numpy as np

# 自助默认种子：固定值保证同一输入得到同一条区间（报告可复现）。
DEFAULT_BOOTSTRAP_SEED = 20261002


def _clean(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype="float64").reshape(-1)
    return array[~np.isnan(array)]


def _default_lags(count: int) -> int:
    """Newey–West 经验滞后阶数（整数，至少 0）。"""
    if count <= 1:
        return 0
    return int(np.floor(4.0 * (count / 100.0) ** (2.0 / 9.0)))


def newey_west_se(values: Sequence[float], *, lags: Optional[int] = None) -> float:
    """均值估计的 Newey–West (HAC) 标准误。

    自相关为正时结果大于 ``std/√n``；重叠 h 日的样本应传 ``lags≥h−1``。
    """
    array = _clean(values)
    count = len(array)
    if count < 2:
        return float("nan")
    if lags is None:
        lags = _default_lags(count)
    lags = max(0, min(int(lags), count - 1))

    centered = array - array.mean()
    gamma0 = float(centered @ centered) / count
    variance = gamma0
    for lag in range(1, lags + 1):
        weight = 1.0 - lag / (lags + 1.0)  # Bartlett 核
        gamma = float(centered[lag:] @ centered[:-lag]) / count
        variance += 2.0 * weight * gamma
    variance = max(variance, 0.0)
    return float(math.sqrt(variance / count))


def _normal_survival(statistic: float) -> float:
    """标准正态的右尾概率 P(Z ≥ statistic)。"""
    if not math.isfinite(statistic):
        return float("nan")
    return 0.5 * math.erfc(statistic / math.sqrt(2.0))


def _two_sided_normal_p(statistic: float) -> float:
    if not math.isfinite(statistic):
        return float("nan")
    return float(math.erfc(abs(statistic) / math.sqrt(2.0)))


def _p_value(statistic: float, alternative: str) -> float:
    if alternative == "two-sided":
        return _two_sided_normal_p(statistic)
    if alternative == "greater":
        return _normal_survival(statistic)
    if alternative == "less":
        return _normal_survival(-statistic)
    raise ValueError(f"未知的备择假设：{alternative}")


def hac_t_statistic(
    values: Sequence[float],
    *,
    mu: float = 0.0,
    lags: Optional[int] = None,
    alternative: str = "two-sided",
) -> dict:
    """「均值 = mu」的 HAC t 检验（正态近似）。

    ``alternative`` 取 ``two-sided`` / ``greater`` / ``less``；
    「模型是否优于基准」用 ``greater``。``values`` 传的是**已经减去被检验对象**
    的序列时最方便；例如 DM 检验传入两个模型的损失差。
    返回 ``statistic`` / ``p_value`` / ``lags`` / ``se`` / ``alternative``。
    """
    array = _clean(values)
    count = len(array)
    if lags is None:
        lags = _default_lags(count)
    se = newey_west_se(array, lags=lags)
    if count < 2 or not math.isfinite(se) or se == 0.0:
        return {
            "statistic": float("nan"),
            "p_value": float("nan"),
            "se": float("nan"),
            "lags": lags,
            "sample_size": count,
        }
    statistic = float((array.mean() - mu) / se)
    return {
        "statistic": statistic,
        "p_value": _p_value(statistic, alternative),
        "se": se,
        "lags": lags,
        "alternative": alternative,
        "sample_size": count,
    }


def diebold_mariano(
    loss_a: Sequence[float],
    loss_b: Sequence[float],
    *,
    lags: Optional[int] = None,
    alternative: str = "two-sided",
) -> dict:
    """两个预测的 Diebold–Mariano 检验（双尾）。

    ``d = loss_a − loss_b``：显著为负 → A 的损失显著更低（A 更好）；
    显著为正 → B 更好。损失必须是**同一样本上的可比损失**。
    正自相关（如重叠窗口）会让朴素检验虚高，因此标准误用 HAC。
    """
    left = _clean(loss_a)
    right = _clean(loss_b)
    count = min(len(left), len(right))
    if count < 2:
        return {
            "statistic": float("nan"),
            "p_value": float("nan"),
            "mean_diff": float("nan"),
            "lags": 0 if lags is None else lags,
            "sample_size": count,
        }
    difference = left[:count] - right[:count]
    result = hac_t_statistic(difference, lags=lags, alternative=alternative)
    return {
        "statistic": result["statistic"],
        "p_value": result["p_value"],
        "mean_diff": float(difference.mean()),
        "lags": result["lags"],
        "sample_size": count,
    }


def block_bootstrap_ci(
    values: Sequence[float],
    stat: Callable[[np.ndarray], float] = np.mean,
    *,
    block: int = 20,
    n: int = 2000,
    alpha: float = 0.05,
    seed: int = DEFAULT_BOOTSTRAP_SEED,
) -> tuple[float, float]:
    """圆周分块自助的百分位置信区间。

    ``block`` 要 ≥ 前瞻长度 h，否则重采样打破重叠结构、区间重新变窄。
    同一输入 + 同一种子 → 同一条区间。
    """
    array = _clean(values)
    total = len(array)
    if total == 0:
        return (float("nan"), float("nan"))
    block = max(1, min(int(block), total))
    samples_needed = int(np.ceil(total / block))
    offsets = np.arange(block, dtype="float64").astype(int)
    rng = np.random.default_rng(seed)

    estimates = np.empty(n, dtype="float64")
    positions = np.arange(total)
    for index in range(n):
        starts = rng.choice(positions, size=samples_needed, replace=True)
        picked = (starts[:, None] + offsets[None, :]) % total
        estimates[index] = stat(array[picked.reshape(-1)][:total])
    return (
        float(np.quantile(estimates, alpha / 2.0)),
        float(np.quantile(estimates, 1.0 - alpha / 2.0)),
    )


def brier_skill_score(
    probabilities: Sequence[float],
    outcomes: Sequence[float],
    *,
    base_rate: Optional[float] = None,
) -> Optional[float]:
    """Brier 技能分：``1 − BS / BS_ref``。

    ``BS_ref`` 用基准概率（默认样本内事件频率）的 Brier 分。完全无技能 = 0，
    正值优于基准，负值劣于基准；样本为空或分母为 0 时返回 None。
    """
    p = np.asarray(probabilities, dtype="float64").reshape(-1)
    y = np.asarray(outcomes, dtype="float64").reshape(-1)
    count = min(len(p), len(y))
    if count == 0:
        return None
    p, y = p[:count], y[:count]
    if base_rate is None:
        base_rate = float(y.mean())
    denominator = float(np.mean((base_rate - y) ** 2))
    if denominator == 0.0:
        return None
    return float(1.0 - float(np.mean((p - y) ** 2)) / denominator)


def reliability_bins(
    probabilities: Sequence[float],
    outcomes: Sequence[float],
    *,
    bins: int = 10,
) -> list[dict]:
    """可靠性分桶：每个概率区间的预测均值、实际频率与样本数。

    概率应落在 [0, 1]；区间按等宽划分，``lo`` 含、``hi`` 不含（最后一桶含 1）。
    """
    if bins < 1:
        raise ValueError("bins 必须 ≥ 1")
    p = np.asarray(probabilities, dtype="float64").reshape(-1)
    y = np.asarray(outcomes, dtype="float64").reshape(-1)
    count = min(len(p), len(y))
    rows: list[dict] = []
    edges = np.linspace(0.0, 1.0, bins + 1)
    for index in range(bins):
        lo, hi = float(edges[index]), float(edges[index + 1])
        if index == bins - 1:
            member = (p[:count] >= lo) & (p[:count] <= hi)
        else:
            member = (p[:count] >= lo) & (p[:count] < hi)
        size = int(member.sum())
        rows.append(
            {
                "lo": lo,
                "hi": hi,
                "count": size,
                "mean_predicted": float(p[:count][member].mean()) if size else None,
                "frequency": float(y[:count][member].mean()) if size else None,
            }
        )
    return rows


def effective_sample_size(count: int, horizon: int) -> float:
    """重叠样本的保守折算：n/h（h ≤ 1 时就是 n）。"""
    if horizon <= 1:
        return float(count)
    return float(count) / float(horizon)


__all__ = [
    "DEFAULT_BOOTSTRAP_SEED",
    "block_bootstrap_ci",
    "brier_skill_score",
    "diebold_mariano",
    "effective_sample_size",
    "hac_t_statistic",
    "newey_west_se",
    "reliability_bins",
]
