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


