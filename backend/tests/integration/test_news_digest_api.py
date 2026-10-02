"""消息板块 API 的集成测试。

钉住三件容易静默坏掉的事：

1. `/news/digest` 不能被 `/news/{news_id}` 抢占 —— 先注册路径参数，
   用户拿到的是 422（"digest" 不是整数），榜单却看起来「接口还在」；
2. 空库必须 200 + `has_data=false` + 明确原因，不允许 500，更不允许
   编造任何条目；
3. 手动抓取（POST refresh）必须真的落库，抓完 GET 能看见；
   重复抓取按 URL 去重，不产生重复条目。
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import format_datetime

import pytest

from app.services import news_digest
from app.services.news_digest import SourceSpec

# 固定「现在」，让 RSS 的 pubDate 换算与窗口归属完全确定。
# PUBLISHED_UTC（02:30Z）= 北京时间 10:30，距 12:00 为 1.5 小时，稳进 24h 窗口。
NOW_LOCAL = datetime(2026, 10, 2, 12, 0, 0)
PUBLISHED_UTC = datetime(2026, 10, 2, 2, 30, 0, tzinfo=timezone.utc)


def _rss_body() -> str:
    stamp = format_datetime(PUBLISHED_UTC)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel>
  <item>
    <title>Gold prices hit record high</title>
    <link>https://example.invalid/digest/a?utm_source=rss</link>
    <pubDate>{stamp}</pubDate>
    <description>Bullion demand surges across Asia.</description>
  </item>
  <item>
    <title>Gold steadies as Fed holds rates</title>
    <link>https://example.invalid/digest/b</link>
    <pubDate>{stamp}</pubDate>
    <description>Policy unchanged.</description>
  </item>
  <item>
    <title>Swimmer wins her third gold medal</title>
    <link>https://example.invalid/digest/medal</link>
    <pubDate>{stamp}</pubDate>
    <description>Sports roundup.</description>
  </item>
</channel></rss>"""


class _FakeResponse:
    status_code = 200

    def __init__(self, content: bytes) -> None:
        self.content = content


@pytest.fixture
def fake_digest_source(monkeypatch):
    """单个假来源 + 假 HTTP：抓取链路里只有 RSS 解析与落库是真实代码。"""
    monkeypatch.setattr(
        news_digest,
        "configured_sources",
        lambda: [
            SourceSpec(name="路透社", url="https://feed.invalid/rss", tier=1, relevance="gold")
        ],
    )
    monkeypatch.setattr(
        news_digest.requests,
        "get",
        lambda url, **kwargs: _FakeResponse(_rss_body().encode("utf-8")),
    )
    monkeypatch.setattr(news_digest.timeutil, "now_naive", lambda: NOW_LOCAL)


@pytest.mark.integration
def test_digest_route_is_not_swallowed_by_news_id(client):
    resp = client.get("/api/gold/news/digest")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [window["key"] for window in body["windows"]] == ["24h", "7d", "30d"]


@pytest.mark.integration
def test_empty_database_reports_unavailable_without_items(client):
    body = client.get("/api/gold/news/digest").json()

    assert body["has_data"] is False
    assert body["unavailable_reason"]
    assert body["last_fetch"] is None
    assert all(window["items"] == [] for window in body["windows"])


@pytest.mark.integration
def test_manual_refresh_stores_items_and_get_returns_them(client, fake_digest_source):
    refresh = client.post("/api/gold/news/digest/refresh")
    assert refresh.status_code == 200, refresh.text
    report = refresh.json()

    assert report["success"] is True
    assert report["ok_sources"] == 1 and report["failed_sources"] == 0
    # 体育金（gold medal）被过滤；其余两条落库
    assert report["new_items"] == 2
    assert report["skipped_filtered"] == 1

    body = client.get("/api/gold/news/digest").json()
    assert body["has_data"] is True
    assert body["unavailable_reason"] is None
    assert body["last_fetch"]["new_items"] == 2

    windows = {window["key"]: window for window in body["windows"]}
    for key in ("24h", "7d", "30d"):
        assert len(windows[key]["items"]) == 2
        titles = {item["title"] for item in windows[key]["items"]}
        assert "Swimmer wins her third gold medal" not in titles

    first = windows["24h"]["items"][0]
    assert first["rank"] == 1
    assert first["source"] == "路透社"
    assert first["tier_label"] == "一级信源"
    assert first["importance"] > 0 and first["confidence"] > 0
    assert first["signals"]
    # 入库前 URL 规范化：跟踪参数去掉，原文链接仍可点
    assert first["url"].startswith("https://example.invalid/digest/")
    assert "utm_source" not in first["url"]


@pytest.mark.integration
def test_second_refresh_dedupes_by_url(client, fake_digest_source):
    first = client.post("/api/gold/news/digest/refresh").json()
    second = client.post("/api/gold/news/digest/refresh").json()

    assert first["new_items"] == 2
    assert second["new_items"] == 0
    assert second["duplicates"] == 2
    assert second["success"] is True
