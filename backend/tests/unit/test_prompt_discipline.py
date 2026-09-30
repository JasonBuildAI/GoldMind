"""提示词不得让模型**编造**没有依据的内容。

项目红线（`AGENTS.md` 第 1 条、`docs/00-产品方向.md` 第四节第 1 条）：

> 数据源或联网搜索不可用时，返回「不可用」并说明原因，**不得**让模型凭印象生成
> 机构目标价、央行购金量、金价点位等具体数字后当作事实展示。

这条红线在提示词里被违反过**三次**，每次都在不同的服务里：

| 轮次 | 位置 | 原文 |
|---|---|---|
| 第 2 轮 | 机构预测 | 「如果新闻中没有某家机构的最新预测，请基于该机构历史观点和市场常识**合理推断**」 |
| 第 21 轮 | 看涨因子 | 「如果没有相关新闻支撑某个因子，请基于当前市场常识**合理推断**」 |
| 第 21 轮 | 看跌因子 | 同上 |

写死的兜底常量已经清掉了，但**提示词里的这类指令更隐蔽** ——
它不产生任何「默认值」，只是让模型自己编，产物看起来与真实分析完全一样。

这条守卫扫描所有提示词字符串，禁止「推断 / 凭印象 / 凭常识」这类**肯定式**指令。
否定式（「不要凭印象编造」）是合规的，所以带否定词的行放行。
"""
import ast
import re
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# 肯定式「让模型自己编」的说法
FORBIDDEN_PHRASES = (
    "合理推断",
    "凭印象",
    "凭常识",
    "自行推断",
    "可以推断",
    "请推断",
    "合理推测",
    "自行补充",
)

# 出现这些词说明是在**禁止**编造，放行
NEGATIONS = ("不", "勿", "禁止", "绝不", "不要", "不得", "宁可", "而不")


def _prompt_strings() -> list[tuple[str, int, str]]:
    """(文件, 行号, 字符串内容) —— 所有看起来像提示词的字符串字面量。"""
    out: list[tuple[str, int, str]] = []
    for path in APP_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            text = node.value
            # 只挑长文本（提示词都很长），避免把普通字符串误判
            if len(text) < 80:
                continue
            if not any(k in text for k in ("你是一位", "请", "分析", "返回", "JSON")):
                continue
            out.append((path.relative_to(APP_DIR).as_posix(), node.lineno, text))
    return out


@pytest.mark.unit
def test_no_prompt_asks_the_model_to_invent():
    offenders = []
    for fname, lineno, text in _prompt_strings():
        for i, line in enumerate(text.splitlines()):
            if not any(p in line for p in FORBIDDEN_PHRASES):
                continue
            # 否定式是合规的：「不要凭印象编造」
            if any(n in line for n in NEGATIONS):
                continue
            offenders.append(f"{fname}:{lineno + i}: {line.strip()[:100]}")

    assert not offenders, (
        "这些提示词在让模型编造没有依据的内容（红线见 docs/00-产品方向.md 第四节）：\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.unit
def test_the_scan_actually_finds_prompt_strings():
    """守卫要真的扫到提示词 —— 空集合上断言「没问题」是假绿。"""
    prompts = _prompt_strings()

    assert len(prompts) >= 5, f"只扫到 {len(prompts)} 段提示词，解析八成坏了"
    joined = "\n".join(t for _, _, t in prompts)
    # 几个已知必须存在的提示词特征
    assert "看涨" in joined
    assert "看跌" in joined
    assert "机构" in joined


@pytest.mark.unit
def test_the_guard_detects_a_violation(tmp_path, monkeypatch):
    """守卫自身的判别力（本会话已多次被假绿测试坑过）。"""
    import importlib

    module = importlib.import_module("tests.unit.test_prompt_discipline")

    fake = tmp_path / "app"
    fake.mkdir(parents=True)
    # 提示词要足够长才会被扫描（守卫只挑长文本，避免误判普通字符串）
    long_intro = "你是一位专业的黄金市场分析师，专注于分析影响黄金价格的因素。" * 3
    (fake / "bad.py").write_text(
        f'PROMPT = """{long_intro}\n'
        "如果没有相关新闻支撑，请基于当前市场常识合理推断。\n"
        '必须返回有效的 JSON 格式。"""\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "APP_DIR", fake)

    with pytest.raises(AssertionError):
        module.test_no_prompt_asks_the_model_to_invent()


@pytest.mark.unit
def test_negated_warnings_are_allowed(tmp_path, monkeypatch):
    """「不要凭印象编造」是合规的，不该被判违规。"""
    import importlib

    module = importlib.import_module("tests.unit.test_prompt_discipline")

    fake = tmp_path / "app"
    fake.mkdir(parents=True)
    long_intro = "你是一位专业的黄金市场分析师，专注于分析影响黄金价格的因素。" * 3
    (fake / "good.py").write_text(
        f'PROMPT = """{long_intro}\n'
        "如果新闻里没有，就写「暂无最新预测」，不要凭印象编造目标价。\n"
        '必须返回有效的 JSON 格式。"""\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "APP_DIR", fake)

    # 先确认它确实被扫到了 —— 否则这条测试只是「什么都没检查」
    monkeypatch.setattr(module, "APP_DIR", fake)
    assert module._prompt_strings(), "假提示词没被扫到，这条测试没有判别力"

    module.test_no_prompt_asks_the_model_to_invent()      # 不应抛异常
