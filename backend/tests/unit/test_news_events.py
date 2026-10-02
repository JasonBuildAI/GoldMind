# -*- coding: utf-8 -*-
"""事件标注与聚合入口守卫（2.0.2 第 4、5 条）。

规则必须确定性、可解释：同一个标题任何时候都得到同一组标签；
宁可漏标也不许把「金价」误标成「央行购金」。
"""
from __future__ import annotations

from app.services import news_events


def test_fomc_headline_is_tagged():
    tags = news_events.tag_events("美联储 FOMC 会议维持利率不变")
    assert news_events.EVENT_FOMC in tags
    assert news_events.EVENT_CENTRAL_BANK in tags
    assert news_events.event_labels(tags) == ["FOMC", "央行决议"]


def test_cpi_and_nfp_are_tagged_from_their_common_writings():
    assert news_events.tag_events("美国 9 月 CPI 高于预期") == [news_events.EVENT_CPI]
    assert news_events.tag_events("US CPI rises 0.4% in September") == [news_events.EVENT_CPI]
    assert news_events.tag_events("非农就业报告今晚公布") == [news_events.EVENT_NFP]
    assert news_events.tag_events("Nonfarm payrolls beat expectations") == [
        news_events.EVENT_NFP
    ]


def test_central_bank_gold_buying_needs_both_subject_and_action():
    assert news_events.tag_events("央行连续第 11 个月增持黄金") == [
        news_events.EVENT_CENTRAL_BANK_GOLD
    ]
    assert news_events.tag_events("Central bank gold reserves hit a record") == [
        news_events.EVENT_CENTRAL_BANK_GOLD
    ]
    # 只有「黄金储备」这个名词、没有主体时不许标（宁缺毋滥）。
    assert news_events.EVENT_CENTRAL_BANK_GOLD not in news_events.tag_events(
        "Gold reserves are in focus today"
    )


def test_plain_gold_news_gets_no_event_tag():
    """普通行情稿不该被硬塞事件标签。"""
    assert news_events.tag_events("金价周五收涨 0.5%", "市场情绪回暖") == []


def test_empty_text_yields_no_tags():
    assert news_events.tag_events(None, None) == []
    assert news_events.tag_events("", "") == []


def test_tags_are_deterministic_and_case_insensitive():
    first = news_events.tag_events("FOMC minutes show a hawkish tone")
    second = news_events.tag_events("fomc minutes show a hawkish tone")
    assert first == second == [news_events.EVENT_FOMC]


def test_describe_events_returns_a_readable_line():
    assert news_events.describe_events([news_events.EVENT_FOMC, news_events.EVENT_CPI]) == (
        "FOMC、美国CPI"
    )
    assert news_events.describe_events([]) == ""


def test_aggregator_hosts_are_recognized():
    assert news_events.is_aggregator_url("https://news.google.com/rss/articles/abc")
    assert news_events.is_aggregator_url("https://NEWS.GOOGLE.COM/rss/articles/abc")
    assert not news_events.is_aggregator_url("https://www.reuters.com/gold-abc")
    assert not news_events.is_aggregator_url("https://example.com/news.google.com.evil.test")
    assert not news_events.is_aggregator_url(None)
    assert not news_events.is_aggregator_url("不是链接")


def test_prompt_formats_event_tags_and_aggregator_marker():
    """prompt 里要能看到事件标签与聚合提示，否则模型拿不到这层信息。"""
    from app.services.news_service import format_news_for_prompt

    text = format_news_for_prompt(
        [
            {
                "title": "FOMC holds rates steady",
                "summary": "The committee left the target range unchanged.",
                "source": "Google News",
                "url": "https://news.google.com/rss/articles/xyz",
                "published_at": None,
            }
        ]
    )
    assert "（经聚合入口）" in text
    assert "事件：FOMC" in text
    assert text.index("事件：") < text.index("摘要：")
