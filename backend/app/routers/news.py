"""新闻 API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import news_events
from app.services.news_service import NewsService
from app.services.news_digest import NewsDigestService, build_digest_payload
from app.schemas.news import NewsResponse, SentimentEnum
from app.schemas.news_digest import DigestRefreshResponse, DigestResponse

router = APIRouter()


@router.get("/news", response_model=List[NewsResponse])
async def get_news(
    limit: int = Query(default=20, ge=1, le=100),
    source: Optional[str] = None,
    # 用枚举而不是裸 str：取值与 schema / 响应体保持一致（小写），
    # 传了不认识的值 FastAPI 直接 422，而不是静默返回空列表。
    sentiment: Optional[SentimentEnum] = None,
    db: Session = Depends(get_db)
):
    """获取新闻列表，可按来源与情感过滤（无分页，只取前 limit 条）。"""
    service = NewsService(db)
    news = service.get_news(limit, source, sentiment)
    
    return [_news_response(n) for n in news]


def _news_response(n) -> NewsResponse:
    """ORM 行 → 响应：事件标签与聚合标记都现算（确定性，不入库）。

    现算而不是落库：规则改了之后历史条目立刻跟着改口径，
    界面与 prompt 永远用同一套规则，也不会因为补历史而写错数据。
    """
    tags = news_events.tag_events(n.title, n.content)
    return NewsResponse(
        id=n.id,
        title=n.title,
        content=n.content,
        source=n.source,
        url=n.url,
        published_at=n.published_at,
        sentiment=n.sentiment,
        keywords=n.keywords,
        created_at=n.created_at,
        event_tags=tags,
        event_labels=news_events.event_labels(tags),
        via_aggregator=news_events.is_aggregator_url(n.url),
    )


# --------------------------------------------------------------------------- #
# 消息板块（高权威消息精选）
# --------------------------------------------------------------------------- #
# 注意路由顺序：`/news/digest` 必须声明在 `/news/{news_id}` **之前**。
# Starlette 的路径参数是普通字符串匹配，`/news/{news_id}` 先注册就会吞掉
# `digest`，用户拿到的是 422（news_id 不是整数）而不是榜单。
@router.get("/news/digest", response_model=DigestResponse)
async def get_news_digest(db: Session = Depends(get_db)):
    """消息精选：24 小时 / 7 天 / 30 天三个窗口各取前 10 条。

    评分完全确定性（来源权威 + 黄金相关度 + 同题覆盖 + 时效），不调用 LLM。
    空库返回 `has_data=false` 与明确原因，不返回任何编造内容。
    """
    return build_digest_payload(db)


@router.post("/news/digest/refresh", response_model=DigestRefreshResponse)
async def refresh_news_digest(db: Session = Depends(get_db)):
    """立即抓取一轮全部来源并落库，返回本次抓取报告。

    网络 IO 在线程池执行，不阻塞事件循环；路径以 `/refresh` 结尾，
    自动落到更严的重操作限流档（本接口不调用 LLM，不产生付费调用）。
    """
    report = await run_in_threadpool(NewsDigestService(db).fetch_all_sources)
    return DigestRefreshResponse(success=report["ok_sources"] > 0, **report)


@router.get("/news/{news_id}")
async def get_news_detail(news_id: int, db: Session = Depends(get_db)):
    """获取单条新闻详情。"""
    service = NewsService(db)
    news = service.get_news_by_id(news_id)
    
    if not news:
        # 资源不存在就该是 404。原实现返回 200 + {"error": ...}，
        # 调用方无法用状态码判断成败，只能去猜响应体。
        raise HTTPException(status_code=404, detail="新闻不存在")
    
    return {
        "id": news.id,
        "title": news.title,
        "content": news.content,
        "source": news.source,
        "url": news.url,
        "published_at": news.published_at,
        "sentiment": news.sentiment,
        "keywords": news.keywords
    }


@router.get("/news/sentiment/summary")
async def get_sentiment_summary(db: Session = Depends(get_db)):
    """新闻情感分布统计。注：入库时 sentiment 一律为 NEUTRAL，本项目没有做情感分析，这里恒为全中性，保留字段只为接口形状稳定。"""
    service = NewsService(db)
    summary = service.get_sentiment_summary()
    
    return summary or {"positive": 0, "neutral": 0, "negative": 0}
