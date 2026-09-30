"""导入健康度测试。

`app/` 下每个模块都必须能被导入。这条测试专门防「死代码同时是坏代码」——
历史上就发生过：一个模型模块缺少 `Float` 导入因而根本无法导入，
却因为没有任何地方 import 它而长期没被发现。
"""
import importlib
import pkgutil
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parent.parent.parent / "app"


def _discover_modules() -> list[str]:
    """枚举 `app` 包下的全部子模块名（如 app.main、app.services.llm_provider）。"""
    modules: list[str] = []
    for module_info in pkgutil.walk_packages([str(APP_DIR)], prefix="app."):
        if "__pycache__" in module_info.name:
            continue
        modules.append(module_info.name)
    return sorted(set(modules))


DISCOVERED = _discover_modules()


@pytest.mark.unit
def test_discovery_found_modules():
    """确保枚举逻辑本身有效，否则下面的参数化会静默变成空集合。"""
    assert len(DISCOVERED) > 10
    assert "app.main" in DISCOVERED


@pytest.mark.unit
@pytest.mark.parametrize("module_name", DISCOVERED)
def test_module_imports(module_name):
    importlib.import_module(module_name)
