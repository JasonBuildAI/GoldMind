"""消息板块数据模型。

与 `gold_news`（LLM 分析的输入）**完全隔离**：消息板块有自己的一张表，
既不改既有分析行为，也让「消息」的抓取节奏、保留窗口与评分口径互不干扰。
"""
from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class NewsDigestItem(Base):
    __tablename__ = "news_digest_items"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    summary = Column(Text)
    # 展示名（来自 RSS 条目的 source.title，缺失时用配置名）
    source = Column(String(100), nullable=False)
    # 归一化后的来源标识：聚类时按它数「多少家不同来源」同题报道
    source_key = Column(String(100), nullable=False)
    # 1 = 官方 / 通讯社 / 行业机构；2 = 专业财经媒体
    authority_tier = Column(Integer, nullable=False, default=2)
    url = Column(String(500), nullable=False)
    published_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())


# 去重按 url 查（`WHERE url = ?`），没有索引就是全表扫描。
# MySQL 下 utf8mb4 的 500 字符索引超长，所以用前缀索引 191；
# 名字与 backend/schema.sql 保持一致，两者由 test_schema_matches_models.py 守住。
Index("ix_news_digest_items_url", NewsDigestItem.url, mysql_length=191)
