"""消息板块 API 的响应模型。

字段与 `app/services/news_digest.build_digest_payload` 的输出一一对应。
空库时 `has_data=False` 且必须有 `unavailable_reason` —— 宁可页面显示
「不可用 + 原因」，也不允许出现任何没有真实来源的条目。
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class DigestRelatedItem(BaseModel):
    """同一事件下的另一家来源报道。"""

    title: str
    source: str
    url: str
    published_at: datetime


class DigestItem(BaseModel):
    rank: int
    id: int
    title: str
    summary: str
    source: str
    tier: int
    tier_label: str
    url: str
    published_at: datetime
    age_hours: float
    importance: float
    confidence: float
    signals: List[str]
    # 确定性事件标注（id + 中文标签）与聚合入口标记，见 services/news_events.py。
    event_tags: List[str] = []
    event_labels: List[str] = []
    via_aggregator: bool = False
    coverage_count: int
    related: List[DigestRelatedItem]


class DigestWindow(BaseModel):
    key: str
    label: str
    hours: int
    total_clusters: int
    items: List[DigestItem]


class DigestFetchSource(BaseModel):
    name: str
    status: str
    entries: int
    kept: int
    new: int
    error: Optional[str] = None


class DigestFetchReport(BaseModel):
    fetched_at: str
    total_sources: int
    ok_sources: int
    failed_sources: int
    entries: int
    kept: int
    new_items: int
    duplicates: int
    skipped_no_title: int
    skipped_no_url: int
    skipped_no_time: int
    skipped_filtered: int
    # 落库阶段被跳过的行（如单行数据超长）。默认 0：修复前写入的缓存报告仍可解析。
    skipped_unstorable: int = 0
    sources: List[DigestFetchSource]


class DigestResponse(BaseModel):
    generated_at: str
    has_data: bool
    unavailable_reason: Optional[str] = None
    last_fetch: Optional[DigestFetchReport] = None
    windows: List[DigestWindow]


class DigestRefreshResponse(DigestFetchReport):
    """手动抓取的结果：整份抓取报告 + 本次是否至少有一个来源成功。"""

    success: bool
