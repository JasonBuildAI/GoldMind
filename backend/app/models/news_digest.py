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
    # TEXT 而不是 VARCHAR(500)：Google News 的文章链接实测超过 500 字符
    # （2026-10-02 事故：MySQL 报 Data too long，整批落库回滚；SQLite 不校验
    # 长度所以测试全绿）。见 docs/specs/2026-10-02-消息落库修复.md。
    url = Column(Text, nullable=False)
    published_at = Column(DateTime, nullable=False, index=True)
    fetched_at = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())

    # ------------------------------------------------------------------ #
    # 中文译文（2026-10-03）
    #
    # 来源池全是英文 RSS，读者要自己翻译。这四个字段存**叠加**在英文原文
    # 之上的中文：`title` / `summary` 永远保留原样，中文只是补充。
    #
    # 为什么是四个而不是两个：`translation_model` 让「换了模型」这件事可判定
    # —— 旧模型产的译文在新模型下可以识别为陈旧并重翻；`translated_at` 让
    # 页面上「这条中文是什么时候生成的」有据可查（不拿当前时间顶替）。
    #
    # 全部可空：NULL 的准确含义就是「还没有译文」，不是「译文是空字符串」。
    # 页面据此如实显示英文原标题 + 原因，而不是摆一段编出来的中文。
    # ------------------------------------------------------------------ #
    title_zh = Column(String(500))
    brief_zh = Column(Text)
    translated_at = Column(DateTime)
    translation_model = Column(String(100))


# 去重按 url 查（`WHERE url = ?`），没有索引就是全表扫描。
# MySQL 下 utf8mb4 的 500 字符索引超长，所以用前缀索引 191；
# 名字与 backend/schema.sql 保持一致，两者由 test_schema_matches_models.py 守住。
Index("ix_news_digest_items_url", NewsDigestItem.url, mysql_length=191)
