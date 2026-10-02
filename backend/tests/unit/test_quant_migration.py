"""老库升级路径：`scripts/migrate_quant.py` 只加不删、幂等。

背景：`schema.sql` 的 `CREATE TABLE IF NOT EXISTS` 对已存在的 `predictions`
是空操作，新列不会自己出现。已部署的库必须走迁移脚本，而这条路径此前没有任何
测试覆盖 —— 上线时静默少一列，接口会在运行期才炸。

这里用一个**独立的临时 SQLite 库**模拟老库，不碰测试主库。
"""
from __future__ import annotations

import importlib.util
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app.models.analysis import FactorObservationRevision
from app.utils import timeutil

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


@pytest.fixture
def populated_engine(tmp_path):
    """一个已经跑过量化 v4 的库：有 factor_observations（带数据），没有流水表。"""
    from app.models.analysis import FactorObservation

    engine = create_engine(f"sqlite:///{tmp_path / 'v4.db'}")
    FactorObservation.__table__.create(engine)
    with engine.begin() as conn:
        for index, (key, day, value) in enumerate(
            [("real_yield_10y", "2026-01-05", 1.9), ("real_yield_10y", "2026-01-06", 2.0),
             ("vix", "2026-01-05", 17.5)]
        ):
            conn.execute(
                text(
                    "INSERT INTO factor_observations (factor_key, obs_date, value, source, "
                    "created_at, updated_at) VALUES (:k, :d, :v, 's', '2026-03-01 08:00:00', "
                    "'2026-03-01 08:00:00')"
                ),
                {"k": key, "d": day, "v": value},
            )
    return engine


@pytest.mark.unit
def test_plan_previews_the_ledger_backfill(migration, populated_engine):
    joined = chr(10).join(migration.plan_migration(populated_engine))
    assert "factor_observation_revisions" in joined
    assert "3 行" in joined, f"计划里没有预告要补写的行数：{joined}"


@pytest.mark.unit
def test_migration_seeds_the_ledger_from_existing_observations(migration, populated_engine):
    """老库升级必须补写流水 —— 否则 `--as-of` 会静默返回空面板。

    变异验证：删掉 apply_migration 里 `if pending:` 那段补写，本测试第一条断言必红
    （流水表建出来了但是空的）；把 recorded_at 写成 NOW() 而不是 created_at，
    第二条断言必红（重建历史时点就错了）。
    """
    migration.apply_migration(populated_engine)
    from sqlalchemy import inspect as sa_inspect

    assert "factor_observation_revisions" in sa_inspect(populated_engine).get_table_names()
    revision = FactorObservationRevision.__table__
    with populated_engine.connect() as conn:
        rows = conn.execute(
            select(
                revision.c.factor_key,
                revision.c.obs_date,
                revision.c.value,
                revision.c.recorded_at,
            ).order_by(revision.c.factor_key, revision.c.obs_date)
        ).all()
    assert len(rows) == 3
    # created_at 是 server_default（SQLite = UTC）：抄进流水前必须换算成项目时区，
    # 否则同一列里混两个时钟，凌晨 0–8 点写入的值会被算进前一天的面板
    expected = timeutil.from_utc_naive(datetime(2026, 3, 1, 8, 0, 0))
    assert {row[3] for row in rows} == {expected}, "recorded_at 必须是项目时区的写入时点"
    assert [row[0] for row in rows] == ["real_yield_10y", "real_yield_10y", "vix"]

    # 重复运行不再补写（幂等）
    migration.apply_migration(populated_engine)
    with populated_engine.begin() as conn:
        assert int(conn.execute(text("SELECT COUNT(*) FROM factor_observation_revisions")).scalar()) == 3


@pytest.mark.unit
def test_ledger_backfill_fills_only_the_missing_observations(migration, populated_engine):
    """流水表非空、但观测缺流水时，必须**只补缺的那些**。

    「流水表全空才补」这条守卫在最常见的升级路径上会失效：启动时 `create_all`
    先建出空表，随后任一次同步都会追加几行流水 —— 于是 68k 历史观测永远进不了
    流水，`--as-of` 静默给出只剩近期窗口的残缺面板，而且不会报错。

    变异验证：把 `ledger_backfill_rows` 改回「流水表非空即返回 0」，第一条断言必红
    （应补 2 行却报 0 行）。
    """
    revision = FactorObservationRevision.__table__
    migration.Base.metadata.create_all(bind=populated_engine)  # 建出（空的）流水表
    with populated_engine.begin() as conn:
        conn.execute(
            revision.insert(),
            [
                {
                    "factor_key": "real_yield_10y",
                    "obs_date": date(2026, 1, 5),
                    "value": 1.9,
                    "source": "s",
                    "meta": None,
                    "recorded_at": datetime(2026, 3, 1, 16, 0, 0),
                }
            ],
        )

    # 3 条观测里有 1 条已经有流水 → 还缺 2 条
    assert migration.ledger_backfill_rows(populated_engine) == 2

    migration.apply_migration(populated_engine)
    with populated_engine.connect() as conn:
        rows = conn.execute(
            select(revision.c.factor_key, revision.c.obs_date, revision.c.recorded_at)
        ).all()
    assert len(rows) == 3
    # 既有那条流水原样保留，不被重写
    kept = [
        row for row in rows if (row[0], row[1]) == ("real_yield_10y", date(2026, 1, 5))
    ]
    assert len(kept) == 1
    assert kept[0][2] == datetime(2026, 3, 1, 16, 0, 0)


@pytest.mark.unit
def test_point_in_time_panel_matches_the_current_panel_after_backfill(migration, populated_engine):
    """补写之后，「按最新时点重建」必须与「读当前值」逐值相同 —— 否则流水就是二等数据。"""
    from datetime import date

    from sqlalchemy.orm import sessionmaker

    from app.services.quant import storage

    migration.apply_migration(populated_engine)
    session = sessionmaker(bind=populated_engine)()
    try:
        rebuilt = storage.load_series_as_of(session, date(2026, 3, 1))
        current = storage.load_all(session)
        assert set(rebuilt) == set(current)
        for key in rebuilt:
            assert rebuilt[key].sort_index().tolist() == current[key].sort_index().tolist(), key
        # 早于「我们知道这些值」的那天，诚实地给空面板
        assert storage.load_series_as_of(session, date(2026, 2, 28)) == {}
    finally:
        session.close()

