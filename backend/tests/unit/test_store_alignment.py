"""服务库 ↔ 长库对齐（2.0.2 第 14 条）：方向不对称、幂等、缺文件如实跳过。

方向为什么要不对称：长库是研究副本，服务库是生产口径。服务库缺的历史日期
从长库补入（insert-only），重叠日期不一致时以**服务库为准**覆盖长库 ——
反向把过期研究值写回生产库会造成真实的口径回退。

变异验证（commit body 有记录）：
- 把覆盖方向反过来（长库值覆盖服务库）→ 服务库不可变断言必红；
- 去掉冲突计数 → conflicts_before 断言必红；
- 幂等第二次仍报冲突 → 幂等断言必红。
"""
from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import text

from app.services import store_alignment


def _make_long_db(path, rows) -> None:
    connection = sqlite3.connect(str(path))
    try:
        connection.execute(
            "CREATE TABLE factor_observations ("
            "factor_key TEXT NOT NULL, obs_date TEXT NOT NULL, value REAL NOT NULL, "
            "source TEXT, updated_at TEXT, PRIMARY KEY (factor_key, obs_date))"
        )
        connection.executemany(
            "INSERT INTO factor_observations (factor_key, obs_date, value, source) "
            "VALUES (?, ?, ?, ?)",
            rows,
        )
        connection.commit()
    finally:
        connection.close()


def _service_insert(key: str, day: str, value: float, source: str) -> None:
    from app.database import engine

    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO factor_observations (factor_key, obs_date, value, source) "
                "VALUES (:key, :day, :value, :source)"
            ),
            {"key": key, "day": day, "value": value, "source": source},
        )


def _service_value(key: str, day: str) -> float:
    from app.database import engine

    with engine.connect() as conn:
        return float(
            conn.execute(
                text(
                    "SELECT value FROM factor_observations "
                    "WHERE factor_key = :key AND obs_date = :day"
                ),
                {"key": key, "day": day},
            ).scalar()
        )


def _long_values(path, key: str) -> dict:
    connection = sqlite3.connect(str(path))
    try:
        return {
            day: value
            for day, value in connection.execute(
                "SELECT obs_date, value FROM factor_observations WHERE factor_key = ?", (key,)
            )
        }
    finally:
        connection.close()


@pytest.mark.unit
def test_align_backfills_service_and_overwrites_long(tmp_path):
    from app.database import engine

    long_path = tmp_path / "goldmind-long.db"
    _make_long_db(
        long_path,
        [
            ("gold_close", "2025-01-02", 100.0, "长库"),
            ("gold_close", "2025-01-05", 105.0, "长库"),
        ],
    )
    _service_insert("gold_close", "2025-01-02", 99.0, "服务库")
    _service_insert("gold_close", "2025-01-06", 106.0, "服务库")

    stats = store_alignment.align_stores(engine, long_db=long_path)

    assert stats["status"] == "done"
    assert stats["inserted_into_service"] == 1, "长库独有的 01-05 应补入服务库"
    assert stats["updated_in_long"] == 1, "01-02 冲突应以服务库为准覆盖长库"
    assert stats["inserted_into_long"] == 1, "服务库独有的 01-06 应补入长库"
    assert stats["conflicts_before"] == 1
    assert stats["worst_conflict"]["factor_key"] == "gold_close"
    assert stats["worst_conflict"]["relative_diff"] > 0

    # 服务库已有值不许被长库覆盖；缺的日期要补进来
    assert _service_value("gold_close", "2025-01-02") == 99.0
    assert _service_value("gold_close", "2025-01-05") == 105.0

    values = _long_values(long_path, "gold_close")
    assert values["2025-01-02"] == 99.0, "长库必须跟随服务库口径"
    assert values["2025-01-06"] == 106.0


@pytest.mark.unit
def test_align_is_idempotent(tmp_path):
    from app.database import engine

    long_path = tmp_path / "goldmind-long.db"
    _make_long_db(long_path, [("gold_close", "2025-01-02", 100.0, "长库")])
    _service_insert("gold_close", "2025-01-02", 99.0, "服务库")

    first = store_alignment.align_stores(engine, long_db=long_path)
    second = store_alignment.align_stores(engine, long_db=long_path)

    assert first["updated_in_long"] == 1
    assert second["conflicts_before"] == 0
    assert second["updated_in_long"] == 0
    assert second["inserted_into_long"] == 0
    assert second["inserted_into_service"] == 0


@pytest.mark.unit
def test_align_reports_absent_long_db(tmp_path):
    from app.database import engine

    stats = store_alignment.align_stores(engine, long_db=tmp_path / "missing.db")

    assert stats["status"] == "absent"


@pytest.mark.unit
def test_align_reports_absent_table(tmp_path):
    from app.database import engine

    long_path = tmp_path / "empty.db"
    sqlite3.connect(str(long_path)).close()

    stats = store_alignment.align_stores(engine, long_db=long_path)

    assert stats["status"] == "absent"
    assert "factor_observations" in stats["note"]