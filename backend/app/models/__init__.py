"""黄金市场分析系统"""
from app.database import Base
from app.models.gold_price import GoldPrice, DollarIndex
from app.models.news import GoldNews
from app.models.news_digest import NewsDigestItem
from app.models.analysis import (
    FactorObservation,
    InstitutionView,
    MarketFactor,
    ModelEvaluation,
    Prediction,
)

__all__ = [
    "Base",
    "GoldPrice",
    "DollarIndex",
    "GoldNews",
    "NewsDigestItem",
    "MarketFactor",
    "InstitutionView",
    "Prediction",
    "FactorObservation",
    "ModelEvaluation",
]
