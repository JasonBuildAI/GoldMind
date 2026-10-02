"""数据体检守卫：未来日期 / 非法数值 / 跨库一致性。

每条守卫都用「先把数据改坏、确认它会红」的方式验证过（第三轮 spec 第 16 条）。
测试只碰临时 SQLite 文件，绝不连接真实服务库。
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.analysis import FactorObservation
from app.services import data_sanity
from scripts import check_data_sanity

TODAY = date(2026, 10, 3)


def _service_url(tmp_path: Path) -> str:
    engine = create_engine(f"sqlite:///{(tmp_path / 'service.db').as_posix()}")
    FactorObservation.__table__.create(engine)
    engine.dispose()
    return f"sqlite:///{(tmp_path / 'service.db').as_posix()}"


def _add(url: str, key: str, day: str, value: float) -> None:
    engine = create_engine(url)
    with Session(engine) as session:
        session.add(
            FactorObservation(
                factor_key=key,
                obs_date=date.fromisoformat(day),
                value=value,
                source="test",
            )
        )
        session.commit()
    engine.dispose()


def _long_db(tmp_path: Path, rows: list[tuple[str, str, float, str]]) -> Path:
    path = tmp_path / "long.db"
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE factor_observations ("
            "id INTEGER PRIMARY KEY, factor_key TEXT, obs_date TEXT, value REAL, source TEXT)"
        )
        connection.executemany(
            "INSERT INTO factor_observations (factor_key, obs_date, value, source) VALUES (?,?,?,?)",
            rows,
        )
        connection.commit()
    finally:
        connection.close()
    return path


def test_future_observations_are_found_and_purged(tmp_path):
    url = _service_url(tmp_path)
    _add(url, "etf_shares", "2026-10-05", 2.6e8)
    _add(url, "gold_close", "2026-10-02", 4200.0)

    engine = create_engine(url)
    with Session(engine) as session:
        findings = data_sanity.audit_service_store(session, today=TODAY)
    assert [finding.kind for finding in findings] == ["future"]
    assert findings[0].factor_key == "etf_shares"

    with Session(engine) as session:
        assert data_sanity.purge_future_observations(session, today=TODAY) == 1
    with Session(engine) as session:
        assert data_sanity.audit_service_store(session, today=TODAY) == []
        assert session.query(FactorObservation).count() == 1
    engine.dispose()


def test_long_store_flags_bounds_nonfinite_and_duplicates(tmp_path):
    path = _long_db(
        tmp_path,
        [
            ("vix", "2026-10-01", 999.0, "test"),
            ("gold_close", "2026-10-01", float("inf"), "test"),
            ("gold_close", "2026-10-01", 4200.0, "test"),
        ],
    )
    connection = sqlite3.connect(str(path))
    try:
        findings = data_sanity.audit_long_store(connection, today=TODAY)
    finally:
        connection.close()
    kinds = {finding.kind for finding in findings}
    assert {"bounds", "nonfinite", "duplicate"} <= kinds


def test_long_future_rows_are_purged(tmp_path):
    path = _long_db(
        tmp_path,
        [
            ("etf_shares", "2026-10-05", 2.6e8, "test"),
            ("gold_close", "2026-10-02", 4200.0, "test"),
        ],
    )
    connection = sqlite3.connect(str(path))
    try:
        deleted = data_sanity.purge_long_future_observations(connection, today=TODAY)
        left = connection.execute("SELECT COUNT(*) FROM factor_observations").fetchone()[0]
    finally:
        connection.close()
    assert deleted == 1
    assert left == 1


def test_compare_stores_reports_mismatch_and_one_sided_keys(tmp_path):
    url = _service_url(tmp_path)
    _add(url, "gold_close", "2026-10-01", 4200.0)
    _add(url, "gold_close", "2026-10-02", 4210.0)
    _add(url, "vix", "2026-10-02", 15.0)
    long_path = _long_db(
        tmp_path,
        [
            ("gold_close", "2026-10-01", 4200.0, "test"),
            ("gold_close", "2026-10-02", 4205.0, "test"),
            ("dollar_index", "2026-10-02", 98.0, "test"),
        ],
    )
    engine = create_engine(url)
    connection = sqlite3.connect(str(long_path))
    try:
        with Session(engine) as session:
            report = data_sanity.compare_stores(session, connection)
    finally:
        connection.close()
        engine.dispose()
    assert report["mismatch_total"] == 1
    assert report["only_service"] == ["vix"]
    assert report["only_long"] == ["dollar_index"]
    assert report["keys"][0]["factor_key"] == "gold_close"


def test_run_reports_future_rows_and_fixes_them(tmp_path):
    url = _service_url(tmp_path)
    _add(url, "etf_shares", "2026-10-05", 2.6e8)

    code, lines = check_data_sanity.run(url, long_db=None, today=TODAY)
    assert code == 1
    assert any("未来日期" in line for line in lines)

    code, lines = check_data_sanity.run(url, long_db=None, fix=True, today=TODAY)
    assert code == 0
    assert any("已删除" in line for line in lines)


def test_strict_flag_fails_on_cross_store_mismatch(tmp_path):
    url = _service_url(tmp_path)
    _add(url, "gold_close", "2026-10-01", 4200.0)
    long_path = _long_db(tmp_path, [("gold_close", "2026-10-01", 4300.0, "test")])

    code, lines = check_data_sanity.run(url, long_path, today=TODAY)
    assert code == 0
    assert any("重叠不一致 1" in line for line in lines)

    code, lines = check_data_sanity.run(url, long_path, strict=True, today=TODAY)
    assert code == 1
    assert any("--strict" in line for line in lines)


def test_run_unwraps_secretstr_database_url(tmp_path, monkeypatch):
    """真实缺陷回归：settings.DATABASE_URL 是 SecretStr，直接喂给 create_engine 会崩。"""
    url = _service_url(tmp_path)
    _add(url, "gold_close", "2026-10-02", 4200.0)
    monkeypatch.setattr(check_data_sanity.settings, "DATABASE_URL", SecretStr(url))

    code, lines = check_data_sanity.run(long_db=None, today=TODAY)

    assert code == 0, lines


def test_same_day_quote_divergence_over_threshold_is_flagged(tmp_path):
    """同一天、实时报价与收盘差 4% → 必须点名（A9 第 2 条）。"""
    url = _service_url(tmp_path)
    _add(url, "gold_close", "2026-10-02", 4200.0)

    engine = create_engine(url)
    try:
        with Session(engine) as session:
            point = data_sanity.latest_close_point(session)
            assert point == ("2026-10-02", 4200.0)
            findings = data_sanity.audit_quote_divergence(
                point, {"date": "2026-10-02", "price": 4368.0, "source": "sina"}
            )
    finally:
        engine.dispose()

    assert [finding.kind for finding in findings] == ["quote_divergence"]
    assert findings[0].factor_key == "gold_close"
    assert findings[0].obs_date == "2026-10-02"
    assert "3.85%" in findings[0].detail


def test_same_day_quote_within_threshold_is_not_flagged(tmp_path):
    url = _service_url(tmp_path)
    _add(url, "gold_close", "2026-10-02", 4200.0)

    engine = create_engine(url)
    try:
        with Session(engine) as session:
            point = data_sanity.latest_close_point(session)
            findings = data_sanity.audit_quote_divergence(
                point, {"date": "2026-10-02", "price": 4230.0, "source": "sina"}
            )
    finally:
        engine.dispose()

    assert findings == []


def test_quote_divergence_ignores_other_days(tmp_path):
    """跨天的价差是真实行情，不是数据问题 —— 不许拿来报警。"""
    url = _service_url(tmp_path)
    _add(url, "gold_close", "2026-10-01", 4200.0)

    engine = create_engine(url)
    try:
        with Session(engine) as session:
            point = data_sanity.latest_close_point(session)
            findings = data_sanity.audit_quote_divergence(
                point, {"date": "2026-10-02", "price": 4368.0, "source": "sina"}
            )
    finally:
        engine.dispose()

    assert findings == []


def test_quote_divergence_needs_both_sides_instead_of_inventing_a_value(tmp_path):
    """缺收盘或缺报价时跳过，不许用 0 代替缺失值。"""
    assert data_sanity.audit_quote_divergence(None, {"date": "2026-10-02", "price": 1.0}) == []
    assert data_sanity.audit_quote_divergence(("2026-10-02", 4200.0), None) == []
    assert (
        data_sanity.audit_quote_divergence(
            ("2026-10-02", 4200.0), {"date": "2026-10-02", "price": None}
        )
        == []
    )


def test_sanity_script_reports_quote_divergence_as_a_finding(tmp_path):
    """脚本层：同一路对账要真的接进 run()，而不是只在单元函数里自转。"""
    url = _service_url(tmp_path)
    _add(url, "gold_close", "2026-10-02", 4200.0)

    code, lines = check_data_sanity.run(
        url,
        long_db=None,
        today=TODAY,
        realtime_quote={"date": "2026-10-02", "price": 4368.0, "source": "sina"},
    )

    assert code == 1
    assert any("报价背离" in line for line in lines)
    assert any("[实时报价]" in line for line in lines)
