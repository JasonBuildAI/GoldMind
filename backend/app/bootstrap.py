"""启动引导：把「填好 ``backend/.env`` → 启动」变成系统唯一的运行入口。

人工步骤（``init_db.py`` / ``backfill_quant.py`` / 各 ``migrate_*.py`` / 体检）从此全部是
**可选运维工具**；启动引导按阶段自动完成，幂等、可中断续跑、失败下轮重试。

本模块当前覆盖第一段：**自动迁移**。

- 迁移注册表（``MIGRATIONS``）+ ``schema_migrations`` 表：应用过的迁移记录在案，
  重复启动不会重放；
- 幂等：每条迁移沿用原脚本的纯函数判定（按「当前库长什么样」决定动不动手），
  迁移实现与运维 CLI 共用同一份代码（``backend/scripts/``），不抄第二遍口径；
- 备份：SQLite 在**会改动既有表**的迁移执行前，把库文件复制到
  ``backend/backups/``（.gitignore 覆盖）；备份失败即中止该条迁移 ——
  宁可停在旧状态，也不在无备份的情况下改库；
- MySQL：只做加列 / 建表 / 改列型，不删除任何数据；自动备份不代跑 mysqldump
  （如实标注为不支持，见 README「全自动运行」）。

后续阶段（覆盖度检测、冷启动回填、首轮分析）挂在同一个入口上，见
``docs/specs/2026-10-03-2.0.2-整改与自动化.md`` 第二节。
"""
from __future__ import annotations

import importlib
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from loguru import logger
from sqlalchemy import Engine, inspect, text

from app.utils import timeutil

BACKEND_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BACKEND_DIR / "backups"

# SQLite 迁移前备份保留份数（自动每日备份的保留策略另见调度层）
MIGRATION_BACKUP_KEEP = 20

REGISTRY_TABLE = "schema_migrations"


@dataclass(frozen=True)
class Migration:
    """一条迁移：key 是记录在 ``schema_migrations`` 里的唯一标识。

    ``alters_existing`` 表示「会改动既有表」—— SQLite 下这类迁移执行前必须先备份。
    ``applier`` 给定时优先使用（少数迁移需要方言分支），否则按
    ``module.entry`` 导入调用（与运维 CLI 同一份实现）。
    """

    key: str
    description: str
    module: str
    alters_existing: bool = True
    entry: str = "apply_migration"
    applier: Optional[Callable[[Engine], str]] = None


def _apply_enum_values(engine: Engine) -> str:
    """枚举列取值修正：MySQL 专属（SQLite 不做 ENUM 大小写比较）。"""
    if engine.dialect.name != "mysql":
        return f"{engine.dialect.name} 下不适用（枚举取值只有 MySQL 需要修正）"
    _ensure_sys_path()
    from scripts import fix_enum_columns

    return "；".join(fix_enum_columns.apply(engine))


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        key="quant-tables",
        description="建出量化三表、补 predictions 的量化列、补写修订流水",
        module="scripts.migrate_quant",
    ),
    Migration(
        key="institution-view-columns",
        description="机构观点表补列（as_of_date / source）",
        module="scripts.migrate_institution_views",
    ),
    Migration(
        key="news-digest-url-text",
        description="news_digest_items.url 从 VARCHAR(500) 迁到 TEXT",
        module="scripts.migrate_news_digest_url",
        entry="apply",
    ),
    Migration(
        key="enum-values-uppercase",
        description="枚举列取值改为与模型一致的大写（仅 MySQL）",
        module="scripts.fix_enum_columns",
        applier=_apply_enum_values,
    ),
)

MIGRATIONS_BY_KEY = {migration.key: migration for migration in MIGRATIONS}

assert len(MIGRATIONS_BY_KEY) == len(MIGRATIONS), "迁移 key 必须唯一"


def _ensure_sys_path() -> None:
    """scripts/ 不在 app 包内：导入前确保 backend 在 sys.path 上。"""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))


def ensure_registry(engine: Engine) -> None:
    """建出 ``schema_migrations`` 表（幂等）。"""
    with engine.begin() as conn:
        conn.execute(
            text(
                f"CREATE TABLE IF NOT EXISTS {REGISTRY_TABLE} ("
                "  key VARCHAR(64) NOT NULL PRIMARY KEY,"
                "  description TEXT NULL,"
                "  note TEXT NULL,"
                "  applied_at DATETIME NOT NULL"
                ")"
            )
        )


def applied_keys(engine: Engine) -> set[str]:
    ensure_registry(engine)
    with engine.connect() as conn:
        rows = conn.execute(text(f"SELECT key FROM {REGISTRY_TABLE}")).all()
    return {str(row[0]) for row in rows}


def _record(engine: Engine, migration: Migration, note: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                f"INSERT INTO {REGISTRY_TABLE} (key, description, note, applied_at) "
                "VALUES (:key, :description, :note, :applied_at)"
            ),
            {
                "key": migration.key,
                "description": migration.description,
                "note": note[:2000],
                "applied_at": timeutil.now_naive().isoformat(sep=" ", timespec="seconds"),
            },
        )


def _sqlite_file(engine: Engine) -> Optional[Path]:
    """SQLite 库文件路径；内存库返回 None。"""
    if engine.dialect.name != "sqlite":
        return None
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    return Path(database)


def backup_sqlite(engine: Engine, migration_key: str) -> Optional[Path]:
    """迁移前备份 SQLite 库文件；非 SQLite / 内存库返回 None。

    备份失败会抛出异常 —— 调用方（``run_migrations``）据此拒绝执行迁移。
    """
    source = _sqlite_file(engine)
    if source is None:
        return None
    if not source.exists():  # 全新库，还没有可备份的内容
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = timeutil.now_naive().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"{source.stem}-{stamp}-pre-{migration_key}.db"
    shutil.copy2(source, target)
    logger.info(f"[引导] 迁移前备份：{target}")
    _prune_migration_backups()
    return target


def _prune_migration_backups() -> None:
    files = sorted(BACKUP_DIR.glob("*-pre-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    for stale in files[MIGRATION_BACKUP_KEEP:]:
        try:
            stale.unlink()
        except OSError as exc:  # 清理失败不影响迁移；下一轮再清
            logger.warning(f"[引导] 备份清理失败：{stale}（{exc}）")


def _describe(result) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, (list, tuple)):
        return "；".join(str(item) for item in result) or "无操作"
    if hasattr(result, "statements"):
        # 计划对象（如机构观点迁移）：只记计数 —— note 要能一眼读懂，不是整份计划的倾倒场
        backfill = getattr(result, "backfill", [])
        copies = getattr(result, "copies", [])
        return (
            f"{len(result.statements)} 条 DDL；回填 {len(backfill)} 行；"
            f"机构观点对齐 {len(copies)} 条"
        )
    return str(result)


def _apply(migration: Migration, engine: Engine) -> str:
    if migration.applier is not None:
        return _describe(migration.applier(engine))
    _ensure_sys_path()
    module = importlib.import_module(migration.module)
    function = getattr(module, migration.entry)
    return _describe(function(engine))


def run_migrations(engine: Engine) -> list[dict]:
    """应用尚未记录的迁移；返回逐条结果（applied / already / failed）。

    失败的迁移**不记录**：下一次启动会重试（错误原文进日志与返回值，
    页面在 /health 里能看到「引导停在哪一步」）。
    """
    ensure_registry(engine)
    done = applied_keys(engine)
    results: list[dict] = []
    for migration in MIGRATIONS:
        if migration.key in done:
            results.append({"key": migration.key, "status": "already"})
            continue
        backup: Optional[Path] = None
        try:
            if migration.alters_existing:
                backup = backup_sqlite(engine, migration.key)
            note = _apply(migration, engine)
        except Exception as exc:  # noqa: BLE001 —— 迁移失败必须是「可重试」而不是崩溃
            logger.error(f"[引导] 迁移 {migration.key} 失败（未记录，下轮重试）：{exc}")
            results.append(
                {"key": migration.key, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        _record(engine, migration, note)
        logger.info(f"[引导] 迁移 {migration.key} 完成：{note[:200]}")
        results.append(
            {
                "key": migration.key,
                "status": "applied",
                "note": note,
                "backup": str(backup) if backup else None,
            }
        )
    return results


def registry_snapshot(engine: Engine) -> dict:
    """给 /health 用的迁移进度快照。"""
    done = applied_keys(engine)
    return {
        "applied": sorted(done),
        "pending": [migration.key for migration in MIGRATIONS if migration.key not in done],
        "total": len(MIGRATIONS),
    }


__all__ = [
    "BACKUP_DIR",
    "MIGRATIONS",
    "MIGRATIONS_BY_KEY",
    "Migration",
    "applied_keys",
    "backup_sqlite",
    "ensure_registry",
    "registry_snapshot",
    "run_migrations",
]
