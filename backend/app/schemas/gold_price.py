"""Pydantic 数据模型"""
from datetime import date
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
    # 窗口口径：滚动 12 个月（不足时 window_label 如实说明实际跨度）。
    window_label: str
    window_start: str
    window_end: str
    # 窗口涨跌幅 = (窗口末收盘 − 窗口首收盘) / 窗口首收盘。
    window_return: float
    max_price: float
    min_price: float
    max_date: str
    min_date: str
    # 高低振幅 = (期间最高 − 期间最低) / 期间最低。**不是波动率**，也非年化。
    amplitude: float
    market_status: str
    market_status_desc: str
    updated_at: str
    # 数据来源（人类可读）与是否真的拿到了实时价。
    # 前端用 is_realtime 决定显示「实时」还是「历史数据」——
    # 缺了这两个字段时，服务里算出来的来源信息会被响应模型直接丢掉。
    data_source: str
    is_realtime: bool

