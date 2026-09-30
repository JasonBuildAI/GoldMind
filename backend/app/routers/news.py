"""新闻 API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.news_service import NewsService
from app.schemas.news import NewsResponse

router = APIRouter()


@router.get("/news", response_model=List[NewsResponse])
async def get_news(
    limit: int = Query(default=20, le=100),
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取新闻列表，可按来源与情感过滤（无分页，只取前 limit 条）。"""
    service = NewsService(db)
    news = service.get_news(limit, source, sentiment)
    
    return [
        NewsResponse(
            id=n.id,
            title=n.title,
            content=n.content,
            source=n.source,
            url=n.url,
            published_at=n.published_at,
            sentiment=n.sentiment,
            keywords=n.keywords,
            created_at=n.created_at
        )
        for n in news
    ]


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
    """获取新闻情感分布统计。"""
    service = NewsService(db)
    summary = service.get_sentiment_summary()
    
    return summary or {"positive": 0, "neutral": 0, "negative": 0}
