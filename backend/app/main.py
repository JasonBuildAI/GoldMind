"""FastAPI 主应用入口"""
import os
import sys
import time
import asyncio

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.utils import timeutil
from app.config import settings
from app.database import engine, Base
from app.routers import gold_prices, analysis, news, predictions, quant
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

# --------------------------------------------------------------------------- #
# 启动引导（2.0.2）
# --------------------------------------------------------------------------- #
# 「填好 backend/.env → 启动」是唯一人工步骤：迁移在 lifespan 里自动应用，
# 结果暴露在 /health 的 bootstrap 字段。失败不阻塞服务 —— 下轮启动自动重试。
_bootstrap_state: dict = {
    "status": "pending" if settings.AUTO_BOOTSTRAP else "disabled",
    "enabled": bool(settings.AUTO_BOOTSTRAP),
    "migrations": None,
    "error": None,
}


def _run_bootstrap() -> None:
    """应用迁移注册表；异常不外抛 —— 引导失败不该拖垮整个服务。"""
    from app import bootstrap

    try:
        results = bootstrap.run_migrations(engine)
        failed = next((item for item in results if item["status"] == "failed"), None)
        _bootstrap_state.update(
            status="failed" if failed else "done",
            migrations=bootstrap.registry_snapshot(engine),
            error=failed.get("error") if failed else None,
            at=timeutil.now_iso(),
        )
        logger.info(f"[引导] 迁移完成：{_bootstrap_state['migrations']}")
    except Exception as exc:  # noqa: BLE001 —— 任何引导异常都不该阻止服务启动
        _bootstrap_state.update(
            status="failed", error=f"{type(exc).__name__}: {exc}", at=timeutil.now_iso()
        )
        logger.error(f"[引导] 迁移阶段异常：{exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("启动黄金市场分析系统...")
    
    Base.metadata.create_all(bind=engine)
    # 启动自检：create_all 只建「模型已经被导入」的表；漏建任何一张，
    # 相关接口都会在运行时变成 1146 缺表错误。这里把它在启动时就点名。
    missing_tables = _missing_metadata_tables()
    if missing_tables:
        logger.error(
            f"[启动自检] 数据库缺少 {len(missing_tables)} 张表："
            f"{'、'.join(missing_tables)}。{_MISSING_SCHEMA_HINT}"
        )
    else:
        logger.info("数据库表创建完成")

    if settings.AUTO_BOOTSTRAP:
        _run_bootstrap()

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
    version="2.0.1",
    lifespan=lifespan
)


# --------------------------------------------------------------------------- #
# 缺表 → 503（而不是裸 500）
# --------------------------------------------------------------------------- #
# 2026-10-02 的真实故障：开发库的表被一次误跑的测试删光，此后每个读库接口都是
# `ProgrammingError(1146, "Table ... doesn't exist")` → 裸 500，页面上整片
# 「暂不可用」—— 而且刷新永远不会好，因为这不是瞬态错误。缺表不是程序崩了，
# 是数据库没初始化：按 503（暂时不可用）返回，并把「怎么修」写进 detail，
# 前端可以原样展示给用户/运维。
_MISSING_SCHEMA_HINT = (
    "数据表缺失：默认开启的启动引导（AUTO_BOOTSTRAP）会自动建表；"
    "若反复出现，请查看后端日志与 /health 的 bootstrap 字段排查。"
    "旧版本或关闭了引导时，也可以在 backend/ 目录运行 `python init_db.py` 手工建表。"
)

# MySQL / MariaDB 错误码：1146 表不存在、1049 库不存在。
# SQLite 没有错误码，靠消息里的 "no such table" / "unknown database" 识别。
_MISSING_SCHEMA_MYSQL_CODES = frozenset({1049, 1146})


def _is_missing_schema_error(exc: Exception) -> bool:
    """只认「缺库/缺表」，别把列名写错之类的 SQL 错误也翻译成「去建表」。"""
    orig = getattr(exc, "orig", None) or exc
    args = getattr(orig, "args", ()) or ()
    if args and args[0] in _MISSING_SCHEMA_MYSQL_CODES:
        return True
    message = str(orig).lower()
    if "no such table" in message or "unknown database" in message:
        return True
    # PostgreSQL: relation "x" does not exist（列不存在的措辞是 column ... does not exist）
    return "relation" in message and "does not exist" in message


def _missing_metadata_tables() -> list[str]:
    """metadata 里登记了、但库里查不到的表（启动自检用，不硬编码表名）。"""
    from sqlalchemy import inspect

    existing = set(inspect(engine).get_table_names())
    return sorted(name for name in Base.metadata.tables if name not in existing)


async def _missing_schema_handler(request: Request, exc: Exception) -> JSONResponse:
    if not _is_missing_schema_error(exc):
        # 其余 SQL 错误（如 Unknown column）仍然走默认 500：它们不是
        # 「跑一次 init_db.py 就好」的问题，不能被这条指引掩盖。
        raise exc
    logger.error(f"[数据库] {request.method} {request.url.path} 命中缺表/缺库错误：{exc}")
    return JSONResponse(
        status_code=503,
        content={"error": "database_not_initialized", "detail": _MISSING_SCHEMA_HINT},
    )


app.add_exception_handler(ProgrammingError, _missing_schema_handler)
app.add_exception_handler(OperationalError, _missing_schema_handler)

# --------------------------------------------------------------------------- #
# 限流
# --------------------------------------------------------------------------- #
# 普通接口与「会触发付费 LLM 调用」的接口分别限流：后者一次调用就要花钱，
# 用同一个上限等于给了刷额度的空间。
_general_limiter = SlidingWindowRateLimiter(settings.RATE_LIMIT_PER_MINUTE)
_ai_limiter = SlidingWindowRateLimiter(settings.RATE_LIMIT_AI_PER_MINUTE)

# 健康检查不参与限流：它是给探针用的，被限流会被误判成服务不可用
_RATE_LIMIT_EXEMPT_PATHS = frozenset({"/health"})

# 上游探测结果的短缓存（见 health_check 里的说明）
_UPSTREAM_PROBE_TTL = 60.0
_upstream_probe: dict = {"at": 0.0, "payload": None}

# 会真实调用 LLM（消耗额度）的请求，使用更严的上限。
#
# 判据有两类，缺一不可：
#   1. 路径以 `/refresh` 结尾（POST 强制刷新）
#   2. 查询串里带 `refresh=true`（GET 同样会走 use_cache=False → 真实调 LLM）
#
# 只按第 1 条判断会漏掉第 2 条：`GET .../bullish-factors-ai?refresh=true`
# 和 POST /refresh 一样花钱，却只受通用上限约束 ——
# 也就是把 6 次/分 的额度放大成 60 次/分。
_AI_PATH_SUFFIXES = ("/refresh",)
_AI_QUERY_FLAGS = ("refresh=true", "refresh=1")

def _is_ai_path(path: str, query: str = "") -> bool:
    if path.endswith(_AI_PATH_SUFFIXES):
        return True
    # 只对 AI 分析接口看查询串，普通接口带个同名参数不该被误伤
    if "-ai" not in path:
        return False
    lowered = (query or "").lower()
    return any(flag in lowered for flag in _AI_QUERY_FLAGS)

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
        limiter = (
            _ai_limiter if _is_ai_path(path, request.url.query) else _general_limiter
        )

        allowed, retry_after = limiter.allow(client_ip)
        if not allowed:
            logger.warning(f"[限流] {client_ip} 触发 {path} 的请求上限")
            return JSONResponse(
                status_code=429,
                content={
                    "error": "请求过于频繁，请稍后再试",
                    "retry_after": retry_after,
                },
                # 标准头。客户端（含浏览器、curl、反代）都认这个；
                # 只放在 body 里的话，通用工具看不到「还要等多久」。
                headers={"Retry-After": str(retry_after)},
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
app.include_router(quant.router, prefix="/api/gold", tags=["量化预测"])

@app.get("/")
async def root():
    """服务信息与文档入口。"""
    return {"message": "黄金市场分析系统 API", "version": "2.0.1", "docs": "/docs"}

@app.get("/health")
async def health_check():
    """增强健康检查 - 检查所有关键依赖服务"""
    from sqlalchemy import text
    
    health_status = {
        "status": "healthy",
        "timestamp": timeutil.now_iso(),
        "version": "2.0.1",
        "bootstrap": dict(_bootstrap_state),
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
    #
    # 结果缓存 60 秒。原因：/health 是**公开**且**不限流**的接口（负载均衡需要它
    # 随时可调），而这里每次都会同步请求一次上游 —— 也就是说任何人都能让服务器
    # 按请求量去打腾讯，同时把自己的 /health 拖慢到 3 秒。
    # 实测：20 次调用 = 20 次出网（1:1 放大）。
    # 缓存之后出网次数被钉在「每分钟一次」，而探测结果对运维依然足够新鲜。
    try:
        now = time.monotonic()
        cached = _upstream_probe.get("payload")
        if cached is not None and now - _upstream_probe.get("at", 0.0) < _UPSTREAM_PROBE_TTL:
            health_status["services"]["tencent_api"] = cached
        else:
            import requests
            response = requests.get(
                "https://qt.gtimg.cn/q=hf_GC",
                timeout=3,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            payload = {
                "status": "available" if response.status_code == 200 else "degraded",
                "response_code": response.status_code,
            }
            _upstream_probe.update(at=now, payload=payload)
            health_status["services"]["tencent_api"] = payload
    except Exception as e:
        logger.error(f"[健康检查] 腾讯行情接口不可用: {e}")
        payload = {
            "status": "unavailable",
            "error_type": type(e).__name__,
        }
        # 失败也缓存：否则上游挂了的时候，每次 /health 都要等满 3 秒超时
        _upstream_probe.update(at=time.monotonic(), payload=payload)
        health_status["services"]["tencent_api"] = payload
    
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
