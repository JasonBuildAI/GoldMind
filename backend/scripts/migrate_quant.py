"""量化引擎的数据库迁移：只加不删，幂等。

`schema.sql` 与 `init_db.py` 只覆盖**新建库**的路径：`CREATE TABLE IF NOT EXISTS`
对已经存在的 `predictions` 表是一个空操作，新增的列不会自己出现。
本脚本补上这一段：

1. 建出模型里有、库里没有的表（`factor_observations`、`factor_observation_revisions`、
   `model_evaluations`，以及未来任何新增的表）；
2. 给已存在的表补上模型里有、库里没有的**列**（当前是 `predictions` 的量化列）。

用法：

    python scripts/migrate_quant.py --dry-run   # 只打印将要执行的语句
    python scripts/migrate_quant.py             # 执行
    python scripts/migrate_quant.py --drop --yes  # 回滚：删除量化新增的三张表

`--drop` 只删量化自己建的三张表（含修订流水 `factor_observation_revisions`）；
`predictions` 上新增的列全部可空，保留不影响旧代码读取，因此不删。

核心逻辑都是纯函数（吃一个 engine），便于用临时库测试，不依赖全局连接。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from loguru import logger  # noqa: E402
from sqlalchemy import Engine, inspect, select, text  # noqa: E402

import app.models  # noqa: F401,E402  确保所有模型都已注册到 metadata
from app.database import Base, engine as default_engine  # noqa: E402
from app.models.analysis import (  # noqa: E402
    FactorObservation,
    FactorObservationRevision,
)
from app.utils import timeutil  # noqa: E402


QUANT_TABLES = (
    "factor_observations",
    "factor_observation_revisions",
    "model_evaluations",
)


def missing_columns(bind: Engine, table_name: str) -> list[tuple[str, str]]:
    """返回 [(列名, 类型 SQL)]，仅包含模型里有、库里没有的列。"""
    inspector = inspect(bind)
    existing = {col["name"].lower() for col in inspector.get_columns(table_name)}
    table = Base.metadata.tables[table_name]

    missing: list[tuple[str, str]] = []
    for column in table.columns:
        if column.name.lower() in existing:
            continue
        missing.append((column.name, column.type.compile(dialect=bind.dialect)))
    return missing


def plan_migration(bind: Engine) -> list[str]:
    """列出待执行的语句（不执行）。新旧库、重复执行都安全。"""
    existing_tables = set(inspect(bind).get_table_names())
    statements: list[str] = []

    for table_name in Base.metadata.tables:
        if table_name not in existing_tables:
            statements.append(f"CREATE TABLE {table_name}")

    # 流水表将要新建或已建但空着 → 预告这次会补写多少行
    if "factor_observation_revisions" not in existing_tables:
        if "factor_observations" in existing_tables:
            pending = _count(bind, "factor_observations")
            if pending:
                statements.append(
                    f"INSERT INTO factor_observation_revisions SELECT ... ({pending} 行)"
                )
    elif ledger_backfill_rows(bind):
        statements.append("INSERT INTO factor_observation_revisions SELECT ... (补写流水)")

    if "predictions" in existing_tables:
        for column_name, column_type in missing_columns(bind, "predictions"):
            statements.append(f"ALTER TABLE predictions ADD COLUMN {column_name} {column_type}")

    return statements


LEDGER_INSERT = (
    "INSERT INTO factor_observation_revisions "
    "(factor_key, obs_date, value, source, meta, recorded_at) "
    "SELECT factor_key, obs_date, value, source, meta, "
    "COALESCE(created_at, updated_at) FROM factor_observations"
)


def seed_ledger(bind: Engine) -> int:
    """把观测表里还没有流水行的观测补进流水，返回补写行数。

    为什么不用一条 ``INSERT ... SELECT``：``created_at`` 是
    ``server_default=func.now()``，**SQLite 下那是 UTC**，而应用写 ``recorded_at``
    用的是项目时区。纯 SQL 抄过去就把两个时钟混进了同一列：凌晨 0–8 点写入的值
    会被算到前一天，`--as-of` 于是把「今天才知道的值」放进昨天的面板 ——
    正是流水表要防的前视（红线五）。所以在 Python 侧逐行换算。
    """
    observation = FactorObservation.__table__
    revision = FactorObservationRevision.__table__
    with bind.connect() as conn:
        existing = {
            (row[0], row[1])
            for row in conn.execute(select(revision.c.factor_key, revision.c.obs_date))
        }
        pending = [
            row
            for row in conn.execute(select(observation)).mappings()
            if (row["factor_key"], row["obs_date"]) not in existing
        ]
    if not pending:
        return 0

    rows = [
        {
            "factor_key": row["factor_key"],
            "obs_date": row["obs_date"],
            "value": row["value"],
            "source": row["source"],
            "meta": row["meta"],
            "recorded_at": timeutil.from_utc_naive(row["created_at"] or row["updated_at"])
            or timeutil.now_naive(),
        }
        for row in pending
    ]
    with bind.begin() as conn:
        conn.execute(revision.insert(), rows)
    return len(rows)


def _count(bind: Engine, table: str) -> int:
    """SQLAlchemy 2.x：Engine 上没有 execute，必须开连接。"""
    with bind.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)


def ledger_backfill_rows(bind: Engine) -> int:
    """还缺多少条流水：观测表里有、流水表里没有的那些。

    为什么必须在迁移里做：`load_series_as_of` 只认流水表。老库升级后如果流水表是空的，
    `--as-of` 会**静默返回空面板** —— 看着能跑、其实什么都没算，这是最坏的一种失败。

    为什么不能只判「流水表是不是全空」：`main.py` 启动即 `create_all` 建出**空**表，
    随后任一次同步都会追加几行流水，于是「全空才补」在最常见的升级路径上失效 ——
    历史观测永远进不了流水，`--as-of` 给出的是**残缺面板**而不是空面板，
    更难发现。所以按 `(factor_key, obs_date)` 逐条比对，只补缺的。

    诚实的边界：补出来的 `recorded_at` 是那一行**进入本系统**的时间。历史回填是一次性
    写进来的，所以这些行的时点都落在回填那天；问更早的日期得到空面板是**正确**的答案
    （那时我们确实还不知道这些值），不是数据丢失。
    """
    tables = set(inspect(bind).get_table_names())
    if "factor_observation_revisions" not in tables or "factor_observations" not in tables:
        return 0
    observation = FactorObservation.__table__
    revision = FactorObservationRevision.__table__
    with bind.connect() as conn:
        existing = {
            (row[0], row[1])
            for row in conn.execute(select(revision.c.factor_key, revision.c.obs_date))
        }
        return sum(
            1
            for row in conn.execute(
                select(observation.c.factor_key, observation.c.obs_date)
            )
            if (row[0], row[1]) not in existing
        )


def apply_migration(bind: Engine, dry_run: bool = False) -> list[str]:
    """执行迁移；返回实际（或将要，dry_run 时）执行的语句列表。"""
    statements = plan_migration(bind)
    if dry_run:
        return statements

    # 新表交给 create_all —— 它只建缺的表，不会碰已有表。
    Base.metadata.create_all(bind=bind)

    # 新列逐列检查后再 ALTER，重复执行安全。
    with bind.begin() as conn:
        for column_name, column_type in missing_columns(bind, "predictions"):
            conn.execute(text(f"ALTER TABLE predictions ADD COLUMN {column_name} {column_type}"))

    # 老库的观测补写流水（只在流水表为空时执行，重复运行安全）。
    pending = ledger_backfill_rows(bind)
    if pending:
        seeded = seed_ledger(bind)
        statements.append(f"INSERT INTO factor_observation_revisions SELECT ... ({seeded} 行)")

    return statements


def drop_quant_tables(bind: Engine) -> list[str]:
    """删除量化新增的表；不动既有表与数据。

    修订流水也在其中：它是回滚单位的一部分，留着它等于回滚不干净。
    """
    existing_tables = set(inspect(bind).get_table_names())
    dropped: list[str] = []
    with bind.begin() as conn:
        for table in QUANT_TABLES:
            if table in existing_tables:
                conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                dropped.append(table)
    return dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="量化引擎数据库迁移（幂等，只加不删）")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要执行的语句")
    parser.add_argument("--drop", action="store_true", help="回滚：删除量化新增的表")
    parser.add_argument("--yes", action="store_true", help="与 --drop 搭配，确认执行删除")
    args = parser.parse_args(argv)

    if args.drop:
        if not args.yes:
            logger.error(
                "--drop 会删除 factor_observations、factor_observation_revisions、"
                "model_evaluations 三张表及其数据。"
                "确认后请加 --yes 重跑。"
            )
            return 2
        for table in drop_quant_tables(default_engine):
            logger.warning(f"[迁移] 已删除表 {table}")
        return 0

    statements = apply_migration(default_engine, dry_run=args.dry_run)

    if not statements:
        logger.info("[迁移] 无待执行项：库结构已经是最新。")
        return 0

    for statement in statements:
        logger.info(f"[迁移] {statement}")
    if args.dry_run:
        logger.info("[迁移] --dry-run：未执行。")
    else:
        logger.info("[迁移] 完成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
