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
from typing import Any, Callable, Optional, Sequence

import numpy as np

# 自助默认种子：固定值保证同一输入得到同一条区间（报告可复现）。
DEFAULT_BOOTSTRAP_SEED = 20261002


def json_safe(value: Any) -> Any:
    """把 JSON 不能承载的浮点值（NaN / ±Inf）递归换成 None。

    为什么必须有这一层：SQLite 会安静地把 NaN 存进 JSON 列，MySQL 直接拒收
    （``(3140, 'Invalid JSON text: "Invalid value."')``）—— 同一份回测在两种
    方言下一条能落库、一条让整个刷新接口 500（2026-10-02 实测，250 日尺度的
    ``p_value_vs_up`` 在「模型与永远看多逐日一致」时方差为 0，t 检验给出 NaN）。
    清洗放在写出边界，方言差异就不存在了。

    None 的语义也比 NaN 诚实：这不是「0」，而是「这个统计量在这份样本上
    不可计算」—— 与页面上其它「算不出就给 None」的处理保持一致。
    """
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


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


def nonoverlapping(values: Sequence[float], stride: int) -> np.ndarray:
    """从**末尾**往回每 ``stride`` 个取一个，得到近似不共享信息的样本。

    h 日前瞻收益每天取一个，相邻样本共享 h−1 天的信息；``stride = h`` 时取出来的
    窗口互不重叠。保留最后一个观测（最近的表现最要紧），所以锚点在尾部而不是头部。

    这不是「替代」重叠样本 —— 重叠样本才是模型每天真实面对的那串预测；
    它回答的是另一个问题：「把这些年当成 k 次独立下注，成绩还有多可信」。
    """
    array = _clean(values)
    if stride <= 1 or len(array) == 0:
        return array
    return array[::-stride][::-1]


def effective_sample_size(count: int, horizon: int) -> float:
    """重叠样本的保守折算：n/h（h ≤ 1 时就是 n）。"""
    if horizon <= 1:
        return float(count)
    return float(count) / float(horizon)


# Beta 后验的先验写死在这里：Beta(1, 1)（均匀先验）。
# 不提供按调用点覆盖的入口 —— 同一份裁决在任何时候都必须用同一个先验，
# 换先验是一次需要写进预注册文档的口径变更，不是调用参数。
BETA_PRIOR_ALPHA = 1.0
BETA_PRIOR_BETA = 1.0


def _beta_cdf_integer(x: float, alpha: int, beta: int) -> float:
    """正则化不完全 Beta 函数 I_x(alpha, beta)，只支持整数形状参数。

    没有 scipy，也不想为一个 CDF 引进新依赖：整数形状下
    ``I_x(a, b) = Σ_{k=a}^{a+b-1} C(a+b-1, k) x^k (1-x)^(a+b-1-k)``，
    逐项递推求和的项数 = b；取 ``b ≤ a`` 的那一侧算（否则用对称式
    ``I_x(a,b) = 1 − I_{1-x}(b,a)``），两边都不会溢出。
    """
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    if beta < alpha:
        return 1.0 - _beta_cdf_integer(1.0 - x, beta, alpha)
    total_steps = alpha + beta - 1
    log_first = (
        math.lgamma(total_steps + 1)
        - math.lgamma(alpha + 1)
        - math.lgamma(total_steps - alpha + 1)
        + alpha * math.log(x)
        + (total_steps - alpha) * math.log1p(-x)
    )
    term = math.exp(log_first)
    total = term
    ratio = x / (1.0 - x)
    for k in range(alpha, total_steps):
        term *= ratio * (total_steps - k) / (k + 1)
        total += term
    return min(1.0, max(0.0, total))


def beta_quantile(p: float, alpha: float, beta: float) -> float:
    """Beta(alpha, beta) 的 p 分位（整数形状；二分求逆）。"""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    low, high = 0.0, 1.0
    for _ in range(80):
        mid = 0.5 * (low + high)
        if _beta_cdf_integer(mid, int(alpha), int(beta)) < p:
            low = mid
        else:
            high = mid
    return 0.5 * (low + high)


def beta_posterior(
    successes: int,
    total: int,
    *,
    threshold: Optional[float] = None,
) -> dict:
    """命中率的 Beta 后验：先验 Beta(1,1)（写死），后验 = 先验 + 计数。

    ``successes`` / ``total`` 必须是**独立下注**口径的整数计数（重叠样本不是
    独立证据，调用方负责先折算）。``threshold`` 给定时附
    ``probability_above_threshold`` = P(p > threshold)，用于回答
    「模型优于永远看多的概率有多大」，而不是只给一个点估计。
    """
    hits = max(0, int(successes))
    count = max(hits, int(total))
    misses = count - hits
    alpha = BETA_PRIOR_ALPHA + hits
    beta = BETA_PRIOR_BETA + misses
    payload = {
        "prior": [BETA_PRIOR_ALPHA, BETA_PRIOR_BETA],
        "alpha": alpha,
        "beta": beta,
        "successes": hits,
        "independent_bets": count,
        "mean": alpha / (alpha + beta),
        "ci95": [
            beta_quantile(0.025, alpha, beta),
            beta_quantile(0.975, alpha, beta),
        ],
    }
    if threshold is not None and math.isfinite(threshold):
        clipped = min(1.0, max(0.0, float(threshold)))
        payload["threshold"] = clipped
        payload["probability_above_threshold"] = 1.0 - _beta_cdf_integer(
            clipped, int(alpha), int(beta)
        )
    return payload


__all__ = [
    "BETA_PRIOR_ALPHA",
    "BETA_PRIOR_BETA",
    "DEFAULT_BOOTSTRAP_SEED",
    "beta_posterior",
    "beta_quantile",
    "block_bootstrap_ci",
    "brier_skill_score",
    "diebold_mariano",
    "effective_sample_size",
    "hac_t_statistic",
    "newey_west_se",
    "nonoverlapping",
    "reliability_bins",
]
