#!/usr/bin/env python
"""数据库备份：SQLite 用 backup API 全量复制并逐表校验行数；MySQL 只给指引、不代跑。

用法（在 backend 目录下）：

    python scripts/backup_db.py                 # 默认写到 backend/backups/（已进 .gitignore）
    python scripts/backup_db.py --out D:/backups

退出码：0 = 备份完成且校验通过；1 = 失败（半成品会删掉，不留下一个看起来成功的文件）；
2 = MySQL 路径本脚本不代跑，已打印 mysqldump 命令模板，需要持有人手动执行。
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path
from urllib.parse import urlsplit

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.utils import timeutil  # noqa: E402

DEFAULT_OUT_DIR = BACKEND_DIR / "backups"


def _sqlite_path(url: str) -> Path | None:
    """从 SQLAlchemy URL 取出 SQLite 文件路径；内存库与非 SQLite 一律返回 None。"""
    if not url.startswith("sqlite") or ":memory:" in url:
        return None
    body = url.split(":///", 1)[1] if ":///" in url else ""
    if not body:
        return None
    path = Path(body)
    return path if path.is_absolute() else BACKEND_DIR / path


def _table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    names = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {
        name: connection.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        for name in names
    }


def backup_sqlite(source: Path, out_dir: Path, *, stamp: str | None = None) -> dict:
    """一致性快照 + 逐表行数校验；任何一项不过就把半成品删掉再抛错。"""
    if not source.exists():
        raise FileNotFoundError(f"SQLite 库文件不存在：{source}")
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = stamp or timeutil.now().strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"{source.stem}-{tag}.db"
    if target.exists():
        raise FileExistsError(f"目标文件已存在，不覆盖：{target}")

    src = sqlite3.connect(str(source))
    try:
        dst = sqlite3.connect(str(target))
        try:
            src.backup(dst)
            expected = _table_counts(src)
            actual = _table_counts(dst)
            integrity = dst.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dst.close()
    finally:
        src.close()

    if expected != actual:
        target.unlink(missing_ok=True)
        raise RuntimeError(f"备份校验失败（逐表行数不一致）：{target} 已删除")
    if integrity != "ok":
        target.unlink(missing_ok=True)
        raise RuntimeError(f"备份校验失败（integrity_check = {integrity}）：{target} 已删除")
    return {"path": target, "tables": len(expected), "rows": sum(expected.values())}


def mysql_guidance(url: str) -> dict:
    """拼出 mysqldump 命令模板 —— 不含密码，也不替持有人执行。"""
    parsed = urlsplit(url.replace("mysql+pymysql", "mysql", 1))
    database = (parsed.path or "/").lstrip("/") or "gold_analysis"
    info = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "user",
        "database": database,
    }
    info["command"] = (
        "mysqldump --single-transaction --routines --triggers --set-gtid-purged=OFF "
        f"-h {info['host']} -P {info['port']} -u {info['user']} -p {info['database']}"
        f" > {info['database']}-backup.sql"
    )
    return info


def run(database_url: str, out_dir: Path) -> tuple[int, list[str]]:
    if not database_url:
        return 1, ["没有配置 DATABASE_URL：无从知道要备份哪个库"]
    if database_url.startswith("sqlite") and ":memory:" not in database_url:
        path = _sqlite_path(database_url)
        if path is None:
            return 1, ["SQLite URL 解析不出文件路径：请检查 DATABASE_URL 的写法"]
        try:
            result = backup_sqlite(path, out_dir)
        except Exception as exc:  # 失败原因照实报，不吞
            return 1, [f"备份失败：{exc}"]
        return 0, [
            f"备份完成：{result['tables']} 张表 / {result['rows']} 行 → {result['path']}"
        ]
    if database_url.startswith("sqlite"):
        return 1, ["这是内存 SQLite（:memory:）：没有可复制的文件，内存库无法这样备份"]
    info = mysql_guidance(database_url)
    return 2, [
        "MySQL 路径本脚本不代跑（避免悄悄备份失败还报成功）。请在库主机上手动执行：",
        f"  {info['command']}",
        "（-p 回车后再输入密码；不要把密码写进命令或脚本。备份文件请落在仓库外。）",
    ]


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover
        pass
    parser = argparse.ArgumentParser(
        description="备份数据库：SQLite 全量复制并逐表校验行数；MySQL 打印 mysqldump 指引"
    )
    parser.add_argument(
        "--out", default=str(DEFAULT_OUT_DIR), help="备份输出目录（默认 backend/backups/）"
    )
    args = parser.parse_args()
    database_url = settings.DATABASE_URL.get_secret_value() if settings.DATABASE_URL else ""
    code, lines = run(database_url, Path(args.out))
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
