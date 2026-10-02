"""事件标注 / 聚合来源的接口层守卫（2.0.2 第 4、5 条）。

单元规则在 tests/unit/test_news_events.py；这里钉住接口真的把它们带出去，
且板块（digest）与分析输入走的是同一套确定性规则。
"""
from __future__ import annotations

from datetime import timedelta

import pytest

pytestmark = pytest.mark.integration


def _add_news(db_session, *, title, url, content="", source="测试"):
    from app.models.news import GoldNews, SentimentType
    from app.utils import timeutil

    row = GoldNews(
        title=title,
        content=content,
        source=source,
        url=url,
        published_at=timeutil.now_naive() - timedelta(hours=1),
        sentiment=SentimentType.NEUTRAL,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_news_endpoint_labels_events_and_aggregator_links(client, db_session):
    _add_news(
        db_session,
        title="Fed holds rates steady at FOMC meeting",
        url="https://news.google.com/rss/articles/fomc-1",
    )
    _add_news(
        db_session,
        title="金价周五收涨 0.5%",
        url="https://www.reuters.com/markets/gold-weekly",
    )

    body = client.get("/api/gold/news?limit=10").json()
    by_title = {item["title"]: item for item in body}

    tagged = by_title["Fed holds rates steady at FOMC meeting"]
    assert tagged["event_tags"] == ["fomc", "central_bank_decision"]
    assert tagged["event_labels"] == ["FOMC", "央行决议"]
    assert tagged["via_aggregator"] is True

    plain = by_title["金价周五收涨 0.5%"]
    assert plain["event_tags"] == []
    assert plain["event_labels"] == []
    assert plain["via_aggregator"] is False


def test_digest_items_carry_the_same_event_labels(client, db_session):
    from app.models.news_digest import NewsDigestItem
    from app.services.news_digest import normalize_source_key
    from app.utils import timeutil

    db_session.add(
        NewsDigestItem(
            title="US CPI beats expectations in September",
            summary="Inflation ran hotter than forecast.",
            source="Reuters",
            source_key=normalize_source_key("Reuters"),
            url="https://www.reuters.com/markets/cpi-september",
            published_at=timeutil.now_naive() - timedelta(hours=2),
            authority_tier=1,
        )
    )
    db_session.commit()

    body = client.get("/api/gold/news/digest").json()
    assert body["has_data"] is True
    items = [item for window in body["windows"] for item in window["items"]]
    assert items
    first = items[0]
    assert first["event_tags"] == ["cpi"]
    assert first["event_labels"] == ["美国CPI"]
    assert first["via_aggregator"] is False
