"""黄金价格数据模型"""
from sqlalchemy import Column, Integer, Float, Date, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base


class GoldPrice(Base):
    __tablename__ = "gold_prices"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float, nullable=False)
    volume = Column(Integer)
    change_percent = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class DollarIndex(Base):
    __tablename__ = "dollar_index"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
