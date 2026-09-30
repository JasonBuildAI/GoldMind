"""定时任务的集成测试。

这块此前**完全没有覆盖**，而它决定了数据会不会更新。重点钉两件事：

1. 金价任务要用数据源给的真实 OHLC，而不是自己凑；
2. 美元指数任务原先会把「昨收当开盘、max/min 当高低」硬凑出来的 OHLC
   写进数据库 —— 而新浪接口其实返回了真实的开高低。
"""
from __future__ import annotations

from datetime import date, datetime

import pytest

from app import scheduler as sched


# --------------------------------------------------------------------------- #
# 交易日判断
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize(
    "day,expected",
    [
        (date(2026, 9, 28), True),   # 周一
        (date(2026, 10, 2), True),   # 周五
        (date(2026, 10, 3), False),  # 周六
        (date(2026, 10, 4), False),  # 周日
    ],
)
def test_is_trading_day(day, expected):
    assert sched.is_trading_day(day) is expected


# --------------------------------------------------------------------------- #
# 期间统计
# --------------------------------------------------------------------------- #
@pytest.mark.integration
async def test_calculate_period_statistics(db_session, seed_gold_prices):
    seed_gold_prices(days=5, start=2600.0, step=10.0)  # 2600..2640，high=+5，low=-5

    # 传「今天」而不是写死的 2026-01-01 —— 夹具的数据截至今天，
    # 写死的过去日期会把它们全过滤掉（`date <= today`）。
    from app.utils import timeutil

    stats = await sched.calculate_period_statistics(db_session, timeutil.today())

    assert stats["period_high"] == 2645.0
    assert stats["period_low"] == 2595.0
    assert stats["period_high_date"] is not None
    assert stats["period_low_date"] is not None
    assert stats["volatility_range"] == pytest.approx(1.93, abs=0.05)


@pytest.mark.integration
async def test_calculate_period_statistics_on_empty_database(db_session):
    """空库不能崩，也不能除零。"""
    from app.utils import timeutil

    stats = await sched.calculate_period_statistics(db_session, timeutil.today())

    assert stats["period_high"] == 0
    assert stats["period_low"] == 0
    assert stats["volatility_range"] == 0


# --------------------------------------------------------------------------- #
# 金价任务
# --------------------------------------------------------------------------- #
REALTIME_GOLD = {
    "price": 4230.0,
    "previous_close": 4180.0,
    "change": 50.0,
    "change_percent": 1.2,
    "open": 4216.0,
    "high": 4233.0,
    "low": 4197.0,
    "updated_at": "2026-02-03T10:00:00",
    "date": "2026-02-03",
    "update_time": "2026-02-03 10:00:00",
    "source": "tencent",
    "source_name": "腾讯财经-纽约黄金",
    "symbol": "XAU/USD",
    "unit": "美元/盎司",
}


@pytest.mark.integration
async def test_update_prices_job_skips_weekends(db_session, monkeypatch):
    monkeypatch.setattr(sched, "is_trading_day", lambda *_: False)

    called = []
    monkeypatch.setattr(
        "app.services.realtime_price.get_realtime_gold_price",
        lambda **kw: called.append(1),
    )

    await sched.update_prices_job()

    assert called == [], "休市时不应去打数据源"


@pytest.mark.integration
async def test_update_prices_job_writes_real_ohlc(db_session, monkeypatch, _clean_tables):
    from app.database import SessionLocal
    from app.models.gold_price import GoldPrice

    monkeypatch.setattr(sched, "is_trading_day", lambda *_: True)
    monkeypatch.setattr(
        "app.services.realtime_price.get_realtime_gold_price",
        lambda **kw: dict(REALTIME_GOLD),
    )

    await sched.update_prices_job()

    db = SessionLocal()
    try:
        row = db.query(GoldPrice).order_by(GoldPrice.date.desc()).first()
    finally:
        db.close()

    assert row is not None
    assert row.close_price == 4230.0
    assert row.open_price == 4216.0, "开盘价必须是数据源给的，不是凑的"
    assert row.high_price == 4233.0
    assert row.low_price == 4197.0
    assert row.high_price >= row.low_price


@pytest.mark.integration
async def test_update_prices_job_keeps_running_high_and_low(db_session, monkeypatch):
    """同一天第二次更新时，最高/最低应当取两轮的极值，而不是被覆盖。"""
    from app.database import SessionLocal
    from app.models.gold_price import GoldPrice

    monkeypatch.setattr(sched, "is_trading_day", lambda *_: True)

    first = dict(REALTIME_GOLD, high=4233.0, low=4197.0)
    second = dict(REALTIME_GOLD, price=4250.0, high=4260.0, low=4240.0)

    monkeypatch.setattr("app.services.realtime_price.get_realtime_gold_price", lambda **kw: first)
    await sched.update_prices_job()

    monkeypatch.setattr("app.services.realtime_price.get_realtime_gold_price", lambda **kw: second)
    await sched.update_prices_job()

    db = SessionLocal()
    try:
        rows = db.query(GoldPrice).all()
    finally:
        db.close()

    assert len(rows) == 1, "同一天只应有一条记录"
    assert rows[0].high_price == 4260.0
    assert rows[0].low_price == 4197.0
    assert rows[0].close_price == 4250.0


@pytest.mark.integration
async def test_update_prices_job_survives_a_dead_source(db_session, monkeypatch):
    monkeypatch.setattr(sched, "is_trading_day", lambda *_: True)
    monkeypatch.setattr("app.services.realtime_price.get_realtime_gold_price", lambda **kw: None)

    await sched.update_prices_job()  # 不应抛异常


# --------------------------------------------------------------------------- #
# 美元指数任务
# --------------------------------------------------------------------------- #
@pytest.mark.integration
async def test_update_dollar_index_job_uses_real_ohlc(db_session, monkeypatch):
    """回归：原先这里把 OHLC 硬凑出来写库。

    新浪的 DINIW 接口本身就返回开盘/最高/最低，原实现把这三个字段丢掉，
    然后用「昨收当开盘、max(price, prev_close) 当最高、min(...) 当最低」
    编出一组数据落库。
    """
    from app.database import SessionLocal
    from app.models.gold_price import DollarIndex
    from app.services.gold_service import GoldService

    monkeypatch.setattr(sched, "is_trading_day", lambda *_: True)
    monkeypatch.setattr(
        GoldService,
        "get_realtime_dollar_index",
        lambda self: {
            "price": 101.30,
            "previous_close": 101.30,
            "change": 0.0,
            "change_percent": 0.0,
            "open": 101.38,
            "high": 101.47,
            "low": 101.20,
            "updated_at": "2026-02-03T10:00:00",
            "date": "2026-02-03",
            "source": "新浪财经-ICE美元指数(DXY)",
        },
    )

    await sched.update_dollar_index_job()

    db = SessionLocal()
    try:
        row = db.query(DollarIndex).order_by(DollarIndex.date.desc()).first()
    finally:
        db.close()

    assert row is not None
    assert row.open_price == 101.38, "开盘价应当来自数据源"
    assert row.high_price == 101.47
    assert row.low_price == 101.20
    assert row.close_price == 101.30


@pytest.mark.integration
async def test_update_dollar_index_job_approximates_only_when_ohlc_is_missing(
    db_session, monkeypatch
):
    """数据源确实没给 OHLC 时才允许近似 —— 并且要能跑通。"""
    from app.database import SessionLocal
    from app.models.gold_price import DollarIndex
    from app.services.gold_service import GoldService

    monkeypatch.setattr(sched, "is_trading_day", lambda *_: True)
    monkeypatch.setattr(
        GoldService,
        "get_realtime_dollar_index",
        lambda self: {
            "price": 101.30,
            "previous_close": 101.00,
            "change_percent": 0.30,
            "updated_at": "2026-02-03T10:00:00",
            "source": "测试",
        },
    )

    await sched.update_dollar_index_job()

    db = SessionLocal()
    try:
        row = db.query(DollarIndex).order_by(DollarIndex.date.desc()).first()
    finally:
        db.close()

    assert row is not None
    assert row.open_price == 101.00
    assert row.high_price == 101.30
    assert row.low_price == 101.00


@pytest.mark.integration
async def test_update_dollar_index_job_skips_weekends(db_session, monkeypatch):
    monkeypatch.setattr(sched, "is_trading_day", lambda *_: False)

    called = []
    from app.services.gold_service import GoldService

    monkeypatch.setattr(
        GoldService, "get_realtime_dollar_index", lambda self: called.append(1)
    )

    await sched.update_dollar_index_job()

    assert called == []


# --------------------------------------------------------------------------- #
# 新闻任务
# --------------------------------------------------------------------------- #
@pytest.mark.integration
async def test_update_news_job_saves_fetched_items(db_session, monkeypatch):
    from app.database import SessionLocal
    from app.models.news import GoldNews
    from app.services.news_service import NewsService

    monkeypatch.setattr(
        NewsService,
        "fetch_all_rss_news",
        lambda self, **kw: [
            {"title": "定时任务新闻 A", "url": "https://example.invalid/a", "source": "E2E"},
            {"title": "定时任务新闻 B", "url": "https://example.invalid/b", "source": "E2E"},
        ],
    )

    await sched.update_news_job()

    db = SessionLocal()
    try:
        count = db.query(GoldNews).count()
    finally:
        db.close()

    assert count == 2


@pytest.mark.integration
async def test_update_news_job_survives_a_fetch_failure(db_session, monkeypatch):
    from app.services.news_service import NewsService

    def boom(self, **kw):
        raise RuntimeError("RSS 全挂")

    monkeypatch.setattr(NewsService, "fetch_all_rss_news", boom)

    await sched.update_news_job()  # 不应抛异常


# --------------------------------------------------------------------------- #
# AI 分析任务
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_run_ai_analysis_sync_updates_every_service(monkeypatch):
    """四个分析服务都必须被刷新 —— 漏掉一个就会一直显示旧内容。"""
    import app.services.bearish_factor_service as bearish
    import app.services.bullish_factor_service as bullish
    import app.services.institution_prediction_service as institution
    import app.services.investment_advice_service as advice

    refreshed: list[str] = []
    for module, label in (
        (bullish, "bullish"),
        (bearish, "bearish"),
        (institution, "institution"),
        (advice, "advice"),
    ):
        for name in dir(module):
            candidate = getattr(module, name)
            if isinstance(candidate, type) and hasattr(candidate, "refresh_analysis_sync"):
                monkeypatch.setattr(
                    candidate,
                    "refresh_analysis_sync",
                    lambda self, _label=label, **kw: refreshed.append(_label),
                )

    sched._run_ai_analysis_sync()

    assert sorted(refreshed) == ["advice", "bearish", "bullish", "institution"]


@pytest.mark.integration
async def test_update_ai_analysis_job_does_not_raise(monkeypatch):
    monkeypatch.setattr(sched, "_run_ai_analysis_sync", lambda: None)

    await sched.update_ai_analysis_job()  # 不应抛异常
