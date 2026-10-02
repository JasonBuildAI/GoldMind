"""研究台：候选清单与预注册文本逐项对齐，报告覆盖三个样本期。

预注册的意义在于「先写死、再执行」：这两个守卫（候选表对齐、硬规则常量对齐）
 保证代码不能在看到留出期成绩之后悄悄换候选或放松判定。
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

import pandas as pd
import pytest

from app.services.quant import backtest, engine, regimes
from scripts import quant_lab

REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "2026-10-02-量化策略提升路线图.md"
# 第四轮（Regime 与基准对照）的登记文本在这一轮的 spec 里，与上面的路线图 6.1 平权：
# 候选清单分成两份文档，守卫必须**两份都对齐**，否则新增一族可以绕开对齐检查。
ROUND_FOUR_PATH = REPO_ROOT / "docs" / "specs" / "2026-10-03-2.0.2-整改与自动化.md"


def _spec_text() -> str:
    return SPEC_PATH.read_text(encoding="utf-8")


def _spec_table_rows() -> list[tuple[str, int, str]]:
    """解析 spec 6.1 的候选表：(组名, 数量, 候选说明)。"""
    section = _spec_text().split("#### 6.1 预注册候选清单", 1)[1]
    section = section.split("裁决口径", 1)[0]
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 3 or not cells[1].isdigit():
            continue
        rows.append((cells[0], int(cells[1]), cells[2]))
    return rows


def _round_four_table_rows() -> list[tuple[str, int, str]]:
    """解析第四轮预注册的候选表（Regime / 基准对照）：格式与 6.1 相同。"""
    section = ROUND_FOUR_PATH.read_text(encoding="utf-8").split("第四轮预注册", 1)[1]
    section = section.split("### ", 1)[0]
    rows = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 3 or not cells[1].isdigit():
            continue
        rows.append((cells[0], int(cells[1]), cells[2]))
    return rows


def _all_spec_rows() -> list[tuple[str, int, str]]:
    """两份预注册文本的候选表合并 —— 代码必须有且仅有这些组与候选。"""
    return _spec_table_rows() + _round_four_table_rows()


def test_candidate_groups_match_the_preregistered_table():
    spec_counts = {label: count for label, count, _ in _all_spec_rows()}
    assert spec_counts, "预注册文本必须能解析出候选表"

    code_counts = Counter(
        quant_lab.GROUP_LABELS[candidate.group] for candidate in quant_lab.CANDIDATES
    )
    assert dict(code_counts) == spec_counts


def test_candidate_keys_are_exactly_the_preregistered_keys():
    groups = {label: text for label, _, text in _all_spec_rows()}
    for candidate in quant_lab.CANDIDATES:
        label = quant_lab.GROUP_LABELS[candidate.group]
        assert re.search(rf"\b{re.escape(candidate.key)}\b", groups[label]), (
            f"候选 {candidate.key} 未写在 spec 的「{label}」一行"
        )
    assert sum(count for _, count, _ in _all_spec_rows()) == len(quant_lab.CANDIDATES)


def test_hard_rule_constants_track_the_preregistered_text():
    text = _spec_text()
    assert "≤1pp" in text
    assert quant_lab.RULE_2_ACCURACY_TOLERANCE == pytest.approx(-0.01)
    assert "≤2pp" in text
    assert quant_lab.RULE_OTHER_SCALE_TOLERANCE == pytest.approx(-0.02)
    assert "≥3/5" in text
    assert "p < 0.05" in text
    assert quant_lab.RULE_2_BRIER_P == pytest.approx(0.05)
    assert quant_lab.TARGET_SCALE == 250


def _long_calendar() -> pd.DatetimeIndex:
    return pd.date_range("2019-01-01", "2026-09-30", freq="B")


def _fast_bootstrap(monkeypatch) -> None:
    # 研究台测试只关心口径与列结构，自助次数不必是生产值（口径由 stats 测试单独钉住）
    monkeypatch.setattr(backtest, "BOOTSTRAP_DRAWS", 50)


def _subset(*keys: str) -> tuple[quant_lab.Candidate, ...]:
    return tuple(quant_lab.CANDIDATES_BY_KEY[key] for key in keys)


def test_report_contains_development_and_holdout_columns(make_panel, monkeypatch):
    _fast_bootstrap(monkeypatch)
    factors, close = make_panel(_long_calendar())
    subset = _subset("B0", "S1", "E0", "F1")

    rows = quant_lab.run_lab(factors, close, horizons=(20,), candidates=subset)
    markdown = quant_lab.format_markdown(rows, horizons=(20,))

    assert len(rows) == len(subset) * 4
    # 必须钉住主表表头本身：「留出期」在裁决标题里也出现，只搜正文会假绿
    header = next(line for line in markdown.splitlines() if line.startswith("| 候选 |"))
    header_cells = [cell.strip() for cell in header.strip("|").split("|")]
    # 「留出期」这一列指的是**历史**留出期（裁决窗口另算），表头必须写清楚；
    # 前向留出期单列，因为它是唯一的裁决窗口
    assert (
        "开发期" in header_cells
        and "历史留出期" in header_cells
        and "前向留出期" in header_cells
        and "全样本" in header_cells
    )
    assert "| B0 |" in markdown and "| E0 |" in markdown
    holdout = next(
        row for row in rows if row["candidate"] == "B0" and row["period"] == "holdout"
    )
    assert holdout["accuracy"] is not None
    assert holdout["samples"] >= backtest.MIN_EVALUATION_SAMPLES


@pytest.mark.unit
def test_regime_candidate_gates_the_composite_score(make_panel, monkeypatch):
    """R 族 = 合成得分 × 状态闸门，走的还是同一次标准评估。

    等价性检查：手工复现「合成得分 → 状态闸门 → evaluate_periods」的整条链路，
    成绩必须与 run_lab 给出的一致。变异验证：把 evaluate_candidate 里的
    ``if candidate.regime`` 分支删掉，本测试红。
    """
    _fast_bootstrap(monkeypatch)
    calendar = _long_calendar()
    factors, close = make_panel(calendar)
    rows = quant_lab.run_lab(factors, close, horizons=(20,), candidates=_subset("R1"))
    row = next(
        item
        for item in rows
        if item["candidate"] == "R1" and item["period"] == "holdout" and item["horizon_days"] == 20
    )

    signals = engine.build_signals(engine.align_factors(factors, calendar), calendar)
    score = engine.composite_score(signals, horizon=20, mode="weighted", include=None)
    mask = regimes.regime_mask("R1", factors, calendar)
    expected = backtest.evaluate_periods(
        factors,
        close,
        horizon=20,
        holdout_start=quant_lab.HOLDOUT_START,
        score_mode="weighted",
        include=None,
        regression_window=None,
        interval="aci",
        calibration_mode=engine.CALIBRATION_ROW,
        score=regimes.apply_regime(score, mask),
    )["holdout"]

    assert row["accuracy"] == pytest.approx(expected.accuracy)
    assert row["benchmark"] == "gold_close"


@pytest.mark.unit
def test_benchmark_candidate_swaps_the_evaluation_target(make_panel, monkeypatch):
    """G2 评估的是 GLD 序列本身：换一条走势相反的基准，成绩必须跟着变。

    变异验证：把 evaluate_candidate 里的基准选择删掉（永远用生产基准），本测试红。
    """
    _fast_bootstrap(monkeypatch)
    calendar = _long_calendar()
    factors, close = make_panel(calendar)
    mirrored = pd.Series(close.to_numpy()[::-1], index=calendar, name="gld_close")
    factors["gld_close"] = mirrored

    rows = quant_lab.run_lab(factors, close, horizons=(20,), candidates=_subset("G1", "G2"))
    g1 = next(item for item in rows if item["candidate"] == "G1" and item["period"] == "holdout")
    g2 = next(item for item in rows if item["candidate"] == "G2" and item["period"] == "holdout")

    assert g1["benchmark"] == "gold_close" and g2["benchmark"] == "gld_close"
    assert g1["accuracy"] != g2["accuracy"], "换了基准成绩却没变 ⇒ 基准对照没有生效"


def test_control_candidates_reuse_the_baseline_run(make_panel, monkeypatch):
    """S4 / P4 / F4 与 B0 同口径：必须只计算一次（否则研究台在悄悄重复算）。"""
    _fast_bootstrap(monkeypatch)
    calls = []
    original = backtest.prepare_evaluation

    def counting(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(backtest, "prepare_evaluation", counting)
    factors, close = make_panel(_long_calendar())
    subset = _subset("B0", "S4", "P4", "F4")

    rows = quant_lab.run_lab(factors, close, horizons=(20,), candidates=subset)

    assert len(calls) == 1, "同口径的控制候选必须复用同一次计算"
    holdout_values = {
        row["accuracy"]
        for row in rows
        if row["period"] == "holdout" and row["horizon_days"] == 20
    }
    assert len(holdout_values) == 1 and None not in holdout_values


def test_unavailable_data_reports_failures_instead_of_fabricating():
    rows = quant_lab.run_lab(
        {},
        pd.Series(dtype="float64"),
        horizons=(20,),
        candidates=_subset("B0"),
    )

    assert all(row["accuracy"] is None for row in rows)
    markdown = quant_lab.format_markdown(rows, horizons=(20,))
    assert "缺少黄金价格序列" in markdown and "失败" in markdown


def test_csv_writer_exports_every_attempt(tmp_path):
    rows = quant_lab.run_lab(
        {},
        pd.Series(dtype="float64"),
        horizons=(20,),
        candidates=_subset("B0"),
    )
    path = tmp_path / "quant_lab.csv"

    quant_lab.write_csv(rows, path)

    content = path.read_text(encoding="utf-8-sig")
    assert content.splitlines()[0].startswith("candidate,")
    assert len(content.strip().splitlines()) == len(rows) + 1


def test_parse_horizons_rejects_unknown_scales():
    assert quant_lab._parse_horizons("20,250") == (20, 250)
    with pytest.raises(Exception):
        quant_lab._parse_horizons("20,999")

def test_bench_rows_carry_the_round_two_adjudication_metrics(make_panel, monkeypatch):
    """研究台必须输出第二轮裁决要用的那三个指标，否则 M1/T1 规则无法执行。

    这是补出来的洞：`backtest` 已经算了 `magnitude_skill_vs_flat` / `down_calls` /
    `interval_sharpness_80`，但表格列没带上，于是「用幅度技能裁决」写在 spec 里却跑不出来。
    变异验证：把这三列从 `ROW_FIELDS` / 行构造里删掉，本测试必红。
    """
    _fast_bootstrap(monkeypatch)
    factors, close = make_panel(_long_calendar())

    rows = quant_lab.run_lab(factors, close, horizons=(20,), candidates=_subset("B0"))

    for row in rows:
        for key in (
            "magnitude_skill",
            "down_calls",
            "down_call_accuracy",
            "interval_sharpness_80",
            "coverage_calm",
            "coverage_turbulent",
            "coverage_bets_calm",
            "coverage_bets_turbulent",
            "distribution_normal_share",
        ):
            assert key in row, f"{row['period']} 缺少 {key}：第二轮规则无法裁决"
        for key in (
            "coverage_calm",
            "coverage_turbulent",
            "coverage_bets_calm",
            "coverage_bets_turbulent",
        ):
            # 行里有、ROW_FIELDS 里没有 = CSV 里静默丢掉这一列
            assert key in quant_lab.ROW_FIELDS, f"{key} 没有进 ROW_FIELDS，导出的 CSV 会缺列"
        if row["period"] == "development":
            assert row["magnitude_skill"] is not None
            assert isinstance(row["down_calls"], int)

    # 分档覆盖率要出现在报告里，否则「整体 0.79 ≈ 0.80」还能继续糊
    markdown = quant_lab.format_markdown(rows, horizons=(20,), generated_at=None)
    assert "覆盖率按波动率分档" in markdown
    assert "档间差" in markdown


@pytest.mark.unit
def test_the_band_section_marks_short_buckets_as_unknown_rather_than_zero(make_panel):
    """分档下注数不足时，那一行要显示「—」并解释含义，不许显示 0%。

    变异验证：把 `_pct(...)` 换成 `f\"{100.0 * value:.1f}%\"`（None 时抛错或印成 0.0%），
    或把末尾那句解释删掉，本测试红。
    """
    factors, close = make_panel(pd.date_range("2015-01-02", "2016-06-30", freq="B"))

    rows = quant_lab.run_lab(factors, close, horizons=(20,), candidates=_subset("B0"))
    markdown = quant_lab.format_markdown(rows, horizons=(20,), generated_at=None)

    section = markdown.split("覆盖率按波动率分档", 1)[1]
    line = next(item for item in section.splitlines() if item.startswith("| 20 |"))
    assert line.count("—") >= 3, f"分档未知时应当印「—」：{line}"
    assert "不是 0%" in section


# --------------------------------------------------------------------------- #
# 裁决窗口：只认前向留出期，且样本不够时是「不可判定」而不是「未过线」
# --------------------------------------------------------------------------- #
def _verdict_row(key: str, period: str, horizon: int = 20, **overrides) -> dict:
    """一条裁决用的行；默认是「过线」的形状，按用例覆盖。"""
    row = {
        "candidate": key,
        "group": quant_lab.CANDIDATES_BY_KEY[key].group,
        "horizon_days": horizon,
        "period": period,
        "samples": 400,
        "accuracy": 0.60,
        "baseline_up": 0.50,
        "baseline_momentum": 0.50,
        "accuracy_diff_vs_up": 0.10,
        "accuracy_ci_low": 0.55,
        "accuracy_ci_high": 0.65,
        "p_value_vs_up": 0.01,
        "brier_score": 0.20,
        "brier_skill_score": 0.05,
        "brier_skill_p_value": 0.01,
        "coverage_80": 0.80,
        "coverage_ci_low": 0.76,
        "coverage_ci_high": 0.84,
        "effective_sample_size": 20.0,
        "independent_bets": 30,
        "reason": None,
    }
    row.update(overrides)
    return row


def _empty_forward(key: str, horizons=(5, 20, 60)) -> list[dict]:
    return [
        _verdict_row(
            key,
            "forward",
            horizon=horizon,
            samples=0,
            accuracy=None,
            baseline_up=None,
            accuracy_diff_vs_up=None,
            accuracy_ci_low=None,
            brier_skill_score=None,
            brier_skill_p_value=None,
            coverage_80=None,
            effective_sample_size=None,
            independent_bets=0,
            reason="前向留出期还没有可评估样本",
        )
        for horizon in horizons
    ]


def test_the_bench_adjudicates_on_the_forward_window():
    """裁决只认前向留出期。历史留出期已经被前两轮看过，不能再当入选依据。

    变异验证：把 `decide()` 里的 `"forward"` 改回 `"holdout"` 本测试必红
    （S1 会在历史留出期上「入选」）。
    """
    horizons = (5, 20, 60)
    spent = [
        _verdict_row("B0", "holdout", horizon=h, accuracy_ci_low=0.40) for h in horizons
    ] + [_verdict_row("S1", "holdout", horizon=h) for h in horizons]

    verdicts = quant_lab.decide(spent + _empty_forward("B0", horizons) + _empty_forward("S1", horizons))

    # S1 在历史留出期完全过线，但那段已被翻看 → 不许据此入选，状态是「还判不了」
    assert verdicts["S1"]["selected"] is False
    assert verdicts["S1"]["status"] == "pending"
    assert verdicts["S1"]["sufficient_scales"] == []

    # 前向窗口攒够下注且过线 → 才允许入选
    fresh = [
        _verdict_row("B0", "forward", horizon=h, accuracy_ci_low=0.40) for h in horizons
    ] + [_verdict_row("S1", "forward", horizon=h) for h in horizons]
    verdicts = quant_lab.decide(spent + fresh)

    assert verdicts["S1"]["status"] == "passed"
    assert verdicts["S1"]["selected"] is True


def test_a_bench_with_no_forward_data_says_undecidable_not_failed(make_panel, monkeypatch):
    """前向窗口还没有数据时，报告必须写「不可判定」，不能写「未过线」。

    这正是第二轮宣布要消灭的错误：把「还不知道」印成「知道了，是坏的」。
    面板在 `ACTIVE_HOLDOUT_START`（2026-10-02）之前结束 → 前向窗口必然是空的。

    变异验证：把 `format_markdown` 的结论改回无条件「未过线（保留线上版本）」，
    或让 `decide()` 不看 `sufficient_scales`，本测试必红。
    """
    _fast_bootstrap(monkeypatch)
    factors, close = make_panel(_long_calendar())  # 结束于 2026-09-30

    rows = quant_lab.run_lab(factors, close, horizons=(20,), candidates=_subset("B0", "S1"))
    markdown = quant_lab.format_markdown(rows, horizons=(20,), generated_at=None)

    assert "不可判定" in markdown
    # 结论行不能说「未过线」/「无候选过线」，只能说还判不了（说明文字里出现这些词不算）
    assert "未过线（保留线上版本）" not in markdown
    assert "裁决：前向留出期尚不可判" in markdown
    # 前向留出期必须是报告里的一个正式样本期
    assert "前向留出期" in markdown

