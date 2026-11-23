"""Python 源码里不得出现无效转义序列。

Python 3.12 起，字符串里的无效转义（例如 docstring 中写成 ``\\```）会给出
``SyntaxWarning``，而不是悄悄当成普通反斜杠；这条警告最终会升级为
``SyntaxError``，那时整个模块在导入阶段就失败，而测试与运行时都会先撞上它。

本仓库之前恰好有两处（``app/services/quant/sync.py`` 与
``tests/integration/test_sources_status_api.py``），``pytest`` 的输出里已经有
``SyntaxWarning: invalid escape sequence '\\`'``。这里把「不能有」变成可执行的检查：
按文件逐个 ``compile``，把告警收集起来，出现一条就算失败并给出文件与行号。
"""
from __future__ import annotations

import warnings
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _python_files() -> list[Path]:
    return sorted(p for p in BACKEND_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


def _invalid_escape_warnings(path: Path) -> list[str]:
    with warnings.catch_warnings(record=True) as caught:
        # 不能依赖调用方的告警过滤器：pytest 或环境可能已经把 SyntaxWarning 藏起来。
        warnings.simplefilter("always")
        compile(path.read_bytes(), str(path), "exec")
    return [
        f"{item.lineno}: {item.message}"
        for item in caught
        if issubclass(item.category, SyntaxWarning)
    ]


@pytest.mark.unit
def test_the_scan_covers_the_whole_backend() -> None:
    """守卫自己也要能被验证：路径写错时不能因为「扫到 0 个文件」而变绿。"""
    files = _python_files()

    assert len(files) > 100
    assert BACKEND_ROOT / "app" / "main.py" in files
    assert BACKEND_ROOT / "tests" / "conftest.py" in files


@pytest.mark.unit
def test_no_python_file_has_an_invalid_escape_sequence() -> None:
    offenders = {}
    for path in _python_files():
        problems = _invalid_escape_warnings(path)
        if problems:
            offenders[str(path.relative_to(BACKEND_ROOT)).replace("\\", "/")] = problems

    assert not offenders, "源码里有无效转义序列（Python 3.12+ 会给出 SyntaxWarning，未来会变成 SyntaxError）：\n" + "\n".join(
        f"  {name}: {', '.join(problems)}" for name, problems in sorted(offenders.items())
    )
