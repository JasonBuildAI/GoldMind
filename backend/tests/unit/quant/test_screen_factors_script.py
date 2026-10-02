"""筛选报告的两件事：闸门①②的表格口径，以及第 ③ 道闸门必须**可见**。

第 ③ 道闸门（前向窗口）今天判不了，所以它最大的风险不是算错，而是被忘掉：
只有当报告里印着「每个尺度还差多少个交易日」和「已可判的候选复核成了什么」，
等不等才是一个摆在台面上的决定，而不是一个可以悄悄跳过的步骤。
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.services.quant import screen
from scripts import screen_factors

WINDOW_START = pd.Timestamp(screen.FORWARD_WINDOW_START)
HORIZONS = (5, 20)


def _market(calendar: pd.DatetimeIndex) -> pd.Series:
    rng = np.random.default_rng(5)
    return pd.Series(
        1800.0 * np.exp(np.cumsum(rng.normal(0.0002, 0.009, len(calendar)))), index=calendar
    )


def _perfect_lead(benchmark: pd.Series) -> pd.Series:
    """作弊用的完美前瞻信号：只用来检验报告会不会把「已可判」的格子真的判出来。"""
    return ((benchmark.shift(-5) / benchmark - 1.0) * 8.0).fillna(0.0)


def _anti_lead(benchmark: pd.Series) -> pd.Series:
    """反向的完美前瞻信号（混入噪声，好让 t 落在「显著但别太夸张」的区间）。"""
    rng = np.random.default_rng(11)
    anti = -(benchmark.shift(-20) / benchmark - 1.0)
    clean = (anti / anti.std()).fillna(0.0).to_numpy()
    return pd.Series(clean * 0.3 + rng.normal(0.0, 1.0, len(benchmark)), index=benchmark.index)


@pytest.mark.unit
def test_report_shows_gate_three_progress_for_every_horizon():
    """窗口还没到：每个尺度都要摊开「差多少」，并且一条结论都不许下。"""
    calendar = pd.date_range("2022-01-03", end=WINDOW_START - pd.tseries.offsets.BDay(1), freq="B")
    benchmark = _market(calendar)
    lead = _perfect_lead(benchmark)

    section = screen_factors.format_forward_window(
        benchmark,
        screen.screen_round({"lead": lead}, benchmark, horizons=HORIZONS),
        {"lead": lead},
        horizons=HORIZONS,
    )

    assert "第 ③ 道闸门" in section
    assert screen.FORWARD_WINDOW_START.isoformat() in section
    assert section.count("| 否 |") == len(HORIZONS)
    assert "前向复核" not in section, "窗口一天没到，报告就不许给出方向结论"
    for horizon in HORIZONS:
        required = max(screen.MIN_FORWARD_BETS, math.ceil(screen.MIN_SCREEN_SAMPLES / horizon))
        assert f"| {horizon} | 0 | 0 | {required} | 否 | {required * horizon} |" in section


@pytest.mark.unit
def test_report_rechecks_candidates_once_the_window_has_data():
    """窗口攒够之后，报告必须自己把前向复核跑出来 —— 不许停在「等以后再说」。

    变异验证：删掉 `format_forward_window` 里调用 `confirm_on_forward_window` 的那一段，
    本测试的 `前向复核` 与两个 t 值断言同时红。
    """
    calendar = pd.date_range("2022-01-03", WINDOW_START + pd.tseries.offsets.BDay(700), freq="B")
    benchmark = _market(calendar)
    lead = _perfect_lead(benchmark)
    verdicts = screen.screen_round({"lead": lead}, benchmark, horizons=HORIZONS)

    section = screen_factors.format_forward_window(
        benchmark, verdicts, {"lead": lead}, horizons=HORIZONS
    )

    assert section.count("| 是 |") == len(HORIZONS), "700 个交易日应让两个尺度都可判"
    assert "前向复核" in section
    assert screen.STATUS_FORWARD_AGREE in section, section
    assert "开发期 t=" in section and "前向 t=" in section
    # 每个已可判的尺度都要留下一行结论，不许只报进度表
    assert section.count("- lead @ ") == len(HORIZONS)


@pytest.mark.unit
def test_report_registers_reversed_hypotheses_and_rechecks_them():
    """反向显著的候选必须在报告里单独成行，并且同样进前向复核队列。

    变异验证：把 `format_forward_window` 的 ``watched`` 收回成只含 ``STATUS_AWAIT``，
    本测试后半（前向复核那一段）红；把 `format_markdown` 里登记反向假设那行删掉，前半红。
    """
    calendar = pd.date_range("2022-01-03", WINDOW_START + pd.tseries.offsets.BDay(700), freq="B")
    benchmark = _market(calendar)
    anti = _anti_lead(benchmark)
    verdicts = screen.screen_round({"anti": anti}, benchmark, horizons=HORIZONS)
    rows = screen.summary_rows(verdicts)
    assert [verdict.status for verdict in verdicts] == [screen.STATUS_REVERSED]

    summary = screen_factors.format_markdown(rows, horizons=HORIZONS)
    section = screen_factors.format_forward_window(
        benchmark, verdicts, {"anti": anti}, horizons=HORIZONS
    )

    assert "反向假设" in summary and "anti @ 5日" in summary, summary
    assert "前向复核" in section and "（反向假设）" in section
    assert screen.STATUS_FORWARD_AGREE in section, "反向假设在新窗口里成立，报告必须说出来"


@pytest.mark.unit
def test_window_start_is_the_announcement_date_not_a_moving_target():
    """窗口起点写死为封板日；挪它等于作废整轮预注册，所以钉进测试。

    2026-10-02 是第二/三轮的封板日；2.0.2 的 quant-v7 发布滞后修正重新封板到
    2026-10-03（见 definitions.ACTIVE_HOLDOUT_START），屏幕层必须跟着同一处定义走。
    """
    assert screen.FORWARD_WINDOW_START == date(2026, 10, 3)
