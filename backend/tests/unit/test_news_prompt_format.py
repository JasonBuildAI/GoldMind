"""新闻拼进 prompt 的格式 —— 统一入口 `format_news_for_prompt`。

这一组的由来：五个分析服务**各写一份**拼装代码，其中
`investment_advice_service` 用的是 `created_at`（**入库时刻**）而不是
`published_at`（**发布时刻**）：

    f"- [{news.created_at.strftime('%Y-%m-%d %H:%M')}] {news.title}"

等于告诉模型「这条新闻是刚刚抓到的」，而它可能是 20 小时前的。
`created_at` 还来自数据库的 `func.now()`（库服务器本地时间），
按项目红线（AGENTS.md 第 5 条）也不该直接当时间展示。
"""
from datetime import datetime, timedelta

import pytest

from app.models.news import GoldNews
from app.services.news_service import NEWS_PROMPT_LIMIT, format_news_for_prompt
from app.utils import timeutil


def _news(**kwargs) -> GoldNews:
    base = {
        "title": "测试标题",
        "content": "正文",
        "url": "https://example.invalid/a",
        "source": "测试源",
        "sentiment": None,
    }
    base.update(kwargs)
    return GoldNews(**base)


@pytest.mark.unit
def test_default_limit_is_the_shared_constant():
    """默认条数只有一个真源：NEWS_PROMPT_LIMIT。

    这个值不是随手定的：15 条新闻的看跌请求实测会被端点以
    `finish_reason=content_filter` 拒绝（正文 "The request was rejected
    because it was considered high risk"），10 条通过 —— 语料里的冲突类
    内容越多越容易触发。条数飘回 15 就等于把这个回归放回去。
    """
    items = [
        _news(title=f"第{i}条新闻", published_at=timeutil.now_naive())
        for i in range(NEWS_PROMPT_LIMIT + 5)
    ]

    text = format_news_for_prompt(items)

    assert text.count("- [") == NEWS_PROMPT_LIMIT


# --------------------------------------------------------------------------- #
# 时间字段
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_uses_published_at_not_created_at():
    """回归：必须用**发布时刻**，不能用**入库时刻**。"""
    published = timeutil.now_naive() - timedelta(hours=20)
    created = timeutil.now_naive()
    item = _news(published_at=published, created_at=created)

    text = format_news_for_prompt([item])

    assert published.strftime("%Y-%m-%d %H:%M") in text
    assert created.strftime("%Y-%m-%d %H:%M") not in text, "用的是入库时刻，不是发布时刻"


@pytest.mark.unit
def test_falls_back_to_created_at_when_published_is_missing():
    """发布时刻缺失时回退到入库时刻 —— 有总比没有强。"""
    created = timeutil.now_naive() - timedelta(hours=3)
    item = _news(published_at=None, created_at=created)

    text = format_news_for_prompt([item])

    assert created.strftime("%Y-%m-%d %H:%M") in text


@pytest.mark.unit
def test_says_unknown_rather_than_guessing():
    """两个时间都没有时说「时间未知」，不要拿当前时间顶上。"""
    item = _news(published_at=None, created_at=None)

    text = format_news_for_prompt([item])

    assert "时间未知" in text
    assert timeutil.now_naive().strftime("%Y-%m-%d") not in text


# --------------------------------------------------------------------------- #
# 形状与边界
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_accepts_orm_objects_and_dicts():
    """库里取的是 ORM 对象，联网搜索拿到的是 dict，两种都要支持。"""
    published = timeutil.now_naive()
    orm = _news(title="来自数据库", published_at=published, source="库")
    raw = {"title": "来自联网搜索", "source": "网", "published_at": published}

    text = format_news_for_prompt([orm, raw])

    assert "来自数据库" in text
    assert "来自联网搜索" in text


@pytest.mark.unit
def test_respects_the_limit():
    items = [_news(title=f"新闻{i}", url=f"https://e.invalid/{i}") for i in range(30)]

    text = format_news_for_prompt(items, limit=5)

    assert text.count("- [") == 5, "limit=5 应当只输出 5 条（每条可带一行摘要）"
    assert "新闻4" in text
    assert "新闻5" not in text


@pytest.mark.unit
def test_empty_input_says_so():
    assert format_news_for_prompt([]) == "暂无新闻数据"
    # 全是空标题也一样
    assert format_news_for_prompt([_news(title="   ")]) == "暂无新闻数据"


@pytest.mark.unit
def test_skips_items_without_a_title():
    good = _news(title="有标题", url="https://e.invalid/1")
    bad = _news(title="", url="https://e.invalid/2")

    text = format_news_for_prompt([bad, good])

    assert "有标题" in text
    assert text.count("- [") == 1, "空标题的条目应当被跳过"


@pytest.mark.unit
def test_missing_source_does_not_render_none():
    item = _news(source=None)

    text = format_news_for_prompt([item])

    assert "None" not in text
    assert "未知来源" in text
