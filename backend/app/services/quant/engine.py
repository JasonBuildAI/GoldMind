"""信号引擎：因子面板 → 可回测的合成得分、概率与目标价。

三条纪律在这一层落地一次，别处不再重复实现：

1. **只用 t 之前的数据**。滚动 z 分数的均值/标准差、概率的 σ、回归的样本
   全部 ``shift`` 到 t 之前；``tests/unit/quant/test_no_lookahead.py`` 用
   「把 t 之后的数据改成垃圾值，t 时刻的结果必须逐位不变」来守这条。
2. **不确定就说不确定**。可用因子少于 3 个、价格序列缺失、得分算不出来，
   一律返回「预测不可用」并给出原因，绝不退回默认方向或默认数字。
3. **单位跟 definitions 走**。``change_Nd`` 是**原单位**的 N 个交易日变化 ——
   利率是百分点而不是百分比，指数是指数点。
4. **陈旧即停用**。``max_age_days`` 不只是界面上一行灰字：超过上限的观测在
   ``align_series`` 里就变成 NaN，因此不进 z、不进合成得分、也不进回测的可用因子计数
   （见 ``align_series`` 的第二条纪律）。低频因子的空窗是**如实反映**，不是回归。

三段式（与 spec 一致）::

    signed_z_i = sign_i × z(x_i)                逐因子方向对齐
    score_h    = Σ w_i(h) × signed_z_i / Σ w_i(h)  按尺度取权重（缺省=基础权重）
    μ_h        = α + β · score                   扩展窗口 OLS，样本对满足 s + h ≤ t
    scale_h    = std(e_s | s + h ≤ t)            走查预测误差，样本不足退回已实现收益的扩展标准差
    F̂_h        最近 CALIBRATION_WINDOW 个已实现 e_s/scale_h 的加权经验分布
                 （半衰期 ACI_HALF_LIFE；名义错失率 α 由 ACI 在线递推）
    区间       = μ + scale · [ F̂⁻¹(α/2),  F̂⁻¹(1−α/2) ]
    情景区间   = μ + scale · [ F̂⁻¹(0.25), F̂⁻¹(0.75) ]
    p_up       = 1 − F̂( −μ / scale )             与区间、情景同一个分布
    σ_display  = (区间上界 − 区间下界) / (2 · z80)  展示用的「等效正态尺度」

方向、概率、目标价、区间、情景只从这一个分布出发 —— 概率**不是** ``Φ(μ/σ_display)``，
那是把为区间宽度放大过的尺度当分母，会把每个概率都压向 50%（实测让 Brier 技能分
全线为负的直接机制）。样本不足时四者一起退回解析正态，逐行记 ``distribution_mode``。
``score`` 是**未校准**的因子偏向，只在因子表里展示，
并在回测里单列成绩（``metrics.score_direction_accuracy``）。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import erf, sqrt
from statistics import NormalDist
from typing import Optional

import numpy as np
import pandas as pd

from app.services.quant.definitions import FACTORS, factor_by_key
from app.utils import timeutil

# 滚动 z 分数：5 年窗口（约 252 个交易日），至少 60 个样本才开始出信号
ZSCORE_WINDOW = 252
MIN_HISTORY = 60
# 概率的 σ 至少要有这么多个历史得分
MIN_SCORES_FOR_SIGMA = 20
# 扩展窗口 OLS 至少要有这么多个「已实现」的样本对，否则 β=0（目标价=基准价）
MIN_OLS_SAMPLES = 60
# 走查预测误差的 σ 至少要有这么多个「已实现」的误差（与 OLS 同一档）
MIN_ERRORS_FOR_SIGMA = 60
# 80% 名义区间的双侧分位点 Φ⁻¹(0.90)；展示口径统一成「μ ± INTERVAL_Z_80 × uncertainty」
INTERVAL_Z_80 = NormalDist().inv_cdf(0.90)
# 情景分层（基准 = 中间 50%）的分位点 Φ⁻¹(0.75)，正态口径下用
QUARTILE_Z = NormalDist().inv_cdf(0.75)
# 分布中位数所在的分位点：方向评的是它，不是 μ（见 SignalSnapshot.direction）
MEDIAN_QUANTILE = 0.50
# 80% 名义区间的目标错失率（α = 0.20）
INTERVAL_ALPHA = 0.20
# 情景分层的分位点（基准 = [q25, q75]，看涨 q75 以上，看跌 q25 以下）
QUARTILE_LOW = 0.25
QUARTILE_HIGH = 0.75
# ACI（自适应保形推断，Gibbs & Candès 2021）的步长：误差连续落在区间外就把
# α 调小（区间变宽），连续落在区间内就把 α 调大（区间收紧）
ACI_GAMMA = 0.01
# 指数权重半衰期（交易日）：250 日前的样本权重减半 —— 允许分布缓慢漂移
ACI_HALF_LIFE = 250
# 校准样本最长回看：半衰期之外再老的数据权重过低，只增加计算量
CALIBRATION_WINDOW = 750
# α 的安全范围：太小的 α 会让区间退化成「永远覆盖」，太大则失去意义
ACI_ALPHA_FLOOR = 0.005
ACI_ALPHA_CAP = 0.6
# 合成得分的变体（研究台用；默认仍是 weighted，即线上口径）
SCORE_MODES = ("weighted", "equal", "winsor", "trimmed")
WINSOR_LIMIT = 2.0
# 区间口径的变体（研究台用；默认仍是 aci，即线上口径）
INTERVAL_MODES = ("aci", "aci_symmetric", "empirical", "normal")

EPS = 1e-12

STATUS_OK = "ok"
STATUS_STALE = "stale"
STATUS_MISSING = "missing"
# 数据是新的，但历史样本还不够算 z（新接入的因子在最初 60 个交易日会经历这个状态）
STATUS_WARMING = "warming"


def normal_cdf(value: float) -> float:
    """标准正态分布函数（用 math.erf，避免为一个函数引入 scipy）。"""
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


# --------------------------------------------------------------------------- #
# 因子 → 信号
# --------------------------------------------------------------------------- #
def apply_transform(series: pd.Series, transform: str) -> pd.Series:
    """按定义把因子值变成平稳序列。``change_Nd`` = 原单位的 N 日变化。"""
    if transform.startswith("change_"):
        periods = int(transform[len("change_"):].rstrip("d"))
        return series - series.shift(periods)
    return series


def rolling_z(
    series: pd.Series,
    *,
    window: int = ZSCORE_WINDOW,
    min_history: int = MIN_HISTORY,
) -> pd.Series:
    """滚动 z 分数：t 时刻用 t **之前**的 window 个样本算均值与标准差。

    ``shift(1)`` 不是可选项：没有它，t 时刻的 z 里就混进了 t 自己的值，
    回测会因此高估命中率（历史的 t 在真实预测时还没收盘）。
    """
    mean = series.rolling(window, min_periods=min_history).mean().shift(1)
    std = series.rolling(window, min_periods=min_history).std().shift(1)
    return (series - mean) / std.where(std > EPS)


def align_series(
    series: pd.Series, calendar: pd.DatetimeIndex, *, max_age_days: Optional[int] = None
) -> pd.Series:
    """把一个序列落到价格日历上：只向前填充，且**填充不得越过新鲜度上限**。

    两条纪律，缺一不可：

    1. t 时刻不会用到 t 之后才发布的数（只向前填充）；
    2. 最近一条**真实观测**超过 ``max_age_days`` 之后，该因子在这一行是 NaN。
       「陈旧」必须同时意味着「不参与合成」：历史上 ``max_age_days`` 只进了
       ``factor_states`` 的展示分支，于是月频因子断更两个月后，页面写着「陈旧」、
       得分却继续按它最高档的权重贡献 —— 显示层与计算层说的是两件事。
    """
    reindexed = series.reindex(calendar)
    aligned = reindexed.ffill()
    if max_age_days is None:
        return aligned
    last_real = pd.Series(calendar, index=calendar).where(reindexed.notna()).ffill()
    age_days = (pd.Series(calendar, index=calendar) - last_real).dt.days
    return aligned.mask(age_days > max_age_days)


def align_factors(
    factors: dict[str, pd.Series], calendar: pd.DatetimeIndex
) -> dict[str, pd.Series]:
    """把每个因子对齐到价格日历：低频序列（月度储备、周度持仓）按最近值前向填充。

    新鲜度上限取自 ``definitions``（每个因子自己的发布节奏）；不在因子表里的原始序列
    （金价、HYG/IEF 这类中间量）没有「发布节奏」可言，因此不受该上限约束。
    """
    aligned: dict[str, pd.Series] = {}
    for key, series in factors.items():
        if series is None or series.empty:
            continue
        definition = factor_by_key.get(key)
        aligned[key] = align_series(
            series, calendar, max_age_days=None if definition is None else definition.max_age_days
        )
    return aligned


def build_signals(
    factors: dict[str, pd.Series], calendar: pd.DatetimeIndex
) -> pd.DataFrame:
    """每个因子的方向对齐信号 ``signed_z = sign × z(transform(x))``。

    返回值：index = 价格日历，columns = 因子 key，NaN = 当日不可用（含「陈旧」）。
    """
    columns: dict[str, pd.Series] = {}
    for definition in FACTORS:
        series = factors.get(definition.key)
        if series is None or series.empty:
            continue
        aligned = align_series(series, calendar, max_age_days=definition.max_age_days)
        transformed = apply_transform(aligned, definition.transform)
        z = rolling_z(transformed)
        columns[definition.key] = (z * definition.sign).rename(definition.key)
    if not columns:
        return pd.DataFrame(index=calendar)
    return pd.DataFrame(columns, index=calendar)


def composite_score(
    signals: pd.DataFrame,
    *,
    horizon: Optional[int] = None,
    mode: str = "weighted",
    include: Optional[tuple[str, ...]] = None,
) -> pd.Series:
    """加权合成得分，权重按当日**可用**因子归一（缺因子不等于该因子为 0）。

    ``horizon`` 决定用哪一组权重：不同时间尺度主导项不同（见 definitions 的
    ``horizon_weights``）；``None`` 表示基础权重。

    ``mode`` 是研究台的预注册变体：``weighted``（线上口径）、``equal``（等权）、
    ``winsor``（z 截尾到 ±2 再加权）、``trimmed``（每行剔除绝对值最大的一个贡献）。
    ``include`` 限定因子子集（研究台用；默认全部）。
    """
    if signals.empty:
        return pd.Series(dtype="float64", index=signals.index)
    if mode not in SCORE_MODES:
        raise ValueError(f"未知的合成模式：{mode}")
    frame = signals
    if include is not None:
        frame = frame[[key for key in frame.columns if key in set(include)]]
    if frame.empty:
        return pd.Series(np.nan, index=signals.index)
    weights = pd.Series(
        {
            key: factor_by_key[key].weight_for(horizon)
            for key in frame.columns
            if key in factor_by_key
        }
    )
    if weights.empty:
        return pd.Series(np.nan, index=signals.index)
    if mode == "equal":
        weights = pd.Series(1.0, index=weights.index)
    values = frame.clip(-WINSOR_LIMIT, WINSOR_LIMIT) if mode == "winsor" else frame
    if mode == "trimmed":
        weighted_values = values.mul(weights, axis=1)
        available_count = values.notna().mul(weights, axis=1).sum(axis=1)
        rank = weighted_values.abs().rank(axis=1, ascending=False, method="first")
        keep = (rank > 1) | (available_count < 4).values[:, None]
        values = values.where(keep)
    present = values.notna().mul(weights, axis=1)
    total_weight = present.sum(axis=1)
    weighted = values.mul(weights, axis=1).sum(axis=1, skipna=True)
    return weighted / total_weight.where(total_weight > EPS)


# --------------------------------------------------------------------------- #
# 得分 → 概率与期望收益
# --------------------------------------------------------------------------- #
def _sorted_sample(values: np.ndarray, weights: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """把校准样本按值排序，返回 ``(值, 对应权重, 权重和)``。

    排序一次就够：分位点与尾概率都从这同一个有序视图取，保证
    「区间的两个端点」和「上行概率」问的是**同一个**分布。
    """
    order = np.argsort(values, kind="stable")
    ordered = weights[order]
    return values[order], ordered, float(ordered.sum())


def _weighted_quantile_from(sorted_values: np.ndarray, cumulative: np.ndarray,
                            total: float, level: float) -> float:
    """加权分位数：按权重累计到 ``level`` 处的样本值（阶梯取值，不线性插值）。"""
    index = int(np.searchsorted(cumulative, level * total, side="left"))
    return float(sorted_values[min(index, len(sorted_values) - 1)])


def _weighted_tail_above(sorted_values: np.ndarray, cumulative: np.ndarray,
                         total: float, point: float) -> float:
    """加权尾概率 ``P(V > point)`` —— 与上面的分位数共用同一个有序视图。"""
    index = int(np.searchsorted(sorted_values, point, side="right"))
    if index <= 0:
        return 1.0
    if index >= len(sorted_values):
        return 0.0
    return float(max(0.0, min(1.0, (total - cumulative[index - 1]) / total)))


def normal_probability_up(expected: pd.Series, sigma: pd.Series) -> pd.Series:
    """正态兜底的上行概率 ``Φ(μ/σ)`` —— 只在经验样本不足时使用。

    σ 缺失或非正时不给概率（NaN）—— 不拿别处的 σ 顶替，也不退回 50%。
    """
    ratio = expected / sigma.where(sigma > EPS)
    return ratio.map(lambda value: normal_cdf(float(value)) if pd.notna(value) else np.nan)


def calibrate_distribution(
    ratio: pd.Series,
    flat_z: pd.Series,
    *,
    alpha: float = INTERVAL_ALPHA,
    gamma: float = ACI_GAMMA,
    half_life: Optional[int] = ACI_HALF_LIFE,
    window: Optional[int] = CALIBRATION_WINDOW,
    min_samples: int = MIN_ERRORS_FOR_SIGMA,
    symmetric: bool = False,
) -> pd.DataFrame:
    """studentized 误差 → 逐日校准分布的出口：区间端点、四分位、上行概率。

    输入 ``ratio`` 是**已经实现**的预测误差除以其尺度（``e / scale``，已按实现时间
    右移），``flat_z`` 是「收益恰好为 0」在这套 z 上的位置（``−μ / scale``）。
    一行之内所有出口都来自同一个加权经验分布 ``F̂``：

    ```
    区间   = μ + scale · [ F̂⁻¹(α/2),      F̂⁻¹(1−α/2) ]      （symmetric 时取 ±|z| 分位）
    四分位 = μ + scale · [ F̂⁻¹(0.25),     F̂⁻¹(0.75)  ]
    上行   = 1 − F̂(flat_z)                                  （不是 Φ(μ/σ)！）
    ```

    名义错失率 α 按 ACI（自适应保形推断，Gibbs & Candès 2021）在线递推：
    ``α ← α + γ × (α_target − miss)``，误差落在区间外就把 α 调小（区间变宽），
    落回区间内则逐步收紧；半衰期 ``half_life`` 个交易日让分布能缓慢漂移。

    三个参数把预注册的四种区间口径统一到这里，不再各写一套：
    ``gamma=0`` 且 ``half_life=None`` 且 ``window=None`` = 纯经验分位（无 ACI、全历史等权），
    ``symmetric=True`` = 对称版本，``interval="normal"`` 由调用方走解析正态、不调这里。

    样本不足 ``min_samples`` 的行返回 NaN，由调用方回退到正态分位。
    """
    values = ratio.to_numpy(dtype="float64")
    points = flat_z.to_numpy(dtype="float64")
    count = len(values)
    columns = {
        "lower": np.full(count, np.nan, dtype="float64"),
        "upper": np.full(count, np.nan, dtype="float64"),
        "alpha": np.full(count, np.nan, dtype="float64"),
        "q25": np.full(count, np.nan, dtype="float64"),
        "q50": np.full(count, np.nan, dtype="float64"),
        "q75": np.full(count, np.nan, dtype="float64"),
        "probability_up": np.full(count, np.nan, dtype="float64"),
    }
    history: list[float] = []
    current_alpha = float(alpha)

    for position in range(count):
        if len(history) >= min_samples:
            tail = history[-window:] if window else history
            if half_life:
                ages = np.arange(len(tail) - 1, -1, -1, dtype="float64")
                weights = np.power(0.5, ages / float(half_life))
            else:
                weights = np.ones(len(tail), dtype="float64")
            sample = np.asarray(tail, dtype="float64")
            sorted_values, sorted_weights, total = _sorted_sample(sample, weights)
            cumulative = np.cumsum(sorted_weights)
            if symmetric:
                # 对称口径：用 |z| 的经验分位当半宽，两个端点强制关于 0 对称
                magnitude_values, magnitude_weights, magnitude_total = _sorted_sample(
                    np.abs(sample), weights
                )
                magnitude = _weighted_quantile_from(
                    magnitude_values,
                    np.cumsum(magnitude_weights),
                    magnitude_total,
                    1.0 - current_alpha / 2.0,
                )
                q_low, q_high = -magnitude, magnitude
            else:
                q_low = _weighted_quantile_from(
                    sorted_values, cumulative, total, current_alpha / 2.0
                )
                q_high = _weighted_quantile_from(
                    sorted_values, cumulative, total, 1.0 - current_alpha / 2.0
                )
            columns["lower"][position] = q_low
            columns["upper"][position] = q_high
            columns["alpha"][position] = current_alpha
            columns["q25"][position] = _weighted_quantile_from(
                sorted_values, cumulative, total, QUARTILE_LOW
            )
            columns["q50"][position] = _weighted_quantile_from(
                sorted_values, cumulative, total, MEDIAN_QUANTILE
            )
            columns["q75"][position] = _weighted_quantile_from(
                sorted_values, cumulative, total, QUARTILE_HIGH
            )
            if np.isfinite(points[position]) and total > EPS:
                columns["probability_up"][position] = _weighted_tail_above(
                    sorted_values, cumulative, total, points[position]
                )
            value = values[position]
            if np.isfinite(value):
                miss = 1.0 if (value < q_low or value > q_high) else 0.0
                current_alpha = float(
                    np.clip(
                        current_alpha + gamma * (alpha - miss),
                        ACI_ALPHA_FLOOR,
                        ACI_ALPHA_CAP,
                    )
                )
        if np.isfinite(values[position]):
            history.append(float(values[position]))

    return pd.DataFrame(columns, index=ratio.index)


def expanding_ols(
    x: pd.Series,
    y: pd.Series,
    *,
    min_samples: int = MIN_OLS_SAMPLES,
    window: Optional[int] = None,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """扩展窗口（或滚动窗口）一元回归，返回 ``(alpha, beta, residual_sigma, calibrated)``。

    ``window`` 给定时改为滚动窗口（研究台的「漂移」预注册变体）：
    只使用最近 ``window`` 个已实现样本，允许定价关系随时间漂移。

    调用方必须传**已经右移过 h 期**的 x / y（见 ``build_prediction_frame``）：
    这样 t 时刻的样本只包含 ``s + h <= t`` 的已实现样本对，回归不会看到未来。
    ``calibrated`` 是「这个时刻的回归能不能用」：样本不足或 x 无波动时为 False，
    此时 alpha/beta 置 0 只是为了让级数连续，调用方必须用 ``calibrated`` 判断
    能不能拿它当预测 —— 不能（见 ``build_prediction_frame``）。
    """
    frame = pd.DataFrame({"x": x, "y": y}).dropna()
    if frame.empty:
        empty = pd.Series(np.nan, index=x.index, dtype="float64")
        return empty, empty, empty, pd.Series(False, index=x.index, dtype="bool")

    if window is None:
        expanding = frame["x"].expanding()
        y_expanding = frame["y"].expanding()
        xx_expanding = (frame["x"] ** 2).expanding()
        xy_expanding = (frame["x"] * frame["y"]).expanding()
        yy_expanding = (frame["y"] ** 2).expanding()
    else:
        expanding = frame["x"].rolling(window, min_periods=min_samples)
        y_expanding = frame["y"].rolling(window, min_periods=min_samples)
        xx_expanding = (frame["x"] ** 2).rolling(window, min_periods=min_samples)
        xy_expanding = (frame["x"] * frame["y"]).rolling(window, min_periods=min_samples)
        yy_expanding = (frame["y"] ** 2).rolling(window, min_periods=min_samples)
    n = expanding.count()
    sum_x = expanding.sum()
    sum_y = y_expanding.sum()
    sum_xx = xx_expanding.sum()
    sum_xy = xy_expanding.sum()
    sum_yy = yy_expanding.sum()

    denominator = n * sum_xx - sum_x ** 2
    usable = (n >= min_samples) & (denominator.abs() > EPS)
    beta = ((n * sum_xy - sum_x * sum_y) / denominator.where(denominator.abs() > EPS)).where(usable, 0.0)
    alpha = ((sum_y - beta * sum_x) / n).where(usable, 0.0)

    residual_sq = (
        sum_yy
        - 2 * alpha * sum_y
        - 2 * beta * sum_xy
        + n * alpha ** 2
        + 2 * alpha * beta * sum_x
        + beta ** 2 * sum_xx
    )
    sigma = (residual_sq.clip(lower=0.0) / (n - 2).clip(lower=1.0)).pow(0.5)
    sigma = sigma.where(n >= max(min_samples, 3))

    return (
        alpha.reindex(x.index),
        beta.reindex(x.index),
        sigma.reindex(x.index),
        usable.reindex(x.index, fill_value=False).astype("bool"),
    )


def build_prediction_frame(
    score: pd.Series,
    close: pd.Series,
    horizon: int,
    *,
    regression_window: Optional[int] = None,
    interval: str = "aci",
) -> pd.DataFrame:
    """把得分序列变成逐日的预测：期望收益、区间、情景区间、上行概率、目标价。

    **一个分布，四个出口。** 区间、情景的四分位区间与上行概率必须来自同一张
    校准分布，否则页面会出现「区间按 80% 说的是一套、概率说的是另一套」。
    四种 ``interval`` 口径只是同一张分布的不同取法：

    ```
    aci            加权经验分位 + ACI 在线调 α（非对称，线上口径）
    aci_symmetric  同上，但端点关于期望收益强制对称
    empirical      全历史等权经验分位、不调 α（预注册候选 P2）
    normal         解析正态 N(μ, scale²)（预注册候选 P3，也是样本不足时的兜底）
    ```

    ``uncertainty`` 定义为**该行区间宽度折算成的正态尺度** ``（上界 − 下界）/ (2·z80)``：
    对称口径（``normal`` / ``empirical``）下 ``μ ± 1.2816 × uncertainty`` 恰好等于展示的区间；
    线上口径 ``aci`` 是非对称的，区间中点不等于 μ，两者只有宽度相等。
    它不再充当概率的分母：概率要么来自同一个经验分布的尾部比例，
    要么来自同一个正态 —— 拿放大过的 σ 去除 ``Φ`` 会把每个概率都压向 50%。

    尺度 ``scale`` 是**走查预测误差**的标准差，不是回归残差：残差只说明
    「拟合线周围的散布」，预测误差才回答「模型自己错了多少」——
    两者的差距就是区间覆盖率与名义值（80%）之间的差距。
    """
    if interval not in INTERVAL_MODES:
        raise ValueError(f"未知的区间口径：{interval}")
    forward = close.shift(-horizon) / close - 1.0
    alpha, beta, _, calibrated = expanding_ols(
        score.shift(horizon), forward.shift(horizon), window=regression_window
    )
    # 没校准就没有期望收益：NaN 而不是 0，否则「样本不足」会被下游当成「预期不变」
    expected = (alpha + beta * score).where(calibrated)
    # t 时刻只取 (s + h ≤ t) 的误差：e_s = 已实现收益 − 当时给出的期望收益
    errors = (forward - expected).shift(horizon)
    error_scale = errors.expanding(min_periods=MIN_ERRORS_FOR_SIGMA).std()
    # 回归样本不足时退回「已实现 h 日收益的扩展标准差」，仍然只用过去的数据
    fallback = forward.shift(horizon).expanding(min_periods=MIN_SCORES_FOR_SIGMA).std()
    scale = error_scale.fillna(fallback)
    # 收益恰好为 0 在这套 studentized 误差上的位置：r = 0 ⟺ z = −μ / scale
    flat_z = -expected / scale.where(scale > EPS)

    if interval == "normal":
        lower_factor = pd.Series(-INTERVAL_Z_80, index=expected.index)
        upper_factor = pd.Series(INTERVAL_Z_80, index=expected.index)
        quartile_low = pd.Series(-QUARTILE_Z, index=expected.index)
        quartile_high = pd.Series(QUARTILE_Z, index=expected.index)
        # 解析正态关于 μ 对称，中位数就是 μ
        median = pd.Series(0.0, index=expected.index)
        probability = normal_probability_up(expected, scale)
        interval_alpha = pd.Series(np.nan, index=expected.index)
        distribution_mode = pd.Series("normal", index=expected.index)
    else:
        adaptive = interval != "empirical"
        calibration = calibrate_distribution(
            errors / scale,
            flat_z,
            gamma=ACI_GAMMA if adaptive else 0.0,
            half_life=ACI_HALF_LIFE if adaptive else None,
            window=CALIBRATION_WINDOW if adaptive else None,
            symmetric=interval in ("aci_symmetric", "empirical"),
        )
        # 经验样本不足的行：区间、四分位与概率**一起**退回正态，不许一半经验一半正态
        insufficient = calibration["lower"].isna()
        lower_factor = calibration["lower"].mask(insufficient, -INTERVAL_Z_80)
        upper_factor = calibration["upper"].mask(insufficient, INTERVAL_Z_80)
        quartile_low = calibration["q25"].mask(insufficient, -QUARTILE_Z)
        quartile_high = calibration["q75"].mask(insufficient, QUARTILE_Z)
        median = calibration["q50"].mask(insufficient, 0.0)
        probability = calibration["probability_up"].mask(
            insufficient, normal_probability_up(expected, scale)
        )
        interval_alpha = calibration["alpha"]
        distribution_mode = pd.Series(
            np.where(insufficient.to_numpy(), "normal", interval), index=expected.index
        )

    lower_return = expected + scale * lower_factor
    upper_return = expected + scale * upper_factor
    frame = pd.DataFrame(
        {
            "score": score,
            "expected_return": expected,
            "base_price": close,
            "lower_return": lower_return,
            "upper_return": upper_return,
            "quartile_low_return": expected + scale * quartile_low,
            "quartile_high_return": expected + scale * quartile_high,
            "median_return": expected + scale * median,
            "interval_alpha": interval_alpha,
            "distribution_mode": distribution_mode,
        }
    )
    frame["uncertainty"] = (upper_return - lower_return) / (2.0 * INTERVAL_Z_80)
    frame["probability_up"] = probability
    frame["target_price"] = frame["base_price"] * (1.0 + frame["expected_return"])
    return frame


# --------------------------------------------------------------------------- #
# 快照：接口与界面要的那一份
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FactorState:
    key: str
    name: str
    category: str
    unit: str
    source: str
    description: str
    sign: int
    weight: float
    value: Optional[float]
    obs_date: Optional[date]
    age_days: Optional[int]
    max_age_days: int
    z: Optional[float]
    signed_z: Optional[float]
    contribution: Optional[float]
    status: str
    reason: Optional[str]

    @property
    def available(self) -> bool:
        return self.status == STATUS_OK and self.signed_z is not None


@dataclass(frozen=True)
class SignalSnapshot:
    as_of: date
    horizon_days: int
    status: str
    reason: Optional[str]
    base_price: Optional[float]
    score: Optional[float]
    probability_up: Optional[float]
    expected_return: Optional[float]
    uncertainty: Optional[float]
    target_price: Optional[float]
    states: tuple[FactorState, ...]
    weight_used: float
    # 校准分布的其余出口（与区间同批分位样本，见 build_prediction_frame）：
    # 情景区间取四分位，distribution_mode 记录这一行用的是经验分布还是正态兜底。
    interval_low_return: Optional[float] = None
    interval_high_return: Optional[float] = None
    scenario_low_return: Optional[float] = None
    scenario_high_return: Optional[float] = None
    median_return: Optional[float] = None
    distribution_mode: Optional[str] = None

    @property
    def direction(self) -> Optional[str]:
        """方向 = 期望收益 μ 的符号 —— 页面上的方向与回测评的都是它。

        为什么不用分布中位数定方向（2026-10-02 试过，用真实 20 年面板实测后退回）：
        走查预测误差的位置项系统性偏负（中位数比 μ 低：20 日 0.31pp、60 日 0.68pp、
        250 日 4.4pp），按中位数定方向会把约 30% 的喊单翻成看跌，而这段行情里只有
        56–83% 的日子在涨 —— 留出期命中率 60 日从 83.3% 掉到 78.9%、20 日从 68.2%
        掉到 64.9%，只有 1 日持平。**位置项在这个用途上是噪声**，所以决策用 μ，
        分布位置只用来给概率与区间定标度（那一项实测是全线变好的）。

        均值与中位数可以合法地给出不同符号（右偏分布 = 常小幅跌、偶大幅涨），
        所以「方向」与「上行概率」是两个不同的统计量，不是互相打脸。
        μ 恰为 0（回归样本不足）记 ``flat``：不拿未校准的得分符号顶替。
        """
        if self.status != STATUS_OK or self.expected_return is None:
            return None
        if self.expected_return > 0:
            return "up"
        if self.expected_return < 0:
            return "down"
        return "flat"

    @property
    def available_factors(self) -> int:
        return sum(1 for state in self.states if state.available)


PREDICTION_UNAVAILABLE = "unavailable"


def _asof_position(calendar: pd.DatetimeIndex, as_of: Optional[date]) -> int:
    if as_of is None:
        return len(calendar) - 1
    position = int(calendar.searchsorted(pd.Timestamp(as_of), side="right")) - 1
    if position < 0:
        raise ValueError(f"价格日历里没有 {as_of} 之前的数据")
    return position


def _clean(value) -> Optional[float]:
    if value is None:
        return None
    number = float(value)
    return None if np.isnan(number) else number


def factor_states(
    factors: dict[str, pd.Series],
    signals: pd.DataFrame,
    *,
    as_of: pd.Timestamp,
    horizon: Optional[int] = None,
) -> tuple[FactorState, ...]:
    """t 时刻每个因子的状态：最新值、新鲜度、z、贡献（权重取该尺度下的）。"""
    total_weight = 0.0
    prepared: list[dict] = []

    for definition in FACTORS:
        weight = definition.weight_for(horizon)
        series = factors.get(definition.key)
        value = None
        obs_date = None
        age_days = None
        if series is not None and not series.empty:
            position = int(series.index.searchsorted(as_of, side="right")) - 1
            if position >= 0:
                obs_date = series.index[position].date()
                value = _clean(series.iloc[position])
                age_days = (as_of.date() - obs_date).days

        z = None
        signed_z = None
        if definition.key in signals.columns and as_of in signals.index:
            signed_z = _clean(signals.at[as_of, definition.key])
            if signed_z is not None:
                # signed_z = sign × z，还原界面要展示的原始 z
                z = signed_z * definition.sign

        if value is None:
            status, reason = STATUS_MISSING, "尚无数据"
        elif age_days is not None and age_days > definition.max_age_days:
            status, reason = (
                STATUS_STALE,
                f"最近一条数据是 {age_days} 天前，超过该因子的更新周期（{definition.max_age_days} 天）",
            )
        elif signed_z is None:
            status, reason = STATUS_WARMING, "历史样本不足，暂不参与合成（需要至少 60 个交易日）"
        else:
            status, reason = STATUS_OK, None

        if status == STATUS_OK and signed_z is not None:
            total_weight += weight

        prepared.append(
            {
                "definition": definition,
                "weight": weight,
                "value": value,
                "obs_date": obs_date,
                "age_days": age_days,
                "z": z,
                "signed_z": signed_z,
                "status": status,
                "reason": reason,
            }
        )

    states = []
    for item in prepared:
        definition = item["definition"]
        contribution = None
        if item["status"] == STATUS_OK and item["signed_z"] is not None and total_weight > EPS:
            contribution = item["weight"] * item["signed_z"] / total_weight
        states.append(
            FactorState(
                key=definition.key,
                name=definition.name,
                category=definition.category,
                unit=definition.unit,
                source=definition.source,
                description=definition.description,
                sign=definition.sign,
                weight=item["weight"],
                value=item["value"],
                obs_date=item["obs_date"],
                age_days=item["age_days"],
                max_age_days=definition.max_age_days,
                z=item["z"],
                signed_z=item["signed_z"],
                contribution=contribution,
                status=item["status"],
                reason=item["reason"],
            )
        )
    return tuple(states)


MIN_AVAILABLE_FACTORS = 3


def build_snapshot(
    factors: dict[str, pd.Series],
    close: pd.Series,
    *,
    horizon: int,
    as_of: Optional[date] = None,
) -> SignalSnapshot:
    """t 时刻的完整快照。不可用时 status=unavailable 且所有数字为 None。"""
    if close is None or close.empty:
        return _unavailable(horizon, "缺少黄金价格序列", as_of=as_of, states=())

    calendar = close.index
    position = _asof_position(calendar, as_of)
    effective = calendar[position]

    aligned = align_factors({key: value for key, value in factors.items()}, calendar)
    signals = build_signals(aligned, calendar)
    frame = build_prediction_frame(composite_score(signals, horizon=horizon), close, horizon)
    # 新鲜度看的是原始序列（对齐后的序列尾部全是前向填充，会永远显示「今天刚更新」）
    states = factor_states(factors, signals, as_of=effective, horizon=horizon)

    available = [state for state in states if state.available]
    weight_used = sum(state.weight for state in available)

    row = frame.iloc[position]
    base_price = _clean(row["base_price"])

    if len(available) < MIN_AVAILABLE_FACTORS:
        return _unavailable(
            horizon,
            f"可用因子只有 {len(available)} 个（至少需要 {MIN_AVAILABLE_FACTORS} 个）",
            as_of=effective.date(),
            states=states,
        )
    if base_price is None:
        return _unavailable(horizon, "基准价格缺失", as_of=effective.date(), states=states)

    score = _clean(row["score"])
    if score is None:
        return _unavailable(horizon, "合成得分不可用（因子历史样本不足）", as_of=effective.date(), states=states)
    if _clean(row["expected_return"]) is None:
        # 没有校准就没有方向与目标价：给出原因，不退回「预期不变」
        return _unavailable(
            horizon,
            f"回归校准样本不足（{horizon} 日尺度至少需要 {MIN_OLS_SAMPLES} 组已实现的样本对）",
            as_of=effective.date(),
            states=states,
        )

    return SignalSnapshot(
        as_of=effective.date(),
        horizon_days=horizon,
        status=STATUS_OK,
        reason=None,
        base_price=base_price,
        score=score,
        probability_up=_clean(row["probability_up"]),
        expected_return=_clean(row["expected_return"]),
        uncertainty=_clean(row["uncertainty"]),
        target_price=_clean(row["target_price"]),
        states=states,
        weight_used=weight_used,
        interval_low_return=_clean(row["lower_return"]),
        interval_high_return=_clean(row["upper_return"]),
        scenario_low_return=_clean(row["quartile_low_return"]),
        scenario_high_return=_clean(row["quartile_high_return"]),
        median_return=_clean(row["median_return"]),
        distribution_mode=str(row["distribution_mode"]),
    )


def _unavailable(
    horizon: int,
    reason: str,
    *,
    as_of: Optional[date],
    states: tuple[FactorState, ...],
) -> SignalSnapshot:
    return SignalSnapshot(
        as_of=as_of or timeutil.today(),
        horizon_days=horizon,
        status=PREDICTION_UNAVAILABLE,
        reason=reason,
        base_price=None,
        score=None,
        probability_up=None,
        expected_return=None,
        uncertainty=None,
        target_price=None,
        states=states,
        weight_used=0.0,
    )
