"""机构观点迁移脚本：别名行 → 规范行的数据恢复。

这是 2026-10-01 故障的恢复路径：真实目标价只留在别名行（`Goldman Sachs`），
规范行（`高盛 (Goldman Sachs)`）被覆盖成空。脚本必须把它们接上，同时
**不删除任何行**、不覆盖规范行已有的真实数据。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = BACKEND_DIR / "scripts" / "migrate_institution_views.py"

OLD_SCHEMA = """
CREATE TABLE institution_views (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    institution_name VARCHAR(100) NOT NULL,
    logo VARCHAR(50),
    rating VARCHAR(20) NOT NULL,
    target_price FLOAT,
    timeframe VARCHAR(50),
    reasoning TEXT,
    key_points TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
)
"""


def _load_migration():
    spec = importlib.util.spec_from_file_location("migrate_institution_views", SCRIPT_PATH)
    assert spec and spec.loader, f"无法加载 {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    # dataclass 会按 cls.__module__ 反查 sys.modules（脚本里用了 from __future__
    # import annotations），不注册就会在装饰器处抛 AttributeError。
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _seed_old_rows(conn):
    rows = [
        # 被覆盖的规范行：空目标价 + 今天的时间戳
        ("高盛 (Goldman Sachs)", "neutral", None, "暂无", "暂无最新预测", "2026-10-01 06:01:42"),
        ("瑞银 (UBS)", "neutral", None, "暂无", "暂无最新预测", "2026-10-01 06:01:42"),
        # 真实数据仍在的别名行
        ("Goldman Sachs", "bullish", 5400.0, "2026年底", "真实理由 GS", "2026-02-08 20:02:28"),
        ("UBS", "bullish", 5000.0, "2026年", "真实理由 UBS", "2026-02-08 20:02:28"),
        # 不在注册表里的机构：完全不碰
        ("摩根大通 (JPMorgan Chase)", "bullish", 6300.0, "2026年底", "别家机构", "2026-02-06 21:08:07"),
    ]
    for name, rating, price, timeframe, reasoning, updated_at in rows:
        conn.execute(
            text(
                "INSERT INTO institution_views"
                " (institution_name, rating, target_price, timeframe, reasoning, updated_at)"
                " VALUES (:name, :rating, :price, :timeframe, :reasoning, :updated_at)"
            ),
            {
                "name": name, "rating": rating, "price": price,
                "timeframe": timeframe, "reasoning": reasoning, "updated_at": updated_at,
            },
        )


@pytest.fixture
def old_engine():
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(text(OLD_SCHEMA))
        _seed_old_rows(conn)
    return engine


@pytest.mark.unit
def test_plan_adds_columns_backfills_and_copies(old_engine):
    migration = _load_migration()

    plan = migration.build_plan(old_engine)

    assert len(plan.statements) == 2, "两列都要加"
    assert len(plan.backfill) == 5, "所有行的 as_of_date 都要回填"
    copies = {copy.canonical_name: copy for copy in plan.copies}
    assert set(copies) == {"高盛 (Goldman Sachs)", "瑞银 (UBS)"}
    assert copies["高盛 (Goldman Sachs)"].action == "update"
    assert copies["高盛 (Goldman Sachs)"].target_price == 5400.0
    assert copies["高盛 (Goldman Sachs)"].as_of_date.isoformat() == "2026-02-08"


@pytest.mark.unit
def test_apply_restores_real_predictions_without_deleting_rows(old_engine):
    migration = _load_migration()
    migration.apply_migration(old_engine, dry_run=False)

    with old_engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT institution_name, target_price, as_of_date, source"
                " FROM institution_views ORDER BY id"
            )
        ).all()

    assert len(rows) == 5, "迁移不得删除或新增行（两条规范行原地更新）"
    by_name = {row[0]: row for row in rows}

    goldman = by_name["高盛 (Goldman Sachs)"]
    assert goldman[1] == 5400.0, "真实目标价必须回到规范行"
    assert str(goldman[2]) == "2026-02-08", "as_of 取别名行的 updated_at 日期，不是被覆盖那天"
    assert goldman[3] == "legacy"

    ubs = by_name["瑞银 (UBS)"]
    assert ubs[1] == 5000.0
    assert ubs[3] == "legacy"

    # 别名行与别家机构都还在，数据未动
    assert by_name["Goldman Sachs"][1] == 5400.0
    assert by_name["摩根大通 (JPMorgan Chase)"][1] == 6300.0
    assert by_name["摩根大通 (JPMorgan Chase)"][3] is None


@pytest.mark.unit
def test_apply_is_idempotent_and_never_overwrites_real_canonical_data(old_engine):
    migration = _load_migration()
    migration.apply_migration(old_engine, dry_run=False)
    migration.apply_migration(old_engine, dry_run=False)

    with old_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT institution_name, target_price, as_of_date FROM institution_views")
        ).all()

    assert len(rows) == 5
    by_name = {row[0]: row for row in rows}
    assert by_name["高盛 (Goldman Sachs)"][1] == 5400.0
    assert str(by_name["高盛 (Goldman Sachs)"][2]) == "2026-02-08"

    # 规范行与别名行数据不同时，规范行已有的真实数据优先
    with old_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE institution_views SET target_price = 7777, as_of_date = '2026-09-01'"
                " WHERE institution_name = '高盛 (Goldman Sachs)'"
            )
        )
    migration.apply_migration(old_engine, dry_run=False)
    with old_engine.connect() as conn:
        value = conn.execute(
            text(
                "SELECT target_price FROM institution_views"
                " WHERE institution_name = '高盛 (Goldman Sachs)'"
            )
        ).scalar()
    assert value == 7777, "规范行已有真实数据时迁移必须放手"


@pytest.mark.unit
def test_drop_columns_removes_only_the_two_new_columns(old_engine):
    migration = _load_migration()
    migration.apply_migration(old_engine, dry_run=False)

    statements = migration.drop_columns(old_engine, dry_run=False)

    assert len(statements) == 2
    with old_engine.connect() as conn:
        remaining = {col["name"] for col in inspect(old_engine).get_columns("institution_views")}
        count = conn.execute(text("SELECT COUNT(*) FROM institution_views")).scalar()
    assert "as_of_date" not in remaining and "source" not in remaining
    assert count == 5, "回滚只删列，不删行"
