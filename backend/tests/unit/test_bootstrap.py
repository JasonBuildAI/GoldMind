"""启动引导：迁移只应用一次、失败可重试、备份先于改动。

变异验证（见 commit message body）：
- 让 `run_migrations` 忽略 `schema_migrations`（每次重放）→ 幂等测试必红；
- 让失败的迁移也写进注册表 → 重试测试必红；
- 去掉「备份失败即中止」→ 备份守卫测试必红；
- 注册表 SQL 退回手写裸 `key` → MySQL 引号守卫测试必红（真实库 1064 回归）。
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, create_mock_engine, text

from app import bootstrap


@pytest.fixture
def file_engine(tmp_path):
    """独立 SQLite 文件库：备份行为需要真实文件（内存库没有可备份的文件）。"""
    engine = create_engine(f"sqlite:///{(tmp_path / 'bootstrap.db').as_posix()}")
    yield engine
    engine.dispose()


@pytest.fixture
def backup_dir(tmp_path, monkeypatch):
    """备份目录重定向到 tmp_path，测试不往仓库的 backend/backups/ 里写。"""
    target = tmp_path / "backups"
    monkeypatch.setattr(bootstrap, "BACKUP_DIR", target)
    return target


@pytest.mark.unit
def test_migrations_apply_once_and_stay_idempotent(file_engine, backup_dir):
    first = {item["key"]: item["status"] for item in bootstrap.run_migrations(file_engine)}
    assert first == {migration.key: "applied" for migration in bootstrap.MIGRATIONS}

    # SQLite 文件库：会改动既有表的迁移必须先落一份备份
    assert sorted(path.name for path in backup_dir.glob("bootstrap-*-pre-*.db"))

    second = {item["key"]: item["status"] for item in bootstrap.run_migrations(file_engine)}
    assert second == {migration.key: "already" for migration in bootstrap.MIGRATIONS}
    assert bootstrap.registry_snapshot(file_engine)["pending"] == []


@pytest.mark.unit
def test_every_migration_is_recorded_with_a_note(file_engine, backup_dir):
    bootstrap.run_migrations(file_engine)

    with file_engine.connect() as conn:
        rows = conn.execute(
            text("SELECT key, description, note, applied_at FROM schema_migrations")
        ).all()

    assert {row[0] for row in rows} == {migration.key for migration in bootstrap.MIGRATIONS}
    assert all(row[2] for row in rows), "每条迁移都要留下 note（日志与 /health 靠它说明做了什么）"


@pytest.mark.unit
def test_failed_migration_is_not_recorded_and_retries_next_run(
    file_engine, backup_dir, monkeypatch
):
    attempts = {"n": 0}

    def flaky(engine):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("boom")
        return "recovered"

    migration = bootstrap.Migration(
        key="flaky", description="测试用", module="unused", applier=flaky
    )
    monkeypatch.setattr(bootstrap, "MIGRATIONS", (migration,))

    first = bootstrap.run_migrations(file_engine)
    assert first[0]["status"] == "failed"
    assert "boom" in first[0]["error"]
    assert bootstrap.applied_keys(file_engine) == set(), "失败的迁移不许写进注册表（否则永不重试）"

    second = bootstrap.run_migrations(file_engine)
    assert second[0]["status"] == "applied"
    assert bootstrap.applied_keys(file_engine) == {"flaky"}


@pytest.mark.unit
def test_backup_failure_blocks_the_migration(file_engine, backup_dir, monkeypatch):
    def broken_backup(engine, key):
        raise OSError("disk full")

    monkeypatch.setattr(bootstrap, "backup_sqlite", broken_backup)

    results = bootstrap.run_migrations(file_engine)

    assert {item["status"] for item in results} == {"failed"}
    assert bootstrap.applied_keys(file_engine) == set(), "没有备份就不许改库"
class _EmptyResult:
    def all(self):
        return []


class _MockConn:
    """mock 连接的执行代理：语句交 mock 记录，结果集固定为空。"""

    def __init__(self, mock):
        self._mock = mock

    def execute(self, statement, *args, **kwargs):
        self._mock.execute(statement, *args, **kwargs)
        return _EmptyResult()


class _Ctx:
    def __init__(self, inner):
        self._inner = inner

    def __enter__(self):
        return self._inner

    def __exit__(self, *exc):
        return False


class _MockEngineShim:
    """MockEngine 没有 begin()/connect() 上下文；补一层薄壳让生产函数原样跑。"""

    def __init__(self, mock):
        self._mock = mock
        self.dialect = mock.dialect

    def _run_ddl_visitor(self, visitor, element, **kwargs):
        return self._mock._run_ddl_visitor(visitor, element, **kwargs)

    def begin(self):
        return _Ctx(self._mock)

    def connect(self):
        return _Ctx(_MockConn(self._mock))


@pytest.mark.unit
def test_registry_sql_quotes_reserved_key_on_mysql_dialect():
    """`key` 是 MySQL 保留字：注册表三处 SQL 都必须由方言加引号。

    回归背景：注册表最初手写裸 SQL，SQLite 能建、MySQL 直接 1064（真实库实测）。
    本测试把生产函数原样跑在 MySQL 方言的 mock 引擎上；任何一处退回手写 SQL，
    捕获到的语句就不含反引号，这里必红。
    """
    captured: list[str] = []
    holder: dict = {}

    def record(statement, *multiparams, **params):
        captured.append(str(statement.compile(dialect=holder["engine"].dialect)))

    mock = create_mock_engine("mysql+pymysql://", record)
    holder["engine"] = mock
    engine = _MockEngineShim(mock)

    bootstrap.ensure_registry(engine)
    assert bootstrap.applied_keys(engine) == set()
    bootstrap._record(engine, bootstrap.MIGRATIONS_BY_KEY["quant-tables"], "测试用 note")

    unquoted = [statement for statement in captured if "`key`" not in statement]
    assert len(captured) >= 4, captured
    assert not unquoted, f"这些注册表 SQL 在 MySQL 方言下漏了引号：{unquoted}"
