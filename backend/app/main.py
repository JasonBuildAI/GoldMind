"""FastAPI 主应用入口"""
import os
import sys
import asyncio
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.config import settings
from app.database import engine, Base
from app.routers import gold_prices, analysis, news, predictions
from app.scheduler import init_scheduler, shutdown_scheduler
from app.utils.rate_limit import SlidingWindowRateLimiter


# --------------------------------------------------------------------------- #
# 日志
# --------------------------------------------------------------------------- #
# loguru 的默认 handler 固定 DEBUG 级别、格式也写死。这里按 LOG_LEVEL 重新配置，
# 让 .env 里那一项真正生效（此前没有任何代码读它）。
# diagnose=False：异常回溯里不带局部变量值，避免把密钥之类的东西打进日志。
def _configure_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level=(settings.LOG_LEVEL or "INFO").upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        ),
        backtrace=False,
        diagnose=False,
    )


_configure_logging()


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

# --------------------------------------------------------------------------- #
# 限流
# --------------------------------------------------------------------------- #
# 普通接口与「会触发付费 LLM 调用」的接口分别限流：后者一次调用就要花钱，
# 用同一个上限等于给了刷额度的空间。
_general_limiter = SlidingWindowRateLimiter(settings.RATE_LIMIT_PER_MINUTE)
_ai_limiter = SlidingWindowRateLimiter(settings.RATE_LIMIT_AI_PER_MINUTE)

# 健康检查不参与限流：它是给探针用的，被限流会被误判成服务不可用
_RATE_LIMIT_EXEMPT_PATHS = frozenset({"/health"})

# 这些后缀的路径会真实调用 LLM（消耗额度），使用更严的上限
_AI_PATH_SUFFIXES = ("/refresh",)


def _is_ai_path(path: str) -> bool:
    return path.endswith(_AI_PATH_SUFFIXES)


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """按客户端 IP 限流。

    与原实现的区别：

    - 状态不再挂在中间件函数对象上，且过期键会被清理，内存不会无界增长；
    - 健康检查不限流；
    - 会触发付费 LLM 调用的接口使用更严的上限。
    """
    path = request.url.path

    if path not in _RATE_LIMIT_EXEMPT_PATHS:
        client_ip = request.client.host if request.client else "unknown"
        limiter = _ai_limiter if _is_ai_path(path) else _general_limiter

        allowed, retry_after = limiter.allow(client_ip)
        if not allowed:
            logger.warning(f"[限流] {client_ip} 触发 {path} 的请求上限")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "请求过于频繁，请稍后再试",
                    "retry_after": retry_after,
                },
            )

    return await call_next(request)


# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #
_cors_origins = [o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # 通配来源 + 允许凭证 = 任何站点都能带着用户凭证调用本 API。
    # 这里做兜底：来源里出现 "*" 时强制关闭凭证。
    allow_credentials="*" not in _cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(gold_prices.router, prefix="/api/gold", tags=["黄金价格"])
app.include_router(analysis.router, prefix="/api/gold", tags=["市场分析"])
app.include_router(news.router, prefix="/api/gold", tags=["新闻资讯"])
app.include_router(predictions.router, prefix="/api/gold", tags=["价格预测"])


@app.get("/")
async def root():
    """服务信息与文档入口。"""
    return {"message": "黄金市场分析系统 API", "version": "1.0.0", "docs": "/docs"}


@app.get("/health")
async def health_check():
    """增强健康检查 - 检查所有关键依赖服务"""
    from sqlalchemy import text
    
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
        # 只回异常**类型**，不回异常文本。
        # /health 是公开接口（本项目无鉴权），而数据库异常的文本里会带
        # 主机、用户名、驱动细节 —— 例如
        # "Access denied for user 'root'@'localhost'"。
        # 完整信息写进服务端日志，运维照样能查。
        logger.error(f"[健康检查] 数据库连接失败: {e}")
        health_status["services"]["database"] = {
            "status": "disconnected",
            "error_type": type(e).__name__,
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
        logger.error(f"[健康检查] 腾讯行情接口不可用: {e}")
        health_status["services"]["tencent_api"] = {
            "status": "unavailable",
            "error_type": type(e).__name__,
        }
    
    # 3. 检查缓存状态
    try:
        # 用 cache_manager 自己的状态查询，而不是在这里重新拼路径。
        # 原实现写死 `Path(__file__).parent.parent / "cache"`，在 CACHE_DIR
        # 被配置成其他目录时会报告一个根本没在用的目录。
        from app.services.cache_manager import get_cache_status

        cache_status = get_cache_status()
        # 文件缓存被关掉时不能报 "ok"：多进程共享没了，是降级状态。
        # 把原因（file_cache_enabled）一并暴露，运维才知道 files_count 为什么一直是 0。
        file_cache_ok = cache_status.get("file_cache_enabled", True)
        health_status["services"]["cache"] = {
            "status": "ok" if file_cache_ok else "degraded",
            "files_count": len(cache_status["file_cache_keys"]),
            "memory_keys": cache_status["memory_cache_keys"],
            # 只给目录名：完整路径会暴露服务器目录结构，而这是公开接口。
            # 需要完整路径时看服务端日志。
            "cache_dir_name": os.path.basename(cache_status["cache_dir"]),
            "file_cache_enabled": file_cache_ok,
        }
    except Exception as e:
        logger.error(f"[健康检查] 缓存状态读取失败: {e}")
        health_status["services"]["cache"] = {
            "status": "error",
            "error_type": type(e).__name__,
        }
    
    # 4. 检查定时任务调度器
    try:
        from app.scheduler import scheduler
        health_status["services"]["scheduler"] = {
            "status": "running" if scheduler.running else "stopped",
            "jobs_count": len(scheduler.get_jobs())
        }
    except Exception as e:
        logger.error(f"[健康检查] 调度器状态读取失败: {e}")
        health_status["services"]["scheduler"] = {
            "status": "error",
            "error_type": type(e).__name__,
        }
    
    # 5. 检查AI服务配置
    try:
        from app.services.llm_provider import describe as describe_llm

        llm_info = describe_llm()
        health_status["services"]["ai_config"] = {
            "status": "ok" if llm_info["configured"] else "unconfigured",
            **llm_info,
        }
    except Exception as e:
        logger.error(f"[健康检查] AI 配置读取失败: {e}")
        health_status["services"]["ai_config"] = {
            "status": "error",
            "error_type": type(e).__name__,
        }
    
    # 根据错误情况设置总体状态
    if has_error:
        health_status["status"] = "degraded"
    
    return health_status


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.APP_HOST, port=settings.APP_PORT, reload=settings.DEBUG)
