"""因子候选闸门：一个信号要进因子集，必须过三道**事先写死**的检验。

为什么需要独立一层：2026-10-02 之前，「某个因子看起来有用」只凭一张 IC 表，
而 IC 是在**重叠样本**上算的 —— 用 iid 标准误时 t 值能虚高到 6–16 倍
（金银比 60 日：HAC +2.30 对 iid +12.70）。同时，同一段历史被反复翻看、
事后挑参数，等于没有样本外。三道闸门把这两件漏洞变成机械检查：

1. **显著性 + 效应量**：逐日 ``z × h 日前瞻收益`` 的**协方差**（两边先去均值）做
   Newey–West 单尾检验（滞后 = h−1），按本轮检验总数做 Bonferroni 校正，
   并要求 ``|t| ≥ MIN_T_TO_PASS`` —— 只靠 p 阈值会被擦边抽样骗过（见常量注释）。
2. **跨尺度同号**：``|t| ≥ 1`` 的相邻尺度里符号必须一致（一个只在单一尺度冒出来的
   「信号」几乎必然是那一格的噪声）。
3. **前向确认**：结论公布日之后新增的观测上方向不变。这一道**不可能当场通过**，
   所以本模块永远不会返回 ``adopted``：它只能把候选推进到
   ``awaiting_forward_window``（等未来数据）或 ``reject``。

刻意不做的事：不代替预注册文档（规则写进 spec 才算数）、不改因子权重、
不因为「p 差一点」就放宽阈值 —— 阈值是被观测之前定下的，动它就等于事后挑参数。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from app.services.quant import engine, stats

# 低于这个样本数就不给判定（与回测同一档，避免「3 天里对了 2 天」）
MIN_SCREEN_SAMPLES = 300
# 跨尺度同号判定里，一个尺度算「有表现」的最低 |t|
MIN_T_FOR_DIRECTION = 1.0
# 效应量下限：光靠 p < α/检验数 会被「擦边抽样」骗过 —— 实测有一条纯噪声序列在
# 60 日拿到 t=+2.77、p=0.0028，恰好低于 Bonferroni 阈值 0.00333 而被放行。
# 因此入选还要求 |t| ≥ 3：这不是更严格的统计洁癖，而是补上「多重比较校正
# 只在边界附近起作用」这个洞。
MIN_T_TO_PASS = 3.0
# 缺省考察的尺度集合，与 HORIZONS 一致（调用方可收窄）
SCREEN_HORIZONS: tuple[int, ...] = (1, 5, 20, 60, 250)
STATUS_REJECT = "reject"
STATUS_AWAIT = "awaiting_forward_window"
STATUS_INSUFFICIENT = "insufficient_data"


@dataclass(frozen=True)
class HorizonResult:
    """一个（候选，尺度）格子的检验结果。"""

    horizon: int
    samples: int
    mean_alignment: Optional[float]
    t_stat: Optional[float]
    p_value: Optional[float]
    t_stat_iid: Optional[float]
    hit_rate: Optional[float]

    @property
    def usable(self) -> bool:
        return self.p_value is not None and self.t_stat is not None

    def to_dict(self) -> dict:
        return {
            "horizon_days": self.horizon,
            "samples": self.samples,
            "mean_alignment": self.mean_alignment,
            "t_stat": self.t_stat,
            "p_value": self.p_value,
            "t_stat_iid": self.t_stat_iid,
            "hit_rate": self.hit_rate,
        }


@dataclass(frozen=True)
class Verdict:
    """候选的闸门结论。``status`` 只可能是拒绝、待前向确认、数据不足三种。"""

    name: str
    status: str
    reason: str
    results: tuple[HorizonResult, ...]
    bonferroni_alpha: float
    passed_significance: tuple[int, ...]
    sign_consistent: bool

    @property
    def adopted(self) -> bool:  # 故意恒为 False：本模块没有采纳权
        return False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "reason": self.reason,
            "bonferroni_alpha": self.bonferroni_alpha,
            "passed_significance": list(self.passed_significance),
            "sign_consistent": self.sign_consistent,
            "adopted": self.adopted,
            "results": [item.to_dict() for item in self.results],
        }


# 第 ③ 道闸门的数据起点：第二轮结论写进 spec 的那一天（2026-10-02）。
# 之前的历史已经被看过、被汇报过，拿它确认自己 = 事后挑参数；只有这一天之后
# 新增的观测才是干净的。改动它等于作废整轮预注册，必须换新的窗口而不是挪日期。
FORWARD_WINDOW_START = date(2026, 10, 2)
# 前向窗口至少要有这么多次独立下注才允许下结论（与裁决层的可判定下限同档）
MIN_FORWARD_BETS = 20
STATUS_FORWARD_PENDING = "forward_window_pending"
STATUS_FORWARD_AGREE = "forward_window_agrees"
STATUS_FORWARD_FLIP = "forward_window_reversed"


def forward_window_readiness(benchmark: pd.Series, horizon: int) -> dict:
    """第 ③ 道闸门现在能不能判？把已经积累多少、还差多少摊开说。"""
    after = benchmark[benchmark.index >= pd.Timestamp(FORWARD_WINDOW_START)]
    bets = int(np.floor(len(after) / horizon)) if len(after) else 0
    # 两个门槛同时才算「够判」：独立下注次数，以及窗口内的原始样本量
    # （滚动 z 需要历史窗口，样本太少时检验根本给不出 t 值，勉强判等于瞎判）
    required_bets = max(MIN_FORWARD_BETS, math.ceil(MIN_SCREEN_SAMPLES / horizon))
    return {
        "window_start": FORWARD_WINDOW_START.isoformat(),
        "observations": int(len(after)),
        "independent_bets": bets,
        "required_bets": required_bets,
        "decidable": bets >= required_bets,
        "shortfall_bets": max(0, required_bets - bets),
        "approx_trading_days_needed": max(0, required_bets * horizon - len(after)),
    }


def confirm_on_forward_window(
    name: str,
    signal: pd.Series,
    benchmark: pd.Series,
    horizon: int,
    *,
    development_t: Optional[float] = None,
) -> dict:
    """在**结论公布日之后**的窗口上重算一次同号性。

    与闸门 ①② 的分工：①② 在开发期判「有没有、方向稳不稳」，这一道只回答
    「那个方向在新数据上还是不是同一个方向」。新窗口样本不足时只报 pending，
    绝不拿开发期数据顶替 —— 那正是这一层要防的事。
    """
    readiness = forward_window_readiness(benchmark, horizon)
    result = {
        "name": name,
        "horizon_days": horizon,
        "development_t": development_t,
        **readiness,
        "forward_t": None,
        "verdict": STATUS_FORWARD_PENDING,
        "reason": (
            f"前向窗口（{FORWARD_WINDOW_START.isoformat()} 起）只有 "
            f"{readiness['independent_bets']}/{readiness['required_bets']} 次独立下注，"
            f"还需约 {readiness['approx_trading_days_needed']} 个交易日才能判"
        ),
    }
    if not readiness["decidable"]:
        return result

    # z 必须在**全样本**上算（滚动窗口需要历史），只用前向窗口里的行参与评估；
    # 反过来先切数据再算 z 会因为历史不足而拿不到 t 值，看起来「永远判不了」。
    window_mask = benchmark.index >= pd.Timestamp(FORWARD_WINDOW_START)
    forward_result = test_one(
        signal, benchmark, horizon, mask=pd.Series(window_mask, index=benchmark.index)
    )
    t_forward = forward_result.t_stat
    result["forward_t"] = t_forward
    if t_forward is None or development_t is None:
        result["reason"] = "前向窗口或开发期缺少可比 t 值，不下结论"
        return result
    same_sign = (t_forward > 0) == (development_t > 0)
    result["verdict"] = STATUS_FORWARD_AGREE if same_sign else STATUS_FORWARD_FLIP
    result["reason"] = (
        f"开发期 t={development_t:+.2f}、前向窗口 t={t_forward:+.2f}："
        + ("方向一致，可进入因子集评审（采纳仍需人工预注册）" if same_sign
           else "方向反转，开发期那个结果不能算信息，判为噪声")
    )
    return result


def _finite(value) -> Optional[float]:
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def test_one(
    signal: pd.Series,
    benchmark: pd.Series,
    horizon: int,
    *,
    mask: Optional[pd.Series] = None,
) -> HorizonResult:
    """一个（信号，尺度）格子：HAC 单尾检验 + 同口径的 iid 值（用来暴露虚高幅度）。

    检验对象是逐日 ``z × h 日前瞻收益`` 的**协方差**（两边各自去均值后相乘）。
    不去均值会把「市场在涨」读成「信号有用」：任何长期略正的 z 乘上正漂移，
    其均值天然大于 0，纯噪声也能拿到显著的单尾 t。
    """
    forward = benchmark.shift(-horizon) / benchmark - 1.0
    z = engine.rolling_z(signal)
    usable = z.notna() & forward.notna()
    if mask is not None:
        usable = usable & mask.reindex(usable.index).fillna(False)
    count = int(usable.sum())
    if count < MIN_SCREEN_SAMPLES:
        return HorizonResult(horizon, count, None, None, None, None, None)

    z_values = z[usable].to_numpy(dtype="float64")
    r_values = forward[usable].to_numpy(dtype="float64")
    # 必须先各自去均值再相乘：否则「z 常年略正」× 「市场常年上涨」的乘积均值
    # 本身就大于 0，纯噪声也会被 t 检验判成有信号（这一版踩过，见 spec 记录）。
    # 检验的对象因此是协方差 E[(z−z̄)(r−r̄)]，不是均值 E[z·r]。
    alignment = (z_values - z_values.mean()) * (r_values - r_values.mean())
    lags = horizon - 1 if horizon > 1 else None
    hac = stats.hac_t_statistic(alignment, lags=lags, alternative="greater")
    iid = stats.hac_t_statistic(alignment, lags=0, alternative="greater")
    direction_match = np.sign(z[usable].to_numpy(dtype="float64")) == np.sign(
        forward[usable].to_numpy(dtype="float64")
    )
    return HorizonResult(
        horizon=horizon,
        samples=count,
        mean_alignment=_finite(float(alignment.mean())),
        t_stat=_finite(hac["statistic"]),
        p_value=_finite(hac["p_value"]),
        t_stat_iid=_finite(iid["statistic"]),
        hit_rate=_finite(float(direction_match.mean())),
    )


def screen_candidate(
    name: str,
    signal: pd.Series,
    benchmark: pd.Series,
    *,
    horizons: Sequence[int] = SCREEN_HORIZONS,
    tests_in_round: Optional[int] = None,
    alpha: float = 0.05,
    mask: Optional[pd.Series] = None,
) -> Verdict:
    """按三道闸门判定一个候选。``tests_in_round`` 决定 Bonferroni 分母。

    ``tests_in_round`` 必须是**本轮全部候选 × 全部尺度**的格子数（不是本候选的），
    否则一批里测 44 个格子还能各自享受 5% 的容错，等于没有校正。缺省时按本候选算，
    那是**下界**，调用方（研究台脚本）应当显式传入整轮的格子数。
    """
    results = tuple(test_one(signal, benchmark, horizon, mask=mask) for horizon in horizons)
    usable = [item for item in results if item.usable]
    total_tests = int(tests_in_round or max(1, len(results)))
    bonferroni = alpha / total_tests

    if not usable:
        return Verdict(
            name=name,
            status=STATUS_INSUFFICIENT,
            reason=f"没有任何尺度凑够 {MIN_SCREEN_SAMPLES} 个可用样本，不予判定",
            results=results,
            bonferroni_alpha=bonferroni,
            passed_significance=(),
            sign_consistent=False,
        )

    passed = tuple(
        item.horizon
        for item in usable
        if item.p_value < bonferroni and item.t_stat >= MIN_T_TO_PASS
    )
    signs = [int(np.sign(item.t_stat)) for item in usable if abs(item.t_stat) >= MIN_T_FOR_DIRECTION]
    sign_consistent = bool(signs) and (len(set(signs)) == 1) and len(signs) >= 2

    if not sign_consistent:
        return Verdict(
            name=name,
            status=STATUS_REJECT,
            reason=(
                f"方向不跨尺度稳定（有表现的尺度 t 符号 {sorted(set(signs)) or '—'}，"
                f"要求 ≥2 个尺度同号）"
            ),
            results=results,
            bonferroni_alpha=bonferroni,
            passed_significance=passed,
            sign_consistent=False,
        )
    if not passed:
        best = min(usable, key=lambda item: item.p_value)
        return Verdict(
            name=name,
            status=STATUS_REJECT,
            reason=(
                f"没有一个尺度同时满足 HAC 单尾 p < {bonferroni:.5f} 与 |t| ≥ {MIN_T_TO_PASS:g}"
                f"（最接近的 {best.horizon} 日 p={best.p_value:.4f}，"
                f"t={best.t_stat:+.2f}；同一格子的 iid t={best.t_stat_iid:+.2f}）"
            ),
            results=results,
            bonferroni_alpha=bonferroni,
            passed_significance=(),
            sign_consistent=True,
        )
    return Verdict(
        name=name,
        status=STATUS_AWAIT,
        reason=(
            f"过闸门 ①②（{('、'.join(str(h) for h in passed))} 日 p<{bonferroni:.5f}，"
            "各尺度同号），但第 ③ 道要等结论公布日之后新增的观测，本轮不得入选"
        ),
        results=results,
        bonferroni_alpha=bonferroni,
        passed_significance=passed,
        sign_consistent=True,
    )


def screen_round(
    candidates: Mapping[str, pd.Series],
    benchmark: pd.Series,
    *,
    horizons: Sequence[int] = SCREEN_HORIZONS,
    alpha: float = 0.05,
    mask: Optional[pd.Series] = None,
) -> list[Verdict]:
    """一轮筛选：Bonferroni 分母按整轮格子数算，返回每个候选的判定。"""
    total = max(1, len(candidates) * len(horizons))
    return [
        screen_candidate(
            name,
            signal,
            benchmark,
            horizons=horizons,
            tests_in_round=total,
            alpha=alpha,
            mask=mask,
        )
        for name, signal in candidates.items()
    ]


def summary_rows(verdicts: Iterable[Verdict]) -> list[dict]:
    """摊平成表格行（研究台与报告用）：一行 = 一个（候选，尺度）。"""
    rows: list[dict] = []
    for verdict in verdicts:
        for item in verdict.results:
            rows.append(
                {
                    "candidate": verdict.name,
                    "status": verdict.status,
                    "horizon_days": item.horizon,
                    "samples": item.samples,
                    "t_stat": item.t_stat,
                    "p_value": item.p_value,
                    "t_stat_iid": item.t_stat_iid,
                    "hit_rate": item.hit_rate,
                    "bonferroni_alpha": verdict.bonferroni_alpha,
                    "reason": verdict.reason,
                }
            )
    return rows


__all__ = [
    "HorizonResult",
    "forward_window_readiness",
    "confirm_on_forward_window",
    "STATUS_FORWARD_PENDING",
    "STATUS_FORWARD_FLIP",
    "STATUS_FORWARD_AGREE",
    "MIN_FORWARD_BETS",
    "FORWARD_WINDOW_START",
    "MIN_SCREEN_SAMPLES",
    "SCREEN_HORIZONS",
    "MIN_T_FOR_DIRECTION",
    "STATUS_AWAIT",
    "STATUS_INSUFFICIENT",
    "STATUS_REJECT",
    "Verdict",
    "screen_candidate",
    "screen_round",
    "summary_rows",
    "test_one",
]
