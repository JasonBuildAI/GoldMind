"""老库升级路径：`scripts/migrate_quant.py` 只加不删、幂等。

背景：`schema.sql` 的 `CREATE TABLE IF NOT EXISTS` 对已存在的 `predictions`
是空操作，新列不会自己出现。已部署的库必须走迁移脚本，而这条路径此前没有任何
测试覆盖 —— 上线时静默少一列，接口会在运行期才炸。

这里用一个**独立的临时 SQLite 库**模拟老库，不碰测试主库。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parents[2]

QUANT_COLUMNS = {
    "direction",
    "horizon_days",
    "as_of",
    "base_price",
    "score",
    "expected_return",
    "uncertainty",
    "model_version",
}


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "migrate_quant_under_test", BACKEND_DIR / "scripts" / "migrate_quant.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def migration():
    return _load_migration_module()


@pytest.fixture
def old_engine(tmp_path):
    """模拟一个升级前的库：只有旧版 predictions 表，没有任何量化表。"""
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE predictions ("
                "id INTEGER PRIMARY KEY, prediction_type VARCHAR(50) NOT NULL, "
                "target_price FLOAT NOT NULL, confidence FLOAT, timeframe VARCHAR(50), "
                "reasoning TEXT, factors JSON, created_at TIMESTAMP)"
            )
        )
        conn.execute(
            text("INSERT INTO predictions (prediction_type, target_price) VALUES ('up', 4000.0)")
        )
    return engine


@pytest.mark.unit
def test_plan_finds_new_tables_and_missing_columns(migration, old_engine):
    statements = migration.plan_migration(old_engine)
    joined = "\n".join(statements)

    assert "CREATE TABLE factor_observations" in joined
    assert "CREATE TABLE model_evaluations" in joined
    for column in sorted(QUANT_COLUMNS):
        assert f"ADD COLUMN {column} " in joined, f"计划里缺少 {column} 的 ALTER"


@pytest.mark.unit
def test_apply_adds_everything_and_keeps_existing_rows(migration, old_engine):
    migration.apply_migration(old_engine)

    inspector = inspect(old_engine)
    columns = {col["name"].lower() for col in inspector.get_columns("predictions")}
    assert QUANT_COLUMNS <= columns

    tables = set(inspector.get_table_names())
    assert {"factor_observations", "model_evaluations"} <= tables

    with old_engine.connect() as conn:
        row = conn.execute(text("SELECT prediction_type, target_price FROM predictions")).one()
    assert row == ("up", 4000.0), "迁移不得改动既有数据"


@pytest.mark.unit
def test_apply_is_idempotent(migration, old_engine):
    first = migration.apply_migration(old_engine)
    assert first, "第一次迁移应当有事可做"
    second = migration.apply_migration(old_engine)
    assert second == [], f"第二次迁移不应再产生语句，实际：{second}"


@pytest.mark.unit
def test_dry_run_changes_nothing(migration, old_engine):
    statements = migration.apply_migration(old_engine, dry_run=True)
    assert statements

    inspector = inspect(old_engine)
    columns = {col["name"].lower() for col in inspector.get_columns("predictions")}
    assert not (QUANT_COLUMNS & columns), "dry-run 不应真的加列"
    assert "factor_observations" not in set(inspector.get_table_names())


@pytest.mark.unit
def test_drop_removes_only_quant_tables(migration, old_engine):
    migration.apply_migration(old_engine)
    dropped = migration.drop_quant_tables(old_engine)

    assert set(dropped) == {
        "factor_observations",
        "factor_observation_revisions",
        "model_evaluations",
    }
    inspector = inspect(old_engine)
    assert "predictions" in set(inspector.get_table_names())
    with old_engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM predictions")).scalar() == 1


@pytest.mark.unit
def test_drop_requires_explicit_confirmation(migration):
    assert migration.main(["--drop"]) == 2
