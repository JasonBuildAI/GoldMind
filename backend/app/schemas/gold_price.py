"""Pydantic 数据模型"""
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel


class DailyPriceResponse(BaseModel):
    date: str
    price: float
    volume: int


class CorrelationDataResponse(BaseModel):
    date: str
    gold_price: float
    dollar_index: float


class GoldStatsResponse(BaseModel):
    current_price: float
    start_price: float
    ytd_return: float
    max_price: float
    min_price: float
    max_date: str
    min_date: str
    volatility: float
    market_status: str
    market_status_desc: str
    updated_at: str
    # 数据来源（人类可读）与是否真的拿到了实时价。
    # 前端用 is_realtime 决定显示「实时」还是「历史数据」——
    # 缺了这两个字段时，服务里算出来的来源信息会被响应模型直接丢掉。
    data_source: str
    is_realtime: bool


