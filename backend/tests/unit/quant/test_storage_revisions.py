"""修订流水与 point-in-time 重建：让「重跑一次预注册」真的是同一次实验。

背景（`docs/specs/2026-10-02-量化引擎第二轮预注册.md`）：`factor_observations`
值变了就地覆盖，回填一轮就修订过 26,445 行（`docs/specs/2026-10-02-回填报告.md`），
而表里没有任何「何时看到是哪个值」的记录 —— 于是「按 2026-10-02 的输入重算一遍」
在物理上做不到，预注册只剩下一次性价值。

这里用独立的临时 SQLite 库，不碰测试主库。
"""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.analysis import FactorObservation, FactorObservationRevision
from app.services.quant import storage


@pytest.fixture()
def db():
    """独立内存库：StaticPool 保证多次取连接看到的都是同一个 :memory:。"""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _series(pairs: list[tuple[str, float]]) -> pd.Series:
    return pd.Series(
        {pd.Timestamp(day).date(): value for day, value in pairs},
        name="real_yield_10y",
    )


def test_first_write_and_revision_each_leave_one_row(db):
    inserted, updated = storage.upsert_series(
        db,
        "real_yield_10y",
        _series([("2026-01-05", 1.9), ("2026-01-06", 2.0)]),
        source="t1",
        recorded_at=datetime(2026, 1, 5, 9, 0, 0),
    )
    assert (inserted, updated) == (2, 0)
    assert storage.revision_count(db) == 2

    # 数据源回修了 1 月 5 日那条
    inserted, updated = storage.upsert_series(
        db,
        "real_yield_10y",
        _series([("2026-01-05", 1.75)]),
        source="t1",
        recorded_at=datetime(2026, 1, 20, 9, 0, 0),
    )
    assert (inserted, updated) == (0, 1)
    assert storage.revision_count(db) == 3

    # 当前值走的是「最新」口径，不受流水影响
    current = storage.load_series(db, "real_yield_10y")
    assert float(current.loc[datetime(2026, 1, 5)]) == pytest.approx(1.75)


def test_identical_replay_does_not_grow_the_ledger(db):
    """幂等重跑不追加流水 —— 否则每天的定时同步会把流水表写成垃圾堆。

    变异验证：去掉「值与来源都没变就 continue」那条分支，本测试必红。
    """
    payload = _series([("2026-01-05", 1.9)])
    storage.upsert_series(db, "real_yield_10y", payload, source="t1")
    before = storage.revision_count(db)

    inserted, updated = storage.upsert_series(db, "real_yield_10y", payload, source="t1")

    assert (inserted, updated) == (0, 0)
    assert storage.revision_count(db) == before


def test_point_in_time_rebuild_sees_the_value_as_it_was_then(db):
    """回测必须能拿到「当时可见」的面板：修订之后的值不许渗回修订之前。

    变异验证：把 `load_series_as_of` 改成直接读 `factor_observations`（当前值），
    第二个断言必红 —— 那正是「用未来才知道的修订值跑过去的回测」。
    """
    storage.upsert_series(
        db,
        "real_yield_10y",
        _series([("2026-01-05", 1.9), ("2026-01-06", 2.0)]),
        source="t1",
        recorded_at=datetime(2026, 1, 5, 9, 0, 0),
    )

    as_it_was = storage.load_series_as_of(db, date(2026, 1, 10))
    assert list(as_it_was) == ["real_yield_10y"]
    assert float(as_it_was["real_yield_10y"].iloc[0]) == pytest.approx(1.9)

    # 1 月 20 日回修成 1.75：1 月 10 日那天看到的是旧值，1 月 21 日看到的是新值
    storage.upsert_series(
        db,
        "real_yield_10y",
        _series([("2026-01-05", 1.75)]),
        source="t1",
        recorded_at=datetime(2026, 1, 20, 9, 0, 0),
    )
    assert float(storage.load_series_as_of(db, date(2026, 1, 10))["real_yield_10y"].iloc[0]) == (
        pytest.approx(1.9)
    )
    assert float(storage.load_series_as_of(db, date(2026, 1, 21))["real_yield_10y"].iloc[0]) == (
        pytest.approx(1.75)
    )


def test_backfilled_history_is_absent_from_the_earlier_snapshot(db):
    """补抓的历史不会出现在「补抓之前」的面板里。

    这就是回填报告里「新增 36,150 行」那一类数据：它们是在 2026-10-02 才写进来的，
    所以 2026-10-01 的输入面板里根本不该有它们。
    """
    storage.upsert_series(
        db,
        "real_yield_10y",
        _series([("2026-01-05", 1.9)]),
        source="t1",
        recorded_at=datetime(2026, 1, 5, 9, 0, 0),
    )
    storage.upsert_series(
        db,
        "real_yield_10y",
        _series([("2019-01-04", 0.4)]),
        source="t1",
        recorded_at=datetime(2026, 10, 2, 3, 0, 0),
    )

    before_backfill = storage.load_series_as_of(db, date(2026, 10, 1))
    after_backfill = storage.load_series_as_of(db, date(2026, 10, 2))

    assert len(before_backfill["real_yield_10y"]) == 1
    assert len(after_backfill["real_yield_10y"]) == 2
    # 当前值口径仍然是全量
    assert db.query(FactorObservation).count() == 2
    assert db.query(FactorObservationRevision).count() == 2
