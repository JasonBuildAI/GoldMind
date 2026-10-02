"""`.env.example` 必须覆盖代码里读取的每一个配置项。

回归：`MIMO_*` 改名为 `LLM_*` 后，`.env.example` 里留下过 `MIMO_TRUST_ENV`
这类过时项，而新增的定时任务 / 限流 / 量化开关从未写进模板 —— 别人照模板
配环境时根本不知道它们存在。这里把「模板完整」变成可执行的检查。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]

# 允许注释形式（`# KEY=`）—— 默认值即正确、不鼓励改写的项就该注释掉。
KEY_LINE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=", re.MULTILINE)
FRONTEND_KEY = re.compile(r"^\s*#?\s*(VITE_[A-Z0-9_]+)\s*=", re.MULTILINE)
FRONTEND_USAGE = re.compile(r"import\.meta\.env\.(VITE_[A-Z0-9_]+)")


@pytest.mark.unit
def test_backend_env_example_documents_every_setting():
    text = (REPO_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    documented = set(KEY_LINE.findall(text))

    assert len(documented) >= 25, f"只从模板里解析出 {len(documented)} 个键，解析大概失效了"

    missing = sorted(set(Settings.model_fields) - documented)
    assert not missing, (
        "backend/.env.example 未覆盖以下配置项（新增配置时必须同步补上模板）：\n"
        + "\n".join(f"  {name}" for name in missing)
    )


@pytest.mark.unit
def test_frontend_env_example_documents_every_vite_variable():
    used: set[str] = set()
    for path in (REPO_ROOT / "app" / "src").rglob("*.ts*"):
        used.update(FRONTEND_USAGE.findall(path.read_text(encoding="utf-8")))

    assert used, "没有从 app/src 里解析出任何 VITE_* 变量，解析逻辑失效了"

    documented = set(FRONTEND_KEY.findall((REPO_ROOT / "app" / ".env.example").read_text(encoding="utf-8")))
    missing = sorted(used - documented)
    assert not missing, "app/.env.example 未覆盖：" + ", ".join(missing)


@pytest.mark.unit
def test_backend_env_example_has_no_renamed_leftovers():
    """改过名的旧前缀不得留在模板里（回归：MIMO_TRUST_ENV）。"""
    text = (REPO_ROOT / "backend" / ".env.example").read_text(encoding="utf-8")
    documented = set(KEY_LINE.findall(text))
    stale = sorted(name for name in documented if name.startswith("MIMO_"))
    assert not stale, f"模板里留有旧名字：{stale}"
