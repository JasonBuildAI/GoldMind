"""分析 Pydantic 模型"""
from datetime import datetime
from typing import List, Optional
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
    target_price: float
    timeframe: str
    reasoning: str
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
    factors: Optional[List[str]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
