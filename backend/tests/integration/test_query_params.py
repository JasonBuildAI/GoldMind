"""查询参数的行为测试。

此前只测过「接口会不会 500」，没测过「参数到底有没有生效」。补上之后发现：

- `/prices/daily` 与 `/prices/correlation` 的 `limit` **被声明、被校验、从未生效** ——
  传 `limit=3` 照样返回全部数据
- `/prices/daily` 传非法日期会抛 ValueError 冒到中间件，客户端拿到 500（应当是 422）
- `/news?sentiment=positive` 一条都匹配不到：列类型 `Enum(SentimentType)` 在库里存的是
  枚举名（POSITIVE），而接口对外用小写。**接口自己的输出不能当作输入用**
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest


def _seed(client) -> None:
    """塞入 10 天金价/美元指数 + 6 条新闻 + 各 4 条因子。"""
    from app.database import SessionLocal
    from app.models.analysis import FactorType, ImpactLevel, MarketFactor
    from app.models.gold_price import DollarIndex, GoldPrice
    from app.models.news import GoldNews, SentimentType

    db = SessionLocal()
    try:
        base = date(2025, 1, 2)
        for i in range(10):
            d = base + timedelta(days=i)
            db.add(GoldPrice(date=d, open_price=2600 + i, high_price=2610 + i,
                             low_price=2590 + i, close_price=2605 + i, volume=100,
                             change_percent=0.2))
            db.add(DollarIndex(date=d, open_price=108, high_price=108.5,
                               low_price=107.5, close_price=108.2))
        for i in range(6):
            db.add(GoldNews(
                title=f"新闻{i}",
                url=f"https://example.invalid/{i}",
                source="A" if i % 2 == 0 else "B",
                sentiment=SentimentType.POSITIVE if i % 3 == 0 else SentimentType.NEGATIVE,
                published_at=datetime(2025, 1, 2 + i),
                content="x",
            ))
        for i in range(4):
            # 必须传枚举成员：type 与 impact 的列类型都是 Enum(...)，
            # 直接塞小写字符串会写进一个读不出来的值（生产代码也是传成员的）。
            db.add(MarketFactor(type=FactorType.BULLISH, title=f"多{i}", details=[],
                                impact=ImpactLevel.HIGH))
            db.add(MarketFactor(type=FactorType.BEARISH, title=f"空{i}", details=[],
                                impact=ImpactLevel.LOW))
        db.commit()
    finally:
        db.close()


@pytest.fixture
def seeded(client):
    _seed(client)
    return client


# --------------------------------------------------------------------------- #
# /prices/daily
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_daily_limit_actually_limits(seeded):
    """回归：limit 被声明、被校验，却从未传给查询，传 3 也返回全部。"""
    body = seeded.get("/api/gold/prices/daily?limit=3&include_realtime=false").json()

    assert len(body) == 3


@pytest.mark.integration
def test_daily_limit_holds_even_with_the_realtime_point(seeded):
    """补上实时点之后也不能超过 limit —— 否则「最多 N 条」这个承诺就不成立。"""
    body = seeded.get("/api/gold/prices/daily?limit=3&include_realtime=true").json()

    assert len(body) == 3


@pytest.mark.integration
def test_daily_limit_keeps_the_most_recent_points(seeded):
    body = seeded.get("/api/gold/prices/daily?limit=3&include_realtime=false").json()

    dates = [p["date"] for p in body]
    assert dates == sorted(dates), "应当按时间升序返回"
    all_dates = [p["date"] for p in
                 seeded.get("/api/gold/prices/daily?include_realtime=false").json()]
    assert dates == all_dates[-3:], "limit 应当保留最近的 N 个点"


@pytest.mark.integration
@pytest.mark.parametrize("value", ["0", "-5", "999"])
def test_daily_rejects_out_of_range_limit(seeded, value):
    assert seeded.get(f"/api/gold/prices/daily?limit={value}").status_code == 422


@pytest.mark.integration
def test_daily_invalid_date_is_422_not_500(seeded):
    """回归：非法日期原本抛 ValueError，客户端拿到 500。"""
    for param in ("start_date", "end_date"):
        response = seeded.get(f"/api/gold/prices/daily?{param}=not-a-date")

        assert response.status_code == 422, f"{param} 非法应当返回 422"
        assert response.status_code != 500


@pytest.mark.integration
def test_daily_date_range_filters(seeded):
    body = seeded.get(
        "/api/gold/prices/daily"
        "?start_date=2025-01-03&end_date=2025-01-05&include_realtime=false"
    ).json()

    assert [p["date"] for p in body] == ["2025-01-03", "2025-01-04", "2025-01-05"]


# --------------------------------------------------------------------------- #
# /prices/correlation
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_correlation_limit_actually_limits(seeded):
    """回归：service 收了 limit 参数却从不使用。"""
    body = seeded.get("/api/gold/prices/correlation?limit=4&include_realtime=false").json()

    assert len(body) == 4


@pytest.mark.integration
def test_correlation_limit_holds_with_the_realtime_point(seeded):
    body = seeded.get("/api/gold/prices/correlation?limit=4&include_realtime=true").json()

    assert len(body) == 4


# --------------------------------------------------------------------------- #
# /news
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_news_limit_actually_limits(seeded):
    assert len(seeded.get("/api/gold/news?limit=2").json()) == 2


@pytest.mark.integration
@pytest.mark.parametrize("value", ["0", "-1", "999"])
def test_news_rejects_out_of_range_limit(seeded, value):
    assert seeded.get(f"/api/gold/news?limit={value}").status_code == 422


@pytest.mark.integration
def test_news_sentiment_filter_matches_the_value_it_returns(seeded):
    """**核心不变量**：接口返回的情感值必须能直接当过滤条件用。

    回归：`/news` 返回 `"sentiment": "positive"`，但
    `?sentiment=positive` 一条都匹配不到（库里存的是枚举名 POSITIVE），
    只有 `?sentiment=POSITIVE` 才有结果 —— 接口自己的输出不能当输入用。
    """
    first = seeded.get("/api/gold/news?limit=1").json()[0]
    returned = first["sentiment"]
    assert returned, "响应里应当带 sentiment"

    filtered = seeded.get(f"/api/gold/news?sentiment={returned}")

    assert filtered.status_code == 200, f"把自己返回的 {returned!r} 当过滤条件竟然失败"
    assert len(filtered.json()) > 0, (
        f"接口返回 sentiment={returned!r}，用它过滤却得到空结果"
    )


@pytest.mark.integration
def test_news_sentiment_filter_counts_are_right(seeded):
    positives = seeded.get("/api/gold/news?sentiment=positive").json()
    negatives = seeded.get("/api/gold/news?sentiment=negative").json()

    assert len(positives) == 2
    assert len(negatives) == 4
    assert all(n["sentiment"] == "positive" for n in positives)
    assert all(n["sentiment"] == "negative" for n in negatives)


@pytest.mark.integration
def test_news_rejects_an_unknown_sentiment(seeded):
    """认不出的取值应当是 422，而不是静默返回空列表。"""
    assert seeded.get("/api/gold/news?sentiment=garbage").status_code == 422


@pytest.mark.integration
def test_news_source_filter(seeded):
    assert len(seeded.get("/api/gold/news?source=A").json()) == 3
    assert seeded.get("/api/gold/news?source=ZZZ").json() == []


# --------------------------------------------------------------------------- #
# /factors
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_factors_type_filter(seeded):
    bullish = seeded.get("/api/gold/factors?factor_type=bullish").json()
    bearish = seeded.get("/api/gold/factors?factor_type=bearish").json()

    assert len(bullish) == 4
    assert len(bearish) == 4
    assert {f["factor_type"] for f in bullish} == {"bullish"}
    assert {f["factor_type"] for f in bearish} == {"bearish"}


@pytest.mark.integration
def test_factors_limit(seeded):
    assert len(seeded.get("/api/gold/factors?limit=2").json()) == 2
