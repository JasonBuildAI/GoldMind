"""抓取尝试流水：一行 = 某个通道对某个源的一次尝试。"""
from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class FetchAttempt(Base):
    __tablename__ = "fetch_attempts"

    id = Column(Integer, primary_key=True, index=True)
    # 抓取通道：quant_sync / news_digest / news_rss / price（见 source_status.CHANNEL_LABELS）
    channel = Column(String(50), nullable=False)
    # 通道内的源标识（源名 / 配置名）
    source_key = Column(String(100), nullable=False)
    # ok / empty / error / skipped（见 source_status.STATUS_LABELS）
    status = Column(String(20), nullable=False)
    # 时间只在 SCHEDULER_TIMEZONE 里流动（red line 5），这里存该时区的本地时间
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime)
    # 本次尝试取到的条目数（序列条数 / 新闻条数 / 1 条行情）
    items = Column(Integer)
    error = Column(Text)
    created_at = Column(DateTime, server_default=func.now())


# 看板要按 (channel, source_key) 取「最近一行」：先按 id 倒序扫最近 N 行即可，
# 这个复合索引让扫描不用回表排序全表。
Index("ix_fetch_attempts_channel_source", FetchAttempt.channel, FetchAttempt.source_key)
