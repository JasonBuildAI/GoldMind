"""接口文档漂移闸门（中英两份都守）。

`docs/API.md` 与 `docs/en/api.md` 由 `backend/scripts/gen_api_doc.py` 从
FastAPI 路由表生成。这个测试保证它们不会再次与实现脱节 —— 手写版本曾经把前缀
写成 `/api/analysis/*`、把 `/gold/stats` 的字段名写错，而且没人会发现。

英文版由生成器而非人工翻译产出，正是为了不让两份文档在第一天就分叉；
因此校验也必须两份都做，只守中文等于放英文版自流。

改接口后运行 `cd backend && python scripts/gen_api_doc.py` 即可修复。
"""
import importlib.util
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
GENERATOR_PATH = BACKEND_DIR / "scripts" / "gen_api_doc.py"


def _load_generator():
    """按文件路径加载生成器模块（scripts/ 不是包，不能直接 import）。"""
    spec = importlib.util.spec_from_file_location("gen_api_doc", GENERATOR_PATH)
    assert spec and spec.loader, f"无法加载 {GENERATOR_PATH}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
def test_api_doc_matches_route_table():
    gen = _load_generator()

    for lang, path in (("zh", gen.DOC_PATH), ("en", gen.DOC_PATH_EN)):
        expected = gen.render(lang)
        actual = path.read_text(encoding="utf-8")

        assert actual == expected, (
            f"{path.name}（{lang}）与路由表不一致。"
            "修复：cd backend && python scripts/gen_api_doc.py"
        )


@pytest.mark.integration
def test_every_api_route_appears_in_the_doc():
    """两份文档都必须覆盖全部业务路由 —— 新增接口不能只存在于代码里。"""
    gen = _load_generator()
    routes = gen._collect_routes()
    assert routes, "没有采集到任何路由，生成器可能失效了"

    for lang in ("zh", "en"):
        doc = gen.render(lang)
        missing = [f"{r['method']} {r['path']}" for r in routes if f"`{r['path']}`" not in doc]
        assert not missing, f"这些路由没有出现在 {lang} 文档里: {missing}"


@pytest.mark.integration
def test_english_doc_has_no_untranslated_summaries():
    """英文版不得出现中文说明，也不得留着没替换的占位符。

    生成器对查不到译文的条目回退路由名（ASCII），所以这里既能挡住「漏翻译
    直接抄中文」，也能挡住模板占位符（`{llm}` / `{heavy}`）漏在正文里。
    """
    gen = _load_generator()
    doc = gen.render("en")

    assert "{llm}" not in doc and "{heavy}" not in doc

    table_rows = [
        line
        for line in doc.splitlines()
        if line.startswith("| `GET`") or line.startswith("| `POST`")
    ]
    assert len(table_rows) == len(gen._collect_routes())
    unreadable = [line for line in table_rows if any("\u4e00" <= ch <= "\u9fff" for ch in line)]
    assert not unreadable, f"英文版里出现了中文说明: {unreadable}"


@pytest.mark.integration
def test_doc_flags_the_llm_backed_endpoints():
    """会花钱的接口必须在两份文档里都被标注出来。"""
    gen = _load_generator()
    doc = gen.render()

    assert "会调用 LLM" in doc
    # 五个分析接口各有一个 refresh 端点
    assert doc.count("会调用 LLM") == 5
    # 不花 LLM 额度、但同样按重操作限流的端点（如量化刷新）也要标出来
    assert "重操作" in doc

    doc_en = gen.render("en")
    assert doc_en.count("calls the LLM") == 5
    assert "heavy operation" in doc_en
