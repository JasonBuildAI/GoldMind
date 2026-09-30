"""新闻资讯数据模型"""
from sqlalchemy import Column, Index, Integer, String, DateTime, Text, Enum
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


# 去重是按 url 查的（`WHERE url = ?`）。没有索引就是**全表扫描** ——
# 新闻会持续累积（每天几百条），一年后每条插入都要扫全表。
# MySQL 下 utf8mb4 的 500 字符索引超长，所以用前缀索引；
# 名字与 backend/schema.sql 保持一致，两者由测试守住。
Index("ix_gold_news_url", GoldNews.url, mysql_length=191)
