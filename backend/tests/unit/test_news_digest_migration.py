"""消息板块 url 列迁移脚本的判定与守卫（不依赖 MySQL）。

2026-10-02 的故障：`news_digest_items.url` 的 VARCHAR(500) 装不下 517 字符的
Google News 链接，MySQL 整批拒绝。既有库要靠 `scripts/migrate_news_digest_url.py`
升级到 TEXT。本文件钉住脚本的判定函数：什么时候该升级、SQLite 为什么直通、
以及**回滚会截断数据时必须拒绝**。真实 MySQL 上的执行是 `--apply` 的一次性人工验证。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = BACKEND_DIR / "scripts" / "migrate_news_digest_url.py"

OLD_SCHEMA = """
CREATE TABLE news_digest_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(500) NOT NULL,
    url VARCHAR(500) NOT NULL,
    published_at TIMESTAMP NOT NULL
)
"""


def _load_migration():
    spec = importlib.util.spec_from_file_location("migrate_news_digest_url", SCRIPT_PATH)
    assert spec and spec.loader, f"无法加载 {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    # dataclass 会按 cls.__module__ 反查 sys.modules，不注册会在装饰器处抛 AttributeError。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def old_engine():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(OLD_SCHEMA))
    return engine


@pytest.mark.unit
def test_plan_upgrades_varchar_to_text_on_mysql():
    plan = _load_migration().plan_for(
        dialect="mysql", table_exists=True, current_type="VARCHAR(500)"
    )
    assert plan.needed is True
    assert "TEXT" in plan.statement.upper()
    assert "VARCHAR(500)" not in plan.statement.upper()


@pytest.mark.unit
def test_plan_is_noop_when_column_is_already_text():
    plan = _load_migration().plan_for(dialect="mysql", table_exists=True, current_type="TEXT")
    assert plan.needed is False
    assert "TEXT" in plan.reason


@pytest.mark.unit
def test_plan_is_noop_on_sqlite_even_with_varchar_declaration():
    """SQLite 不强制 VARCHAR 长度（TEXT affinity），宣称要迁移就是假装干活。"""
    plan = _load_migration().plan_for(
        dialect="sqlite", table_exists=True, current_type="VARCHAR(500)"
    )
    assert plan.needed is False
    assert "SQLite" in plan.reason


@pytest.mark.unit
def test_plan_is_noop_when_table_is_missing():
    plan = _load_migration().plan_for(dialect="mysql", table_exists=False, current_type=None)
    assert plan.needed is False
    assert "不存在" in plan.reason


@pytest.mark.unit
def test_rollback_refuses_when_rows_exceed_the_old_limit():
    plan = _load_migration().rollback_for(
        dialect="mysql", current_type="TEXT", max_url_chars=517
    )
    assert plan.needed is False
    assert "517" in plan.reason


@pytest.mark.unit
def test_rollback_returns_statement_when_all_rows_fit():
    plan = _load_migration().rollback_for(
        dialect="mysql", current_type="TEXT", max_url_chars=500
    )
    assert plan.needed is True
    assert "VARCHAR(500)" in plan.statement.upper()


@pytest.mark.unit
def test_describe_reports_the_old_column_type_on_sqlite(old_engine):
    module = _load_migration()
    table_exists, current_type = module.describe(old_engine)
    assert table_exists is True
    assert "VARCHAR" in (current_type or "").upper()


@pytest.mark.unit
def test_longest_url_measures_the_real_maximum(old_engine):
    module = _load_migration()
    with old_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO news_digest_items (title, url, published_at) VALUES"
                " ('a', 'https://example.invalid/short', '2026-10-02 10:00:00'),"
                " ('b', :long_url, '2026-10-02 10:00:00')"
            ),
            {"long_url": "https://news.google.com/rss/articles/" + "x" * 480},
        )
    assert module.longest_url(old_engine) == len("https://news.google.com/rss/articles/" + "x" * 480)
