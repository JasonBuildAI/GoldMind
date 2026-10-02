"""备份脚本：SQLite 全量复制 + 逐表行数校验；失败不留半成品；MySQL 只指路、不吐密码。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scripts import backup_db


def _make_db(path: Path, rows: int = 3) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("CREATE TABLE alpha (id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("CREATE TABLE beta (id INTEGER PRIMARY KEY)")
        connection.executemany("INSERT INTO alpha (value) VALUES (?)", [("x",)] * rows)
        connection.executemany("INSERT INTO beta DEFAULT VALUES", [()] * (rows + 1))
        connection.commit()
    finally:
        connection.close()


def test_sqlite_backup_copies_every_table_and_verifies_row_counts(tmp_path):
    source = tmp_path / "goldmind.db"
    _make_db(source, rows=4)
    out = tmp_path / "backups"

    result = backup_db.backup_sqlite(source, out, stamp="unit")

    assert result["tables"] == 2
    assert result["rows"] == 9
    target = result["path"]
    assert target.exists()
    connection = sqlite3.connect(str(target))
    try:
        assert connection.execute("SELECT COUNT(*) FROM alpha").fetchone()[0] == 4
        assert connection.execute("SELECT COUNT(*) FROM beta").fetchone()[0] == 5
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_row_count_mismatch_deletes_the_half_product(tmp_path, monkeypatch):
    source = tmp_path / "goldmind.db"
    _make_db(source)
    out = tmp_path / "backups"
    real_counts = backup_db._table_counts
    calls = {"count": 0}

    def lying_counts(connection):
        calls["count"] += 1
        counts = dict(real_counts(connection))
        if calls["count"] == 1:
            counts["alpha"] = counts["alpha"] + 999
        return counts

    monkeypatch.setattr(backup_db, "_table_counts", lying_counts)

    with pytest.raises(RuntimeError, match="校验失败"):
        backup_db.backup_sqlite(source, out, stamp="mismatch")
    assert list(out.glob("*.db")) == [], "校验不过必须删掉半成品，不许留下一个看起来成功的文件"


def test_run_backs_up_a_configured_sqlite_file(tmp_path):
    source = tmp_path / "goldmind.db"
    _make_db(source, rows=2)

    code, lines = backup_db.run(f"sqlite:///{source.as_posix()}", tmp_path / "out")

    assert code == 0, lines
    assert len(list((tmp_path / "out").glob("*.db"))) == 1


def test_run_reports_a_missing_sqlite_file_without_writing_anything(tmp_path):
    code, lines = backup_db.run(f"sqlite:///{(tmp_path / 'nope.db').as_posix()}", tmp_path)

    assert code == 1
    assert any("不存在" in line for line in lines)
    assert list(tmp_path.glob("*.db")) == []


def test_mysql_url_returns_guidance_without_leaking_the_password(tmp_path):
    code, lines = backup_db.run(
        "mysql+pymysql://ro:sup3rsecret@db.example:3307/gold_analysis", tmp_path
    )

    assert code == 2
    text = "\n".join(lines)
    assert "mysqldump" in text
    assert "gold_analysis" in text
    assert "sup3rsecret" not in text, "指引里绝对不能回显密码"


def test_memory_sqlite_refuses_with_a_reason(tmp_path):
    code, lines = backup_db.run("sqlite:///:memory:", tmp_path)

    assert code == 1
    assert any("内存" in line for line in lines)
