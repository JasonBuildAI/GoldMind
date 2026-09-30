"""定时任务的时区与「今天是哪天」。

这一组的由来：cron 用的是 `Asia/Shanghai`，而代码里用 `datetime.now().date()`
取「今天」—— 那取的是**服务器本地时间**。容器默认 UTC，于是同一个
「北京时间 06:30」的任务：

    容器（UTC）      本地时间 2026-10-01 22:30 -> today = 2026-10-01
    宿主机（东八区）  本地时间 2026-10-02 06:30 -> today = 2026-10-02

**同一份行情被记到相差一天的日期上。** 而数据源自己就带 `date` 字段。
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app import scheduler as sched
from app.config import settings


# --------------------------------------------------------------------------- #
# scheduler_today / scheduler_now
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_scheduler_now_uses_the_configured_timezone():
    """scheduler_now 必须带调度器时区的偏移，而不是裸的本地时间。"""
    now = sched.scheduler_now()

    assert now.tzinfo is not None, "scheduler_now 返回了 naive 时间"
    assert str(now.tzinfo) == settings.SCHEDULER_TIMEZONE


@pytest.mark.unit
def test_scheduler_today_follows_the_configured_timezone():
    expected = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).date()

    assert sched.scheduler_today() == expected


@pytest.mark.unit
def test_the_container_scenario_is_actually_fixed(monkeypatch):
    """用一个**确定的时刻**复现原 bug，不依赖跑测试时的钟点。

    北京时间 2026-10-02 06:30 == UTC 2026-10-01 22:30 —— 两者日期差一天。
    这正是「cron 按 Asia/Shanghai、代码按服务器本地」会算错的场景。
    （本机恰好是东八区，用真实当前时间测不出差别，所以这里把时刻钉死。）
    """
    moment_utc = datetime(2026, 10, 1, 22, 30, tzinfo=ZoneInfo("UTC"))
    in_sched_tz = moment_utc.astimezone(ZoneInfo(settings.SCHEDULER_TIMEZONE))

    # 前提：这个时刻下两种算法确实不同，否则测试没有判别力
    assert in_sched_tz.date() == date(2026, 10, 2), "调度器时区下应是 10-02"
    assert moment_utc.date() == date(2026, 10, 1), "UTC 容器本地应是 10-01"

    monkeypatch.setattr(sched, "scheduler_now", lambda: in_sched_tz)

    # 修复后取的是调度器时区那天，而不是容器本地那天
    assert sched.scheduler_today() == date(2026, 10, 2)
    assert sched.scheduler_today() != moment_utc.date()


@pytest.mark.unit
def test_is_trading_day_defaults_to_the_scheduler_timezone(monkeypatch):
    """不给参数时，「今天」必须按调度器时区取。"""
    seen: list[date] = []
    real = sched.scheduler_today

    def spy():
        seen.append(real())
        return real()

    monkeypatch.setattr(sched, "scheduler_today", spy)

    sched.is_trading_day()

    assert seen, "is_trading_day 没有用 scheduler_today"


# --------------------------------------------------------------------------- #
# parse_source_date
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-09-30", date(2026, 9, 30)),
        ("2026/09/30", date(2026, 9, 30)),
        ("20260930", date(2026, 9, 30)),
        ("2026-09-30 19:58:03", date(2026, 9, 30)),  # 带时间也要能解析
        ("  2026-09-30  ", date(2026, 9, 30)),
    ],
)
def test_parse_source_date_accepts_common_formats(raw, expected):
    assert sched.parse_source_date(raw) == expected


@pytest.mark.unit
@pytest.mark.parametrize("raw", [None, "", "   ", "not-a-date", "2026-13-45"])
def test_parse_source_date_returns_none_for_junk(raw):
    """解析不了就返回 None，由调用方回退 —— 不要猜一个日期出来。"""
    assert sched.parse_source_date(raw) is None


# --------------------------------------------------------------------------- #
# 任务写库用的日期
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_price_job_records_the_source_date_not_the_server_date(monkeypatch):
    """回归：写库用的日期应当来自数据源，而不是服务器时钟。

    构造一个「数据源报的日期与今天不同」的场景，确认落库用的是前者。
    """
    import asyncio

    from app import scheduler as scheduler_module
    from app.database import Base, SessionLocal, engine
    from app.models.gold_price import GoldPrice

    Base.metadata.create_all(bind=engine)

    # 数据源报一个**明显不是今天**的交易日。
    # 不能用「今天」或「昨天」：本机恰好是东八区，那样两种算法会得出同一个日期，
    # 测试就失去判别力（实测：改回 datetime.now().date() 仍然全绿）。
    source_day = date(2025, 3, 14)
    monkeypatch.setattr(
        scheduler_module,
        "get_realtime_gold_price",
        lambda: {
            "price": 4214.16,
            "open": 4200.0,
            "high": 4230.0,
            "low": 4190.0,
            "previous_close": 4205.0,
            "change_percent": 0.22,
            "source_name": "测试源",
            "date": source_day.isoformat(),
        },
        raising=False,
    )
    monkeypatch.setattr(scheduler_module, "is_trading_day", lambda *a, **k: True)
    # 任务体内部是 `from app.services.realtime_price import get_realtime_gold_price`
    import app.services.realtime_price as realtime_module

    monkeypatch.setattr(
        realtime_module, "get_realtime_gold_price", scheduler_module.get_realtime_gold_price
    )

    asyncio.run(scheduler_module.update_prices_job())

    db = SessionLocal()
    try:
        row = db.query(GoldPrice).filter(GoldPrice.date == source_day).first()
        assert row is not None, f"没有按数据源日期 {source_day} 落库"
        assert abs(row.close_price - 4214.16) < 0.01
    finally:
        db.close()

# --------------------------------------------------------------------------- #
# 休市日
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_holiday_run_does_not_create_a_row_for_the_holiday(monkeypatch):
    """休市日运行时不该为休市日建一行。

    `is_trading_day` 只排除周末，不认节假日 —— 所以圣诞节那天任务照跑。
    但第 7 轮把「记到哪一天」改成以**数据源自报的交易日**为准之后，
    休市日的数据源仍报上一个交易日，任务只是把同一行重写一遍，
    不会造出一份「休市日行情」。这条测试把这个结论钉住，免得以后
    有人把日期来源改回本地时钟又踩回去。
    """
    import asyncio

    from app import scheduler as scheduler_module
    from app.database import Base, SessionLocal, engine
    from app.models.gold_price import GoldPrice

    Base.metadata.create_all(bind=engine)

    last_trading_day = date(2025, 12, 24)
    holiday = date(2025, 12, 25)

    db = SessionLocal()
    try:
        db.query(GoldPrice).delete()
        db.add(
            GoldPrice(
                date=last_trading_day,
                open_price=4480.0,
                high_price=4520.0,
                low_price=4470.0,
                close_price=4500.0,
                volume=0,
                change_percent=0.22,
            )
        )
        db.commit()
    finally:
        db.close()

    # 数据源在休市日仍报上一个交易日
    payload = {
        "price": 4500.0,
        "open": 4480.0,
        "high": 4520.0,
        "low": 4470.0,
        "previous_close": 4490.0,
        "change_percent": 0.22,
        "source_name": "测试源",
        "date": last_trading_day.isoformat(),
    }
    monkeypatch.setattr(scheduler_module, "scheduler_today", lambda: holiday)
    monkeypatch.setattr(scheduler_module, "is_trading_day", lambda *a, **k: True)
    import app.services.realtime_price as realtime_module

    monkeypatch.setattr(realtime_module, "get_realtime_gold_price", lambda: payload)
    monkeypatch.setattr(scheduler_module, "get_realtime_gold_price", lambda: payload, raising=False)

    asyncio.run(scheduler_module.update_prices_job())

    db = SessionLocal()
    try:
        rows = db.query(GoldPrice).order_by(GoldPrice.date).all()
        dates = [r.date for r in rows]
        assert holiday not in dates, f"为休市日 {holiday} 建了一行，那是一份不存在的数据"
        assert dates == [last_trading_day], f"行数变了：{dates}"
    finally:
        db.close()
