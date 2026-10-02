"""投资建议取新闻的方式。

原实现：

    cutoff_time = now - timedelta(hours=24)
    db.query(GoldNews).filter(GoldNews.created_at >= cutoff_time) \\
        .order_by(GoldNews.created_at.desc()).limit(20)

两个问题：

1. **过滤**按 `created_at`（入库时刻）：一条三天前发布、刚刚抓到的新闻会被算进来，
   而两小时前发布、昨天抓到的会被排除 —— 「最近24小时」的窗口没有意义。
2. **排序**也按 `created_at`：抓取是每 2 小时**批量**插入的，同一批的
   `created_at` 几乎相同，于是「最近 20 条」实际是这一批里的任意 20 条。

而且 `created_at` 是数据库 `func.now()` 生成的（库服务器时间），
按红线 5 也不该拿来与项目时区的时间比较。

其余四个服务用的是 `NewsService.get_recent_news()`（按 `published_at`），
这里现在也统一走它。
"""
from datetime import date, timedelta

import pytest

from app.models.news import GoldNews
from app.services.investment_advice_service import InvestmentAdviceAnalyzer
from app.utils import timeutil


def _add(db, title: str, published_at, created_at=None, url=None):
    db.add(
        GoldNews(
            title=title,
            content="x",
            url=url or f"https://e.invalid/{title}",
            source="测试源",
            published_at=published_at,
            created_at=created_at,
        )
    )


@pytest.mark.integration
def test_window_is_measured_from_publication_time(db_session):
    """窗口必须按**发布时刻**算，不是入库时刻。"""
    now = timeutil.now_naive()

    # 三天前发布，但刚刚才抓到（created_at = 现在）
    _add(db_session, "三天前发布但刚抓到", published_at=now - timedelta(days=3), created_at=now)
    # 两小时前发布，但昨天才抓到（created_at = 昨天）
    _add(db_session, "两小时前发布但昨天抓到", published_at=now - timedelta(hours=2),
         created_at=now - timedelta(days=1))
    db_session.commit()

    titles = {n["title"] for n in InvestmentAdviceAnalyzer()._fetch_recent_news(db_session, hours=24)}

    assert "两小时前发布但昨天抓到" in titles, "按入库时刻过滤，把真正新的新闻漏掉了"
    assert "三天前发布但刚抓到" not in titles, "按入库时刻过滤，把三天前的旧闻算成新的"


@pytest.mark.integration
def test_order_is_by_publication_time_not_insert_batch(db_session):
    """同一批抓进来的新闻，要按发布时间排序，而不是按入库顺序。"""
    now = timeutil.now_naive()
    batch_time = now  # 同一批：created_at 完全相同

    # 故意让「入库顺序」与「发布顺序」相反
    _add(db_session, "较早发布", published_at=now - timedelta(hours=5), created_at=batch_time)
    _add(db_session, "最新发布", published_at=now - timedelta(hours=1), created_at=batch_time)
    _add(db_session, "中间发布", published_at=now - timedelta(hours=3), created_at=batch_time)
    db_session.commit()

    result = InvestmentAdviceAnalyzer()._fetch_recent_news(db_session, hours=24)

    assert [n["title"] for n in result] == ["最新发布", "中间发布", "较早发布"]


@pytest.mark.integration
def test_respects_the_limit(db_session):
    now = timeutil.now_naive()
    for i in range(30):
        _add(db_session, f"新闻{i}", published_at=now - timedelta(minutes=i))
    db_session.commit()

    result = InvestmentAdviceAnalyzer()._fetch_recent_news(db_session, hours=24)

    assert len(result) == 20, f"应当只取 20 条，实际 {len(result)}"


# --------------------------------------------------------------------------- #
# 价格窗口：滚动 12 个月，命名如实
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_window_block_uses_a_rolling_window_not_a_hardcoded_year(db_session):
    """拼给 LLM 的价格块必须是滚动窗口，且不许再出现「波动区间 / 2025年至今」。

    数据停在 2025-06-30 而不是「今天」：窗口应当锚定这一行，而不是运行日；
    这正是原来写死 `datetime(2025, 1, 1)` 时做不到的事。
    """
    from app.models.gold_price import GoldPrice

    for day, close in [("2024-06-15", 600.0), ("2024-07-01", 700.0), ("2025-06-30", 900.0)]:
        db_session.add(GoldPrice(date=date.fromisoformat(day), close_price=close))
    db_session.commit()

    analyzer = InvestmentAdviceAnalyzer()
    window = analyzer._fetch_window_data(db_session)
    block = analyzer._format_window_block(window)

    assert window.window_end == date(2025, 6, 30)
    assert "近 12 个月" in block
    assert "+28.57%" in block                 # (900 − 700) / 700
    assert "非波动率" in block
    assert "波动区间" not in block
    assert "2025年至今" not in block


@pytest.mark.integration
def test_window_data_is_none_when_the_database_is_empty(db_session):
    """没有行情就返回 None，让 prompt 如实写「暂无行情数据」而不是造数。"""
    assert InvestmentAdviceAnalyzer()._fetch_window_data(db_session) is None
