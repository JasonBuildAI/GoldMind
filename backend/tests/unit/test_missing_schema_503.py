"""缺库/缺表必须翻译成 503 + 修复指引，而不是裸 500。

2026-10-02 的真实故障：开发库的表被一次误跑的测试删光，此后每个读库接口
都抛 ``ProgrammingError(1146, "Table ... doesn't exist")`` —— 页面整片
「暂不可用」，而且刷新永远不会好（不是瞬态错误）。这条守卫钉住三件事：

* 缺表/缺库 → 503，detail 里带可执行的修复命令；
* 其它 SQL 错误（如 Unknown column）仍按 500 处理，不许被同一句指引掩盖；
* 启动自检能把「库里缺哪些表」如实点出来。
"""
from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError, ProgrammingError


def _mysql_missing_table() -> ProgrammingError:
    orig = Exception(1146, "Table 'gold_analysis.gold_prices' doesn't exist")
    return ProgrammingError("SELECT 1 FROM gold_prices", {}, orig)


def _mysql_unknown_database() -> OperationalError:
    orig = Exception(1049, "Unknown database 'gold_analysis'")
    return OperationalError("SELECT 1", {}, orig)


def _sqlite_missing_table() -> OperationalError:
    orig = Exception("no such table: gold_prices")
    return OperationalError("SELECT 1 FROM gold_prices", {}, orig)


def _unknown_column() -> ProgrammingError:
    orig = Exception(1054, "Unknown column 'nope' in 'field list'")
    return ProgrammingError("SELECT nope FROM gold_prices", {}, orig)


@pytest.mark.unit
@pytest.mark.parametrize(
    "exc",
    [_mysql_missing_table(), _mysql_unknown_database(), _sqlite_missing_table()],
)
def test_missing_schema_errors_are_recognized(exc: Exception) -> None:
    from app.main import _is_missing_schema_error

    assert _is_missing_schema_error(exc) is True


@pytest.mark.unit
def test_other_sql_errors_are_not_misreported_as_missing_schema() -> None:
    from app.main import _is_missing_schema_error

    # 列名写错是代码 bug，不是「数据库没初始化」——不许给用户
    # 「去跑 init_db.py」这种无效指引。
    assert _is_missing_schema_error(_unknown_column()) is False
    assert _is_missing_schema_error(RuntimeError("boom")) is False


@pytest.mark.unit
def test_missing_table_response_is_503_with_fix_command(client) -> None:
    """真实走一遍 HTTP：路由抛 1146 时，客户端拿到 503 + 修复命令。"""
    from app.main import app

    @app.get("/__missing_table_probe__")
    def _probe():
        raise _mysql_missing_table()

    try:
        response = client.get("/__missing_table_probe__")
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__missing_table_probe__"
        ]

    assert response.status_code == 503
    payload = response.json()
    assert payload["error"] == "database_not_initialized"
    assert "init_db.py" in payload["detail"], "必须告诉运维怎么修"
    assert "backfill_quant.py" in payload["detail"]


@pytest.mark.unit
def test_unknown_column_still_returns_500(client) -> None:
    """反向守卫：被 handler 包住之后，非缺表错误不许被静默改成 503。"""
    from fastapi.testclient import TestClient

    from app.main import app

    @app.get("/__unknown_column_probe__")
    def _probe():
        raise _unknown_column()

    try:
        with TestClient(app, raise_server_exceptions=False) as tolerant:
            response = tolerant.get("/__unknown_column_probe__")
    finally:
        app.router.routes = [
            route
            for route in app.router.routes
            if getattr(route, "path", None) != "/__unknown_column_probe__"
        ]

    assert response.status_code == 500


@pytest.mark.unit
def test_startup_probe_detects_an_empty_database(tmp_path, monkeypatch) -> None:
    """启动自检：空库要报出全表缺失；建表之后必须归零。"""
    from sqlalchemy import create_engine

    from app import main as app_main
    from app.database import Base

    fresh = create_engine(f"sqlite:///{(tmp_path / 'probe.db').as_posix()}")
    monkeypatch.setattr(app_main, "engine", fresh)

    missing = app_main._missing_metadata_tables()
    assert "gold_prices" in missing, "空库必须报缺表"
    assert set(missing) == set(Base.metadata.tables), "不许误报 metadata 之外的表"

    Base.metadata.create_all(bind=fresh)
    assert app_main._missing_metadata_tables() == []
