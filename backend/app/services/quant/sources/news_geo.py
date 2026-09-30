"""地缘风险强度：用自有 RSS 语料算出的**代理指标**。

口径：某一天往前 7 个自然日内，标题命中地缘关键词的新闻占比（百分比）。
它不是 GPR 官方指数（那份数据是 .xls，需要额外解析依赖），因此文档与界面
都必须如实标注「语料代理指标」。好处是它与本系统的新闻管道同源、每次抓取
都会更新，不依赖第三方发布节奏。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.services.quant.sources.base import SourceError, clean_series
from app.utils import timeutil

GEO_KEYWORDS_EN = (
    "war",
    "conflict",
    "strike",
    "airstrike",
    "sanction",
    "missile",
    "military",
    "invasion",
    "troops",
    "ceasefire",
    "coup",
    "terror",
    "nuclear",
    "taiwan",
    "iran",
    "israel",
    "russia",
    "ukraine",
    "houthi",
    "red sea",
    "gaza",
    "nato",
)
GEO_KEYWORDS_ZH = (
    "战争",
    "冲突",
    "制裁",
    "军事",
    "导弹",
    "袭击",
    "轰炸",
    "停火",
    "地缘",
    "军演",
    "核",
    "边境",
)
ALL_KEYWORDS = GEO_KEYWORDS_EN + GEO_KEYWORDS_ZH

WINDOW_DAYS = 7
MIN_NEWS_PER_DAY = 3


def is_geopolitical(text: str) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in ALL_KEYWORDS)


def compute_series(published: Iterable[tuple], as_of: Optional[date] = None) -> pd.Series:
    """[(published_at, title)] → 每日地缘新闻占比（%）。"""
    rows = []
    for published_at, title in published:
        if published_at is None:
            continue
        rows.append({"day": pd.Timestamp(published_at).normalize(), "geo": 1.0 if is_geopolitical(title) else 0.0})

    if not rows:
        raise SourceError("新闻库为空，无法计算地缘风险强度")

    frame = pd.DataFrame(rows)
    daily = frame.groupby("day")["geo"].agg(["sum", "count"]).sort_index()

    # 重新采样到连续自然日，缺失日记 0 条新闻。
    full_index = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full_index, fill_value=0)

    geo_count = daily["sum"].rolling(WINDOW_DAYS, min_periods=1).sum()
    total_count = daily["count"].rolling(WINDOW_DAYS, min_periods=1).sum()
    intensity = (geo_count / total_count.replace(0, pd.NA)) * 100

    values = {
        day: float(value)
        for day, value in intensity.items()
        if pd.notna(value) and total_count.loc[day] >= MIN_NEWS_PER_DAY
    }
    if not values:
        raise SourceError("新闻量不足以计算地缘风险强度")
    return clean_series(values, name="news_geo_intensity")


def fetch(db: Session, *, days: int = 180, as_of: Optional[date] = None) -> dict[str, pd.Series]:
    from app.models.news import GoldNews

    end = timeutil.now_naive()
    start = end - timedelta(days=days)
    rows = (
        db.query(GoldNews.published_at, GoldNews.title)
        .filter(GoldNews.published_at >= start)
        .all()
    )
    published = [(row[0], row[1]) for row in rows if row[0] is not None]
    return {"news_geo_intensity": compute_series(published)}
