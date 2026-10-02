"""每日运维自动化（2.0.2 全自动运行）：自动备份 + 数据体检。

`scripts/backup_db.py` 与 `scripts/check_data_sanity.py` 从此是**可选**的运维
入口；调度器每天自动跑一遍，结果写入进程内状态并同步日志：

- `backup_now()` 只对 SQLite 做文件级备份（复用 backup_db 的一致性快照 +
  逐表行数校验），保留最近 ``keep`` 份；MySQL 如实返回 skipped 并说明
  「未代跑 mysqldump」——不假装备份成功；内存库（测试）同样如实说明。
- `data_health_check()` 调用 `check_data_sanity.run()`：未来日期这类安全清理
  只在 `fix=True` 时自动执行，其余问题只报告不动手。
- `daily_maintenance()` 的硬约定：**先备份、后体检**。备份没有真正完成
  （skipped / failed / AUTO_BACKUP=false）时，体检一律以 fix=False 只读运行 ——
  没有任何可回滚的备份就不做自动修复。
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from loguru import logger

from app.config import settings
from app.utils import timeutil

BACKUP_KEEP = 7

_STATE_LOCK = threading.Lock()
_state: dict = {"last_run_at": None, "backup": None, "sanity": None}


def _prune(backup_dir: Path, stem: str, keep: int) -> list[str]:
    """只清理**本通道**产生的备份（goldmind-*.db），迁移前备份 bootstrap-*.db 不动。"""
    files = sorted(backup_dir.glob(f"{stem}-*.db"))
    pruned: list[str] = []
    for old in files[:-keep] if keep > 0 else files:
        try:
            old.unlink()
            pruned.append(old.name)
        except OSError as exc:
            logger.warning(f"[维护] 清理旧备份失败（{old.name}）：{exc}")
    return pruned


def backup_now(*, database_url: Optional[str] = None, keep: int = BACKUP_KEEP) -> dict:
    """SQLite 全量备份并保留最近 ``keep`` 份；MySQL / 内存库如实跳过。"""
    from app import bootstrap
    from scripts import backup_db

    url = database_url if database_url is not None else settings.DATABASE_URL.get_secret_value()
    if not url:
        return {"status": "failed", "reason": "没有配置 DATABASE_URL", "path": None, "pruned": []}
    if url.startswith("sqlite"):
        source = backup_db._sqlite_path(url)
        if source is None:
            return {
                "status": "skipped",
                "reason": "内存 SQLite 没有可复制的文件（测试 / 临时模式），不做文件级备份",
                "path": None,
                "pruned": [],
            }
        if not source.exists():
            return {
                "status": "failed",
                "reason": f"SQLite 库文件不存在：{source.name}",
                "path": None,
                "pruned": [],
            }
        try:
            result = backup_db.backup_sqlite(source, bootstrap.BACKUP_DIR)
        except Exception as exc:  # noqa: BLE001 —— 失败照实报告，绝不静默
            return {
                "status": "failed",
                "reason": f"{type(exc).__name__}: {exc}",
                "path": None,
                "pruned": [],
            }
        pruned = _prune(bootstrap.BACKUP_DIR, source.stem, keep)
        return {
            "status": "done",
            "path": result["path"].name,
            "tables": result["tables"],
            "rows": result["rows"],
            "kept": keep,
            "pruned": pruned,
            "reason": None,
        }

    return {
        "status": "skipped",
        "reason": "MySQL 自动备份不代跑 mysqldump（备份指引见 scripts/backup_db.py），未备份",
        "path": None,
        "pruned": [],
    }


def data_health_check(*, fix: bool = True, long_db: Optional[Path] = None) -> dict:
    """数据体检；``fix=True`` 只允许「未来日期清理」这类安全修复。"""
    from app import bootstrap
    from app.services.store_alignment import DEFAULT_LONG_DB
    from scripts import check_data_sanity

    bootstrap._ensure_sys_path()
    long_path = Path(long_db) if long_db is not None else DEFAULT_LONG_DB
    try:
        code, lines = check_data_sanity.run(
            database_url=settings.DATABASE_URL.get_secret_value(),
            long_db=long_path if long_path.exists() else None,
            fix=fix,
            strict=False,
        )
    except Exception as exc:  # noqa: BLE001 —— 体检异常如实记录，不影响其它任务
        return {
            "status": "failed",
            "exit_code": None,
            "fixed": False,
            "reason": f"{type(exc).__name__}: {exc}",
            "lines": [],
        }
    return {
        "status": "ok" if code == 0 else "problems",
        "exit_code": code,
        "fixed": bool(fix),
        "reason": None if code == 0 else (lines[-1] if lines else "体检发现问题"),
        "lines": lines,
    }


def daily_maintenance(*, database_url: Optional[str] = None, fix: bool = True) -> dict:
    """先备份、后体检；备份未真正完成时体检只读。返回并记录本次结果。"""
    if settings.AUTO_BACKUP:
        backup = backup_now(database_url=database_url)
    else:
        backup = {
            "status": "disabled",
            "reason": "AUTO_BACKUP=false：未做备份",
            "path": None,
            "pruned": [],
        }
    can_fix = fix and backup.get("status") == "done"
    sanity = data_health_check(fix=can_fix)
    result = {
        "at": timeutil.now_iso(),
        "backup": backup,
        "sanity": sanity,
        "auto_fix_applied": bool(can_fix and sanity.get("fixed")),
    }
    with _STATE_LOCK:
        _state["last_run_at"] = result["at"]
        _state["backup"] = backup
        _state["sanity"] = sanity
    if backup["status"] != "done":
        logger.warning(f"[维护] 备份未完成（{backup['status']}）：{backup.get('reason')}")
    return result


def snapshot() -> dict:
    with _STATE_LOCK:
        return {
            "backup_keep": BACKUP_KEEP,
            "last_run_at": _state["last_run_at"],
            "backup": dict(_state["backup"]) if _state["backup"] else None,
            "sanity": dict(_state["sanity"]) if _state["sanity"] else None,
        }