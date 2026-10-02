"""每日运维自动化（2.0.2）：备份先于修复、MySQL / 内存库如实跳过、保留份数。

变异验证（commit body 有记录）：
- 让备份 skipped（MySQL）时也自动修复 → 只读用例必红；
- 去掉清理逻辑 → 保留份数用例必红；
- 备份失败仍标 done → 诚实降级用例必红。
"""
from __future__ import annotations

import sqlite3

import pytest

from app import bootstrap
from app.services import maintenance


def _make_sqlite(path) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute("CREATE TABLE sample (value INTEGER)")
        connection.execute("INSERT INTO sample (value) VALUES (7)")
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    target = tmp_path / "backups"
    monkeypatch.setattr(bootstrap, "BACKUP_DIR", target)
    return target


@pytest.mark.unit
def test_backup_copies_with_row_check_and_prunes(tmp_path, backup_dir):
    db_path = tmp_path / "goldmind.db"
    _make_sqlite(db_path)
    backup_dir.mkdir(parents=True, exist_ok=True)
    for index in range(7):
        (backup_dir / f"goldmind-2020010{index}-000000.db").write_bytes(b"old")

    result = maintenance.backup_now(
        database_url=f"sqlite:///{db_path.as_posix()}", keep=7
    )

    assert result["status"] == "done"
    assert result["tables"] == 1
    assert result["rows"] == 1
    backups = sorted(backup_dir.glob("goldmind-*.db"))
    assert len(backups) == 7, "保留份数必须生效（含新备份）"
    assert result["pruned"], "超出保留数的旧备份要被清理"
    assert (backup_dir / result["path"]).exists()


@pytest.mark.unit
def test_backup_skips_memory_and_mysql_honestly(tmp_path, backup_dir):
    memory = maintenance.backup_now(database_url="sqlite://")
    mysql = maintenance.backup_now(
        database_url="mysql+pymysql://user:pw@localhost:3306/gold_analysis"
    )

    assert memory["status"] == "skipped"
    assert "内存" in memory["reason"]
    assert mysql["status"] == "skipped"
    assert "mysqldump" in mysql["reason"]
    assert not backup_dir.exists() or not list(backup_dir.glob("*.db"))
    assert memory["path"] is None and mysql["path"] is None


@pytest.mark.unit
def test_backup_failure_is_not_reported_as_done(tmp_path, backup_dir, monkeypatch):
    from scripts import backup_db

    def broken(source, out_dir, *, stamp=None):
        raise RuntimeError("disk full")

    monkeypatch.setattr(backup_db, "backup_sqlite", broken)
    db_path = tmp_path / "goldmind.db"
    _make_sqlite(db_path)

    result = maintenance.backup_now(database_url=f"sqlite:///{db_path.as_posix()}")

    assert result["status"] == "failed"
    assert "disk full" in result["reason"]


@pytest.mark.unit
def test_daily_maintenance_backs_up_before_health_check(tmp_path, backup_dir, monkeypatch):
    db_path = tmp_path / "goldmind.db"
    _make_sqlite(db_path)
    seen: list[tuple[str, bool]] = []

    def fake_health(*, fix: bool = True, long_db=None):
        backups = list(backup_dir.glob("goldmind-*.db")) if backup_dir.exists() else []
        seen.append((f"backups={len(backups)}", fix))
        return {"status": "ok", "exit_code": 0, "fixed": fix, "reason": None, "lines": []}

    monkeypatch.setattr(maintenance, "data_health_check", fake_health)
    monkeypatch.setattr(maintenance.settings, "AUTO_BACKUP", True)

    result = maintenance.daily_maintenance(
        database_url=f"sqlite:///{db_path.as_posix()}"
    )

    assert result["backup"]["status"] == "done"
    assert seen == [("backups=1", True)], "体检必须在备份落盘之后、且带 fix=True"
    assert maintenance.snapshot()["last_run_at"] == result["at"]


@pytest.mark.unit
def test_daily_maintenance_is_read_only_without_backup(monkeypatch, tmp_path, backup_dir):
    seen: list[bool] = []

    def fake_health(*, fix: bool = True, long_db=None):
        seen.append(fix)
        return {"status": "ok", "exit_code": 0, "fixed": fix, "reason": None, "lines": []}

    monkeypatch.setattr(maintenance, "data_health_check", fake_health)
    monkeypatch.setattr(maintenance.settings, "AUTO_BACKUP", False)

    result = maintenance.daily_maintenance(database_url="sqlite://")

    assert result["backup"]["status"] == "disabled"
    assert seen == [False], "没有备份就绝不允许自动修复"
    assert result["auto_fix_applied"] is False


@pytest.mark.unit
def test_daily_maintenance_is_read_only_on_mysql(monkeypatch, tmp_path, backup_dir):
    seen: list[bool] = []

    def fake_health(*, fix: bool = True, long_db=None):
        seen.append(fix)
        return {"status": "problems", "exit_code": 1, "fixed": fix, "reason": "x", "lines": []}

    monkeypatch.setattr(maintenance, "data_health_check", fake_health)
    monkeypatch.setattr(maintenance.settings, "AUTO_BACKUP", True)

    result = maintenance.daily_maintenance(
        database_url="mysql+pymysql://user:pw@localhost:3306/gold_analysis"
    )

    assert result["backup"]["status"] == "skipped"
    assert seen == [False], "MySQL 没备份成功前不许自动修复"