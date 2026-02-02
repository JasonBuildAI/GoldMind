"""市场分析数据模型"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class FactorType(enum.Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class ImpactLevel(enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class MarketFactor(Base):
    __tablename__ = "market_factors"
    
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(FactorType), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(200))
    description = Column(Text)
    details = Column(JSON)
    impact = Column(Enum(ImpactLevel), default=ImpactLevel.MEDIUM)
    confidence = Column(Float, default=0.8)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class InstitutionView(Base):
    __tablename__ = "institution_views"
    
    id = Column(Integer, primary_key=True, index=True)
    institution_name = Column(String(100), nullable=False)
    logo = Column(String(50))
    rating = Column(String(20), nullable=False)
    target_price = Column(Float)
    timeframe = Column(String(50))
    reasoning = Column(Text)
    key_points = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Prediction(Base):
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    prediction_type = Column(String(50), nullable=False)
    target_price = Column(Float, nullable=False)
    confidence = Column(Float)
    timeframe = Column(String(50))
    reasoning = Column(Text)
    factors = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
