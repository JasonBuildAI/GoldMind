"""高权威消息进入 LLM 分析输入 —— `services/analysis_input.py` 与摘要格式。

背景：消息板块（`news_digest_items`，13 个高权威信源）此前只服务展示层，
`load_recent_entries` 的文档明确写着「不进入 prompt」—— 央行 / 通讯社 /
交易所的原文对分析服务全部不可见。本组钉住四件事：

1. 合并去重：消息板块优先、URL 规范化后去重、缺 URL 退回标题；
2. 时间口径：只取窗口内条目，按发布时间倒序；
3. 摘要清洗：去 HTML、解实体、压空白、超长截断；
4. 五个分析路径的 prompt 确实能看到 digest 条目（把 `load_analysis_news`
   的 digest 分支改坏必须变红）。
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.models.news import GoldNews
from app.models.news_digest import NewsDigestItem
from app.services.analysis_input import load_analysis_news, merge_news_entries
from app.services.news_service import clean_summary_for_prompt, format_news_for_prompt
from app.utils import timeutil

DIGEST_TITLE = "路透独家：央行三季度购金量创历史新高"


def _digest_item(
    db,
    *,
    title: str,
    hours_ago: float = 1.0,
    url: str | None = None,
    summary: str = "",
    source: str = "路透社",
    tier: int = 1,
):
    moment = timeutil.now_naive()
    row = NewsDigestItem(
        title=title,
        summary=summary,
        source=source,
        source_key="reuters",
        authority_tier=tier,
        url=url or f"https://digest.invalid/{abs(hash(title)) % 10**8}",
        published_at=moment - timedelta(hours=hours_ago),
        fetched_at=moment,
    )
    db.add(row)
    db.commit()
    return row


def _gold_news(db, *, title: str, hours_ago: float = 1.0, url: str | None = None, content: str = ""):
    moment = timeutil.now_naive()
    row = GoldNews(
        title=title,
        content=content,
        source="旧版RSS",
        url=url or f"https://goldnews.invalid/{abs(hash(title)) % 10**8}",
        published_at=moment - timedelta(hours=hours_ago),
    )
    db.add(row)
    db.commit()
    return row


# --------------------------------------------------------------------------- #
# 合并与去重（纯函数）
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_digest_entries_win_when_normalized_urls_match():
    """同一条新闻两条通道都有时，保留消息板块版本（带 tier 与摘要）。"""
    now = timeutil.now_naive()
    digest = {
        "title": "消息板块版本",
        "summary": "高权威摘要",
        "source": "路透社",
        "url": "https://ex.invalid/a?utm_source=rss",
        "published_at": now,
        "tier": 1,
    }
    legacy = {
        "title": "gold_news 版本",
        "summary": "摘要",
        "source": "旧版RSS",
        "url": "https://ex.invalid/a",
        "published_at": now,
    }

    merged = merge_news_entries([digest], [legacy])

    assert len(merged) == 1
    assert merged[0]["title"] == "消息板块版本"


@pytest.mark.unit
def test_entries_without_url_dedupe_by_whitespace_insensitive_title():
    now = timeutil.now_naive()
    first = {"title": "金价 突破 新高", "url": "", "published_at": now}
    second = {"title": "金价突破新高", "url": "  ", "published_at": now}

    merged = merge_news_entries([first], [second])

    assert len(merged) == 1
    assert merged[0] is first


@pytest.mark.unit
def test_merge_sorts_by_published_at_desc():
    now = timeutil.now_naive()
    older = {"title": "旧", "url": "", "published_at": now - timedelta(hours=3)}
    newer = {"title": "新", "url": "", "published_at": now - timedelta(hours=1)}

    merged = merge_news_entries([older], [newer])

    assert [item["title"] for item in merged] == ["新", "旧"]


# --------------------------------------------------------------------------- #
# 统一入口（数据库）
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_load_analysis_news_reads_both_channels(db_session):
    _digest_item(db_session, title=DIGEST_TITLE, summary="世界黄金协会数据", hours_ago=0.5)
    _gold_news(db_session, title="旧通道行情快讯", hours_ago=2)

    items = load_analysis_news(db_session, hours=24)

    titles = [item["title"] for item in items]
    assert titles == [DIGEST_TITLE, "旧通道行情快讯"], "按发布时间倒序"
    assert items[0]["summary"] == "世界黄金协会数据"
    assert items[0]["tier"] == 1


@pytest.mark.integration
def test_load_analysis_news_excludes_entries_outside_the_window(db_session):
    _digest_item(db_session, title="两天前的旧消息", hours_ago=48)

    assert load_analysis_news(db_session, hours=24) == []


@pytest.mark.integration
def test_load_analysis_news_limit_slices_after_merge(db_session):
    for index in range(5):
        _digest_item(db_session, title=f"消息{index}", hours_ago=index + 1)

    items = load_analysis_news(db_session, hours=24, limit=3)

    assert [item["title"] for item in items] == ["消息0", "消息1", "消息2"]


# --------------------------------------------------------------------------- #
# 摘要清洗
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_clean_summary_removes_html_and_entities():
    raw = "<p>Fed&nbsp;holds&nbsp;<b>rates</b> &amp; gold jumps</p>"

    assert clean_summary_for_prompt(raw) == "Fed holds rates & gold jumps"


@pytest.mark.unit
def test_clean_summary_collapses_whitespace():
    assert clean_summary_for_prompt("a\n\n  b\t c") == "a b c"


@pytest.mark.unit
def test_clean_summary_truncates_long_text_with_ellipsis():
    text = clean_summary_for_prompt("字" * 500)

    assert text[:120] == "字" * 120
    assert text.endswith("…")
    assert len(text) == 121


@pytest.mark.unit
def test_clean_summary_handles_none():
    assert clean_summary_for_prompt(None) == ""


@pytest.mark.unit
def test_prompt_includes_the_truncated_summary():
    item = {
        "title": "标题",
        "source": "路透社",
        "summary": "<p>正文要点</p>" + "长" * 500,
        "published_at": timeutil.now_naive(),
    }

    text = format_news_for_prompt([item])

    assert "摘要：" in text
    assert "正文要点" in text
    assert "…" in text


# --------------------------------------------------------------------------- #
# 五个分析路径确实能看到 digest 条目
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_bullish_factor_prompt_sees_digest_entry(db_session, fake_llm):
    from app.services.bullish_factor_service import BullishFactorAnalyzer

    _digest_item(db_session, title=DIGEST_TITLE)

    BullishFactorAnalyzer()._analyze_with_traditional_llm(db_session)

    assert fake_llm.calls, "有新闻却没用 LLM"
    assert DIGEST_TITLE in fake_llm.calls[0]


@pytest.mark.integration
def test_bearish_factor_prompt_sees_digest_entry(db_session, fake_llm):
    from app.services.bearish_factor_service import BearishFactorAnalyzer

    _digest_item(db_session, title=DIGEST_TITLE)

    BearishFactorAnalyzer()._analyze_with_traditional_llm(db_session)

    assert fake_llm.calls, "有新闻却没用 LLM"
    assert DIGEST_TITLE in fake_llm.calls[0]


@pytest.mark.integration
def test_institution_prompt_sees_digest_entry(db_session, fake_llm):
    from app.services.institution_prediction_service import InstitutionPredictionAnalyzer

    _digest_item(db_session, title=DIGEST_TITLE)

    InstitutionPredictionAnalyzer()._analyze_with_traditional_llm(db_session)

    assert fake_llm.calls, "有新闻却没用 LLM"
    assert DIGEST_TITLE in fake_llm.calls[0]


@pytest.mark.integration
def test_investment_advice_prompt_sees_digest_entry(db_session, fake_llm):
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer

    _digest_item(db_session, title=DIGEST_TITLE)

    InvestmentAdviceAnalyzer().analyze(db_session, "震荡", [], [], [])

    assert fake_llm.calls, "有新闻却没用 LLM"
    assert DIGEST_TITLE in fake_llm.calls[0]


@pytest.mark.integration
def test_market_summary_prompt_sees_digest_entry(db_session, fake_llm):
    from app.services.market_summary_service import MarketSummaryAnalyzer

    _digest_item(db_session, title=DIGEST_TITLE)

    MarketSummaryAnalyzer().analyze(
        db_session, "震荡", [], [], [], recent_news=load_analysis_news(db_session)
    )

    assert fake_llm.calls, "有新闻却没用 LLM"
    assert DIGEST_TITLE in fake_llm.calls[0]
