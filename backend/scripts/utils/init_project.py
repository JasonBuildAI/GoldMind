#!/usr/bin/env python3
"""
黄金市场分析系统 - 项目初始化脚本
自动创建所有必要的目录和文件
"""

import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent
BACKEND_DIR = PROJECT_ROOT / "backend"

def create_file(filepath: str, content: str):
    """创建文件"""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ 创建文件: {filepath}")

def main():
    print("🚀 开始创建黄金市场分析系统项目...")
    print("=" * 60)

    # 1. 创建目录结构
    directories = [
        "app",
        "app/models",
        "app/schemas",
        "app/routers",
        "app/agents",
        "app/services",
        "app/utils",
        "app/tasks",
    ]

    for dir_path in directories:
        full_path = BACKEND_DIR / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        print(f"✅ 创建目录: {dir_path}")

    print("\n" + "=" * 60)
    print("📝 创建核心文件...")
    print("=" * 60)

    # 2. 创建 __init__.py 文件
    init_files = [
        "app/__init__.py",
        "app/models/__init__.py",
        "app/schemas/__init__.py",
        "app/routers/__init__.py",
        "app/agents/__init__.py",
        "app/services/__init__.py",
        "app/utils/__init__.py",
        "app/tasks/__init__.py",
    ]

    for file_path in init_files:
        create_file(BACKEND_DIR / file_path, '"""黄金市场分析系统"""')

    # 3. 创建主应用文件
    create_file(
        BACKEND_DIR / "app/main.py",
        '''"""FastAPI 主应用入口"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.database import engine, Base
from app.routers import gold_prices, analysis, news, predictions
from app.scheduler import init_scheduler, shutdown_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 启动黄金市场分析系统...")
    
    # 创建数据库表
    Base.metadata.create_all(bind=engine)
    logger.info("✅ 数据库表创建完成")
    
    # 初始化调度器
    if settings.SCHEDULER_ENABLED:
        init_scheduler()
        logger.info("✅ 定时任务调度器已启动")
    
    yield
    
    # 关闭时
    logger.info("🛑 关闭黄金市场分析系统...")
    shutdown_scheduler()


app = FastAPI(
    title="黄金市场分析系统",
    description="基于AI的黄金市场分析平台，提供实时数据、市场分析和价格预测",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(gold_prices.router, prefix="/api/gold", tags=["黄金价格"])
app.include_router(analysis.router, prefix="/api/gold", tags=["市场分析"])
app.include_router(news.router, prefix="/api/gold", tags=["新闻资讯"])
app.include_router(predictions.router, prefix="/api/gold", tags=["价格预测"])


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "黄金市场分析系统 API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "gold-analysis-api"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG
    )
'''
    )

    # 4. 创建配置文件
    create_file(
        BACKEND_DIR / "app/config.py",
        '''"""配置管理"""
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """应用配置"""
    
    # 数据库配置
    DATABASE_URL: str = "mysql+pymysql://root:root123@localhost:3306/gold_analysis"
    
    # LLM 配置
    LLM_PROVIDER: str = "deepseek"
    DEEPSEEK_API_KEY: str = "sk-d655427bbfb24d6aa3b074a70d95857c"
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    
    # 应用配置
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True
    SECRET_KEY: str = "your-secret-key-change-in-production"
    
    # 调度器配置
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    
    # 数据更新配置
    UPDATE_PRICE_CRON: str = "0 * * * *"
    UPDATE_NEWS_CRON: str = "0 */2 * * *"
    UPDATE_ANALYSIS_CRON: str = "0 8 * * *"
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()


def get_llm_config():
    """获取LLM配置"""
    return {
        "provider": settings.LLM_PROVIDER,
        "api_key": settings.DEEPSEEK_API_KEY,
        "base_url": settings.DEEPSEEK_BASE_URL
    }
'''
    )

    # 5. 创建数据库连接文件
    create_file(
        BACKEND_DIR / "app/database.py",
        '''"""数据库连接和模型基类"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=settings.DEBUG
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
'''
    )

    # 6. 创建数据库模型
    create_file(
        BACKEND_DIR / "app/models/gold_price.py",
        '''"""黄金价格数据模型"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class PriceType(enum.Enum):
    DAILY = "daily"
    MONTHLY = "monthly"


class GoldPrice(Base):
    """黄金价格表"""
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
    
    def __repr__(self):
        return f"<GoldPrice(date={self.date}, close={self.close_price})>"


class DollarIndex(Base):
    """美元指数表"""
    __tablename__ = "dollar_index"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False, index=True)
    open_price = Column(Float)
    high_price = Column(Float)
    low_price = Column(Float)
    close_price = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<DollarIndex(date={self.date}, close={self.close_price})>"
'''
    )

    create_file(
        BACKEND_DIR / "app/models/news.py",
        '''"""新闻资讯数据模型"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class SentimentType(enum.Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class GoldNews(Base):
    """黄金新闻表"""
    __tablename__ = "gold_news"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    content = Column(Text)
    source = Column(String(100))
    url = Column(String(500))
    published_at = Column(DateTime, index=True)
    sentiment = Column(Enum(SentimentType), default=SentimentType.NEUTRAL)
    keywords = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<GoldNews(title={self.title[:30]}...)>"
'''
    )

    create_file(
        BACKEND_DIR / "app/models/analysis.py",
        '''"""市场分析数据模型"""
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
    """市场因素表"""
    __tablename__ = "market_factors"
    
    id = Column(Integer, primary_key=True, index=True)
    factor_type = Column(Enum(FactorType), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    subtitle = Column(String(200))
    description = Column(Text)
    details = Column(JSON)  # 存储为JSON数组
    impact = Column(Enum(ImpactLevel), default=ImpactLevel.MEDIUM)
    source = Column(String(200))
    confidence = Column(Float, default=0.8)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<MarketFactor(type={self.factor_type}, title={self.title})>"


class InstitutionView(Base):
    """机构观点表"""
    __tablename__ = "institution_views"
    
    id = Column(Integer, primary_key=True, index=True)
    institution_name = Column(String(100), nullable=False)
    logo = Column(String(50))
    rating = Column(String(20), nullable=False)  # bullish, bearish, neutral
    target_price = Column(Float)
    timeframe = Column(String(50))
    reasoning = Column(Text)
    key_points = Column(JSON)  # 存储为JSON数组
    source_url = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<InstitutionView(name={self.institution_name}, target={self.target_price})>"


class Prediction(Base):
    """价格预测表"""
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    prediction_type = Column(String(50), nullable=False)
    target_price = Column(Float, nullable=False)
    confidence = Column(Float)
    timeframe = Column(String(50))
    reasoning = Column(Text)
    factors = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<Prediction(price={self.target_price}, confidence={self.confidence})>"
'''
    )

    create_file(
        BACKEND_DIR / "app/models/update_log.py",
        '''"""数据更新日志模型"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.sql import func
from app.database import Base
import enum


class UpdateStatus(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class UpdateLog(Base):
    """数据更新日志表"""
    __tablename__ = "update_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    data_type = Column(String(50), nullable=False, index=True)
    status = Column(Enum(UpdateStatus), nullable=False)
    records_affected = Column(Integer)
    error_message = Column(Text)
    duration_seconds = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    
    def __repr__(self):
        return f"<UpdateLog(type={self.data_type}, status={self.status})>"
'''
    )

    print("\n" + "=" * 60)
    print("🎉 项目结构创建完成!")
    print("=" * 60)
    print("\n下一步操作:")
    print("1. 安装依赖: pip install -r requirements.txt")
    print("2. 创建数据库: mysql -u root -p < schema.sql")
    print("3. 启动服务: python -m uvicorn app.main:app --reload")
    print("\n或使用 Docker:")
    print("1. docker-compose up -d")


if __name__ == "__main__":
    main()
'''
    )

    # 7. 创建 Pydantic schemas
    create_file(
        BACKEND_DIR / "app/schemas/gold_price.py",
        '''"""Pydantic 数据模型"""
from datetime import datetime, date
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class PriceBase(BaseModel):
    """价格基础模型"""
    date: date
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: float
    volume: Optional[int] = None


class PriceCreate(PriceBase):
    """创建价格数据"""
    pass


class PriceResponse(PriceBase):
    """价格响应模型"""
    id: int
    change_percent: Optional[float] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class DailyPriceResponse(BaseModel):
    """日线数据响应"""
    date: str
    price: float
    volume: int


class MonthlyPriceResponse(BaseModel):
    """月度数据响应"""
    month: str
    open: float
    close: float
    change: float


class CorrelationDataResponse(BaseModel):
    """相关性数据响应"""
    date: str
    gold_price: float
    dollar_index: float


class GoldStatsResponse(BaseModel):
    """统计数据响应"""
    start_price: float
    end_price: float
    max_price: float
    min_price: float
    total_return: float
    max_date: str
    min_date: str
'''
    )

    create_file(
        BACKEND_DIR / "app/schemas/news.py",
        '''"""新闻 Pydantic 模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from enum import Enum


class SentimentEnum(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class NewsBase(BaseModel):
    """新闻基础模型"""
    title: str
    content: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    published_at: Optional[datetime] = None


class NewsCreate(NewsBase):
    """创建新闻"""
    pass


class NewsResponse(NewsBase):
    """新闻响应模型"""
    id: int
    sentiment: SentimentEnum
    keywords: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class NewsFilter(BaseModel):
    """新闻过滤条件"""
    source: Optional[str] = None
    sentiment: Optional[SentimentEnum] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 20
'''
    )

    create_file(
        BACKEND_DIR / "app/schemas/analysis.py",
        '''"""分析 Pydantic 模型"""
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


class FactorBase(BaseModel):
    """因素基础模型"""
    title: str
    subtitle: Optional[str] = None
    description: Optional[str] = None
    details: List[str]
    impact: ImpactEnum


class FactorCreate(FactorBase):
    """创建因素"""
    factor_type: FactorTypeEnum


class FactorResponse(FactorBase):
    """因素响应模型"""
    id: int
    factor_type: FactorTypeEnum
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class InstitutionBase(BaseModel):
    """机构基础模型"""
    institution_name: str
    logo: Optional[str] = None
    rating: str
    target_price: float
    timeframe: str
    reasoning: str
    key_points: List[str]


class InstitutionCreate(InstitutionBase):
    """创建机构观点"""
    pass


class InstitutionResponse(InstitutionBase):
    """机构观点响应模型"""
    id: int
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class PredictionBase(BaseModel):
    """预测基础模型"""
    prediction_type: str
    target_price: float
    confidence: Optional[float] = None
    timeframe: str
    reasoning: str
    factors: Optional[List[str]] = None


class PredictionCreate(PredictionBase):
    """创建预测"""
    pass


class PredictionResponse(PredictionBase):
    """预测响应模型"""
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True
'''
    )

    # 8. 创建 API 路由
    create_file(
        BACKEND_DIR / "app/routers/gold_prices.py",
        '''"""黄金价格 API 路由"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.gold_price import GoldPrice, DollarIndex
from app.schemas.gold_price import (
    DailyPriceResponse,
    MonthlyPriceResponse,
    CorrelationDataResponse,
    GoldStatsResponse
)
from app.services.gold_service import GoldService

router = APIRouter()


@router.get("/prices/daily", response_model=List[DailyPriceResponse])
async def get_daily_prices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db)
):
    """获取日线价格数据"""
    service = GoldService(db)
    
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        start = datetime.now() - timedelta(days=limit)
    
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end = datetime.now()
    
    prices = service.get_daily_prices(start, end)
    
    return [
        DailyPriceResponse(
            date=p.date.strftime("%Y-%m-%d"),
            price=p.close_price,
            volume=p.volume or 0
        )
        for p in prices
    ]


@router.get("/prices/monthly", response_model=List[MonthlyPriceResponse])
async def get_monthly_prices(
    limit: int = Query(default=12, le=60),
    db: Session = Depends(get_db)
):
    """获取月度价格数据"""
    service = GoldService(db)
    monthly_data = service.get_monthly_summary(limit)
    
    return [
        MonthlyPriceResponse(
            month=item["month"],
            open=item["open"],
            close=item["close"],
            change=item["change"]
        )
        for item in monthly_data
    ]


@router.get("/prices/correlation", response_model=List[CorrelationDataResponse])
async def get_correlation_data(
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_db)
):
    """获取黄金与美元指数相关性数据"""
    service = GoldService(db)
    correlation_data = service.get_correlation_data(limit)
    
    return [
        CorrelationDataResponse(
            date=item["date"],
            gold_price=item["gold_price"],
            dollar_index=item["dollar_index"]
        )
        for item in correlation_data
    ]


@router.get("/stats", response_model=GoldStatsResponse)
async def get_gold_stats(db: Session = Depends(get_db)):
    """获取黄金统计数据"""
    service = GoldService(db)
    stats = service.get_statistics()
    
    if not stats:
        raise HTTPException(status_code=404, detail="暂无数据")
    
    return GoldStatsResponse(**stats)


@router.get("/latest")
async def get_latest_price(db: Session = Depends(get_db)):
    """获取最新价格"""
    service = GoldService(db)
    latest = service.get_latest_price()
    
    if not latest:
        raise HTTPException(status_code=404, detail="暂无数据")
    
    return {
        "date": latest.date.strftime("%Y-%m-%d"),
        "price": latest.close_price,
        "change": latest.change_percent
    }
'''
    )

    create_file(
        BACKEND_DIR / "app/routers/news.py",
        '''"""新闻 API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.news import GoldNews, SentimentType
from app.schemas.news import NewsResponse, NewsFilter
from app.services.news_service import NewsService

router = APIRouter()


@router.get("/news", response_model=List[NewsResponse])
async def get_news(
    limit: int = Query(default=20, le=100),
    source: Optional[str] = None,
    sentiment: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取新闻列表"""
    service = NewsService(db)
    
    filter_params = NewsFilter(
        source=source,
        sentiment=sentiment if sentiment else None,
        limit=limit
    )
    
    news = service.get_news(filter_params)
    
    return [
        NewsResponse(
            id=n.id,
            title=n.title,
            content=n.content,
            source=n.source,
            url=n.url,
            published_at=n.published_at,
            sentiment=n.sentiment,
            keywords=n.keywords,
            created_at=n.created_at
        )
        for n in news
    ]


@router.get("/news/{news_id}")
async def get_news_detail(news_id: int, db: Session = Depends(get_db)):
    """获取新闻详情"""
    service = NewsService(db)
    news = service.get_news_by_id(news_id)
    
    if not news:
        return {"error": "新闻不存在"}
    
    return {
        "id": news.id,
        "title": news.title,
        "content": news.content,
        "source": news.source,
        "url": news.url,
        "published_at": news.published_at,
        "sentiment": news.sentiment,
        "keywords": news.keywords
    }


@router.get("/news/sentiment/summary")
async def get_sentiment_summary(db: Session = Depends(get_db)):
    """获取情感分析摘要"""
    service = NewsService(db)
    summary = service.get_sentiment_summary()
    
    if not summary:
        return {"positive": 0, "neutral": 0, "negative": 0}
    
    return summary
'''
    )

    create_file(
        BACKEND_DIR / "app/routers/analysis.py",
        '''"""市场分析 API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.analysis import MarketFactor, InstitutionView
from app.schemas.analysis import (
    FactorResponse,
    InstitutionResponse
)

router = APIRouter()


@router.get("/factors", response_model=List[FactorResponse])
async def get_market_factors(
    factor_type: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取市场因素"""
    query = db.query(MarketFactor)
    
    if factor_type:
        query = query.filter(MarketFactor.factor_type == factor_type)
    
    factors = query.order_by(MarketFactor.created_at.desc()).limit(limit).all()
    
    return [
        FactorResponse(
            id=f.id,
            factor_type=f.factor_type,
            title=f.title,
            subtitle=f.subtitle,
            description=f.description,
            details=f.details or [],
            impact=f.impact,
            created_at=f.created_at,
            updated_at=f.updated_at
        )
        for f in factors
    ]


@router.get("/factors/bullish", response_model=List[FactorResponse])
async def get_bullish_factors(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取看涨因素"""
    factors = db.query(MarketFactor).filter(
        MarketFactor.factor_type == "bullish"
    ).order_by(MarketFactor.created_at.desc()).limit(limit).all()
    
    return [
        FactorResponse(
            id=f.id,
            factor_type=f.factor_type,
            title=f.title,
            subtitle=f.subtitle,
            description=f.description,
            details=f.details or [],
            impact=f.impact,
            created_at=f.created_at,
            updated_at=f.updated_at
        )
        for f in factors
    ]


@router.get("/factors/bearish", response_model=List[FactorResponse])
async def get_bearish_factors(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取看跌因素"""
    factors = db.query(MarketFactor).filter(
        MarketFactor.factor_type == "bearish"
    ).order_by(MarketFactor.created_at.desc()).limit(limit).all()
    
    return [
        FactorResponse(
            id=f.id,
            factor_type=f.factor_type,
            title=f.title,
            subtitle=f.subtitle,
            description=f.description,
            details=f.details or [],
            impact=f.impact,
            created_at=f.created_at,
            updated_at=f.updated_at
        )
        for f in factors
    ]


@router.get("/institutions", response_model=List[InstitutionResponse])
async def get_institution_views(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取机构观点"""
    views = db.query(InstitutionView).order_by(
        InstitutionView.created_at.desc()
    ).limit(limit).all()
    
    return [
        InstitutionResponse(
            id=v.id,
            institution_name=v.institution_name,
            logo=v.logo,
            rating=v.rating,
            target_price=v.target_price,
            timeframe=v.timeframe,
            reasoning=v.reasoning,
            key_points=v.key_points or [],
            created_at=v.created_at,
            updated_at=v.updated_at
        )
        for v in views
    ]
'''
    )

    create_file(
        BACKEND_DIR / "app/routers/predictions.py",
        '''"""价格预测 API 路由"""
from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.analysis import Prediction
from app.schemas.analysis import PredictionResponse

router = APIRouter()


@router.get("/predictions", response_model=List[PredictionResponse])
async def get_predictions(
    limit: int = 10,
    db: Session = Depends(get_db)
):
    """获取价格预测"""
    predictions = db.query(Prediction).order_by(
        Prediction.created_at.desc()
    ).limit(limit).all()
    
    return [
        PredictionResponse(
            id=p.id,
            prediction_type=p.prediction_type,
            target_price=p.target_price,
            confidence=p.confidence,
            timeframe=p.timeframe,
            reasoning=p.reasoning,
            factors=p.factors,
            created_at=p.created_at
        )
        for p in predictions
    ]


@router.get("/predictions/latest")
async def get_latest_prediction(db: Session = Depends(get_db)):
    """获取最新预测"""
    prediction = db.query(Prediction).order_by(
        Prediction.created_at.desc()
    ).first()
    
    if not prediction:
        return {"message": "暂无预测数据"}
    
    return {
        "type": prediction.prediction_type,
        "target_price": prediction.target_price,
        "confidence": prediction.confidence,
        "timeframe": prediction.timeframe,
        "reasoning": prediction.reasoning,
        "factors": prediction.factors,
        "created_at": prediction.created_at
    }
'''
    )

    # 9. 创建服务层
    create_file(
        BACKEND_DIR / "app/services/gold_service.py",
        '''"""黄金价格服务"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.gold_price import GoldPrice, DollarIndex

import yfinance as yf


class GoldService:
    """黄金价格服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_daily_prices(self, start_date: datetime, end_date: datetime) -> List[GoldPrice]:
        """获取日线价格"""
        return self.db.query(GoldPrice).filter(
            GoldPrice.date >= start_date.date(),
            GoldPrice.date <= end_date.date()
        ).order_by(GoldPrice.date).all()
    
    def get_monthly_summary(self, months: int = 12) -> List[Dict]:
        """获取月度汇总"""
        # 获取最近月份的数据
        prices = self.db.query(GoldPrice).order_by(
            GoldPrice.date.desc()
        ).limit(months * 30).all()
        
        # 按月份分组
        monthly_data = {}
        for price in prices:
            month_key = price.date.strftime("%Y-%m")
            if month_key not in monthly_data:
                monthly_data[month_key] = {
                    "month": month_key,
                    "open": None,
                    "close": None,
                    "min": float('inf'),
                    "max": float('-inf')
                }
            
            if monthly_data[month_key]["open"] is None:
                monthly_data[month_key]["open"] = price.open_price or price.close_price
            monthly_data[month_key]["close"] = price.close_price
            monthly_data[month_key]["min"] = min(
                monthly_data[month_key]["min"],
                price.low_price or price.close_price
            )
            monthly_data[month_key]["max"] = max(
                monthly_data[month_key]["max"],
                price.high_price or price.close_price
            )
        
        # 计算涨跌
        result = []
        for month_key in sorted(monthly_data.keys(), reverse=True):
            data = monthly_data[month_key]
            change = ((data["close"] - data["open"]) / data["open"] * 100) if data["open"] else 0
            result.append({
                "month": month_key,
                "open": round(data["open"], 2),
                "close": round(data["close"], 2),
                "change": round(change, 2)
            })
        
        return result[:months]
    
    def get_correlation_data(self, limit: int = 100) -> List[Dict]:
        """获取相关性数据"""
        # 获取黄金价格
        gold_prices = self.db.query(GoldPrice).order_by(
            GoldPrice.date.desc()
        ).limit(limit).all()
        
        # 获取美元指数
        dollar_prices = self.db.query(DollarIndex).order_by(
            DollarIndex.date.desc()
        ).limit(limit).all()
        
        # 转换为字典
        gold_dict = {p.date.strftime("%Y-%m-%d"): p.close_price for p in gold_prices}
        dollar_dict = {p.date.strftime("%Y-%m-%d"): p.close_price for p in dollar_prices}
        
        # 合并数据
        result = []
        for date_str in sorted(gold_dict.keys(), reverse=True):
            if date_str in dollar_dict:
                result.append({
                    "date": date_str,
                    "gold_price": gold_dict[date_str],
                    "dollar_index": dollar_dict[date_str]
                })
        
        return result
    
    def get_statistics(self) -> Optional[Dict]:
        """获取统计数据"""
        prices = self.db.query(GoldPrice).all()
        
        if not prices:
            return None
        
        sorted_prices = sorted(prices, key=lambda x: x.date)
        
        start_price = sorted_prices[0].close_price
        end_price = sorted_prices[-1].close_price
        total_return = ((end_price - start_price) / start_price) * 100
        
        max_price = max(p.close_price for p in prices)
        min_price = min(p.close_price for p in prices)
        
        max_date = next(p.date.strftime("%Y-%m-%d") for p in prices if p.close_price == max_price)
        min_date = next(p.date.strftime("%Y-%m-%d") for p in prices if p.close_price == min_price)
        
        return {
            "start_price": round(start_price, 2),
            "end_price": round(end_price, 2),
            "max_price": round(max_price, 2),
            "min_price": round(min_price, 2),
            "total_return": round(total_return, 2),
            "max_date": max_date,
            "min_date": min_date
        }
    
    def get_latest_price(self) -> Optional[GoldPrice]:
        """获取最新价格"""
        return self.db.query(GoldPrice).order_by(
            GoldPrice.date.desc()
        ).first()
    
    def fetch_and_save_prices(self):
        """从Yahoo Finance获取并保存价格"""
        try:
            # 下载黄金价格数据
            gold = yf.Ticker("GLD")
            df = gold.history(period="1y")
            
            for index, row in df.iterrows():
                date = index.date()
                
                # 检查是否已存在
                existing = self.db.query(GoldPrice).filter(
                    GoldPrice.date == date
                ).first()
                
                if existing:
                    continue
                
                gold_price = GoldPrice(
                    date=date,
                    open_price=float(row['Open']),
                    high_price=float(row['High']),
                    low_price=float(row['Low']),
                    close_price=float(row['Close']),
                    volume=int(row['Volume'])
                )
                
                self.db.add(gold_price)
            
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e
    
    def fetch_and_save_dollar_index(self):
        """从Yahoo Finance获取并保存美元指数"""
        try:
            # 下载美元指数数据
            dxy = yf.Ticker("DX-Y.NYB")
            df = dxy.history(period="1y")
            
            for index, row in df.iterrows():
                date = index.date()
                
                # 检查是否已存在
                existing = self.db.query(DollarIndex).filter(
                    DollarIndex.date == date
                ).first()
                
                if existing:
                    continue
                
                dollar_index = DollarIndex(
                    date=date,
                    open_price=float(row['Open']),
                    high_price=float(row['High']),
                    low_price=float(row['Low']),
                    close_price=float(row['Close'])
                )
                
                self.db.add(dollar_index)
            
            self.db.commit()
            return True
        except Exception as e:
            self.db.rollback()
            raise e
'''
    )

    create_file(
        BACKEND_DIR / "app/services/news_service.py",
        '''"""新闻服务"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from app.models.news import GoldNews, SentimentType
import feedparser
import requests


class NewsService:
    """新闻服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_news(self, filter_params) -> List[GoldNews]:
        """获取新闻列表"""
        query = self.db.query(GoldNews)
        
        if filter_params.source:
            query = query.filter(GoldNews.source == filter_params.source)
        
        if filter_params.sentiment:
            query = query.filter(GoldNews.sentiment == filter_params.sentiment)
        
        if filter_params.start_date:
            query = query.filter(GoldNews.published_at >= filter_params.start_date)
        
        if filter_params.end_date:
            query = query.filter(GoldNews.published_at <= filter_params.end_date)
        
        return query.order_by(GoldNews.published_at.desc()).limit(filter_params.limit).all()
    
    def get_news_by_id(self, news_id: int) -> Optional[GoldNews]:
        """根据ID获取新闻"""
        return self.db.query(GoldNews).filter(GoldNews.id == news_id).first()
    
    def get_sentiment_summary(self) -> Dict[str, int]:
        """获取情感分析摘要"""
        stats = self.db.query(
            GoldNews.sentiment,
            func.count(GoldNews.id)
        ).group_by(GoldNews.sentiment).all()
        
        return {
            "positive": 0,
            "neutral": 0,
            "negative": 0,
            **{s[0].value: s[1] for s in stats}
        }
    
    def fetch_from_rss(self, rss_url: str, source: str, limit: int = 10) -> List[Dict]:
        """从RSS获取新闻"""
        try:
            feed = feedparser.parse(rss_url)
            
            news_list = []
            for entry in feed.entries[:limit]:
                news_list.append({
                    'title': entry.title,
                    'summary': entry.get('summary', ''),
                    'link': entry.link,
                    'published_at': entry.get('published', ''),
                    'source': source
                })
            
            return news_list
        except Exception as e:
            print(f"RSS获取失败 {source}: {e}")
            return []
    
    def fetch_all_rss_news(self) -> List[Dict]:
        """从所有RSS源获取新闻"""
        all_news = []
        
        rss_sources = [
            ('http://finance.sina.com.cn/roll/finance_gold/index.d.html', '新浪财经'),
            ('http://www.fx168.com/rss/gold.xml', 'FX168'),
        ]
        
        for rss_url, source in rss_sources:
            try:
                news = self.fetch_from_rss(rss_url, source, limit=5)
                all_news.extend(news)
            except Exception as e:
                print(f"RSS获取失败 {source}: {e}")
        
        return all_news
    
    def save_news(self, news_data: Dict):
        """保存新闻"""
        try:
            # 检查是否已存在
            existing = self.db.query(GoldNews).filter(
                GoldNews.url == news_data.get('url')
            ).first()
            
            if existing:
                return existing
            
            news = GoldNews(
                title=news_data['title'],
                content=news_data.get('content'),
                source=news_data.get('source'),
                url=news_data.get('url'),
                published_at=news_data.get('published_at'),
                sentiment=SentimentType.NEUTRAL,  # 后续可用AI分析
                keywords=news_data.get('keywords')
            )
            
            self.db.add(news)
            self.db.commit()
            
            return news
        except Exception as e:
            self.db.rollback()
            print(f"保存新闻失败: {e}")
            return None
'''
    )

    # 10. 创建 Agent 模块
    create_file(
        BACKEND_DIR / "app/agents/base.py",
        '''"""LangChain Agent 基类"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from app.config import settings


class BaseAgent(ABC):
    """Agent基类"""
    
    def __init__(self):
        self.llm = self._create_llm()
    
    def _create_llm(self) -> ChatOpenAI:
        """创建LLM实例"""
        return ChatOpenAI(
            model="deepseek-chat",
            openai_api_key=settings.DEEPSEEK_API_KEY,
            openai_api_base=settings.DEEPSEEK_BASE_URL,
            temperature=0.7,
            max_tokens=4096
        )
    
    @abstractmethod
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行Agent"""
        pass
    
    def _format_prompt(self, template: str, **kwargs) -> str:
        """格式化Prompt"""
        return template.format(**kwargs)
'''
    )

    create_file(
        BACKEND_DIR / "app/agents/market_analyzer.py",
        '''"""市场分析 Agent"""
from typing import Dict, Any, List
from app.agents.base import BaseAgent


class MarketAnalyzerAgent(BaseAgent):
    """市场分析 Agent"""
    
    def __init__(self):
        super().__init__()
        self.prompt_template = """
你是一位专业的黄金市场分析师。请根据以下信息进行分析：

当前市场数据：
{market_data}

最新新闻：
{news}

请分析：
1. 当前市场的主要看涨因素
2. 当前市场的主要看跌因素
3. 价格走势预测
4. 投资建议

请以JSON格式返回分析结果，格式如下：
{{
    "bullish_factors": [
        {{
            "title": "因素标题",
            "subtitle": "副标题",
            "description": "详细描述",
            "details": ["要点1", "要点2"],
            "impact": "high/medium/low"
        }}
    ],
    "bearish_factors": [
        {{
            "title": "因素标题",
            "subtitle": "副标题",
            "description": "详细描述",
            "details": ["要点1", "要点2"],
            "impact": "high/medium/low"
        }}
    ],
    "prediction": {{
        "target_price": 5000,
        "timeframe": "2026年底",
        "confidence": 0.8,
        "reasoning": "预测理由"
    }},
    "advice": "投资建议"
}}
"""
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行市场分析"""
        market_data = input_data.get('market_data', {})
        news = input_data.get('news', [])
        
        news_text = "\n".join([f"- {n.get('title', '')}" for n in news[:10]])
        
        prompt = self._format_prompt(
            self.prompt_template,
            market_data=str(market_data),
            news=news_text
        )
        
        response = self.llm.invoke(prompt)
        
        # 解析JSON响应
        import json
        try:
            # 尝试直接解析
            result = json.loads(response.content)
        except json.JSONDecodeError:
            # 如果失败，尝试提取JSON
            content = response.content
            start = content.find('{')
            end = content.rfind('}') + 1
            if start != -1 and end != 0:
                result = json.loads(content[start:end])
            else:
                result = {
                    "bullish_factors": [],
                    "bearish_factors": [],
                    "prediction": None,
                    "advice": "分析失败"
                }
        
        return result
'''
    )

    create_file(
        BACKEND_DIR / "app/agents/news_analyzer.py",
        '''"""新闻分析 Agent"""
from typing import Dict, Any, List
from app.agents.base import BaseAgent


class NewsAnalyzerAgent(BaseAgent):
    """新闻分析 Agent"""
    
    def __init__(self):
        super().__init__()
        self.prompt_template = """
你是一位金融新闻分析师。请分析以下黄金相关新闻的情感和重要性：

{news_list}

请对每条新闻进行分析，以JSON格式返回：
[
    {{
        "title": "新闻标题",
        "sentiment": "positive/negative/neutral",
        "importance": "high/medium/low",
        "keywords": ["关键词1", "关键词2"],
        "impact_summary": "对黄金市场的影响概述"
    }}
]
"""
    
    def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """执行新闻分析"""
        news_list = input_data.get('news', [])
        
        news_text = "\n".join([
            f"{i+1}. {n.get('title', '')}"
            for i, n in enumerate(news_list[:20])
        ])
        
        prompt = self._format_prompt(
            self.prompt_template,
            news_list=news_text
        )
        
        response = self.llm.invoke(prompt)
        
        # 解析JSON响应
        import json
        try:
            content = response.content
            start = content.find('[')
            end = content.rfind(']') + 1
            if start != -1 and end != 0:
                result = json.loads(content[start:end])
            else:
                result = []
        except json.JSONDecodeError:
            result = []
        
        return {"analysis": result}
'''
    )

    # 11. 创建定时任务
    create_file(
        BACKEND_DIR / "app/scheduler.py",
        '''"""定时任务调度器"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from app.config import settings

scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)


def init_scheduler():
    """初始化调度器"""
    if not settings.SCHEDULER_ENABLED:
        logger.info("定时任务已禁用")
        return
    
    # 价格更新任务 - 每小时
    scheduler.add_job(
        update_prices_job,
        CronTrigger.from_crontab(settings.UPDATE_PRICE_CRON),
        id='update_prices',
        name='更新黄金价格数据',
        replace_existing=True
    )
    
    # 新闻更新任务 - 每2小时
    scheduler.add_job(
        update_news_job,
        CronTrigger.from_crontab(settings.UPDATE_NEWS_CRON),
        id='update_news',
        name='更新新闻资讯',
        replace_existing=True
    )
    
    # 市场分析任务 - 每天早上8点
    scheduler.add_job(
        update_analysis_job,
        CronTrigger.from_crontab(settings.UPDATE_ANALYSIS_CRON),
        id='update_analysis',
        name='更新市场分析',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("定时任务调度器已启动")


def shutdown_scheduler():
    """关闭调度器"""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("定时任务调度器已关闭")


async def update_prices_job():
    """更新价格数据"""
    logger.info("开始更新黄金价格数据...")
    try:
        from app.services.gold_service import GoldService
        from app.database import SessionLocal
        
        db = SessionLocal()
        try:
            service = GoldService(db)
            service.fetch_and_save_prices()
            service.fetch_and_save_dollar_index()
            logger.info("✅ 价格数据更新完成")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ 价格数据更新失败: {e}")


async def update_news_job():
    """更新新闻数据"""
    logger.info("开始更新新闻资讯...")
    try:
        from app.services.news_service import NewsService
        from app.database import SessionLocal
        
        db = SessionLocal()
        try:
            service = NewsService(db)
            news_list = service.fetch_all_rss_news()
            
            for news in news_list:
                service.save_news(news)
            
            logger.info(f"✅ 新闻数据更新完成，共{len(news_list)}条")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ 新闻数据更新失败: {e}")


async def update_analysis_job():
    """更新市场分析"""
    logger.info("开始更新市场分析...")
    try:
        from app.agents.market_analyzer import MarketAnalyzerAgent
        from app.database import SessionLocal
        
        db = SessionLocal()
        try:
            agent = MarketAnalyzerAgent()
            
            # 获取市场数据
            from app.services.gold_service import GoldService
            service = GoldService(db)
            stats = service.get_statistics()
            
            # 获取新闻
            from app.services.news_service import NewsService
            news_service = NewsService(db)
            news = news_service.get_news(type('NewsFilter', (), {'limit': 20, 'source': None, 'sentiment': None, 'start_date': None, 'end_date': None})())
            
            news_data = [{'title': n.title, 'content': n.content} for n in news]
            
            # 执行分析
            result = agent.run({
                'market_data': stats or {},
                'news': news_data
            })
            
            logger.info("✅ 市场分析更新完成")
            logger.info(f"   看涨因素: {len(result.get('bullish_factors', []))}条")
            logger.info(f"   看跌因素: {len(result.get('bearish_factors', []))}条")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ 市场分析更新失败: {e}")
'''
    )

    # 12. 创建 Docker 配置
    create_file(
        BACKEND_DIR / "Dockerfile",
        '''FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \\
    default-libmysqlclient-dev \\
    build-essential \\
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
'''
    )

    create_file(
        BACKEND_DIR / "docker-compose.yml",
        '''version: '3.8'

services:
  mysql:
    image: mysql:8.0
    container_name: gold_mysql
    environment:
      MYSQL_ROOT_PASSWORD: root123
      MYSQL_DATABASE: gold_analysis
      MYSQL_CHARSET: utf8mb4
      MYSQL_COLLATION: utf8mb4_unicode_ci
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: gold_backend
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      - DATABASE_URL=mysql+pymysql://root:root123@mysql:3306/gold_analysis
      - LLM_PROVIDER=deepseek
      - LLM_API_KEY=${LLM_API_KEY}
      - DEBUG=true
    ports:
      - "8000:8000"
    volumes:
      - ./:/app
    command: >
      sh -c "uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

volumes:
  mysql_data:
'''
    )

    create_file(
        BACKEND_DIR / ".dockerignore",
        '''__pycache__
*.py[cod]
*$py.class
*.so
.Python
.env
.git
.gitignore
.dockerignore
Dockerfile
docker-compose.yml
*.md
venv/
.venv/
.pytest_cache
.coverage
htmlcov/
.tox/
.mypy_cache/
'''
    )

    create_file(
        BACKEND_DIR / "README.md",
        '''# 黄金市场分析系统后端

基于 FastAPI + LangChain + MySQL 的黄金市场分析系统后端服务。

## 功能特性

- 📊 **实时数据获取** - 从Yahoo Finance获取黄金和美元指数数据
- 📰 **新闻资讯聚合** - 从RSS源聚合黄金相关新闻
- 🤖 **AI智能分析** - 使用LangChain Agent进行市场分析
- 📈 **价格预测** - 基于历史数据和新闻的AI预测
- ⏰ **自动更新** - 定时任务自动更新数据

## 技术栈

- **FastAPI** - 高性能Web框架
- **SQLAlchemy** - ORM数据库操作
- **LangChain** - AI Agent框架
- **MySQL** - 关系型数据库
- **APScheduler** - 定时任务调度

## 快速开始

### 1. 安装依赖

\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 2. 配置环境变量

编辑 \`.env\` 文件：

\`\`\`env
DATABASE_URL=mysql+pymysql://root:root123@localhost:3306/gold_analysis
DEEPSEEK_API_KEY=your_api_key_here
\`\`\`

### 3. 创建数据库

\`\`\`bash
mysql -u root -p < schema.sql
\`\`\`

### 4. 启动服务

\`\`\`bash
python -m uvicorn app.main:app --reload
\`\`\`

### 5. 访问API文档

打开浏览器访问：http://localhost:8000/docs

## Docker 部署

\`\`\`bash
docker-compose up -d
\`\`\`

## 项目结构

\`\`\`
backend/
├── app/
│   ├── main.py              # FastAPI入口
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库连接
│   ├── models/              # 数据模型
│   ├── schemas/             # Pydantic模型
│   ├── routers/             # API路由
│   ├── agents/              # LangChain Agent
│   ├── services/            # 业务逻辑
│   ├── utils/               # 工具函数
│   └── tasks/               # 定时任务
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
\`\`\`

## API 接口

### 黄金价格

- \`GET /api/gold/prices/daily\` - 获取日线数据
- \`GET /api/gold/prices/monthly\` - 获取月度汇总
- \`GET /api/gold/prices/correlation\` - 获取相关性数据
- \`GET /api/gold/stats\` - 获取统计数据
- \`GET /api/gold/latest\` - 获取最新价格

### 新闻资讯

- \`GET /api/gold/news\` - 获取新闻列表
- \`GET /api/gold/news/{id}\` - 获取新闻详情
- \`GET /api/gold/news/sentiment/summary\` - 情感分析摘要

### 市场分析

- \`GET /api/gold/factors\` - 获取市场因素
- \`GET /api/gold/factors/bullish\` - 获取看涨因素
- \`GET /api/gold/factors/bearish\` - 获取看跌因素
- \`GET /api/gold/institutions\` - 获取机构观点

### 价格预测

- \`GET /api/gold/predictions\` - 获取预测列表
- \`GET /api/gold/predictions/latest\` - 获取最新预测

## 定时任务

| 任务 | 频率 | 说明 |
|------|------|------|
| 更新价格 | 每小时 | 获取黄金和美元指数数据 |
| 更新新闻 | 每2小时 | 聚合RSS新闻资讯 |
| 更新分析 | 每天8点 | AI市场分析和预测 |

## License

MIT
'''
    )

    create_file(
        BACKEND_DIR / "schema.sql",
        '''-- 黄金市场分析系统数据库 Schema
-- 创建数据库
CREATE DATABASE IF NOT EXISTS gold_analysis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE gold_analysis;

-- 黄金价格表
CREATE TABLE IF NOT EXISTS gold_prices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    open_price DECIMAL(10, 2),
    high_price DECIMAL(10, 2),
    low_price DECIMAL(10, 2),
    close_price DECIMAL(10, 2) NOT NULL,
    volume INT,
    change_percent DECIMAL(5, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 美元指数表
CREATE TABLE IF NOT EXISTS dollar_index (
    id INT AUTO_INCREMENT PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    open_price DECIMAL(10, 4),
    high_price DECIMAL(10, 4),
    low_price DECIMAL(10, 4),
    close_price DECIMAL(10, 4) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_date (date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 黄金新闻表
CREATE TABLE IF NOT EXISTS gold_news (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content TEXT,
    source VARCHAR(100),
    url VARCHAR(500),
    published_at TIMESTAMP,
    sentiment ENUM('positive', 'negative', 'neutral') DEFAULT 'neutral',
    keywords TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_published_at (published_at),
    INDEX idx_sentiment (sentiment)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 市场因素表
CREATE TABLE IF NOT EXISTS market_factors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    type ENUM('bullish', 'bearish') NOT NULL,
    title VARCHAR(200) NOT NULL,
    subtitle VARCHAR(200),
    description TEXT,
    details JSON,
    impact ENUM('high', 'medium', 'low') DEFAULT 'medium',
    source VARCHAR(200),
    confidence DECIMAL(3, 2) DEFAULT 0.80,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 机构观点表
CREATE TABLE IF NOT EXISTS institution_views (
    id INT AUTO_INCREMENT PRIMARY KEY,
    institution_name VARCHAR(100) NOT NULL,
    logo VARCHAR(50),
    rating ENUM('bullish', 'bearish', 'neutral') NOT NULL,
    target_price DECIMAL(10, 2),
    timeframe VARCHAR(50),
    reasoning TEXT,
    key_points JSON,
    source_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 价格预测表
CREATE TABLE IF NOT EXISTS predictions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    prediction_type VARCHAR(50) NOT NULL,
    target_price DECIMAL(10, 2) NOT NULL,
    confidence DECIMAL(5, 2),
    timeframe VARCHAR(50),
    reasoning TEXT,
    factors JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 数据更新日志表
CREATE TABLE IF NOT EXISTS update_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_type VARCHAR(50) NOT NULL,
    status ENUM('success', 'failed') NOT NULL,
    records_affected INT,
    error_message TEXT,
    duration_seconds DECIMAL(10, 3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_data_type (data_type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
'''
    )

    print("\n" + "=" * 60)
    print("🎉 项目创建完成!")
    print("=" * 60)

    print("\n📋 下一步操作:")
    print("-" * 60)
    print("1️⃣  进入项目目录: cd backend")
    print("2️⃣  安装Python依赖: pip install -r requirements.txt")
    print("3️⃣  创建MySQL数据库: mysql -u root -p < schema.sql")
    print("4️⃣  启动后端服务: python -m uvicorn app.main:app --reload")
    print("")
    print("🐳 或者使用Docker:")
    print("   docker-compose up -d")
    print("")
    print("📖 API文档: http://localhost:8000/docs")
    print("🏥 健康检查: http://localhost:8000/health")


if __name__ == "__main__":
    main()
