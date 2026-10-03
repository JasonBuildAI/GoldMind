"""消息板块译文列迁移脚本的判定与守卫（不依赖 MySQL）。

2026-10-03 起消息板块存中文译文（`title_zh` / `brief_zh` / `translated_at` /
`translation_model`）。新库按新模型建表，**老库不会自动补列** ——
`Base.metadata.create_all` 只建缺失的表，不改既有表。不补列，抓取到第一条消息
就会 `no such column: news_digest_items.title_zh`。

本文件钉住三件事：判定函数什么时候该加列；`apply` 在真实 SQLite 上真的加上了且幂等；
**回滚会丢译文时必须拒绝**。另外把「模型 ↔ schema.sql ↔ 引导注册表」三者的译文列
钉在一起 —— 文档化的安装路径（Docker / init_db.py）走的是 schema.sql。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
REPO_ROOT = BACKEND_DIR.parent
SCRIPT_PATH = BACKEND_DIR / "scripts" / "migrate_news_digest_translation.py"
SCHEMA_SQL = BACKEND_DIR / "schema.sql"

OLD_SCHEMA = """
CREATE TABLE news_digest_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    source VARCHAR(100) NOT NULL,
    source_key VARCHAR(100) NOT NULL,
    authority_tier INTEGER NOT NULL DEFAULT 2,
    url TEXT NOT NULL,
    published_at TIMESTAMP NOT NULL
)
"""

EXPECTED_COLUMNS = ("title_zh", "brief_zh", "translated_at", "translation_model")


def _load_migration():
    spec = importlib.util.spec_from_file_location("migrate_news_digest_translation", SCRIPT_PATH)
    assert spec and spec.loader, f"无法加载 {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    # dataclass 会按 cls.__module__ 反查 sys.modules，不注册会在装饰器处抛 AttributeError。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def old_engine():
    """模拟「上个版本建的库」：只有英文列。"""
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(OLD_SCHEMA))
    return engine


def _columns(engine) -> set[str]:
    return {column["name"].lower() for column in inspect(engine).get_columns("news_digest_items")}


# --------------------------------------------------------------------------- #
# 判定函数
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_plan_adds_the_four_translation_columns():
    plan = _load_migration().plan_for(table_exists=True, existing_columns=["id", "title", "url"])
    assert plan.needed is True
    assert len(plan.statements) == 4
    joined = " ".join(plan.statements).lower()
    for name in EXPECTED_COLUMNS:
        assert f"add column {name} " in joined


@pytest.mark.unit
def test_plan_is_noop_when_all_columns_exist():
    plan = _load_migration().plan_for(
        table_exists=True, existing_columns=["id", *EXPECTED_COLUMNS]
    )
    assert plan.needed is False
    assert "已存在" in plan.reason


@pytest.mark.unit
def test_plan_adds_only_the_missing_columns():
    """半迁移状态（上次执行中途失败）只补缺的那几个。"""
    plan = _load_migration().plan_for(
        table_exists=True, existing_columns=["id", "title_zh", "brief_zh"]
    )
    assert plan.needed is True
    joined = " ".join(plan.statements).lower()
    assert "add column translated_at" in joined
    assert "add column translation_model" in joined
    assert "add column title_zh" not in joined


@pytest.mark.unit
def test_plan_is_noop_when_table_is_missing():
    plan = _load_migration().plan_for(table_exists=False, existing_columns=[])
    assert plan.needed is False
    assert "不存在" in plan.reason


@pytest.mark.unit
def test_rollback_refuses_when_translations_exist():
    plan = _load_migration().rollback_for(
        table_exists=True, existing_columns=list(EXPECTED_COLUMNS), translated_rows=7
    )
    assert plan.needed is False
    assert "7" in plan.reason
    assert "拒绝执行" in plan.reason


@pytest.mark.unit
def test_rollback_returns_statements_when_no_translations():
    plan = _load_migration().rollback_for(
        table_exists=True, existing_columns=list(EXPECTED_COLUMNS), translated_rows=0
    )
    assert plan.needed is True
    assert len(plan.statements) == 4
    assert all("drop column" in statement.lower() for statement in plan.statements)


# --------------------------------------------------------------------------- #
# 真的在库上跑
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_apply_adds_columns_and_is_idempotent(old_engine):
    module = _load_migration()
    assert not (_columns(old_engine) & set(EXPECTED_COLUMNS))

    first = module.apply(old_engine)
    assert "已执行" in first
    assert set(EXPECTED_COLUMNS) <= _columns(old_engine)

    # 第二次必须是「无需迁移」，不能重复 ALTER（MySQL 上重复加列会报 1060）
    second = module.apply(old_engine)
    assert "已执行" not in second
    assert "已存在" in second


@pytest.mark.unit
def test_apply_keeps_existing_rows(old_engine):
    """加列不删行：旧数据必须原样在。"""
    with old_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO news_digest_items (title, source, source_key, authority_tier, url, published_at)"
                " VALUES ('Gold hits record', 'Reuters', 'reuters', 1, 'https://example.invalid/a',"
                " '2026-10-02 10:00:00')"
            )
        )
    _load_migration().apply(old_engine)
    with old_engine.connect() as conn:
        rows = conn.execute(text("SELECT title, title_zh FROM news_digest_items")).all()
    assert rows == [("Gold hits record", None)]


@pytest.mark.unit
def test_translated_row_count_reads_the_real_column(old_engine):
    module = _load_migration()
    module.apply(old_engine)
    assert module.translated_row_count(old_engine) == 0
    with old_engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO news_digest_items (title, source, source_key, authority_tier, url,"
                " published_at, title_zh) VALUES ('a', 'Reuters', 'reuters', 1,"
                " 'https://example.invalid/b', '2026-10-02 10:00:00', '金价创纪录')"
            )
        )
    assert module.translated_row_count(old_engine) == 1


# --------------------------------------------------------------------------- #
# 三处声明必须一致：模型 ↔ schema.sql ↔ 引导注册表
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_model_declares_the_translation_columns():
    import app.models  # noqa: F401  确保模型注册到 metadata
    from app.database import Base

    table = Base.metadata.tables["news_digest_items"]
    missing = [name for name in EXPECTED_COLUMNS if name not in table.columns]
    assert not missing, f"模型里缺少译文列：{missing}"
    # 全部可空：NULL 的准确含义是「还没有译文」
    nullable = [name for name in EXPECTED_COLUMNS if not table.columns[name].nullable]
    assert not nullable, f"译文列必须可空，这些不是：{nullable}"


@pytest.mark.unit
def test_schema_sql_declares_the_translation_columns():
    """Docker / init_db.py 走的是 schema.sql，缺列那条安装路径就跑不起来。"""
    text_sql = SCHEMA_SQL.read_text(encoding="utf-8")
    match = re.search(
        r"CREATE TABLE IF NOT EXISTS news_digest_items \((.*?)\) ENGINE", text_sql, re.S
    )
    assert match, "schema.sql 里找不到 news_digest_items 的建表语句"
    body = match.group(1)
    missing = [name for name in EXPECTED_COLUMNS if not re.search(rf"\b{name}\b", body)]
    assert not missing, f"schema.sql 的 news_digest_items 缺少：{missing}"


@pytest.mark.unit
def test_bootstrap_registers_the_migration():
    """没注册进引导注册表 = 老库永远不会补列（而新库测试全绿）。"""
    from app.bootstrap import MIGRATIONS_BY_KEY

    migration = MIGRATIONS_BY_KEY.get("news-digest-translation-columns")
    assert migration is not None, "引导注册表里没有译文列迁移"
    assert migration.module == "scripts.migrate_news_digest_translation"
    assert migration.entry == "apply"
    assert migration.alters_existing is True, "会改既有表，SQLite 下必须先备份再迁移"
