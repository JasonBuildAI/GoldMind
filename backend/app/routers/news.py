"""新闻 API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from app.database import get_db
from app.services import news_events
from app.services.news_service import NewsService
from app.services.news_digest import NewsDigestService, build_digest_payload
from app.schemas.news import NewsResponse
from app.schemas.news_digest import DigestRefreshResponse, DigestResponse

router = APIRouter()


@router.get("/news", response_model=List[NewsResponse])
async def get_news(
    limit: int = Query(default=20, ge=1, le=100),
    source: Optional[str] = None,
    # 过滤库里的历史情感列：2.0.2 起响应不再带该字段（死字段已移除），
    # 但列留存历史数据，过滤参数继续可用。取值统一按 enum_values.resolve_enum
    # 解析（大小写不敏感）；认不出的取值 422，而不是静默返回空列表。
    sentiment: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取新闻列表，可按来源与（历史）情感列过滤（无分页，只取前 limit 条）。"""
    service = NewsService(db)
    if sentiment:
        member = NewsService.as_sentiment(sentiment)
        if member is None:
            # 旧实现把参数声明成 schema 枚举，FastAPI 按值（小写）校验，
            # 于是 `?sentiment=POSITIVE` 直接 422 —— 大小写不敏感从未生效。
            raise HTTPException(status_code=422, detail=f"无法识别的 sentiment：{sentiment}")
        sentiment = member
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
        "keywords": news.keywords
    }
