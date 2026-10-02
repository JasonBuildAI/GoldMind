"""`init_db.py` 的 SQLite 路径：一条命令建出全部表（README 快速开始的第一步）。

用子进程真跑一次脚本，而不是 import 它的函数 —— 这样「README 里的命令」
与测试断言的是同一条路径。SKIP_SEED=1 保证不联网、不抓数据。
"""
from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]

EXPECTED_TABLES = {
    "gold_prices",
    "dollar_index",
    "gold_news",
    "market_factors",
    "institution_views",
    "predictions",
    "factor_observations",
    "model_evaluations",
}


@pytest.mark.integration
def test_init_db_creates_every_table_on_sqlite(tmp_path):
    db_path = tmp_path / "init.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "SKIP_SEED": "1",
        "PYTHONIOENCODING": "utf-8",
    }
    result = subprocess.run(
        [sys.executable, "init_db.py"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert db_path.exists(), "SQLite 库文件必须被创建出来"

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0] for row in conn.execute("select name from sqlite_master where type='table'")
        }

    missing = EXPECTED_TABLES - tables
    assert not missing, f"init_db.py 没有建出这些表: {sorted(missing)}"


@pytest.mark.integration
def test_init_db_survives_a_gbk_console(tmp_path):
    """默认中文 Windows 控制台是 GBK：emoji 打印必须降级，而不是让初始化崩掉。

    回归：全新 clone 按 README 跑 `python init_db.py`，第一个
    `print("🚀 数据库初始化")` 就抛 UnicodeEncodeError —— 快速开始的第一步即失败。
    用 PYTHONIOENCODING=gbk 复现该控制台。
    """
    db_path = tmp_path / "gbk.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "SKIP_SEED": "1",
        "PYTHONIOENCODING": "gbk",
    }
    result = subprocess.run(
        [sys.executable, "init_db.py"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "UnicodeEncodeError" not in result.stderr
    assert db_path.exists()
