"""信号引擎：因子面板 → 可回测的合成得分、概率与目标价。

三条纪律在这一层落地一次，别处不再重复实现：

1. **只用 t 之前的数据**。滚动 z 分数的均值/标准差、概率的 σ、回归的样本
   全部 ``shift`` 到 t 之前；``tests/unit/quant/test_no_lookahead.py`` 用
   「把 t 之后的数据改成垃圾值，t 时刻的结果必须逐位不变」来守这条。
2. **不确定就说不确定**。可用因子少于 3 个、价格序列缺失、得分算不出来，
   一律返回「预测不可用」并给出原因，绝不退回默认方向或默认数字。
3. **单位跟 definitions 走**。``change_Nd`` 是**原单位**的 N 个交易日变化 ——
   利率是百分点而不是百分比，指数是指数点。

三段式（与 spec 一致）::

    signed_z_i = sign_i × z(x_i)                逐因子方向对齐
    score_h    = Σ w_i(h) × signed_z_i / Σ w_i(h)  按尺度取权重（缺省=基础权重）
    p_up       = Φ(score / σ_expanding)          σ 只用 t 之前的历史得分
    r̂          = α + β · score                   扩展窗口 OLS，样本不足时 β=0
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import erf, sqrt
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


def align_factors(
    factors: dict[str, pd.Series], calendar: pd.DatetimeIndex
) -> dict[str, pd.Series]:
    """把每个因子对齐到价格日历：低频序列（月度储备、周度持仓）按最近值前向填充。

    只向前填充：t 时刻不会用到 t 之后才发布的数。
    """
    aligned: dict[str, pd.Series] = {}
    for key, series in factors.items():
        if series is None or series.empty:
            continue
        aligned[key] = series.reindex(calendar).ffill()
    return aligned


def build_signals(
    factors: dict[str, pd.Series], calendar: pd.DatetimeIndex
) -> pd.DataFrame:
    """每个因子的方向对齐信号 ``signed_z = sign × z(transform(x))``。

    返回值：index = 价格日历，columns = 因子 key，NaN = 当日不可用。
    """
    columns: dict[str, pd.Series] = {}
    for definition in FACTORS:
        series = factors.get(definition.key)
        if series is None or series.empty:
            continue
        transformed = apply_transform(series.reindex(calendar).ffill(), definition.transform)
        z = rolling_z(transformed)
        columns[definition.key] = (z * definition.sign).rename(definition.key)
    if not columns:
        return pd.DataFrame(index=calendar)
    return pd.DataFrame(columns, index=calendar)


def composite_score(signals: pd.DataFrame, *, horizon: Optional[int] = None) -> pd.Series:
    """加权合成得分，权重按当日**可用**因子归一（缺因子不等于该因子为 0）。

    ``horizon`` 决定用哪一组权重：不同时间尺度主导项不同（见 definitions 的
    ``horizon_weights``）；``None`` 表示基础权重。
    """
    if signals.empty:
        return pd.Series(dtype="float64", index=signals.index)
    weights = pd.Series(
        {
            key: factor_by_key[key].weight_for(horizon)
            for key in signals.columns
            if key in factor_by_key
        }
    )
    if weights.empty:
        return pd.Series(np.nan, index=signals.index)
    present = signals.notna().mul(weights, axis=1)
    total_weight = present.sum(axis=1)
    weighted = signals.mul(weights, axis=1).sum(axis=1, skipna=True)
    return weighted / total_weight.where(total_weight > EPS)


# --------------------------------------------------------------------------- #
# 得分 → 概率与期望收益
# --------------------------------------------------------------------------- #
def score_probability(score: pd.Series) -> pd.Series:
    """p_up = Φ(score / σ)，σ 为扩展窗口标准差且只取 t 之前的历史得分。"""
    sigma = score.expanding(min_periods=MIN_SCORES_FOR_SIGMA).std().shift(1)
    ratio = score / sigma.where(sigma > EPS)
    return ratio.map(lambda value: normal_cdf(float(value)) if pd.notna(value) else np.nan)


def expanding_ols(
    x: pd.Series,
    y: pd.Series,
    *,
    min_samples: int = MIN_OLS_SAMPLES,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """扩展窗口一元回归，返回 ``(alpha, beta, residual_sigma)``。

    调用方必须传**已经右移过 h 期**的 x / y（见 ``build_prediction_frame``）：
    这样 t 时刻的样本只包含 ``s + h <= t`` 的已实现样本对，回归不会看到未来。
    样本不足或 x 无波动时 ``alpha = beta = 0`` —— 目标价退化为基准价，
    而不是编一个数出来。
    """
    frame = pd.DataFrame({"x": x, "y": y}).dropna()
    if frame.empty:
        empty = pd.Series(np.nan, index=x.index, dtype="float64")
        return empty, empty, empty

    expanding = frame["x"].expanding()
    n = expanding.count()
    sum_x = expanding.sum()
    sum_y = frame["y"].expanding().sum()
    sum_xx = (frame["x"] ** 2).expanding().sum()
    sum_xy = (frame["x"] * frame["y"]).expanding().sum()
    sum_yy = (frame["y"] ** 2).expanding().sum()

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
    )


def build_prediction_frame(
    score: pd.Series,
    close: pd.Series,
    horizon: int,
) -> pd.DataFrame:
    """把得分序列变成逐日的预测：概率、期望收益、不确定度、目标价。"""
    forward = close.shift(-horizon) / close - 1.0
    alpha, beta, sigma = expanding_ols(score.shift(horizon), forward.shift(horizon))
    expected = alpha + beta * score
    # 回归样本不足时退回「已实现 h 日收益的扩展标准差」，仍然只用过去的数据
    fallback = forward.shift(horizon).expanding(min_periods=MIN_SCORES_FOR_SIGMA).std()

    frame = pd.DataFrame(
        {
            "score": score,
            "probability_up": score_probability(score),
            "expected_return": expected,
            "uncertainty": sigma.fillna(fallback),
            "base_price": close,
        }
    )
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

    @property
    def direction(self) -> Optional[str]:
        if self.status != STATUS_OK or self.score is None:
            return None
        return "up" if self.score > 0 else "down"

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
