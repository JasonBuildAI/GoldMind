"""「clone 下来零配置也能跑」的配置级守卫。

README 的快速开始承诺：不装 MySQL、不写任何数据库配置，`python init_db.py`
就能建出 SQLite 单文件库。这条承诺靠三处配置共同成立，任何一处被改回 MySQL，
新用户的第一步就会失败 —— 这里把它们钉住。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app import config as config_module

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = REPO_ROOT / "backend" / ".env.example"


@pytest.mark.unit
def test_default_database_url_is_a_local_sqlite_file():
    url = config_module.DEFAULT_DATABASE_URL

    assert url.startswith("sqlite:///"), "默认库必须是 SQLite"
    assert url.endswith("goldmind.db"), "默认落盘到 backend/goldmind.db"
    assert "\r" not in url and "\n" not in url


@pytest.mark.unit
def test_default_database_url_matches_a_real_backend_path():
    url = config_module.DEFAULT_DATABASE_URL
    db_path = Path(url[len("sqlite:///"):])

    assert db_path.is_absolute(), "默认路径必须与启动目录无关"
    assert db_path.parent == (REPO_ROOT / "backend").resolve()


@pytest.mark.unit
def test_env_example_does_not_force_mysql():
    """`.env.example` 里不能有生效的 MySQL DATABASE_URL —— 复制它就等于选了 MySQL。"""
    active = [
        line for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line.strip().startswith("DATABASE_URL=")
    ]

    assert active == [], f"示例文件里不应有生效的 DATABASE_URL，发现: {active}"
