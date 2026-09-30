"""新闻服务单元测试。

重点是钉住三个曾经存在的静默故障：
1. 抓取端写 `link`/`summary`，存储端读 `url`/`content` —— URL 与正文被丢弃。
2. `published_at` 塞 RSS 原始字符串进 DateTime 列；
   后来又发现直接 `datetime(*parsed[:6])` 存的是 **UTC 墙上时间**，
   与本地时间混用会把「最近24小时」的窗口撑到约 32 小时。
3. 内置「RSS 源」其实是 HTML 页面，永远返回 0 条目。
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import settings

import pytest

from app.models.news import GoldNews, SentimentType
from app.services import news_service
from app.services.news_service import NewsService, parse_rss_sources

FEED_TIME = (2026, 2, 3, 10, 30, 0, 0, 0, 0)

# RSS 的 pubDate 是 GMT；库里存的是**部署时区**的本地时间。
# 见 tests/unit/test_news_timezone.py 与 news_service.to_local_naive。
EXPECTED_PUBLISHED = (
    datetime(2026, 2, 3, 10, 30, tzinfo=timezone.utc)
    .astimezone(ZoneInfo(settings.SCHEDULER_TIMEZONE))
    .replace(tzinfo=None)
)


class _FakeFeed:
    def __init__(self, entries):
        self.entries = entries


def _entry(title="黄金价格创三个月新高", link="https://example.invalid/a", summary="正文摘要"):
    return {
        "title": title,
        "link": link,
        "summary": summary,
        "published_parsed": FEED_TIME,
    }


@pytest.fixture
def stub_feed(monkeypatch):
    """把 feedparser.parse 换成可控的假实现。"""

    def _install(entries, capture=None):
        def _fake_parse(url, *args, **kwargs):
            if capture is not None:
                capture.append(url)
            return _FakeFeed(list(entries))

        monkeypatch.setattr(news_service.feedparser, "parse", _fake_parse)

    return _install


# --------------------------------------------------------------------------- #
# parse_rss_sources
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_parse_rss_sources_parses_valid_entries():
    result = parse_rss_sources("FXStreet|https://a.invalid/rss,CNBC|https://b.invalid/rss")

    assert result == [("FXStreet", "https://a.invalid/rss"), ("CNBC", "https://b.invalid/rss")]


@pytest.mark.unit
def test_parse_rss_sources_skips_malformed():
    """缺竖线、空名称、空 URL、空串都应被跳过而不是抛异常。"""
    result = parse_rss_sources("坏配置,|https://x.invalid,好名字|,  ,正常|https://ok.invalid/rss")

    assert result == [("正常", "https://ok.invalid/rss")]


@pytest.mark.unit
def test_parse_rss_sources_handles_empty():
    assert parse_rss_sources("") == []
    assert parse_rss_sources(None) == []


# --------------------------------------------------------------------------- #
# fetch_from_rss
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_fetch_from_rss_uses_keys_save_news_expects(db_session, stub_feed):
    """回归：抓取结果的键必须与 save_news 的入参一致。"""
    stub_feed([_entry()])
    service = NewsService(db_session)

    items = service.fetch_from_rss("https://feed.invalid/rss", "测试源", limit=5)

    assert len(items) == 1
    item = items[0]
    assert set(item) == {"title", "content", "url", "published_at", "source"}
    assert item["url"] == "https://example.invalid/a"
    assert item["content"] == "正文摘要"


@pytest.mark.unit
def test_fetch_from_rss_parses_published_into_datetime(db_session, stub_feed):
    stub_feed([_entry()])
    service = NewsService(db_session)

    item = service.fetch_from_rss("https://feed.invalid/rss", "测试源")[0]

    assert isinstance(item["published_at"], datetime)
    # RSS 报的是 GMT，落库前要换算成本地时间（不再直接塞 UTC 墙上时间）
    assert item["published_at"] == EXPECTED_PUBLISHED
    assert item["published_at"] != datetime(2026, 2, 3, 10, 30, 0)


@pytest.mark.unit
def test_fetch_from_rss_skips_entries_without_title(db_session, stub_feed):
    stub_feed([_entry(title=""), _entry(title="有标题")])
    service = NewsService(db_session)

    items = service.fetch_from_rss("https://feed.invalid/rss", "测试源")

    assert [i["title"] for i in items] == ["有标题"]


@pytest.mark.unit
def test_fetch_from_rss_returns_empty_on_parse_failure(db_session, monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("网络炸了")

    monkeypatch.setattr(news_service.feedparser, "parse", _boom)
    service = NewsService(db_session)

    assert service.fetch_from_rss("https://feed.invalid/rss", "测试源") == []


@pytest.mark.unit
def test_fetch_from_rss_respects_limit(db_session, stub_feed):
    stub_feed([_entry(title=f"新闻{i}") for i in range(10)])
    service = NewsService(db_session)

    assert len(service.fetch_from_rss("https://feed.invalid/rss", "测试源", limit=3)) == 3


# --------------------------------------------------------------------------- #
# save_news
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_fetch_then_save_roundtrip_persists_url_and_content(db_session, stub_feed):
    """端到端回归：抓取 → 保存 → 落库，URL 与正文都不能丢。"""
    stub_feed([_entry()])
    service = NewsService(db_session)

    for item in service.fetch_from_rss("https://feed.invalid/rss", "测试源"):
        service.save_news(item)

    saved = db_session.query(GoldNews).one()
    assert saved.url == "https://example.invalid/a"
    assert saved.content == "正文摘要"
    assert saved.source == "测试源"
    assert saved.published_at == EXPECTED_PUBLISHED
    assert saved.sentiment == SentimentType.NEUTRAL


@pytest.mark.unit
def test_save_news_defaults_published_at_to_now(db_session):
    """RSS 不提供时间时不能留 NULL，否则「最近24小时」查询会漏掉它。"""
    service = NewsService(db_session)

    before = datetime.now()
    service.save_news({"title": "无时间新闻", "source": "测试源"})

    saved = db_session.query(GoldNews).one()
    assert saved.published_at is not None
    assert saved.published_at >= before - timedelta(seconds=5)


@pytest.mark.unit
def test_save_news_deduplicates_by_url(db_session):
    service = NewsService(db_session)
    payload = {"title": "同一条", "url": "https://example.invalid/same", "source": "测试源"}

    first = service.save_news(payload)
    second = service.save_news(payload)

    assert first.id == second.id
    assert db_session.query(GoldNews).count() == 1


@pytest.mark.unit
def test_save_news_deduplicates_by_title_when_url_missing(db_session):
    service = NewsService(db_session)
    payload = {"title": "没有链接", "source": "测试源"}

    service.save_news(payload)
    service.save_news(payload)

    assert db_session.query(GoldNews).count() == 1


@pytest.mark.unit
def test_save_news_rejects_blank_title(db_session):
    service = NewsService(db_session)

    assert service.save_news({"title": "   ", "source": "测试源"}) is None
    assert db_session.query(GoldNews).count() == 0


# --------------------------------------------------------------------------- #
# 读取
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_get_recent_news_filters_by_hours(db_session):
    now = datetime.now()
    db_session.add_all(
        [
            GoldNews(title="刚发布", published_at=now - timedelta(hours=1)),
            GoldNews(title="昨天", published_at=now - timedelta(hours=30)),
        ]
    )
    db_session.commit()
    service = NewsService(db_session)

    recent = service.get_recent_news(hours=24)

    assert [n.title for n in recent] == ["刚发布"]


@pytest.mark.unit
def test_get_sentiment_summary_handles_null_sentiment(db_session):
    """sentiment 为 NULL 的历史数据不能让统计抛异常。"""
    from sqlalchemy import text

    db_session.add_all(
        [
            GoldNews(title="正面", sentiment=SentimentType.POSITIVE),
            GoldNews(title="中性", sentiment=SentimentType.NEUTRAL),
        ]
    )
    db_session.commit()

    # GoldNews.sentiment 有 Python 侧 default，ORM 无法插入 NULL（default 在值为
    # None 时同样生效），所以用原生 SQL 造这条历史脏数据。
    db_session.execute(
        text("INSERT INTO gold_news (title, sentiment) VALUES ('无标注', NULL)")
    )
    db_session.commit()

    summary = NewsService(db_session).get_sentiment_summary()

    assert summary["positive"] == 1
    assert summary["neutral"] == 1
    assert summary["negative"] == 0


# --------------------------------------------------------------------------- #
# 源配置
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_fetch_all_rss_news_uses_configured_sources(db_session, stub_feed, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "NEWS_RSS_SOURCES", "甲|https://a.invalid/rss,乙|https://b.invalid/rss")
    seen: list[str] = []
    stub_feed([_entry()], capture=seen)
    service = NewsService(db_session)

    items = service.fetch_all_rss_news()

    assert seen == ["https://a.invalid/rss", "https://b.invalid/rss"]
    assert len(items) == 2


@pytest.mark.unit
def test_fetch_all_rss_news_falls_back_to_defaults(db_session, stub_feed, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "NEWS_RSS_SOURCES", "")
    seen: list[str] = []
    stub_feed([_entry()], capture=seen)
    service = NewsService(db_session)

    service.fetch_all_rss_news()

    assert seen, "未配置时必须回落到内置默认源"
    assert len(seen) == len(parse_rss_sources(news_service.DEFAULT_RSS_SOURCES))


@pytest.mark.unit
def test_default_sources_are_not_html_pages():
    """回归：默认源不能是 HTML 页面（原实现拿 index.d.html 当 RSS）。"""
    for _, url in parse_rss_sources(news_service.DEFAULT_RSS_SOURCES):
        assert not url.endswith(".html") or "rss" in url or "device/rss" in url
