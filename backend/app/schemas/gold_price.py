"""Pydantic 数据模型"""
from datetime import date
from typing import List, Optional
from pydantic import BaseModel

class PriceBasisInfo(BaseModel):
    """一处价格的口径说明：basis 是机器口径，label 给人看。"""

    basis: str
    label: str
    source: Optional[str] = None
    as_of: Optional[str] = None


class DailyPriceResponse(BaseModel):
    date: str
    price: float
    volume: int
    # 口径：close = 日收盘；realtime = 实时报价（只有被实时价替换 / 追加的那一点）。
    basis: str = "close"
    basis_label: str = "日收盘"
    source: Optional[str] = None
    as_of: Optional[str] = None

class CorrelationDataResponse(BaseModel):
    date: str
    gold_price: float
    dollar_index: float
    # 两条序列各自的口径；黄金最新一点可能是实时报价，其余都是日收盘。
    gold_basis: str = "close"
    gold_basis_label: str = "日收盘"
    gold_source: Optional[str] = None
    dollar_basis: str = "close"
    dollar_basis_label: str = "日收盘"
    dollar_source: Optional[str] = None
    as_of: Optional[str] = None

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
    # 当前价的显式口径（实时报价 / 日收盘）：前端不再靠 is_realtime 反推。
    price_basis: str = "close"
    price_basis_label: str = "日收盘"
    price_as_of: Optional[str] = None

