"""同步的年份范围：整年缺口必须被请求，而不是只请求首尾两年。

真实教训（2026-10-02 实测）：``real_yield_10y`` 的年份分布是
2016=249、2017=1、2026=188 —— 2018–2025 整段没有观测。旧实现只请求
「最近一条观测所在年」和「今年」，于是缺口在每一轮增量同步里被永远跳过。
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from app.services.quant import storage, sync
from app.services.quant.definitions import BENCHMARK_KEY

TODAY = date(2026, 10, 2)
HISTORY_YEARS = 10


def _put_year(db, key, year, *, count=250, source="test"):
    """写入某年的一批工作日观测，返回实际写入的日期数。"""
    index = pd.bdate_range(start=f"{year}-01-01", end=f"{year}-12-31", freq="B")[:count]
    series = pd.Series([100.0 + i for i in range(len(index))], index=index)
    storage.upsert_series(db, key, series, source=source)
    return len(index)


def _gap_shape(db, key="real_yield_10y"):
    """复刻真实库的形状：2016 完整、2017 只有一行、2018–2025 全空、2026 进行中。"""
    _put_year(db, key, 2016, count=250)
    _put_year(db, key, 2017, count=1)
    _put_year(db, key, 2026, count=180)


def test_sparse_years_flags_zero_and_thin_years(db_session):
    _gap_shape(db_session)
    gaps = storage.sparse_years(db_session, "real_yield_10y", window=range(2016, 2027))

    assert 2017 in gaps, "只有一行观测的年份也要算缺口"
    assert set(range(2018, 2026)) <= gaps, "完全没有观测的年份必须算缺口"
    assert 2016 not in gaps and 2026 not in gaps


def test_years_to_fetch_requests_newest_gap_years_first(db_session):
    _gap_shape(db_session)
    years = sync._years_to_fetch(db_session, "real_yield_10y", TODAY, HISTORY_YEARS)

    assert years == [2025, 2024, 2023], "缺口年必须被请求；单轮最多 3 年，新的优先"


def test_gap_years_are_eventually_covered_across_rounds(db_session):
    _gap_shape(db_session)
    requested: set[int] = set()

    for _ in range(6):
        years = sync._years_to_fetch(db_session, "real_yield_10y", TODAY, HISTORY_YEARS)
        assert len(years) <= sync.MAX_GAP_YEARS_PER_SYNC
        requested.update(years)
        for year in years:
            _put_year(db_session, "real_yield_10y", year)

    expected = set(range(2018, 2026)) | {2017}
    assert expected <= requested, f"多轮同步仍漏掉缺口年：{sorted(expected - requested)}"


def test_no_gap_only_refreshes_current_year(db_session):
    for year in range(2016, 2027):
        _put_year(db_session, "real_yield_10y", year)

    years = sync._years_to_fetch(db_session, "real_yield_10y", TODAY, HISTORY_YEARS)

    assert years == [TODAY.year]


def test_empty_database_starts_from_newest_years(db_session):
    years = sync._years_to_fetch(db_session, "real_yield_10y", TODAY, 20)

    assert years == [2026, 2025, 2024]


def test_treasury_source_uses_gap_years(db_session, monkeypatch):
    _gap_shape(db_session)
    captured: dict = {}

    def fake_fetch(years, **kwargs):
        captured["years"] = list(years)
        return {}

    monkeypatch.setattr(sync.treasury, "fetch", fake_fetch)
    sync._fetch_source("treasury", db_session, today=TODAY, history_years=HISTORY_YEARS)

    assert set(captured["years"]) == {2023, 2024, 2025}, "财政部源的请求年份没有走缺口逻辑"


def test_yahoo_period_tracks_actual_history_span(db_session, monkeypatch):
    captured: dict = {}

    def fake_fetch(*, period="10y", **kwargs):
        captured["period"] = period
        return {}

    monkeypatch.setattr(sync.yahoo, "fetch", fake_fetch)

    sync._fetch_source("yahoo", db_session, today=TODAY, history_years=HISTORY_YEARS)
    assert captured["period"] == "10y", "空库要按请求窗口回填"

    _put_year(db_session, BENCHMARK_KEY, 2026, count=60)
    sync._fetch_source("yahoo", db_session, today=TODAY, history_years=HISTORY_YEARS)
    assert captured["period"] == "10y", "只有三个月历史时不能退化成 3mo"

    _put_year(db_session, BENCHMARK_KEY, 2016, count=250)
    sync._fetch_source("yahoo", db_session, today=TODAY, history_years=HISTORY_YEARS)
    assert captured["period"] == "3mo", "跨度已够，增量只取最近三个月"
