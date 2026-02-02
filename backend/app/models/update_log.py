"""数据更新日志模型"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class UpdateStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class UpdateLog(Base):
    __tablename__ = "update_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    data_type = Column(String(50), nullable=False, index=True)
    status = Column(Enum(UpdateStatus), nullable=False)
    records_affected = Column(Integer)
    error_message = Column(Text)
    duration_seconds = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
