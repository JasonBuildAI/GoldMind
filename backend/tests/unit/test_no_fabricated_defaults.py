"""兜底方法不得返回**编造的内容**。

红线第 1 条（`AGENTS.md` / `docs/00-产品方向.md` 第四节）：

> 不为了好看而展示编造的数据 —— 宁可显示「数据不可用」。

这条红线在代码里有**四个载体**，每一次都是单独发现的：

| # | 载体 | 何时修的 |
|---|---|---|
| 1 | 前端各区块的 `fallbackData` / `defaultFactors` | 第 2 轮 |
| 2 | 服务层**缓存未命中**时的 `_get_default_response()` | 第 2 轮 |
| 3 | 提示词里让模型「合理推断」的指令 | 第 21 轮 |
| 4 | 分析器层 **LLM 失败**时的 `_get_default_factors()` | 第 22 轮 |

第 4 个最要命：它落在「LLM 调用失败」「JSON 解析失败」「返回空内容」三条路径上 ——
也就是说**模型一出问题，页面照样显示一份看起来完整的分析**，
而那份内容是写死的常量。

这条守卫扫描所有 `*default*` 方法，要求它们返回的列表/字典**都是空的**。
"""
import ast
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# 这些键承载的是「状态」而不是「内容」，允许非空
_STATUS_KEYS = frozenset(
    {
        "metadata",
        "status",
        "message",
        "cached",
        "cache_source",
        "generated_at",
        "data_sources",
        "analysis_method",
        "error",
    }
)


def _default_methods():
    """产出 (文件, 方法名, 返回的 dict 字面量节点, 源码)。"""
    for path in sorted(APP_DIR.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            if "default" not in node.name.lower():
                continue
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and isinstance(sub.value, ast.Dict):
                    yield path.relative_to(APP_DIR).as_posix(), node.name, sub.value, src


@pytest.mark.unit
def test_no_default_method_returns_fabricated_content():
    """兜底返回的列表与字典必须为空。"""
    offenders = []

    for fname, method, dict_node, src in _default_methods():
        for key_node, value_node in zip(dict_node.keys, dict_node.values):
            if not isinstance(key_node, ast.Constant):
                continue
            key = key_node.value

            # 列表：必须为空
            if isinstance(value_node, ast.List):
                if len(value_node.elts) > 0:
                    snippet = ast.get_source_segment(src, value_node) or ""
                    offenders.append(
                        f"{fname} :: {method}() 的 {key!r} 有 {len(value_node.elts)} 条内容："
                        f"{snippet[:70]}"
                    )

            # 字典：必须为空 —— 但**状态类**的键除外。
            # `metadata: {"status": "analyzing"}` 是告诉前端「正在分析」，
            # 不是内容；把它一起禁掉会让守卫误报，进而被人关掉。
            if key in _STATUS_KEYS:
                continue
            if isinstance(value_node, ast.Dict) and len(value_node.keys) > 0:
                snippet = ast.get_source_segment(src, value_node) or ""
                offenders.append(
                    f"{fname} :: {method}() 的 {key!r} 非空：{snippet[:70]}"
                )

    assert not offenders, (
        "这些兜底方法返回了编造的内容 —— 模型失败时用户会看到一份假分析：\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.unit
def test_the_scan_finds_the_default_methods():
    """守卫要真的扫到方法 —— 空集合上断言「没问题」是假绿。"""
    found = list(_default_methods())

    assert len(found) >= 5, f"只扫到 {len(found)} 个兜底方法，解析八成坏了"
    names = {name for _, name, _, _ in found}
    assert "_get_default_factors" in names, "没扫到分析器层的兜底方法（第 22 轮修的那个）"
    assert "_get_default_response" in names
    assert "get_default_predictions" in names


@pytest.mark.unit
def test_the_guard_detects_a_violation(tmp_path, monkeypatch):
    """判别力：塞一个带内容的兜底方法进去，必须被抓到。"""
    import importlib

    module = importlib.import_module("tests.unit.test_no_fabricated_defaults")

    fake = tmp_path / "app"
    fake.mkdir(parents=True)
    (fake / "bad.py").write_text(
        "def _get_default_factors(self):\n"
        "    return {\n"
        '        "bullish_factors": [\n'
        '            {"id": "fed-policy", "title": "美联储降息周期", "impact": "high"}\n'
        "        ],\n"
        '        "analysis_summary": "基于当前市场状况的综合分析",\n'
        "    }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "APP_DIR", fake)

    with pytest.raises(AssertionError) as excinfo:
        module.test_no_default_method_returns_fabricated_content()

    assert "bullish_factors" in str(excinfo.value)


@pytest.mark.unit
def test_an_empty_default_passes(tmp_path, monkeypatch):
    """空兜底不该被判违规。"""
    import importlib

    module = importlib.import_module("tests.unit.test_no_fabricated_defaults")

    fake = tmp_path / "app"
    fake.mkdir(parents=True)
    (fake / "good.py").write_text(
        "def _get_default_factors(self):\n"
        "    return {\n"
        '        "bullish_factors": [],\n'
        '        "analysis_summary": "",\n'
        '        "metadata": {"status": "analyzing"},\n'
        "    }\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "APP_DIR", fake)

    # 先确认它确实被扫到（否则这条测试只是「什么都没检查」）
    assert list(module._default_methods()), "假兜底方法没被扫到，这条测试没有判别力"

    module.test_no_default_method_returns_fabricated_content()
