"""监测仪表盘：方法论第七节的「周更表」。

每行一个指标：频率、来源、当前值、信号（看涨 / 看跌 / 中性 / 信息）、数据截至时间。
信号规则是确定性阈值，集中在 ``_rule`` 一处；汇率、未平仓量是信息型指标
（``signal=None``），不硬套多空。取不到数据或历史不足的行返回「不可用 + 原因」，
不编数字 —— 上海金溢价就是如实标不可用的例子。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from statistics import fmean, pstdev
from typing import Optional

import pandas as pd

from app.services.quant import storage
from app.services.quant.definitions import BENCHMARK_KEY

SIGNAL_BULL = "bull"
SIGNAL_BEAR = "bear"
SIGNAL_NEUTRAL = "neutral"
# 信息型指标：不参与多空判断（signal 保持 null）
INFO_KEYS = {"usdcny", "cny_gold", "cftc_oi"}

SIGNAL_LABELS = {SIGNAL_BULL: "看涨", SIGNAL_BEAR: "看跌", SIGNAL_NEUTRAL: "中性"}

MA_WINDOW = 200
MIN_MA_SAMPLES = 120
# CFTC 净头寸拥挤度：约 3 年周度报告
CROWDING_WINDOW = 156
CROWDING_MIN_SAMPLES = 52
CROWDING_Z = 1.5
# TGA 的 500 亿美元、RRP 的 50 亿美元（各自单位见行定义）
TGA_FLOW_THRESHOLD = 50_000.0  # 百万美元
RRP_FLOW_THRESHOLD = 50.0  # 亿美元


@dataclass(frozen=True)
class RowSpec:
    key: str
    name: str
    frequency: str
    source: str
    unit: str
    note: str


ROW_SPECS: tuple[RowSpec, ...] = (
    RowSpec(
        "real_yield_10y", "美债 10 年期实际利率（TIPS）", "日",
        "美国财政部（TIPS 实际收益率曲线）", "%",
        "最近 5 个观测变化 ≤ −0.10pp 看涨、≥ +0.10pp 看跌",
    ),
    RowSpec(
        "inflation_expectation", "盈亏平衡通胀（10Y 名义 − 实际）", "日",
        "美国财政部收益率曲线", "%",
        "5 个观测变化 ≥ +0.10pp 看涨（通胀对冲）、≤ −0.10pp 看跌",
    ),
    RowSpec(
        "dollar_index", "美元指数（DXY）", "日", "Yahoo Finance（DX-Y.NYB）", "点",
        "5 个观测涨跌 ≥ +1% 看跌、≤ −1% 看涨",
    ),
    RowSpec(
        "policy_expectation", "市场隐含政策预期（2Y − EFFR）", "日",
        "美国财政部 − 纽约联储", "%",
        "5 个观测变化 ≥ +0.10pp 看跌（预期更紧）、≤ −0.10pp 看涨",
    ),
    RowSpec(
        "central_bank", "央行黄金储备", "月", "新浪财经（官方储备数据）", "万盎司",
        "环比增加看涨、减少看跌",
    ),
    RowSpec(
        "etf_shares", "黄金 ETF 份额（GLD）", "日（自采集起）", "Yahoo Finance", "份",
        "最近两次观测增加看涨（申购）、减少看跌",
    ),
    RowSpec(
        "cftc_positioning", "CFTC 净多头（拥挤度）", "周", "CFTC 持仓报告", "张",
        "净头寸 z ≥ +1.5 看跌（多头拥挤）、≤ −1.5 看涨（空头拥挤）",
    ),
    RowSpec(
        "shanghai_premium", "上海金溢价", "日", "上海黄金交易所 AU9999", "元/克",
        "公开无密钥接口实测不可用：如实标不可用，不编数",
    ),
    RowSpec(
        "vix", "VIX 恐慌指数", "日", "Yahoo Finance（^VIX）", "点",
        "≥ 25 看涨（避险需求）、≤ 15 看跌（风险偏好）",
    ),
    RowSpec(
        "credit_appetite", "信用偏好（HYG/IEF 20 日变化）", "日", "Yahoo Finance", "%",
        "≥ +2 看跌（避险降温）、≤ −2 看涨（信用压力）",
    ),
    RowSpec(
        "ma200", "金价 vs 200 日均线", "日", "自有价格序列", "美元",
        "偏离 ≥ +0.5% 看涨、≤ −0.5% 看跌",
    ),
    RowSpec(
        "usdcny", "美元兑人民币（USDCNY）", "日", "Yahoo Finance（CNY=X）", "元",
        "信息行：只作人民币金价换算参考，不参与多空",
    ),
    RowSpec(
        "cny_gold", "人民币金价参考", "日", "黄金收盘 × USDCNY ÷ 31.1035", "元/克",
        "信息行：国内投资者视角的价格锚",
    ),
    RowSpec(
        "tga", "美国财政部 TGA 余额", "日", "美国财政部 Fiscal Data（每日报表）", "百万美元",
        "20 个观测增加 ≥ 500 亿看跌（抽走流动性）、减少 ≥ 500 亿看涨",
    ),
    RowSpec(
        "rrp", "纽约联储逆回购（RRP）", "日", "纽约联储公开市场操作结果", "亿美元",
        "20 个观测增加 ≥ 50 亿看跌、减少 ≥ 50 亿看涨（释放流动性）",
    ),
    RowSpec(
        "cftc_oi", "COMEX 黄金未平仓合约", "周", "CFTC 持仓报告", "张",
        "信息行：衡量市场参与度，不直接给方向",
    ),
)


@dataclass(frozen=True)
class MonitorRow:
    key: str
    name: str
    frequency: str
    source: str
    value: Optional[float]
    unit: str
    change: Optional[float]
    obs_date: Optional[date]
    signal: Optional[str]
    signal_label: str
    note: str
    status: str
    reason: Optional[str]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "frequency": self.frequency,
            "source": self.source,
            "value": self.value,
            "unit": self.unit,
            "change": self.change,
            "obs_date": self.obs_date.isoformat() if self.obs_date else None,
            "signal": self.signal,
            "signal_label": self.signal_label,
            "note": self.note,
            "status": self.status,
            "reason": self.reason,
        }


def _latest(series: Optional[pd.Series]) -> Optional[tuple[date, float]]:
    if series is None or series.empty:
        return None
    return series.index[-1].date(), float(series.iloc[-1])


def _delta(series: pd.Series, periods: int) -> Optional[float]:
    if series is None or len(series) <= periods:
        return None
    return float(series.iloc[-1] - series.iloc[-1 - periods])


def _pct_delta(series: pd.Series, periods: int) -> Optional[float]:
    base = _delta(series, periods)
    if base is None:
        return None
    previous = float(series.iloc[-1 - periods])
    if previous == 0:
        return None
    return base / previous * 100.0


def _threshold(change: Optional[float], threshold: float, *, up_is_bull: bool) -> Optional[str]:
    if change is None:
        return None
    if threshold <= 0:
        if change == 0:
            return SIGNAL_NEUTRAL
    elif abs(change) < threshold:
        return SIGNAL_NEUTRAL
    rising = change > 0
    return SIGNAL_BULL if rising == up_is_bull else SIGNAL_BEAR


def _zscore(series: pd.Series, window: int, min_samples: int) -> Optional[float]:
    """当前值相对之前 window 个观测的 z 分数（不含当前值本身）。"""
    if series is None or len(series) < min_samples + 1:
        return None
    history = [float(value) for value in series.iloc[-(window + 1) : -1]]
    spread = pstdev(history)
    if spread <= 0:
        return None
    return (float(series.iloc[-1]) - fmean(history)) / spread


def _ma200(close: Optional[pd.Series]) -> Optional[float]:
    if close is None or close.empty:
        return None
    window = close.rolling(MA_WINDOW, min_periods=MIN_MA_SAMPLES).mean()
    value = window.iloc[-1]
    return float(value) if pd.notna(value) else None


def _rule(key: str, series: pd.Series) -> tuple[Optional[str], Optional[float]]:
    """一行一条确定性规则；返回 (signal, change)。"""
    if key == "real_yield_10y":
        change = _delta(series, 5)
        return _threshold(change, 0.10, up_is_bull=False), change
    if key == "inflation_expectation":
        change = _delta(series, 5)
        return _threshold(change, 0.10, up_is_bull=True), change
    if key == "dollar_index":
        change = _pct_delta(series, 5)
        return _threshold(change, 1.0, up_is_bull=False), change
    if key == "policy_expectation":
        change = _delta(series, 5)
        return _threshold(change, 0.10, up_is_bull=False), change
    if key == "central_bank":
        change = _delta(series, 1)
        return _threshold(change, 0.0, up_is_bull=True), change
    if key == "etf_shares":
        change = _delta(series, 1)
        return _threshold(change, 0.0, up_is_bull=True), change
    if key == "cftc_positioning":
        z = _zscore(series, CROWDING_WINDOW, CROWDING_MIN_SAMPLES)
        if z is None:
            return None, _delta(series, 1)
        if z >= CROWDING_Z:
            return SIGNAL_BEAR, _delta(series, 1)
        if z <= -CROWDING_Z:
            return SIGNAL_BULL, _delta(series, 1)
        return SIGNAL_NEUTRAL, _delta(series, 1)
    if key == "vix":
        value = float(series.iloc[-1])
        if value >= 25:
            return SIGNAL_BULL, _delta(series, 5)
        if value <= 15:
            return SIGNAL_BEAR, _delta(series, 5)
        return SIGNAL_NEUTRAL, _delta(series, 5)
    if key == "credit_appetite":
        value = float(series.iloc[-1])
        if value >= 2:
            return SIGNAL_BEAR, _delta(series, 5)
        if value <= -2:
            return SIGNAL_BULL, _delta(series, 5)
        return SIGNAL_NEUTRAL, _delta(series, 5)
    if key == "tga":
        change = _delta(series, 20)
        return _threshold(change, TGA_FLOW_THRESHOLD, up_is_bull=False), change
    if key == "rrp":
        change = _delta(series, 20)
        return _threshold(change, RRP_FLOW_THRESHOLD, up_is_bull=False), change
    if key == "usdcny":
        return None, _delta(series, 5)
    if key == "cny_gold":
        return None, _pct_delta(series, 5)
    if key == "cftc_oi":
        return None, _delta(series, 1)
    raise AssertionError(f"没有为 {key} 定义信号规则")


def _unavailable(spec: RowSpec, reason: str) -> MonitorRow:
    return MonitorRow(
        key=spec.key,
        name=spec.name,
        frequency=spec.frequency,
        source=spec.source,
        value=None,
        unit=spec.unit,
        change=None,
        obs_date=None,
        signal=None,
        signal_label="不可用",
        note=spec.note,
        status="unavailable",
        reason=reason,
    )


def _build_row(
    spec: RowSpec,
    series: Optional[pd.Series],
    close: Optional[pd.Series],
) -> MonitorRow:
    if spec.key == "shanghai_premium":
        return _unavailable(
            spec,
            "公开无密钥接口（上海黄金交易所 AU9999）实测返回空，不编数",
        )

    if spec.key == "ma200":
        latest = _latest(close)
        ma = _ma200(close)
        if latest is None:
            return _unavailable(spec, "缺少黄金价格序列（行情源未同步）")
        if ma is None:
            return _unavailable(spec, f"200 日均线历史样本不足（至少需要 {MIN_MA_SAMPLES} 个交易日）")
        deviation = (latest[1] / ma - 1.0) * 100.0
        if deviation >= 0.5:
            signal = SIGNAL_BULL
        elif deviation <= -0.5:
            signal = SIGNAL_BEAR
        else:
            signal = SIGNAL_NEUTRAL
        return MonitorRow(
            key=spec.key,
            name=spec.name,
            frequency=spec.frequency,
            source=spec.source,
            value=ma,
            unit=spec.unit,
            change=deviation,
            obs_date=latest[0],
            signal=signal,
            signal_label=SIGNAL_LABELS[signal],
            note=spec.note,
            status="ok",
            reason=None,
        )

    latest = _latest(series)
    if latest is None:
        return _unavailable(spec, f"最近一次同步未取到该序列（来源：{spec.source}）")

    signal, change = _rule(spec.key, series)
    if signal is None and spec.key not in INFO_KEYS:
        return MonitorRow(
            key=spec.key,
            name=spec.name,
            frequency=spec.frequency,
            source=spec.source,
            value=latest[1],
            unit=spec.unit,
            change=change,
            obs_date=latest[0],
            signal=None,
            signal_label="样本不足",
            note=spec.note + "；历史样本不足，暂不给信号",
            status="ok",
            reason=None,
        )
    return MonitorRow(
        key=spec.key,
        name=spec.name,
        frequency=spec.frequency,
        source=spec.source,
        value=latest[1],
        unit=spec.unit,
        change=change,
        obs_date=latest[0],
        signal=signal,
        signal_label=SIGNAL_LABELS.get(signal, "信息"),
        note=spec.note,
        status="ok",
        reason=None,
    )


def build_monitor(db) -> dict:
    """读出库里所有序列，按 ROW_SPECS 生成仪表盘。"""
    series = storage.load_all(db)
    close = series.get(BENCHMARK_KEY)
    rows = [_build_row(spec, series.get(spec.key), close) for spec in ROW_SPECS]
    as_of = max((row.obs_date for row in rows if row.obs_date), default=None)
    return {"as_of": as_of, "rows": [row.to_dict() for row in rows]}


__all__ = [
    "MonitorRow",
    "ROW_SPECS",
    "RowSpec",
    "SIGNAL_BEAR",
    "SIGNAL_BULL",
    "SIGNAL_NEUTRAL",
    "build_monitor",
]
