"""第四轮预注册的状态切换候选与基准对照口径（2026-10-03）。

研究台（``scripts/quant_lab.py``）只照抄执行这里写死的口径；报告、读接口与文档
都从这里取定义 —— 目的是「先写死、再执行」：候选一旦登记，就不再按留出期成绩
增删或调参。登记文本见 ``docs/specs/2026-10-03-2.0.2-整改与自动化.md`` 的
「第四轮预注册」。

三条 Regime 候选（状态切换 = 只在状态成立时持仓，其余时间记中性 0 分）：

- R1 实际利率周期：10 年期实际利率低于其 504 个交易日（2 年）滚动中位数；
- R2 美元周期：美元指数低于其 504 个交易日滚动中位数；
- R3 央行购金时代：中国官方黄金储备的 252 个交易日（约 12 个月）变化为正。

口径细节：滚动窗口的最少观测数为 252（不满 1 年不产生状态，记「不成立」）；
「不成立」记 0 分（中性），不是反向 —— 状态不成立不等于看跌。窗口只用当日
及以前的数据，滚动统计天然无前视。

基准对照（第四轮只进研究台，生产基准本轮不换）：

- 生产基准：GC=F 期货收盘（连续合约）。**含展期**：连续合约的换月价差未做
  调整，这本身就是需要被度量的口径之一。
- 对照候选：GLD 收盘（黄金 ETF，跟踪现货、无展期影响；含 ETF 费用）。
- 未落地（如实记录，不构造替代数字）：XAUUSD 现货（Yahoo 图接口 2026-10-03
  实测 404）；展期调整后的连续序列（需要逐月合约与展期价差，无免费合规来源）。
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from app.services.quant import engine
from app.services.quant.definitions import BENCHMARK_KEY

# 滚动中位数的窗口与最少观测（写死，不按结果调整）
REGIME_WINDOW_DAYS = 504
REGIME_MIN_OBSERVATIONS = 252
# 央行储备的变化窗口：按交易日近似 12 个月（储备是月频，对齐到价格日历后前向填充）
CB_CHANGE_DAYS = 252


@dataclass(frozen=True)
class RegimeCandidate:
    key: str
    name: str
    series_key: str
    description: str
    # below_rolling_median / change_positive
    rule: str


REGIME_CANDIDATES: tuple[RegimeCandidate, ...] = (
    RegimeCandidate(
        key="R1",
        name="实际利率周期",
        series_key="real_yield_10y",
        description="仅在 10 年期实际利率低于其 504 个交易日滚动中位数时持仓，其余时间中性",
        rule="below_rolling_median",
    ),
    RegimeCandidate(
        key="R2",
        name="美元周期",
        series_key="dollar_index",
        description="仅在美元指数低于其 504 个交易日滚动中位数时持仓，其余时间中性",
        rule="below_rolling_median",
    ),
    RegimeCandidate(
        key="R3",
        name="央行购金时代",
        series_key="central_bank",
        description="仅在中国官方黄金储备的 252 个交易日（约 12 个月）变化为正时持仓，其余时间中性",
        rule="change_positive",
    ),
)

regime_by_key = {item.key: item for item in REGIME_CANDIDATES}

assert len(regime_by_key) == len(REGIME_CANDIDATES), "Regime 候选 key 必须唯一"


def regime_mask(key: str, factors: dict[str, pd.Series], calendar: pd.DatetimeIndex) -> pd.Series:
    """状态成立与否（布尔序列，索引 = 价格日历）；缺序列或观测不足时为 False。

    只用当日及以前的数据：滚动中位数 / 前值差都是后视窗口，不引入前视。
    """
    candidate = regime_by_key[key]
    series = factors.get(candidate.series_key)
    if series is None or series.empty:
        return pd.Series(False, index=calendar)
    aligned = engine.align_series(series, calendar, max_age_days=None, publication_lag_days=0)
    if candidate.rule == "below_rolling_median":
        reference = aligned.rolling(REGIME_WINDOW_DAYS, min_periods=REGIME_MIN_OBSERVATIONS).median()
        mask = aligned < reference
    elif candidate.rule == "change_positive":
        mask = aligned > aligned.shift(CB_CHANGE_DAYS)
    else:  # pragma: no cover - 定义表写死，走到这里说明注册表被改坏了
        raise ValueError(f"未知的 regime 规则：{candidate.rule}")
    return mask.fillna(False).astype(bool)


def apply_regime(score: pd.Series, mask: pd.Series) -> pd.Series:
    """状态不成立 → 0 分（中性）；成立 → 原得分。

    中性而不是反向：状态变量回答的是「这套信号此刻适不适用」，
    而不是「金价此刻会跌」。
    """
    return score.where(mask.reindex(score.index).fillna(False), 0.0)


@dataclass(frozen=True)
class BenchmarkChoice:
    key: str
    name: str
    note: str
    available: bool
    reason: str = ""


BENCHMARK_CHOICES: tuple[BenchmarkChoice, ...] = (
    BenchmarkChoice(
        key=BENCHMARK_KEY,
        name="GC=F 期货收盘（连续合约）",
        note="含展期：连续合约的换月价差未做调整；本轮生产基准不换",
        available=True,
    ),
    BenchmarkChoice(
        key="gld_close",
        name="GLD 收盘（黄金 ETF）",
        note="跟踪现货、无展期影响；含 ETF 费用与分红除息，作为敏感性对照",
        available=True,
    ),
    BenchmarkChoice(
        key="xauusd_spot",
        name="XAUUSD 现货（Yahoo）",
        note="未落地：Yahoo 图接口 2026-10-03 实测 404，无免费可核实序列",
        available=False,
        reason="Yahoo XAUUSD=X 图接口实测 404（2026-10-03）",
    ),
    BenchmarkChoice(
        key="roll_adjusted",
        name="展期调整后的连续序列",
        note="未落地：需要逐月合约与展期价差数据，无免费合规来源，本轮不构造",
        available=False,
        reason="无免费合规的逐月合约与展期价差来源",
    ),
)

benchmark_by_key = {item.key: item for item in BENCHMARK_CHOICES}

assert len(benchmark_by_key) == len(BENCHMARK_CHOICES), "基准候选 key 必须唯一"

PRODUCTION_BENCHMARK = benchmark_by_key[BENCHMARK_KEY]


__all__ = [
    "BENCHMARK_CHOICES",
    "CB_CHANGE_DAYS",
    "PRODUCTION_BENCHMARK",
    "REGIME_CANDIDATES",
    "REGIME_MIN_OBSERVATIONS",
    "REGIME_WINDOW_DAYS",
    "RegimeCandidate",
    "BenchmarkChoice",
    "apply_regime",
    "benchmark_by_key",
    "regime_by_key",
    "regime_mask",
]
