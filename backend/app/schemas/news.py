"""新闻 Pydantic 模型"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum


class SentimentEnum(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class NewsResponse(BaseModel):
    id: int
    title: str
    content: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None
    sentiment: SentimentEnum
    keywords: Optional[str] = None
    created_at: datetime
    # 确定性事件标注（见 app/services/news_events.py）：id + 中文标签。
    event_tags: List[str] = []
    event_labels: List[str] = []
    # 链接来自聚合入口（如 Google News）而不是媒体直发时置真。
    via_aggregator: bool = False
    
    class Config:
        from_attributes = True
