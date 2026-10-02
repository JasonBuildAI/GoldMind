"""README 的监测仪表盘一节必须与 `monitor.ROW_SPECS` 逐行对齐。

为什么要有这份守卫：README 里的表格是手写的，而监视行数、名字、信息行性质都在代码里 ——
16 行那版就是这么烂掉的（第二轮接入五条新序列后，README 还写着 16 行）。
`docs/ARCHITECTURE.md` 有同类守卫；README 是读者第一眼看到的那份，同样不能对不上代码。

断言三件事：
1. 小节标题里的行数与表格行数都等于 `len(monitor.ROW_SPECS)`；
2. 每一行的中文名（`RowSpec.name`）都出现在表里；
3. 第二轮接入的五条信息行必须被显式标成「信息行」—— 它们没过多空闸门，
   README 里给它们方向就是编造。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
README = REPO_ROOT / "README.md"

NEW_INFORMATION_KEYS = {
    "gvz",
    "gold_silver_ratio",
    "copper_gold_ratio",
    "cftc_net_oi_ratio",
    "gpr_daily",
}


def _monitor_section() -> str:
    text = README.read_text(encoding="utf-8")
    start = text.index("### 八、监测仪表盘")
    end = text.index("### 九、", start)
    return text[start:end]


@pytest.mark.unit
def test_readme_monitor_row_count_matches_the_code():
    from app.services.quant import monitor

    count = len(monitor.ROW_SPECS)
    assert count >= 20, "监测行数掉下来了，先确认 ROW_SPECS 没被误删"
    section = _monitor_section()
    assert f"{count} 行水位表" in section, (
        f"README 的监测小节标题没写出行数（应为 {count} 行）——数字对不上就是文档在撒谎"
    )
    rows = [line for line in section.splitlines() if re.match(r"^\|\s*\d+\s*\|", line)]
    assert len(rows) == count, (
        f"README 表格有 {len(rows)} 行，monitor.ROW_SPECS 有 {count} 行 —— 两张表已经分叉"
    )
    assert len(rows) == len(set(rows)), "README 监测表里有重复行"


@pytest.mark.unit
def test_readme_monitor_section_names_every_indicator():
    from app.services.quant import monitor

    section = _monitor_section()
    missing = [spec.name for spec in monitor.ROW_SPECS if spec.name not in section]
    assert not missing, (
        "这些监测指标在 README 的 21 行表里没有出现：" + "、".join(missing)
    )


@pytest.mark.unit
def test_readme_marks_the_new_information_rows_as_information_only():
    from app.services.quant import monitor

    assert NEW_INFORMATION_KEYS <= set(monitor.INFO_KEYS), (
        "五条新序列不再是信息行了 —— README 的口径要跟着改，别默默给方向"
    )
    section = _monitor_section()
    for spec in monitor.ROW_SPECS:
        if spec.key not in NEW_INFORMATION_KEYS:
            continue
        row = next(
            (line for line in section.splitlines() if spec.name in line),
            None,
        )
        assert row is not None, f"README 表里找不到 {spec.name}"
        assert "信息行" in row, (
            f"{spec.name} 是没过闸门的信息行，README 必须标「信息行」，不能给多空标签"
        )
