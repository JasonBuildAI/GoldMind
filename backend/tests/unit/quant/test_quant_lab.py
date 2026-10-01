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

from app.services.quant import backtest
from scripts import quant_lab

REPO_ROOT = Path(__file__).resolve().parents[4]
SPEC_PATH = REPO_ROOT / "docs" / "specs" / "2026-10-02-量化策略提升路线图.md"


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


def test_candidate_groups_match_the_preregistered_table():
    spec_counts = {label: count for label, count, _ in _spec_table_rows()}
    assert spec_counts, "spec 6.1 必须能解析出候选表"

    code_counts = Counter(
        quant_lab.GROUP_LABELS[candidate.group] for candidate in quant_lab.CANDIDATES
    )
    assert dict(code_counts) == spec_counts


def test_candidate_keys_are_exactly_the_preregistered_keys():
    groups = {label: text for label, _, text in _spec_table_rows()}
    for candidate in quant_lab.CANDIDATES:
        label = quant_lab.GROUP_LABELS[candidate.group]
        assert re.search(rf"\b{re.escape(candidate.key)}\b", groups[label]), (
            f"候选 {candidate.key} 未写在 spec 的「{label}」一行"
        )
    assert sum(count for _, count, _ in _spec_table_rows()) == len(quant_lab.CANDIDATES)


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

    assert len(rows) == len(subset) * 3
    # 必须钉住主表表头本身：「留出期」在裁决标题里也出现，只搜正文会假绿
    header = next(line for line in markdown.splitlines() if line.startswith("| 候选 |"))
    header_cells = [cell.strip() for cell in header.strip("|").split("|")]
    assert "开发期" in header_cells and "留出期" in header_cells and "全样本" in header_cells
    assert "| B0 |" in markdown and "| E0 |" in markdown
    holdout = next(
        row for row in rows if row["candidate"] == "B0" and row["period"] == "holdout"
    )
    assert holdout["accuracy"] is not None
    assert holdout["samples"] >= backtest.MIN_EVALUATION_SAMPLES


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
