"""覆盖守卫：整年缺口必须在测试里显形。

两条口径（与 `storage.coverage` 共用同一份实现）：

1. 首末观测之间，某年样本数低于「年样本中位数 × 20%」—— 含**整年没有观测** ——
   就是缺口。手工删掉某年的行，守卫必须变红。
2. 有数据的年份少于 2 个的序列标为「积累期」（新序列允许先入库积累），
   与「缺口」分开报告，不把积累期误判成数据故障。
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.models.analysis import FactorObservation
from app.services.quant import storage


def _put_year(db, key, year, *, count=250):
    index = pd.bdate_range(start=f"{year}-01-01", end=f"{year}-12-31", freq="B")[:count]
    series = pd.Series([1.0 + i for i in range(len(index))], index=index)
    storage.upsert_series(db, key, series, source="test")


def _delete_year(db, key, year):
    db.query(FactorObservation).filter(
        FactorObservation.factor_key == key,
        FactorObservation.obs_date >= date(year, 1, 1),
        FactorObservation.obs_date < date(year + 1, 1, 1),
    ).delete(synchronize_session=False)
    db.flush()


def test_complete_series_has_no_gaps(db_session):
    for year in range(2016, 2021):
        _put_year(db_session, "real_yield_10y", year)

    report = storage.coverage(db_session, "real_yield_10y")

    assert report["sparse_years"] == []
    assert report["accumulating"] is False
    assert report["observations"] == sum(report["year_counts"].values())


def test_middle_year_gap_is_flagged(db_session):
    for year in range(2016, 2021):
        _put_year(db_session, "real_yield_10y", year)
    assert storage.coverage(db_session, "real_yield_10y")["sparse_years"] == []

    _delete_year(db_session, "real_yield_10y", 2018)
    report = storage.coverage(db_session, "real_yield_10y")

    assert 2018 in report["sparse_years"], "整年观测被删掉后守卫没有变红"


def test_thin_year_is_flagged(db_session):
    for year in range(2016, 2019):
        _put_year(db_session, "real_yield_10y", year)
    _delete_year(db_session, "real_yield_10y", 2018)
    _put_year(db_session, "real_yield_10y", 2018, count=3)

    report = storage.coverage(db_session, "real_yield_10y")

    assert 2018 in report["sparse_years"], "只有零星几行的年份也要算缺口"


def test_default_window_spans_first_to_last_observation(db_session):
    _put_year(db_session, "gpr", 2016, count=250)
    _put_year(db_session, "gpr", 2020, count=250)

    gaps = storage.sparse_years(db_session, "gpr")

    assert {2017, 2018, 2019} <= gaps, "缺省窗口必须覆盖首末观测之间的空档年"


def test_accumulating_series_is_reported_separately(db_session):
    _put_year(db_session, "gpr", 2026, count=60)

    report = storage.coverage(db_session, "gpr")

    assert report["accumulating"] is True, "只有一个年份的序列是积累期，不是缺口"
    assert report["sparse_years"] == []


def test_empty_series_reports_zero(db_session):
    report = storage.coverage(db_session, "gpr")

    assert report["observations"] == 0
    assert report["accumulating"] is True
    assert report["sparse_years"] == []
