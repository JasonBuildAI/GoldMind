"""接口文档漂移闸门。

`docs/API.md` 由 `backend/scripts/gen_api_doc.py` 从 FastAPI 路由表生成。
这个测试保证它不会再次与实现脱节 —— 手写版本曾经把前缀写成 `/api/analysis/*`、
把 `/gold/stats` 的字段名写错，而且没人会发现。

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

    expected = gen.render()
    actual = gen.DOC_PATH.read_text(encoding="utf-8")

    assert actual == expected, (
        "docs/API.md 与路由表不一致。修复：cd backend && python scripts/gen_api_doc.py"
    )


@pytest.mark.integration
def test_every_api_route_appears_in_the_doc():
    """文档必须覆盖全部业务路由 —— 新增接口不能只存在于代码里。"""
    gen = _load_generator()
    doc = gen.render()

    routes = gen._collect_routes()
    assert routes, "没有采集到任何路由，生成器可能失效了"

    missing = [f"{r['method']} {r['path']}" for r in routes if f"`{r['path']}`" not in doc]
    assert not missing, f"这些路由没有出现在文档里: {missing}"


@pytest.mark.integration
def test_doc_flags_the_llm_backed_endpoints():
    """会花钱的接口必须在文档里被标注出来。"""
    gen = _load_generator()
    doc = gen.render()

    assert "会调用 LLM" in doc
    # 五个分析接口各有一个 refresh 端点
    assert doc.count("会调用 LLM") == 5
