"""情景：把每个尺度的预测分布变成 Base / Bull / Bear 与触发、失效条件。

口径（与方法论一致，不另算一套数字）：

  - 未来 h 个交易日收益率 ~ N(μ, σ²)，μ / σ 直接取 ``engine`` 快照的
    ``expected_return`` / ``uncertainty``；
  - Base = [q25, q75]（50%），Bull = q75 以上（25%），Bear = q25 以下（25%），
    价格 = 基准价 × (1 + 分位收益)，无上/下界如实用「以上 / 以下」表达；
  - 触发 / 失效条件由该尺度**权重最大的可用因子**与 200 日均线生成，
    每个数字都能在因子表与行情序列里核对；
  - 分布、基准价或均线之外的数据不足时，返回「不可用 + 原因」，不编区间。
"""
from __future__ import annotations

from dataclasses import dataclass
from statistics import NormalDist
from typing import Optional

import pandas as pd

from app.services.quant import engine

STATUS_OK = engine.STATUS_OK
STATUS_UNAVAILABLE = engine.PREDICTION_UNAVAILABLE

NORMAL = NormalDist()
LOWER_QUANTILE = 0.25
UPPER_QUANTILE = 0.75
MA_WINDOW = 200
# 200 日均线至少要有这么多交易日才给数字，否则条件里如实写「历史样本不足」
MIN_MA_SAMPLES = 120
# 基准情景的触发阈值：方向对齐 z 在 ±1 之间视作没有决定性驱动
BASE_Z_BAND = 1.0


@dataclass(frozen=True)
class Scenario:
    key: str
    label: str
    probability: float
    price_low: Optional[float]
    price_high: Optional[float]
    trigger: str
    invalidation: str

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "probability": self.probability,
            "price_low": self.price_low,
            "price_high": self.price_high,
            "trigger": self.trigger,
            "invalidation": self.invalidation,
        }


@dataclass(frozen=True)
class ScenarioSet:
    status: str
    reason: Optional[str]
    range_low: Optional[float]
    range_high: Optional[float]
    scenarios: tuple[Scenario, ...]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "range_low": self.range_low,
            "range_high": self.range_high,
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
        }


def _unavailable(reason: str) -> ScenarioSet:
    return ScenarioSet(STATUS_UNAVAILABLE, reason, None, None, ())


def price_at_quantile(base_price: float, mu: float, sigma: float, quantile: float) -> float:
    """分布 N(μ, σ²) 的分位数 → 价格；价格与收益率同一量纲（简单收益）。"""
    return base_price * (1.0 + mu + sigma * NORMAL.inv_cdf(quantile))


def _ma200(close: Optional[pd.Series], as_of) -> Optional[float]:
    if close is None or close.empty:
        return None
    window = close.rolling(MA_WINDOW, min_periods=MIN_MA_SAMPLES).mean()
    position = int(close.index.searchsorted(pd.Timestamp(as_of), side="right")) - 1
    if position < 0:
        return None
    value = window.iloc[position]
    return float(value) if pd.notna(value) else None


def _dominant_factor(snapshot: engine.SignalSnapshot) -> Optional[engine.FactorState]:
    available = [state for state in snapshot.states if state.available]
    if not available:
        return None
    return max(available, key=lambda state: state.weight)


def _ma_phrase(ma: Optional[float], *, up: bool) -> str:
    if ma is None:
        return "200 日均线暂不可用（历史样本不足）"
    verb = "站上" if up else "跌破"
    return f"金价{verb} 200 日均线（{ma:,.0f}）"


def _factor_phrase(state: engine.FactorState) -> str:
    return f"{state.name}方向对齐 z（当前 {state.signed_z:+.2f}）"


def _bull_trigger(state: engine.FactorState, ma: Optional[float]) -> str:
    verb = "维持为正" if state.signed_z > 0 else "转正"
    return f"{_factor_phrase(state)} {verb}，且 {_ma_phrase(ma, up=True)}"


def _bear_trigger(state: engine.FactorState, ma: Optional[float]) -> str:
    verb = "维持为负" if state.signed_z < 0 else "转负"
    return f"{_factor_phrase(state)} {verb}，或 {_ma_phrase(ma, up=False)}"


def _base_trigger(
    state: engine.FactorState, ma: Optional[float], low: float, high: float
) -> str:
    ma_part = (
        "（200 日均线暂不可用，历史样本不足）"
        if ma is None
        else f"（200 日均线 {ma:,.0f}）"
    )
    return (
        f"{_factor_phrase(state)} 停留在 ±{BASE_Z_BAND:.0f} 之间，"
        f"且金价在 [{low:,.0f}, {high:,.0f}] 内震荡{ma_part}"
    )


def _base_invalidation(
    state: engine.FactorState, ma: Optional[float], low: float, high: float
) -> str:
    ma_part = "；200 日均线暂不可用（历史样本不足）" if ma is None else f"，或金价越过 200 日均线（{ma:,.0f}）"
    return (
        f"{_factor_phrase(state)} 越过 ±{BASE_Z_BAND:.0f}"
        f"，或金价收盘走出 [{low:,.0f}, {high:,.0f}]"
        f"{ma_part}"
    )


def build_scenarios(
    snapshot: engine.SignalSnapshot,
    close: Optional[pd.Series],
) -> ScenarioSet:
    """由快照的预测分布生成三情景；不可用时返回原因。"""
    if snapshot.status != STATUS_OK:
        return _unavailable(snapshot.reason or "预测不可用，无法生成情景")

    mu = snapshot.expected_return
    sigma = snapshot.uncertainty
    base_price = snapshot.base_price
    if mu is None or sigma is None or base_price is None:
        return _unavailable("预测分布缺少期望收益或不确定度，无法生成情景区间")
    if sigma <= 0:
        return _unavailable("预测分布的不确定度为 0，无法给出情景区间")
    if base_price <= 0:
        return _unavailable("基准价格非正，无法生成情景区间")

    dominant = _dominant_factor(snapshot)
    if dominant is None:
        return _unavailable("没有可用因子，无法生成触发条件")

    q25 = price_at_quantile(base_price, mu, sigma, LOWER_QUANTILE)
    q75 = price_at_quantile(base_price, mu, sigma, UPPER_QUANTILE)
    if q25 <= 0:
        return _unavailable("分布下沿价格非正，无法生成情景区间")

    ma = _ma200(close, snapshot.as_of)
    bull_trigger = _bull_trigger(dominant, ma)
    bear_trigger = _bear_trigger(dominant, ma)

    scenarios = (
        Scenario(
            key="base",
            label="基准情景",
            probability=0.50,
            price_low=q25,
            price_high=q75,
            trigger=_base_trigger(dominant, ma, q25, q75),
            invalidation=_base_invalidation(dominant, ma, q25, q75),
        ),
        Scenario(
            key="bull",
            label="看涨情景",
            probability=0.25,
            price_low=q75,
            price_high=None,
            trigger=bull_trigger,
            invalidation=bear_trigger,
        ),
        Scenario(
            key="bear",
            label="看跌情景",
            probability=0.25,
            price_low=None,
            price_high=q25,
            trigger=bear_trigger,
            invalidation=bull_trigger,
        ),
    )
    return ScenarioSet(STATUS_OK, None, float(q25), float(q75), scenarios)


__all__ = [
    "BASE_Z_BAND",
    "MA_WINDOW",
    "Scenario",
    "ScenarioSet",
    "build_scenarios",
    "price_at_quantile",
]
