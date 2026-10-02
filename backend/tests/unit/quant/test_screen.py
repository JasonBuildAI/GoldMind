"""因子候选闸门的三条判据与两个已知陷阱。

两个陷阱都是本轮实测踩出来的，测试的意义就是让它们**不可能再被悄悄踩第二次**：

1. 不去均值 → 「纯趋势 + 上涨的市场」会被判成显著信号（均值里全是漂移，不是协方差）；
2. 只靠 Bonferroni p → 擦边抽样能放行噪声（实测一条 iid 噪声在 60 日拿到 t=+2.77、
   p=0.0028 < 阈值 0.00333），所以还必须有 |t| ≥ 3 的效应量下限。
"""
from __future__ import annotations

import math

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

@pytest.mark.unit
def test_forward_window_is_reported_as_pending_with_today_s_data():
    """第 ③ 道闸门现在必然还没到：把「还要等多久」摊开，而不是假装能判。

    变异验证：把 reason 里的 ``approx_trading_days_needed`` 换成写死的 0（或整段删掉），
    下面按数值断言的那条必红；把 ``decidable`` 的判断反过来，前两条断言必红。
    """
    benchmark = _benchmark()  # 止于 2023 年附近，全部早于前向窗口起点

    readiness = screen.forward_window_readiness(benchmark, 20)

    assert readiness["decidable"] is False
    assert readiness["independent_bets"] == 0
    assert readiness["window_start"] == screen.FORWARD_WINDOW_START.isoformat()
    # 门槛要同时覆盖「独立下注次数」和「滚动 z 需要的原始样本量」，取两者更大者
    assert readiness["required_bets"] == max(
        screen.MIN_FORWARD_BETS, math.ceil(screen.MIN_SCREEN_SAMPLES / 20)
    )
    assert readiness["shortfall_bets"] == readiness["required_bets"]

    verdict = screen.confirm_on_forward_window("噪声", _noise(), benchmark, 20, development_t=2.5)
    assert verdict["verdict"] == screen.STATUS_FORWARD_PENDING
    assert verdict["forward_t"] is None
    assert f"还需约 {readiness['approx_trading_days_needed']} 个交易日" in verdict["reason"], (
        f"pending 文案没有给出真实的等待天数：{verdict['reason']}"
    )


def _split_market() -> tuple[pd.Series, pd.Series, pd.Series]:
    """造一段跨过前向窗口起点的市场，返回 (收盘价, 翻转信号, 稳定信号)。

    两个信号都是「作弊序列」（直接由未来收益构造），只用来检验代码路径：一个在窗口
    起点处方向翻转，一个方向不变。注意不能用「动量 + 两段不同的漂移」来造反转：
    两边先去均值之后，漂移在协方差里根本不留痕迹（随机行走的滞后收益与前向收益
    不相关），那种构造看似有反转、其实两边都是噪声。
    """
    start = pd.Timestamp(screen.FORWARD_WINDOW_START)
    calendar = pd.date_range("2020-01-02", start + pd.tseries.offsets.BDay(700), freq="B")
    rng = np.random.default_rng(9)
    close = pd.Series(
        2000.0 * np.exp(np.cumsum(rng.normal(0.0003, 0.008, len(calendar)))), index=calendar
    )
    ahead = (close.shift(-5) / close - 1.0).fillna(0.0)
    noise = rng.normal(0.0, 0.001, len(calendar))
    regime = np.where(calendar < start, 1.0, -1.0)
    return close, pd.Series(ahead.to_numpy() * regime + noise, index=calendar), pd.Series(
        ahead.to_numpy() + noise, index=calendar
    )


@pytest.mark.unit
def test_forward_window_confirmation_uses_only_post_announcement_data():
    """前向确认只许看结论公布日之后的数据：开发期同号、新窗口反向必须判成反转。

    变异验证：把 `confirm_on_forward_window` 里的窗口切片删掉（改用全样本），
    全样本 t 与开发期同号 → 判成 agrees，`pending["verdict"]` 那条断言必红，
    因为那样它把开发期数据当成了新证据。
    """
    close, flip_signal, _ = _split_market()

    whole = screen.test_one(flip_signal, close, 5)
    pending = screen.confirm_on_forward_window(
        "反转候选", flip_signal, close, 5, development_t=whole.t_stat
    )

    readiness = screen.forward_window_readiness(close, 5)
    assert readiness["decidable"] is True, readiness
    assert readiness["required_bets"] >= screen.MIN_FORWARD_BETS
    # 先确认全样本确实给出了正向证据，否则后面的「反转」断言是空的
    assert whole.t_stat is not None and whole.t_stat > 0, whole
    assert pending["verdict"] == screen.STATUS_FORWARD_FLIP
    assert pending["forward_t"] is not None and pending["forward_t"] < 0
    assert "噪声" in pending["reason"] or "反转" in pending["reason"]


@pytest.mark.unit
def test_forward_window_confirmation_accepts_a_direction_that_hold_up():
    """方向在新数据上站得住，就必须报 agrees —— 只会说 pending 的闸门等于没有闸门。

    变异验证：把 `verdict` 那行两个状态常量互换，本测试与上一条同时红。
    """
    close, _, stable_signal = _split_market()

    whole = screen.test_one(stable_signal, close, 5)
    confirmed = screen.confirm_on_forward_window(
        "稳定候选", stable_signal, close, 5, development_t=whole.t_stat
    )

    assert whole.t_stat is not None and whole.t_stat > 0, whole
    assert confirmed["verdict"] == screen.STATUS_FORWARD_AGREE
    assert confirmed["forward_t"] > 0
    assert confirmed["observations"] > 0
    # agrees 也只是「可进入评审」：采纳权仍在人工预注册，本模块不越权
    assert "人工预注册" in confirmed["reason"]

