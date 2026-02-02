"""新闻 Pydantic 模型"""
from datetime import datetime
from typing import Optional
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
    
    class Config:
        from_attributes = True
