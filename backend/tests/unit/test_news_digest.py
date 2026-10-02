"""消息板块单元测试。

重点钉住四类会静默出错的地方：

1. 评分口径（权重写反 / 时效写反时，榜单只是「看起来还能用」）；
2. 窗口边界与 Top10 截断（差一小时、多一条，用户看到的就是另一份榜单）；
3. 聚类与来源覆盖计数（把对立的两条并成一条比不合并更糟）；
4. 抓取兜底（无时间 / 无链接的条目不能猜一个时间顶替，单源失败不能拖垮全量）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.config import settings
from app.models.news_digest import NewsDigestItem
from app.services import news_digest
from app.services.news_digest import (
    DigestRecord,
    NewsDigestService,
    SourceFetchResult,
    SourceSpec,
    _apply_scores,
    build_digest_payload,
    cluster_indices,
    matches_relevance,
    parse_digest_sources,
    relevance_score,
    title_tokens,
)
from app.utils import timeutil

FEED_TIME = (2026, 2, 3, 10, 30, 0, 0, 0, 0)
EXPECTED_PUBLISHED = (
    datetime(2026, 2, 3, 10, 30, tzinfo=timezone.utc)
    .astimezone(ZoneInfo(settings.SCHEDULER_TIMEZONE))
    .replace(tzinfo=None)
)


# --------------------------------------------------------------------------- #
# 造数据
# --------------------------------------------------------------------------- #
def _add_item(
    db,
    *,
    title: str,
    hours_ago: float,
    now: datetime | None = None,
    source: str = "Reuters",
    tier: int = 1,
    url: str | None = None,
    summary: str = "",
    source_key: str | None = None,
):
    moment = now or timeutil.now_naive()
    row = NewsDigestItem(
        title=title,
        summary=summary,
        source=source,
        source_key=source_key or news_digest.normalize_source_key(source),
        authority_tier=tier,
        url=url or f"https://example.invalid/{abs(hash(title)) % 10**8}/{hours_ago}",
        published_at=moment - timedelta(hours=hours_ago),
        fetched_at=moment,
    )
    db.add(row)
    db.commit()
    return row


def _fake_item(url: str, title: str, *, source: str = "甲", tier: int = 1):
    moment = timeutil.now_naive()
    return {
        "title": title,
        "summary": "Gold market summary",
        "url": url,
        "published_at": moment - timedelta(hours=1),
        "fetched_at": moment,
        "source": source,
        "source_key": news_digest.normalize_source_key(source),
        "authority_tier": tier,
    }


# --------------------------------------------------------------------------- #
# 来源解析
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_parse_digest_sources_parses_valid_entries():
    specs = parse_digest_sources("路透社|https://a.invalid/rss|1|gold,CNBC|https://b.invalid/rss|2|monetary")

    assert specs == [
        SourceSpec(name="路透社", url="https://a.invalid/rss", tier=1, relevance="gold"),
        SourceSpec(name="CNBC", url="https://b.invalid/rss", tier=2, relevance="monetary"),
    ]


@pytest.mark.unit
def test_parse_digest_sources_skips_malformed():
    raw = "缺字段|https://x.invalid,|https://x.invalid|1|gold,好名字||1|gold,坏tier|https://x.invalid|9|gold,坏模式|https://x.invalid|1|sports,,正常|https://ok.invalid/rss|1|gold"

    specs = parse_digest_sources(raw)

    assert [spec.name for spec in specs] == ["正常"]


@pytest.mark.unit
def test_parse_digest_sources_handles_empty():
    assert parse_digest_sources("") == []
    assert parse_digest_sources(None) == []


@pytest.mark.unit
def test_default_sources_are_multi_category_and_https():
    """默认池必须含央行 / 通讯社 / 行业机构 / 专业财经，且地址全是 https。"""
    specs = news_digest.configured_sources()

    assert len(specs) >= 12, f"默认来源只有 {len(specs)} 个，来源多样性不足"
    assert all(spec.url.startswith("https://") for spec in specs)
    assert {spec.tier for spec in specs} == {1, 2}
    assert {spec.relevance for spec in specs} == {"gold", "monetary"}
    hosts = " ".join(spec.url for spec in specs)
    assert "federalreserve.gov" in hosts, "缺少美联储（官方货币政策）"
    assert "ecb.europa.eu" in hosts, "缺少欧洲央行（官方）"
    assert "reuters.com" in hosts, "缺少路透社（通讯社）"
    assert "mining.com" in hosts, "缺少矿业行业源"
    assert "gold.org" in hosts, "缺少世界黄金协会（行业机构）"


@pytest.mark.unit
def test_configured_sources_use_settings_override(monkeypatch):
    monkeypatch.setattr(settings, "NEWS_DIGEST_SOURCES", "甲|https://a.invalid/rss|1|gold")

    specs = news_digest.configured_sources()

    assert [spec.name for spec in specs] == ["甲"]


# --------------------------------------------------------------------------- #
# 相关性过滤
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_gold_mode_rejects_sports_gold():
    """美联社源里真实出现过体育金标题，不能进黄金消息榜。"""
    title = "Chinese 13-year-old Yu Zidi wins her third swimming gold medal"

    assert matches_relevance(title, "", "gold") is False
    assert matches_relevance(title, "", "monetary") is False


@pytest.mark.unit
def test_gold_mode_accepts_plain_gold_headline():
    assert matches_relevance("Gold steadies ahead of US payrolls data", "", "gold") is True
    assert matches_relevance("Bullion demand rises in Asia", "", "gold") is True
    assert matches_relevance("Gold prices hit record high", "", "gold") is True


@pytest.mark.unit
def test_gold_mode_rejects_figurative_gold_seen_in_real_feeds():
    """真实抓取（2026-10-02）里混进过榜单的隐喻式 gold，两类都要挡掉。"""
    sports = "Eala's gold dream ends in Nagoya as India set for cricket showdown with Pakistan"
    fashion = "Saint Laurent goes for gold in Paris show that may be Vaccarello's finale"

    # 综合源的摘要经常只是「标题 + 来源名」，用同样的文本验证摘要路径不会放行
    assert matches_relevance(sports, f"{sports} Reuters", "gold") is False
    assert matches_relevance(fashion, f"{fashion} Reuters", "gold") is False
    # 同一天同一条真实行情标题仍是正例：修误判不能把真新闻一起挡掉
    market = "Gold steadies ahead of US payrolls data, heads for weekly decline"
    assert matches_relevance(market, f"{market} Reuters", "gold") is True


@pytest.mark.unit
def test_gold_mode_rejects_unrelated_and_goldman():
    assert matches_relevance("Stocks rally as earnings beat", "Equities extend gains", "gold") is False
    # "Goldman" 里没有独立的 gold 词，不能误命中
    assert matches_relevance("Goldman Sachs raises oil price target", "", "gold") is False


@pytest.mark.unit
def test_monetary_mode_accepts_official_rate_statement():
    title = "Federal Reserve issues FOMC statement"

    assert matches_relevance(title, "", "monetary") is True
    assert matches_relevance(title, "", "gold") is False


@pytest.mark.unit
def test_relevance_score_prefers_specific_gold_terms():
    specific = relevance_score("Gold prices hit record high", "Bullion demand surges")
    generic = relevance_score("Gold steadies", "")
    monetary_only = relevance_score("Federal Reserve issues FOMC statement", "")

    assert 0.0 <= monetary_only < generic <= specific <= 1.0


# --------------------------------------------------------------------------- #
# 评分
# --------------------------------------------------------------------------- #
def _record(**overrides) -> DigestRecord:
    values = {
        "id": 1,
        "title": "Gold price climbs",
        "summary": "",
        "source": "Reuters",
        "source_key": "reuters",
        "tier": 1,
        "url": "https://example.invalid/a",
        "published_at": timeutil.now_naive() - timedelta(hours=1),
        "age_hours": 1.0,
        "relevance": 0.6,
    }
    values.update(overrides)
    return DigestRecord(**values)


@pytest.mark.unit
def test_authority_tier_raises_both_scores():
    first = _record(tier=1)
    second = _record(tier=2)

    _apply_scores(first, coverage=1)
    _apply_scores(second, coverage=1)

    assert first.importance > second.importance
    assert first.confidence > second.confidence


@pytest.mark.unit
def test_coverage_raises_both_scores():
    single = _record()
    covered = _record()

    _apply_scores(single, coverage=1)
    _apply_scores(covered, coverage=3)

    assert covered.importance > single.importance
    assert covered.confidence > single.confidence
    assert "3 家来源同题报道" in covered.signals


@pytest.mark.unit
def test_recency_decays_importance():
    fresh = _record(age_hours=1.0)
    stale = _record(age_hours=700.0)

    _apply_scores(fresh, coverage=1)
    _apply_scores(stale, coverage=1)

    assert fresh.importance > stale.importance


@pytest.mark.unit
def test_signals_explain_the_ranking():
    record = _record(tier=1, title="Gold prices hit record high", age_hours=2.0)

    _apply_scores(record, coverage=2)

    assert "一级信源：官方 / 通讯社 / 行业机构" in record.signals
    assert "2 家来源同题报道" in record.signals
    assert "标题含黄金关键词" in record.signals
    assert "24 小时内发布" in record.signals


# --------------------------------------------------------------------------- #
# 聚类
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_cluster_merges_syndicated_titles():
    tokens = [title_tokens(title) for title in ["Gold prices hit record high", "Gold prices hit record high"]]

    groups = cluster_indices(tokens)

    assert len(groups) == 1 and sorted(groups[0]) == [0, 1]


@pytest.mark.unit
def test_cluster_keeps_distinct_stories_apart():
    tokens = [
        title_tokens("Gold price rises as dollar weakens"),
        title_tokens("Gold price falls as yields jump"),
    ]

    groups = cluster_indices(tokens)

    assert len(groups) == 2


@pytest.mark.unit
def test_cluster_does_not_merge_on_a_single_shared_word():
    """只共享一个词（如 gold）时绝不合并 —— 那是不同事件的最低证据。"""
    tokens = [
        title_tokens("Gold settles higher in Asia"),
        title_tokens("Gold reserves expand in Europe"),
    ]

    groups = cluster_indices(tokens)

    assert len(groups) == 2


# --------------------------------------------------------------------------- #
# 窗口与 Top10
# --------------------------------------------------------------------------- #
RECENT_WORDS = [
    "rallies", "slips", "steadies", "jumps", "drops", "climbs",
    "eases", "surges", "dips", "falters", "rebounds", "retreats",
]
RECENT_TOPICS = [
    "payrolls", "inflation", "dollar", "yields", "tariffs", "elections",
    "holidays", "inventories", "shipments", "forecasts", "auctions", "minutes",
]


@pytest.mark.unit
def test_windows_cap_each_range_at_top_ten(db_session):
    now = timeutil.now_naive()
    for word, topic in zip(RECENT_WORDS, RECENT_TOPICS):
        _add_item(db_session, title=f"Gold price {word} after {topic}", hours_ago=1.5, now=now)

    payload = build_digest_payload(db_session, now=now)
    windows = {window["key"]: window for window in payload["windows"]}

    assert payload["has_data"] is True
    # 12 条候选在三个窗口里都只展示前 10
    for key in ("24h", "7d", "30d"):
        assert len(windows[key]["items"]) == 10
        assert windows[key]["total_clusters"] == 12


@pytest.mark.unit
def test_windows_filter_items_by_age(db_session):
    now = timeutil.now_naive()
    # 6 条候选都进得了各自窗口的 Top10，这里只验证时效边界
    _add_item(db_session, title="Gold price rises on fresh demand", hours_ago=1.5, now=now)
    _add_item(db_session, title="Bullion demand shifts in Asia", hours_ago=30, now=now)
    _add_item(db_session, title="Mining output report lifts sentiment", hours_ago=144, now=now)
    _add_item(db_session, title="Central bank reserve update published", hours_ago=192, now=now)
    _add_item(db_session, title="Jewellery consumption survey released", hours_ago=600, now=now)
    _add_item(db_session, title="Old market recap from last month", hours_ago=960, now=now)

    payload = build_digest_payload(db_session, now=now)
    titles = {
        window["key"]: {item["title"] for item in window["items"]}
        for window in payload["windows"]
    }

    assert "Gold price rises on fresh demand" in titles["24h"]
    # 30 小时前：进 7d，不进 24h
    assert "Bullion demand shifts in Asia" not in titles["24h"]
    assert "Bullion demand shifts in Asia" in titles["7d"]
    # 6 天前进 7d；8 天前进 30d、不进 7d；25 天前进 30d；40 天前哪都不进
    assert "Mining output report lifts sentiment" in titles["7d"]
    assert "Central bank reserve update published" not in titles["7d"]
    assert "Central bank reserve update published" in titles["30d"]
    assert "Jewellery consumption survey released" in titles["30d"]
    assert "Old market recap from last month" not in titles["24h"] | titles["7d"] | titles["30d"]


@pytest.mark.unit
def test_overlapping_windows_share_items_with_identical_scores(db_session):
    now = timeutil.now_naive()
    _add_item(db_session, title="Gold price climbs after payrolls", hours_ago=2, now=now)

    payload = build_digest_payload(db_session, now=now)

    by_window = {window["key"]: window["items"][0] for window in payload["windows"]}
    assert set(by_window) == {"24h", "7d", "30d"}
    assert by_window["24h"]["importance"] == by_window["7d"]["importance"] == by_window["30d"]["importance"]
    assert by_window["24h"]["id"] == by_window["7d"]["id"] == by_window["30d"]["id"]


@pytest.mark.unit
def test_items_are_sorted_by_importance_then_confidence(db_session):
    now = timeutil.now_naive()
    _add_item(db_session, title="Gold price rallies on rate cut bets", hours_ago=1, now=now, tier=1)
    _add_item(db_session, title="Gold price retreats on auction data", hours_ago=1, now=now, tier=2)
    _add_item(db_session, title="Bullion demand cools in Asia", hours_ago=1, now=now, tier=2, source="CNBC")

    payload = build_digest_payload(db_session, now=now)
    items = payload["windows"][0]["items"]

    scores = [(item["importance"], item["confidence"]) for item in items]
    assert scores == sorted(scores, reverse=True)
    assert [item["rank"] for item in items] == list(range(1, len(items) + 1))
    top_titles = [item["title"] for item in items]
    assert top_titles.index("Gold price rallies on rate cut bets") < top_titles.index(
        "Gold price retreats on auction data"
    )


@pytest.mark.unit
def test_tie_break_prefers_newer_id_when_all_else_equal(db_session):
    now = timeutil.now_naive()
    first = _add_item(db_session, title="Gold price climbs after payrolls", hours_ago=2, now=now)
    second = _add_item(db_session, title="Gold price climbs after auctions", hours_ago=2, now=now)
    # 两条内容与时间完全同级（仅标题词不同、relevance 相同），按 id 倒序
    assert first.id != second.id

    payload = build_digest_payload(db_session, now=now)
    items = payload["windows"][0]["items"]
    ids = [item["id"] for item in items]

    assert ids[0] == max(ids)


@pytest.mark.unit
def test_cluster_counts_distinct_sources_and_lists_related(db_session):
    now = timeutil.now_naive()
    _add_item(
        db_session, title="Gold ETF inflows hit record", hours_ago=3, now=now,
        source="Reuters", tier=1,
    )
    _add_item(
        db_session, title="Gold ETF inflows hit record", hours_ago=3, now=now,
        source="Bloomberg", tier=2,
    )

    payload = build_digest_payload(db_session, now=now)
    items = payload["windows"][0]["items"]

    assert len(items) == 1, "同题报道应合并为一条"
    item = items[0]
    assert item["coverage_count"] == 2
    assert item["source"] == "Reuters", "代表条应取簇内分数最高的来源"
    assert [related["source"] for related in item["related"]] == ["Bloomberg"]
    assert "2 家来源同题报道" in item["signals"]


@pytest.mark.unit
def test_empty_database_reports_unavailable_with_reason(db_session):
    payload = build_digest_payload(db_session)

    assert payload["has_data"] is False
    assert all(window["items"] == [] for window in payload["windows"])
    assert payload["unavailable_reason"], "空库必须给出原因，页面据此显示「不可用」"
    assert "抓取" in payload["unavailable_reason"]
    assert payload["last_fetch"] is None


# --------------------------------------------------------------------------- #
# 抓取
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, status_code: int = 200, content: bytes = b"<rss/>"):
        self.status_code = status_code
        self.content = content


class _FakeFeed:
    def __init__(self, entries):
        self.entries = entries


def _entry(title="Gold price steadies ahead of payrolls", link="https://example.invalid/a", published=FEED_TIME, summary="Gold market update"):
    entry = {"title": title, "link": link, "summary": summary}
    if published is not None:
        entry["published_parsed"] = published
    return entry


@pytest.mark.unit
def test_fetch_source_keeps_valid_entries_and_reports_skips(monkeypatch):
    entries = [
        {
            **_entry(title="Gold price steadies ahead of payrolls - Reuters"),
            "source": {"title": "Reuters"},
        },
        _entry(title="No timestamp gold item", published=None),
        _entry(title="Gold item without link", link=""),
        _entry(title="Stocks rally as earnings beat", summary="Equities extend gains"),
        _entry(title=""),
    ]
    monkeypatch.setattr(news_digest.requests, "get", lambda url, **kwargs: _FakeResponse())
    monkeypatch.setattr(news_digest.feedparser, "parse", lambda content: _FakeFeed(entries))
    spec = SourceSpec(name="路透社", url="https://feed.invalid/rss", tier=1, relevance="gold")

    result = news_digest.fetch_source(spec)

    assert result.error is None
    assert result.entries == 5
    assert result.kept == 1
    assert result.skipped_no_time == 1
    assert result.skipped_no_url == 1
    assert result.skipped_filtered == 1
    assert result.skipped_no_title == 1

    item = result.items[0]
    assert item["title"] == "Gold price steadies ahead of payrolls", "来源后缀应被剥掉"
    assert item["source"] == "Reuters", "应优先用条目自带的媒体名"
    assert item["source_key"] == "reuters"
    assert item["authority_tier"] == 1
    assert item["url"] == "https://example.invalid/a"
    # RSS 的 UTC 时间必须换算成本地时间（与 news_service 同一口径）
    assert item["published_at"] == EXPECTED_PUBLISHED


@pytest.mark.unit
def test_fetch_source_reports_http_error(monkeypatch):
    monkeypatch.setattr(news_digest.requests, "get", lambda url, **kwargs: _FakeResponse(status_code=503))
    spec = SourceSpec(name="测试源", url="https://feed.invalid/rss", tier=1, relevance="gold")

    result = news_digest.fetch_source(spec)

    assert result.error is not None and "503" in result.error
    assert result.items == []


@pytest.mark.unit
def test_fetch_source_reports_network_exception(monkeypatch):
    def _boom(url, **kwargs):
        raise RuntimeError("连接被重置")

    monkeypatch.setattr(news_digest.requests, "get", _boom)
    spec = SourceSpec(name="测试源", url="https://feed.invalid/rss", tier=1, relevance="gold")

    result = news_digest.fetch_source(spec)

    assert result.error is not None and "连接被重置" in result.error


@pytest.mark.unit
def test_monetary_source_accepts_rate_statement(monkeypatch):
    entries = [
        {
            "title": "Federal Reserve issues FOMC statement",
            "link": "https://example.invalid/fomc",
            "summary": "",
            "published_parsed": FEED_TIME,
        }
    ]
    monkeypatch.setattr(news_digest.requests, "get", lambda url, **kwargs: _FakeResponse())
    monkeypatch.setattr(news_digest.feedparser, "parse", lambda content: _FakeFeed(entries))
    spec = SourceSpec(name="美联储（货币政策）", url="https://feed.invalid/rss", tier=1, relevance="monetary")

    result = news_digest.fetch_source(spec)

    assert result.kept == 1
    assert result.items[0]["source"] == "美联储（货币政策）"


@pytest.mark.unit
def test_fetch_all_sources_isolates_failure_and_dedupes(db_session, monkeypatch):
    monkeypatch.setattr(
        settings,
        "NEWS_DIGEST_SOURCES",
        "甲|https://a.invalid/rss|1|gold,乙|https://b.invalid/rss|2|gold",
    )
    shared = _fake_item("https://shared.invalid/a", "Gold price shared story")

    def fake_fetch(spec, limit=news_digest.PER_SOURCE_LIMIT):
        if spec.name == "甲":
            result = SourceFetchResult(spec=spec, entries=2, kept=2)
            result.items = [shared, _fake_item("https://a.invalid/1", "Bullion demand rises")]
            return result
        result = SourceFetchResult(spec=spec)
        result.error = "RuntimeError: boom"
        return result

    monkeypatch.setattr(news_digest, "fetch_source", fake_fetch)

    report = NewsDigestService(db_session).fetch_all_sources()

    assert report["ok_sources"] == 1
    assert report["failed_sources"] == 1
    assert report["new_items"] == 2
    assert report["duplicates"] == 0
    assert report["sources"][1]["status"] == "error"
    assert "boom" in report["sources"][1]["error"]
    assert db_session.query(NewsDigestItem).count() == 2

    # 第二次抓取：URL 全部已存在，不再新增；报告如实计入 duplicates
    report_again = NewsDigestService(db_session).fetch_all_sources()
    assert report_again["new_items"] == 0
    assert report_again["duplicates"] == 2
    assert db_session.query(NewsDigestItem).count() == 2


@pytest.mark.unit
def test_fetch_report_is_persisted_for_the_api(db_session, monkeypatch):
    monkeypatch.setattr(settings, "NEWS_DIGEST_SOURCES", "甲|https://a.invalid/rss|1|gold")
    monkeypatch.setattr(
        news_digest,
        "fetch_source",
        lambda spec, limit=news_digest.PER_SOURCE_LIMIT: SourceFetchResult(
            spec=spec, entries=1, kept=1, items=[_fake_item("https://a.invalid/1", "Gold story")]
        ),
    )

    report = NewsDigestService(db_session).fetch_all_sources()

    cached = news_digest.last_fetch_report()
    assert cached is not None
    assert cached["fetched_at"] == report["fetched_at"]
    assert cached["new_items"] == 1
    assert cached["sources"][0]["name"] == "甲"


@pytest.mark.unit
def test_fetch_all_sources_calls_every_configured_source(db_session, monkeypatch):
    monkeypatch.setattr(
        settings,
        "NEWS_DIGEST_SOURCES",
        "甲|https://a.invalid/rss|1|gold,乙|https://b.invalid/rss|2|monetary",
    )
    seen: list[str] = []

    def fake_fetch(spec, limit=news_digest.PER_SOURCE_LIMIT):
        seen.append(spec.url)
        return SourceFetchResult(spec=spec)

    monkeypatch.setattr(news_digest, "fetch_source", fake_fetch)

    NewsDigestService(db_session).fetch_all_sources()

    assert sorted(seen) == ["https://a.invalid/rss", "https://b.invalid/rss"]


@pytest.mark.unit
def test_save_items_keeps_good_rows_when_one_row_is_unstorable(db_session):
    """一行坏数据只跳过该行，不拖垮整批。

    2026-10-02 的故障形态：一条超长 URL 让整批 INSERT 一起回滚，而报告把它
    显示成「全部重复」，页面永远是空的。逐行 savepoint 之后，坏行可数、
    好行照常入库。
    """
    service = NewsDigestService(db_session)
    good_a = _fake_item("https://a.invalid/good-a", "Gold price rises")
    bad = _fake_item("https://a.invalid/bad", "Gold price falls")
    bad["published_at"] = None  # NOT NULL 违反：真实数据库会拒绝这一行
    good_b = _fake_item("https://b.invalid/good-b", "Bullion demand climbs")

    inserted, skipped = service._save_items([good_a, bad, good_b])

    assert inserted == {"https://a.invalid/good-a", "https://b.invalid/good-b"}
    assert skipped == 1
    assert {row.url for row in db_session.query(NewsDigestItem).all()} == inserted


@pytest.mark.unit
def test_fetch_report_counts_rows_that_cannot_be_stored(db_session, monkeypatch):
    monkeypatch.setattr(settings, "NEWS_DIGEST_SOURCES", "甲|https://a.invalid/rss|1|gold")
    bad = _fake_item("https://a.invalid/bad", "Gold price falls")
    bad["published_at"] = None
    monkeypatch.setattr(
        news_digest,
        "fetch_source",
        lambda spec, limit=news_digest.PER_SOURCE_LIMIT: SourceFetchResult(
            spec=spec, entries=1, kept=1, items=[bad]
        ),
    )

    report = NewsDigestService(db_session).fetch_all_sources()

    assert report["skipped_unstorable"] == 1
    assert report["new_items"] == 0
    assert report["duplicates"] == 0  # 跳过的行不能被算成「重复」
    assert db_session.query(NewsDigestItem).count() == 0
