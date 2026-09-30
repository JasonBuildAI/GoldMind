"""新闻时间戳的时区处理。

这一组的由来：feedparser 的 `published_parsed` 是 **UTC** 的 struct_time，
而原实现直接 `datetime(*parsed[:6])` —— 存进去的是「UTC 的墙上时间」。
库里其他地方（`save_news` 的兜底、`get_recent_news` 的窗口）用的却是本地时间：

    东八区部署下，一条刚发布的新闻被存成「8 小时前」，
    「最近 24 小时」的窗口实际覆盖到约 32 小时。

窗口大小因此取决于部署时区 —— 又是「正确性依赖一个没写下来的环境假设」。
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.config import settings
from app.services.news_service import NewsService, to_local_naive

GMT_NOON = (2026, 9, 30, 12, 0, 0, 2, 273, 0)


# --------------------------------------------------------------------------- #
# to_local_naive
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_utc_struct_time_becomes_local_time():
    """GMT 12:00 在东八区应当是 20:00，而不是 12:00。"""
    result = to_local_naive(GMT_NOON)

    expected = (
        datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        .astimezone(ZoneInfo(settings.SCHEDULER_TIMEZONE))
        .replace(tzinfo=None)
    )
    assert result == expected


@pytest.mark.unit
def test_the_offset_is_actually_applied():
    """确认真的做了换算，而不是原样返回。

    （本机是东八区，所以这里能断言具体差值；换到 UTC 机器上差值会是 0，
    因此断言写成「等于按配置时区换算的结果」而不是硬编码 8 小时。）
    """
    result = to_local_naive(GMT_NOON)
    naive_utc = datetime(*GMT_NOON[:6])

    offset = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).utcoffset()
    assert result == naive_utc + offset


@pytest.mark.unit
def test_result_is_naive():
    """库里存的是 naive 本地时间，返回值不该带 tzinfo。"""
    assert to_local_naive(GMT_NOON).tzinfo is None


@pytest.mark.unit
@pytest.mark.parametrize("raw", [None, (), "not-a-struct"])
def test_junk_returns_none(raw):
    """解析不了就返回 None，由调用方兜底，不要猜一个时间。"""
    assert to_local_naive(raw) is None


# --------------------------------------------------------------------------- #
# fetch_from_rss 的产出
# --------------------------------------------------------------------------- #
RSS_FIXTURE = """<?xml version="1.0"?>
<rss version="2.0"><channel><title>t</title>
<item>
  <title>黄金测试新闻</title>
  <link>https://example.invalid/gold</link>
  <description>正文</description>
  <pubDate>Wed, 30 Sep 2026 12:00:00 GMT</pubDate>
</item>
</channel></rss>"""


@pytest.mark.unit
def test_fetch_from_rss_stores_local_time(db_session, monkeypatch):
    """抓取结果里的 published_at 必须是本地时间。"""
    import feedparser

    service = NewsService(db_session)
    # 先抓住真实实现，再替换 —— 否则 patch 会递归调用自己
    real_parse = feedparser.parse
    monkeypatch.setattr(feedparser, "parse", lambda _url: real_parse(RSS_FIXTURE))

    items = service.fetch_from_rss("https://example.invalid/rss", "测试源")

    assert len(items) == 1
    expected = (
        datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)
        .astimezone(ZoneInfo(settings.SCHEDULER_TIMEZONE))
        .replace(tzinfo=None)
    )
    assert items[0]["published_at"] == expected
    assert items[0]["published_at"] != datetime(2026, 9, 30, 12, 0), "存成了 UTC 墙上时间"


# --------------------------------------------------------------------------- #
# 「最近 24 小时」窗口
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_recent_news_window_is_about_24_hours(db_session):
    """窗口应当真的接近 24 小时，而不是被时区偏移撑大。

    夹具用 `timeutil.now_naive()` —— 与 `get_recent_news` 内部同一个口径。
    这一点很重要：这个测试原先夹具和被测代码**都用 `datetime.now()`**，
    两边「错得一样」，于是无论时区怎么错都恒绿，什么也守不住。
    「代码有没有用服务器本地时间」由 `test_timezone_discipline.py` 的结构性
    守卫负责（本机是东八区，靠跑测试根本区分不出两种写法）。
    """
    from app.models.news import GoldNews
    from app.utils import timeutil

    service = NewsService(db_session)
    now = timeutil.now_naive()

    # 窗口内（23 小时前）与窗口外（25 小时前）各放一条
    for title, age_hours in (("窗口内", 23), ("窗口外", 25)):
        db_session.add(
            GoldNews(
                title=title,
                content="x",
                url=f"https://example.invalid/{title}",
                source="测试源",
                published_at=now - timedelta(hours=age_hours),
            )
        )
    db_session.commit()

    titles = {n.title for n in service.get_recent_news(hours=24)}

    assert "窗口内" in titles
    assert "窗口外" not in titles, "24 小时窗口把 25 小时前的新闻也算进来了"


@pytest.mark.integration
def test_recent_news_window_boundary_is_exact(db_session):
    """边界要卡准：24 小时内包含、24 小时外排除。"""
    from app.models.news import GoldNews
    from app.utils import timeutil

    service = NewsService(db_session)
    now = timeutil.now_naive()

    for title, age in (("刚好在内", timedelta(hours=23, minutes=59)),
                       ("刚好在外", timedelta(hours=24, minutes=1))):
        db_session.add(
            GoldNews(
                title=title,
                content="x",
                url=f"https://example.invalid/{title}",
                source="测试源",
                published_at=now - age,
            )
        )
    db_session.commit()

    titles = {n.title for n in service.get_recent_news(hours=24)}

    assert "刚好在内" in titles
    assert "刚好在外" not in titles
