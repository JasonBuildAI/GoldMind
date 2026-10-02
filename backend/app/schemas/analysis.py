"""分析 Pydantic 模型"""
from datetime import date, datetime
from typing import Any, List, Optional
from pydantic import BaseModel
from enum import Enum


class FactorTypeEnum(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class ImpactEnum(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FactorResponse(BaseModel):
    id: int
    factor_type: FactorTypeEnum
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    details: List[str]
    impact: ImpactEnum
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InstitutionResponse(BaseModel):
    id: int
    institution_name: str
    logo: Optional[str] = None
    rating: str
    # 三列在模型里都可空：没有可核实目标价的机构会落一条**占位行**
    # （target_price=None、reasoning="暂无最新预测"），用于表示「仍在跟踪」。
    # 这里若按必填校验，整张 /institutions 表会因为这个诚实结果而 500 ——
    # 实测于 2026-10-02。
    target_price: Optional[float] = None
    timeframe: Optional[str] = None
    reasoning: Optional[str] = None
    key_points: List[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PredictionResponse(BaseModel):
    id: int
    prediction_type: str
    target_price: float
    confidence: Optional[float] = None
    timeframe: str
    reasoning: str
    # 老的行是纯文本因子名列表；量化引擎写入的是 {key, name, contribution, signed_z}
    factors: Optional[List[Any]] = None
    created_at: datetime
    # 量化引擎（services/quant）写入的字段；非量化来源的行这些值为空。
    direction: Optional[str] = None
    horizon_days: Optional[int] = None
    as_of: Optional[date] = None
    base_price: Optional[float] = None
    score: Optional[float] = None
    expected_return: Optional[float] = None
    uncertainty: Optional[float] = None
    model_version: Optional[str] = None
    
    class Config:
        from_attributes = True
