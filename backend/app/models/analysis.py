"""市场分析数据模型"""
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
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
    # prediction_type 保留为方向（up / down / flat），与 model_evaluations 的口径一致。
    prediction_type = Column(String(50), nullable=False)
    target_price = Column(Float, nullable=False)
    confidence = Column(Float)
    timeframe = Column(String(50))
    reasoning = Column(Text)
    factors = Column(JSON)
    # 以下列由量化引擎（services/quant）写入，全部可空 ——
    # 老库升级走 scripts/migrate_quant.py，只加列不改类型。
    direction = Column(String(20))
    horizon_days = Column(Integer)
    as_of = Column(Date)
    base_price = Column(Float)
    score = Column(Float)
    expected_return = Column(Float)
    uncertainty = Column(Float)
    model_version = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())


class FactorObservation(Base):
    """量化因子观测：一个因子、一个交易日、一个原始值。

    存的是**因子原始值**（美债实际利率的百分数、央行储备的万盎司、期货净头寸的张数……），
    不是 z 分数或贡献值 —— 可视化与回测需要的统计量都能从这条序列上重新算出来，
    而原始值是不可再生的事实，一旦丢弃就只剩二手加工品。

    `obs_date` 是**该值可用的交易日**：数据源在黄金收盘之后才发布的
    （美国财政部的收益率曲线、纽约联储的 EFFR、CFTC 的持仓报告），
    写入时会整体平移到下一个交易日，回测据此避免前视。
    """

    __tablename__ = "factor_observations"

    id = Column(Integer, primary_key=True, index=True)
    factor_key = Column(String(64), nullable=False, index=True)
    obs_date = Column(Date, nullable=False, index=True)
    value = Column(Float, nullable=False)
    source = Column(String(120))
    meta = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("factor_key", "obs_date", name="uq_factor_observation"),
    )


class ModelEvaluation(Base):
    """一次走查式回测的结果。每次评估追加一行，形成准确率的时间序列。"""

    __tablename__ = "model_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    model_version = Column(String(50), nullable=False)
    horizon_days = Column(Integer, nullable=False)
    evaluated_at = Column(DateTime, server_default=func.now())
    window_start = Column(Date)
    window_end = Column(Date)
    sample_size = Column(Integer)
    accuracy = Column(Float)
    baseline_up_accuracy = Column(Float)
    baseline_momentum_accuracy = Column(Float)
    brier_score = Column(Float)
    metrics = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
