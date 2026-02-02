"""FastAPI 主应用入口"""
import os
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.database import engine, Base
from app.routers import gold_prices, analysis, news, predictions
from app.scheduler import init_scheduler, shutdown_scheduler


async def warmup_cache():
    """启动时预热缓存（后台执行，不阻塞服务启动）"""
    await asyncio.sleep(5)  # 等待5秒让系统完全启动
    try:
        from app.database import SessionLocal
        from app.services.bullish_factor_service import BullishFactorService
        from app.services.bearish_factor_service import BearishFactorService
        from app.services.institution_prediction_service import InstitutionPredictionService
        from app.services.investment_advice_service import InvestmentAdviceService
        
        db = SessionLocal()
        try:
            logger.info("[缓存预热] 开始后台预热Agent缓存...")
            
            # 预热看涨因子
            bullish_service = BullishFactorService(db)
            if not bullish_service.cache.exists():
                logger.info("[缓存预热] 触发看涨因子分析...")
                bullish_service._trigger_background_analysis()
            
            # 预热看跌因子
            bearish_service = BearishFactorService(db)
            if not bearish_service.cache.exists():
                logger.info("[缓存预热] 触发看跌因子分析...")
                bearish_service._trigger_background_analysis()
            
            # 预热机构预测
            institution_service = InstitutionPredictionService(db)
            if not institution_service.cache.exists():
                logger.info("[缓存预热] 触发机构预测分析...")
                institution_service._trigger_background_analysis()
            
            # 预热投资建议
            advice_service = InvestmentAdviceService(db)
            if not advice_service.cache.exists():
                logger.info("[缓存预热] 触发投资建议分析...")
                advice_service._trigger_background_analysis()
            
            logger.info("[缓存预热] 所有预热任务已启动")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[缓存预热] 预热失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动黄金市场分析系统...")
    
    Base.metadata.create_all(bind=engine)
    logger.info("数据库表创建完成")
    
    if settings.SCHEDULER_ENABLED:
        init_scheduler()
        logger.info("定时任务调度器已启动")
        
        # 启动缓存预热（后台执行，不阻塞）
        asyncio.create_task(warmup_cache())
    
    yield
    
    logger.info("关闭黄金市场分析系统...")
    shutdown_scheduler()


app = FastAPI(
    title="黄金市场分析系统",
    description="基于AI的黄金市场分析平台，提供实时数据、市场分析和价格预测",
    version="1.0.0",
    lifespan=lifespan
)

# 添加请求限流中间件（保护服务不被过载）
@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """简单的请求限流中间件 - 防止单个IP请求过多"""
    from starlette.requests import Request
    
    # 获取客户端IP
    client_ip = request.client.host if request.client else "unknown"
    
    # 简单的内存限流（生产环境建议使用Redis）
    current_time = datetime.now().timestamp()
    
    # 使用全局字典存储请求记录（实际生产建议使用Redis）
    if not hasattr(rate_limit_middleware, "request_records"):
        rate_limit_middleware.request_records = {}
    
    records = rate_limit_middleware.request_records
    
    # 清理过期记录（60秒前的）
    if client_ip in records:
        records[client_ip] = [
            t for t in records[client_ip] 
            if current_time - t < 60
        ]
    else:
        records[client_ip] = []
    
    # 检查限流（每分钟最多60个请求）
    if len(records.get(client_ip, [])) >= 60:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={
                "error": "请求过于频繁，请稍后再试",
                "retry_after": 60
            }
        )
    
    # 记录本次请求
    records[client_ip].append(current_time)
    
    # 继续处理请求
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gold_prices.router, prefix="/api/gold", tags=["黄金价格"])
app.include_router(analysis.router, prefix="/api/gold", tags=["市场分析"])
app.include_router(news.router, prefix="/api/gold", tags=["新闻资讯"])
app.include_router(predictions.router, prefix="/api/gold", tags=["价格预测"])


@app.get("/")
async def root():
    return {"message": "黄金市场分析系统 API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """增强健康检查 - 检查所有关键依赖服务"""
    from sqlalchemy import text
    from pathlib import Path
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "services": {}
    }
    
    has_error = False
    
    # 1. 检查数据库连接
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["services"]["database"] = {
            "status": "connected",
            "response_time_ms": "<50"
        }
    except Exception as e:
        health_status["services"]["database"] = {
            "status": "disconnected",
            "error": str(e)
        }
        has_error = True
    
    # 2. 检查腾讯财经API（轻量级）
    try:
        import requests
        response = requests.get(
            "https://qt.gtimg.cn/q=hf_GC",
            timeout=3,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        health_status["services"]["tencent_api"] = {
            "status": "available" if response.status_code == 200 else "degraded",
            "response_code": response.status_code
        }
    except Exception as e:
        health_status["services"]["tencent_api"] = {
            "status": "unavailable",
            "error": str(e)
        }
    
    # 3. 检查缓存状态
    try:
        cache_dir = Path(__file__).parent.parent / "cache"
        cache_files = list(cache_dir.glob("*.json"))
        health_status["services"]["cache"] = {
            "status": "ok",
            "files_count": len(cache_files),
            "cache_dir": str(cache_dir)
        }
    except Exception as e:
        health_status["services"]["cache"] = {
            "status": "error",
            "error": str(e)
        }
    
    # 4. 检查定时任务调度器
    try:
        from app.scheduler import scheduler
        health_status["services"]["scheduler"] = {
            "status": "running" if scheduler.running else "stopped",
            "jobs_count": len(scheduler.get_jobs())
        }
    except Exception as e:
        health_status["services"]["scheduler"] = {
            "status": "error",
            "error": str(e)
        }
    
    # 5. 检查AI服务配置
    try:
        health_status["services"]["ai_config"] = {
            "status": "ok",
            "deepseek_configured": bool(settings.DEEPSEEK_API_KEY),
            "zhipu_configured": bool(settings.ZHIPU_API_KEY),
            "llm_provider": settings.LLM_PROVIDER
        }
    except Exception as e:
        health_status["services"]["ai_config"] = {
            "status": "error",
            "error": str(e)
        }
    
    # 根据错误情况设置总体状态
    if has_error:
        health_status["status"] = "degraded"
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)
