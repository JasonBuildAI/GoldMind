"""新闻资讯数据模型"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class SentimentType(enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class GoldNews(Base):
    __tablename__ = "gold_news"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    source = Column(String(100))
    url = Column(String(500))
    published_at = Column(DateTime, index=True)
    sentiment = Column(Enum(SentimentType), default=SentimentType.NEUTRAL)
    keywords = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
