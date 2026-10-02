"""因子候选闸门的三条判据与两个已知陷阱。

两个陷阱都是本轮实测踩出来的，测试的意义就是让它们**不可能再被悄悄踩第二次**：

1. 不去均值 → 「纯趋势 + 上涨的市场」会被判成显著信号（均值里全是漂移，不是协方差）；
2. 只靠 Bonferroni p → 擦边抽样能放行噪声（实测一条 iid 噪声在 60 日拿到 t=+2.77、
   p=0.0028 < 阈值 0.00333），所以还必须有 |t| ≥ 3 的效应量下限。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import screen

CALENDAR = pd.date_range("2000-01-03", periods=6000, freq="B")


def _benchmark() -> pd.Series:
    rng = np.random.default_rng(3)
    returns = pd.Series(rng.normal(0.0002, 0.008, len(CALENDAR)), index=CALENDAR)
    return pd.Series(2000.0 * np.exp(returns.cumsum().to_numpy()), index=CALENDAR)


def _pure_trend() -> pd.Series:
    """没有任何信息、但常年略正的序列 —— 专治「把上涨读成信号」。"""
    return pd.Series(np.linspace(0.0, 3.0, len(CALENDAR)), index=CALENDAR)


def _noise() -> pd.Series:
    rng = np.random.default_rng(3)
    rng.normal(0.0002, 0.008, len(CALENDAR))  # 与基准同种子：先抽掉基准用到的那一段
    return pd.Series(rng.normal(0.0, 1.0, len(CALENDAR)), index=CALENDAR)


def _true_lead(benchmark: pd.Series) -> pd.Series:
    """作弊用的完美前瞻信号，只用来验证闸门不会把真信号也拒掉。"""
    return pd.Series((benchmark.shift(-20) / benchmark - 1.0) * 10.0, index=CALENDAR).fillna(0.0)


@pytest.mark.unit
def test_a_pure_trend_is_not_a_signal():
    benchmark = _benchmark()

    verdict = screen.screen_candidate("纯趋势", _pure_trend(), benchmark, tests_in_round=15)

    assert verdict.status == screen.STATUS_REJECT
    assert verdict.passed_significance == ()
    assert "Bonferroni" in verdict.reason or "|t|" in verdict.reason
    # 变异验证：把 test_one 里的去均值删掉，本断言必红（趋势会靠市场漂移拿到显著性）
    assert max(item.t_stat for item in verdict.results if item.t_stat is not None) < 3.0


@pytest.mark.unit
def test_a_near_threshold_noise_result_does_not_pass():
    """t=2.77 / p=0.0028 这种「刚好擦过 Bonferroni」的结果必须被效应量下限拦住。"""
    benchmark = _benchmark()

    verdict = screen.screen_candidate("噪声", _noise(), benchmark, tests_in_round=15)

    assert verdict.status == screen.STATUS_REJECT
    assert verdict.passed_significance == ()
    best = max(
        (item for item in verdict.results if item.usable), key=lambda item: item.t_stat, default=None
    )
    assert best is not None and best.t_stat < screen.MIN_T_TO_PASS, (
        f"噪声拿到 t={None if best is None else best.t_stat:.2f}，效应量下限失效"
    )


@pytest.mark.unit
def test_a_real_lead_passes_gates_but_still_cannot_be_adopted():
    benchmark = _benchmark()

    verdict = screen.screen_candidate("真前瞻", _true_lead(benchmark), benchmark, tests_in_round=15)

    assert verdict.status == screen.STATUS_AWAIT
    assert len(verdict.passed_significance) >= 2
    assert verdict.sign_consistent is True
    # 本模块没有采纳权：第三条闸门要等未来数据，所以 adopted 恒为 False
    assert verdict.adopted is False
    assert "前向" in verdict.reason or "本轮不得入选" in verdict.reason


@pytest.mark.unit
def test_bonferroni_denominator_is_the_whole_round_not_one_candidate():
    benchmark = _benchmark()
    lead = _true_lead(benchmark)
    candidates = {f"c{i}": lead for i in range(6)}

    single = screen.screen_candidate("c0", lead, benchmark)
    round_verdicts = screen.screen_round(candidates, benchmark, horizons=(1, 5, 20, 60, 250))

    # 缺省分母只算自己的格子数（5）；整轮 6×5=30 → 阈值必须更严
    assert single.bonferroni_alpha == pytest.approx(0.05 / 5)
    assert all(
        verdict.bonferroni_alpha == pytest.approx(0.05 / 30) for verdict in round_verdicts
    )
    rows = screen.summary_rows(round_verdicts)
    assert len(rows) == 30
    assert {"candidate", "status", "t_stat_iid", "hit_rate", "bonferroni_alpha"} <= set(rows[0])


@pytest.mark.unit
def test_too_little_history_says_so_instead_of_guessing():
    benchmark = _benchmark().iloc[:200]
    short = _noise().iloc[:200]

    verdict = screen.screen_candidate("短样本", short, benchmark)

    assert verdict.status == screen.STATUS_INSUFFICIENT
    assert "样本" in verdict.reason
    assert verdict.passed_significance == ()
