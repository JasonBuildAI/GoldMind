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
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy.orm import Session

from app.models.gold_price import GoldPrice
from app.services.news_digest import load_recent_entries
from app.services.news_service import NewsService, format_news_for_prompt, normalize_url
from app.services.price_window import compute_price_window
from app.utils import timeutil

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


# 所有分析 prompt 共用的能力声明。
#
# 五个服务都是单轮调用（llm.invoke(prompt)）：没有工具、没有联网、没有会话记忆。
# prompt 里不声明这一点时，模型会用自己的记忆补足「它以为应该有的」数字 ——
# 正是红线 1 禁止的行为。声明收敛在这里，由所有服务共用，避免每个 prompt
# 各写一句、各漂各的。
CAPABILITY_NOTE = (
    "能力声明：本次分析是单轮调用，你没有联网与工具调用能力，也没有历史会话记忆；"
    "下方提供的数据是你唯一可依据的事实，不得引用数据之外的信息或凭记忆补充数字。"
    "数据不足时如实说明，宁可不给结论。"
)


@dataclass(frozen=True)
class AnalysisInput:
    """分析服务共用的输入包：同一份新闻、同一份价格上下文、同一份能力声明。"""

    news_items: List[Dict[str, Any]]
    news_block: str
    news_window_hours: int
    price: Optional[Dict[str, Any]]
    as_of: datetime
    capability_note: str = CAPABILITY_NOTE


def build_price_context(db: Session) -> Optional[Dict[str, Any]]:
    """当前金价上下文 —— 多空因子此前各写一份，这里是唯一实现。

    返回 `{current_price, price_change, window_change, window_label, as_of}`：

    - `price_change` 是「最新收盘 vs 上一交易日收盘」；
    - `window_change` / `window_label` 来自 `price_window` 的滚动 12 个月口径；
    - 没有行情数据时返回 None（prompt 里如实写「暂无数据」，不造数）。
    """
    latest = db.query(GoldPrice).order_by(GoldPrice.date.desc()).first()
    window = compute_price_window(db)
    if not (latest and window):
        return None

    yesterday = (
        db.query(GoldPrice)
        .filter(GoldPrice.date < latest.date)
        .order_by(GoldPrice.date.desc())
        .first()
    )
    price_change = 0.0
    if yesterday:
        price_change = (
            (latest.close_price - yesterday.close_price) / yesterday.close_price
        ) * 100

    return {
        "current_price": round(latest.close_price, 2),
        "price_change": round(price_change, 2),
        "window_change": round(window.change_pct, 2),
        "window_label": window.label,
        "as_of": latest.date,
    }


def build_analysis_input(
    db: Session,
    *,
    news_hours: int = 24,
    news_limit: Optional[int] = None,
    include_prices: bool = True,
) -> AnalysisInput:
    """一次组装共享输入包：新闻（去重合并）+ 价格上下文 + 能力声明。"""
    items = load_analysis_news(db, hours=news_hours, limit=news_limit)
    return AnalysisInput(
        news_items=items,
        news_block=format_news_for_prompt(items),
        news_window_hours=news_hours,
        price=build_price_context(db) if include_prices else None,
        as_of=timeutil.now_naive(),
    )
