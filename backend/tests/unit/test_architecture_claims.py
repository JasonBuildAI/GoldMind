"""`docs/ARCHITECTURE.md` 的量化章节必须与引擎实现一致。

为什么要有这份守卫（不是洁癖）：本轮修引擎时连续出现「代码改了、架构文档还写着旧公式」——
`p_up = Φ(μ/σ)`、`80% 区间 = μ ± 1.2816σ`、`三情景 = N(μ, σ²)` 三句在 v4→ACI 之后全都成了
假话，而 AGENTS.md 要求「文档里的路径、命令、名字必须真实存在」。人肉核对靠不住，
所以把最容易被悄悄过时的几件事写成断言：

1. `services/quant/` 里每个模块都必须在架构文档里出现（新增模块却漏文档 = 红）；
2. 默认区间口径是非对称 ACI 时，文档不许再出现那三句旧公式（改回去 = 红）；
3. 文档必须说得出当前默认口径的名字（`interval="aci"`），否则读者无从对齐代码。

4. 上面两条对**英文文档**同样成立 —— 旧公式在英文版里活了两轮没人发现，说明只盯中文
   等于只守一半；
5. 架构文档写的监测仪表盘行数必须等于 `monitor.ROW_SPECS` 的长度（写死的数字 = 会过期的
   数字，16 行那版就是这么烂掉的）。

只断言这几件「一定咬人」的事；曾写过一条（文档里出现的 snake_case 名字必须是已知序列键），
但它把 `gold_news` / `gold_prices` 这类表名误判成因子键，价值又低，已删除。
"""
from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
ARCHITECTURE = REPO_ROOT / "docs" / "ARCHITECTURE.md"
ARCHITECTURE_EN = REPO_ROOT / "docs" / "en" / "architecture.md"
PRODUCT_DIRECTION = REPO_ROOT / "docs" / "00-产品方向.md"
PRODUCT_DIRECTION_EN = REPO_ROOT / "docs" / "en" / "product-direction.md"
QUANT_DIR = REPO_ROOT / "backend" / "app" / "services" / "quant"

# 这些句子各自对应一个已经被修掉的行为；文档里再出现就说明「代码与文档分叉」回来了
STALE_CLAIMS = {
    "p_up = Φ(μ/σ)": "上行概率又写回正态尾概率（现在是同一张校准分布的尾部比例）",
    "上行概率 p=Φ(μ/σ)": "上行概率又写回正态尾概率（现在是同一张校准分布的尾部比例）",
    "80% 区间 = μ ± 1.2816σ": "区间又写成对称正态（默认口径是非对称 ACI 经验分位）",
    "三情景 = N(μ, σ²)": "情景又写成另算一套正态（现在取同一分布的四分位）",
}
# 英文文档里的同一批旧公式（拼写不同，检查同一件事）
STALE_CLAIMS_EN = {
    "p_up = Φ(μ/σ)": "upside probability is back to a normal tail (it now comes from the same calibrated distribution)",
    "80% interval = μ ± 1.2816σ": "the interval is back to a symmetric normal (the live convention is asymmetric ACI empirical quantiles)",
    "three scenarios = quantiles of": "scenarios are back to a separate normal (they now take the quartiles of the same distribution)",
    "upside probability p=Φ(μ/σ)": "upside probability is back to a normal tail",
}


def _architecture_text() -> str:
    return ARCHITECTURE.read_text(encoding="utf-8")


@pytest.mark.unit
def test_every_quant_module_is_documented():
    text = _architecture_text()
    modules = sorted(
        path.name for path in QUANT_DIR.glob("*.py") if path.name != "__init__.py"
    )
    assert modules, "没扫到任何量化模块，这个测试就白写了"
    missing = [name for name in modules if name not in text]
    assert not missing, (
        "这些量化引擎模块在 docs/ARCHITECTURE.md 里没有任何交代："
        f"{missing}。新增模块必须同时补架构说明（AGENTS.md：同一事实只留一个权威来源）。"
    )


@pytest.mark.unit
def test_docs_do_not_restate_the_superseded_interval_formula():
    from app.services.quant import engine

    if "aci" not in engine.INTERVAL_MODES or engine.INTERVAL_MODES[0] == "normal":
        pytest.skip("默认口径已改回正态，这条断言的前提不成立")
    text = _architecture_text()
    offenders = [claim for claim in STALE_CLAIMS if claim in text]
    assert not offenders, "docs/ARCHITECTURE.md 里还有旧口径的表述：\n" + "\n".join(
        f"  {claim} —— {STALE_CLAIMS[claim]}" for claim in offenders
    )


@pytest.mark.unit
def test_docs_name_the_current_default_interval_mode():
    text = _architecture_text()
    assert 'interval="aci"' in text or "interval=aci" in text, (
        "架构文档没写出当前默认的区间口径名，读者无法把文档与 engine.INTERVAL_MODES 对齐"
    )
    # 封顶与「陈旧即停用」是引擎的硬约束，文档必须提到，否则会被当成可选行为
    assert "EXPECTED_CAP_SIGMAS" in text, "文档漏了期望收益封顶这条硬约束"
    assert "align_series" in text or "max_age_days" in text, "文档漏了「陈旧即停用」这条硬约束"


@pytest.mark.unit
def test_english_docs_do_not_keep_the_superseded_formulas():
    """英文文档曾经把 v4 的旧公式一字不改地留了两轮 —— 只守中文等于只守一半。"""
    from app.services.quant import engine

    if "aci" not in engine.INTERVAL_MODES or engine.INTERVAL_MODES[0] == "normal":
        pytest.skip("默认口径已改回正态，这条断言的前提不成立")
    offenders = []
    for path in (ARCHITECTURE_EN, PRODUCT_DIRECTION_EN):
        text = path.read_text(encoding="utf-8")
        offenders.extend(
            f"{path.name}: {claim} —— {STALE_CLAIMS_EN[claim]}"
            for claim in STALE_CLAIMS_EN
            if claim in text
        )
    assert not offenders, "英文文档里还有旧口径的表述：\n" + "\n".join(offenders)


@pytest.mark.unit
def test_architecture_monitor_row_count_matches_the_code():
    """文档里写死的行数会过期（16 行那版就是这么烂掉的），所以每次对着代码数一遍。"""
    from app.services.quant import monitor

    count = len(monitor.ROW_SPECS)
    assert count >= 20, "监测行数掉下来了，先确认 ROW_SPECS 没被误删"
    assert f"覆盖 {count} 行指标" in _architecture_text(), (
        f"docs/ARCHITECTURE.md 没写出当前的行数（应为 {count} 行）——"
        "数字对不上就是文档在撒谎"
    )
