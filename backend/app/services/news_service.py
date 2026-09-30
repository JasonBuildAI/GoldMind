"""新闻服务"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

import feedparser
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.news import GoldNews, SentimentType
from app.utils.enum_values import resolve_enum
from loguru import logger

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


def to_local_naive(parsed) -> Optional[datetime]:
    """把 feedparser 的时间结构转成**部署时区的本地 naive 时间**。

    feedparser 的 ``published_parsed`` 是 **UTC** 的 ``time.struct_time``。
    原实现直接 ``datetime(*parsed[:6])`` —— 那得到的是「UTC 的墙上时间」，
    而库里其他地方（``save_news`` 的兜底、``get_recent_news`` 的窗口）
    用的都是本地时间。两者相差一个时区偏移：

        东八区部署下，一条刚发布的新闻被存成「8 小时前」，
        「最近 24 小时」的窗口实际覆盖到约 32 小时。

    正确做法是先按 UTC 解释，再转到 ``SCHEDULER_TIMEZONE``，
    最后去掉 tzinfo（库里存的是 naive 本地时间）。
    """
    if not parsed:
        return None
    try:
        moment = datetime(*parsed[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None
    try:
        from zoneinfo import ZoneInfo

        moment = moment.astimezone(ZoneInfo(settings.SCHEDULER_TIMEZONE))
    except Exception:       # 缺 tzdata 时退回 UTC，至少不比原来更差
        logger.warning(f"[新闻] 无法加载时区 {settings.SCHEDULER_TIMEZONE}，RSS 时间按 UTC 存")
    return moment.replace(tzinfo=None)


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
    @staticmethod
    def as_sentiment(value: object) -> Optional[SentimentType]:
        """把接口收到的情感值解析成枚举成员。

        列类型是 `Enum(SentimentType)`，SQLAlchemy 存的是**枚举名**
        （POSITIVE / NEGATIVE / NEUTRAL），而接口对外一律用小写 ——
        响应体里就是 `"sentiment": "positive"`。

        原实现直接把收到的字符串丢给过滤条件，于是
        `GET /news?sentiment=positive` 一条都匹配不到，
        只有 `?sentiment=POSITIVE` 才有结果 —— **接口自己的输出不能当作输入用**。

        解析逻辑统一在 `app/utils/enum_values.py`（因子类型有同样的毛病）。
        """
        return resolve_enum(SentimentType, value)

    def get_news(
        self, limit: int = 20, source: Optional[str] = None, sentiment: Optional[object] = None
    ) -> List[GoldNews]:
        """获取新闻列表，可按来源与情感过滤（无分页，只取前 limit 条）。

        `sentiment` 接受大小写任意形式的 "positive" / "POSITIVE"，
        与接口返回的取值保持一致。
        """
        query = self.db.query(GoldNews)

        if source:
            query = query.filter(GoldNews.source == source)

        if sentiment:
            member = self.as_sentiment(sentiment)
            if member is None:
                # 认不出的情感值：返回空列表，而不是把它当成一个永远匹配不上的
                # 字符串丢给数据库（那样 SQLite 下会静默返回空，MySQL 下行为还不同）。
                return []
            query = query.filter(GoldNews.sentiment == member)

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

                # RSS 时间统一转成本地时间再存，见 to_local_naive 的说明
                published_at = to_local_naive(
                    entry.get("published_parsed") or entry.get("updated_parsed")
                )

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
            logger.error(f"RSS获取失败 {source}: {e}")
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
            logger.error(f"保存新闻失败: {e}")
            return None
