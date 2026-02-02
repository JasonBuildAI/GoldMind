"""Pydantic 数据模型"""
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel


class PriceBase(BaseModel):
    date: date
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: float
    volume: Optional[int] = None


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


class RealtimePriceResponse(BaseModel):
    price: float
    previous_close: float
    change_percent: float
    updated_at: str
