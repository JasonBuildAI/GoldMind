"""黄金市场分析系统"""
from app.database import Base
from app.models.gold_price import GoldPrice, DollarIndex
from app.models.news import GoldNews
from app.models.analysis import MarketFactor, InstitutionView, Prediction
