"""新闻服务"""
from datetime import datetime
from typing import Dict, List, Optional

import feedparser
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.news import GoldNews, SentimentType

# 内置默认 RSS 源，格式 "名称|URL"。
# 这些 URL 都是实测能返回条目与发布时间的；原实现里的
# `finance.sina.com.cn/roll/finance_gold/index.d.html` 是 HTML 页面而非 RSS，
# `fx168.com/rss/gold.xml` 也已失效（两者均返回 0 条目）。
DEFAULT_RSS_SOURCES = (
    "FXStreet|https://www.fxstreet.com/rss/news,"
    "MarketWatch Commodities|https://feeds.content.dowjones.io/public/rss/mw_marketpulse,"
    "CNBC Markets|https://www.cnbc.com/id/100003114/device/rss/rss.html,"
    "WSJ Markets|https://feeds.a.dj.com/rss/RSSMarketsMain.xml"
)


def parse_rss_sources(raw: str) -> List[tuple[str, str]]:
    """把 ``"名称|URL,名称|URL"`` 解析为 ``[(名称, URL)]``。

    格式不合法的项直接跳过 —— 一个坏配置不应该让整条抓取链路失败。
    """
    sources: List[tuple[str, str]] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item or "|" not in item:
            continue
        name, _, url = item.partition("|")
        name, url = name.strip(), url.strip()
        if name and url:
            sources.append((name, url))
    return sources


class NewsService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------ #
    # 读取
    # ------------------------------------------------------------------ #
    def get_news(
        self, limit: int = 20, source: Optional[str] = None, sentiment: Optional[str] = None
    ) -> List[GoldNews]:
        query = self.db.query(GoldNews)

        if source:
            query = query.filter(GoldNews.source == source)

        if sentiment:
            query = query.filter(GoldNews.sentiment == sentiment)

        return query.order_by(GoldNews.published_at.desc()).limit(limit).all()

    def get_news_by_id(self, news_id: int) -> Optional[GoldNews]:
        return self.db.query(GoldNews).filter(GoldNews.id == news_id).first()

    def get_recent_news(self, hours: int = 24) -> List[GoldNews]:
        """最近 N 小时的新闻 —— 因子分析的数据来源。"""
        from datetime import timedelta

        since = datetime.now() - timedelta(hours=hours)
        return (
            self.db.query(GoldNews)
            .filter(GoldNews.published_at >= since)
            .order_by(GoldNews.published_at.desc())
            .all()
        )

    def get_sentiment_summary(self) -> Dict[str, int]:
        """情感分布统计。sentiment 为 NULL 的历史数据不会让统计崩掉。"""
        stats = self.db.query(
            GoldNews.sentiment, func.count(GoldNews.id)
        ).group_by(GoldNews.sentiment).all()

        summary = {"positive": 0, "neutral": 0, "negative": 0}
        for sentiment, count in stats:
            key = sentiment.value if isinstance(sentiment, SentimentType) else str(sentiment)
            if key in summary:
                summary[key] = count
        return summary

    # ------------------------------------------------------------------ #
    # 抓取
    # ------------------------------------------------------------------ #
    def fetch_from_rss(self, rss_url: str, source: str, limit: int = 10) -> List[Dict]:
        """抓取单个 RSS 源。

        返回字段与 :meth:`save_news` 的入参严格对齐（title/content/url/published_at/source）。
        迁移前抓取端写 ``link``/``summary``、存储端读 ``url``/``content``，
        两边键名不一致，导致 URL 与正文被静默丢弃、``published_at`` 还塞了
        RSS 原始字符串进 DateTime 列。
        """
        try:
            feed = feedparser.parse(rss_url)
            news_list: List[Dict] = []
            for entry in feed.entries[:limit]:
                title = (entry.get("title") or "").strip()
                if not title:
                    continue

                parsed = entry.get("published_parsed") or entry.get("updated_parsed")
                published_at = datetime(*parsed[:6]) if parsed else None

                news_list.append(
                    {
                        "title": title,
                        "content": entry.get("summary", ""),
                        "url": entry.get("link", ""),
                        "published_at": published_at,
                        "source": source,
                    }
                )
            return news_list
        except Exception as e:
            print(f"RSS获取失败 {source}: {e}")
            return []

    def fetch_all_rss_news(self, limit_per_source: int = 10) -> List[Dict]:
        """抓取全部 RSS 源；单个源失败不影响其他源。"""
        sources = parse_rss_sources(settings.NEWS_RSS_SOURCES) or parse_rss_sources(
            DEFAULT_RSS_SOURCES
        )
        all_news: List[Dict] = []
        for source, rss_url in sources:
            all_news.extend(self.fetch_from_rss(rss_url, source, limit=limit_per_source))
        return all_news

    # ------------------------------------------------------------------ #
    # 写入
    # ------------------------------------------------------------------ #
    def save_news(self, news_data: Dict) -> Optional[GoldNews]:
        """保存一条新闻；按 URL 去重，URL 缺失时按「标题 + 来源」去重。"""
        title = (news_data.get("title") or "").strip()
        if not title:
            return None

        url = (news_data.get("url") or "").strip()
        source = news_data.get("source")

        if url:
            existing = self.db.query(GoldNews).filter(GoldNews.url == url).first()
        else:
            existing = (
                self.db.query(GoldNews)
                .filter(GoldNews.title == title, GoldNews.source == source)
                .first()
            )
        if existing:
            return existing

        published_at = news_data.get("published_at")
        if published_at is None:
            # RSS 偶尔不提供时间。回落到抓取时刻，否则这条会被
            # 「最近 24 小时」查询直接排除，等于白抓。
            published_at = datetime.now()

        try:
            news = GoldNews(
                title=title,
                content=news_data.get("content"),
                source=source,
                url=url or None,
                published_at=published_at,
                sentiment=SentimentType.NEUTRAL,
                keywords=news_data.get("keywords"),
            )
            self.db.add(news)
            self.db.commit()
            return news
        except Exception as e:
            self.db.rollback()
            print(f"保存新闻失败: {e}")
            return None
