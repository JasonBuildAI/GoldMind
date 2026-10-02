"""分析服务共享的输入装配。

消息板块（`news_digest_items`，13 个高权威来源的白名单）与 `gold_news`
（RSS 采集通道）此前互不相通：展示层看消息板块，LLM 分析只看 `gold_news`
—— 央行 / 通讯社 / 行业机构的消息从来没有进入过分析输入。

`load_analysis_news()` 把两条通道并成一份新闻输入：按规范化 URL（缺 URL 时
退回标题）去重，两边都有同一条时保留消息板块的版本（来源标注与摘要更完整），
按发布时间倒序。四个 LLM 分析服务共用它，窗口与去重口径只有这一处实现。
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.services.news_digest import load_recent_entries
from app.services.news_service import NewsService, normalize_url

_WHITESPACE_RE = re.compile(r"\s+")


def _orm_to_item(row) -> Dict[str, Any]:
    """`gold_news` 行 → 统一 dict（`content` 作为摘要进 prompt）。"""
    return {
        "title": row.title,
        "summary": row.content,
        "source": row.source,
        "published_at": row.published_at,
        "url": row.url,
    }


def _dedupe_key(item: Dict[str, Any]) -> Optional[str]:
    url = normalize_url(item.get("url"))
    if url:
        return f"url:{url}"
    title = _WHITESPACE_RE.sub("", str(item.get("title") or "")).lower()
    return f"title:{title}" if title else None


def merge_news_entries(
    digest_entries: Iterable[Dict[str, Any]],
    db_news_entries: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """合并两路新闻：去重（消息板块优先）、按发布时间倒序。"""
    merged: List[Dict[str, Any]] = []
    seen = set()
    for item in [*digest_entries, *db_news_entries]:
        key = _dedupe_key(item)
        if key is not None:
            if key in seen:
                continue
            seen.add(key)
        merged.append(item)
    merged.sort(
        key=lambda item: item.get("published_at") or datetime.min,
        reverse=True,
    )
    return merged


def load_analysis_news(
    db: Session,
    *,
    hours: int = 24,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """分析服务的统一新闻输入（四个 LLM 分析服务共用）。

    `limit=None` 表示不截断 —— 各服务在拼 prompt 时按 `NEWS_PROMPT_LIMIT`
    或各自窗口上限处理；需要提前截断的调用方显式传入。
    """
    digest_entries = load_recent_entries(db, hours=hours, limit=50)
    db_entries = [
        _orm_to_item(row) for row in NewsService(db).get_recent_news(hours=hours)
    ]
    merged = merge_news_entries(digest_entries, db_entries)
    return merged if limit is None else merged[:limit]
