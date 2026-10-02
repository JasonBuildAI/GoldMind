"""黄金价格 API 路由"""
from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from anyio import to_thread
from app.utils import timeutil
from app.database import get_db_context
from app.schemas.gold_price import (
    DailyPriceResponse,
    CorrelationDataResponse,
    GoldStatsResponse
)
from app.services import price_basis
from app.services.gold_service import GoldService

router = APIRouter()

def _basis_fields(prefix: str, meta: dict, fallback_source: str) -> dict:
    """把 `price_basis.realtime_basis` 的元数据映射成响应字段（gold_* / dollar_*）。

    没有元数据时按日收盘兜底：调用点可能没拿到实时源（例如美元指数
    只沿用了上一行的历史值），此时它确实是收盘口径。
    """
    return {
        f"{prefix}_basis": meta.get("basis", price_basis.CLOSE),
        f"{prefix}_basis_label": meta.get(
            "basis_label", price_basis.label(price_basis.CLOSE)
        ),
        f"{prefix}_source": meta.get("source") or fallback_source,
    }


def _parse_date(value: str, field: str) -> datetime:
    """把 YYYY-MM-DD 解析成 datetime；格式不对返回 422 而不是 500。

    原实现直接 `datetime.strptime(...)`，非法输入抛 ValueError 一路冒到
    中间件，客户端拿到的是 500 —— 那是服务端错误码，但问题出在请求上。
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"{field} 的格式应为 YYYY-MM-DD，收到 {value!r}",
        )

@router.get("/prices/daily", response_model=List[DailyPriceResponse])
async def get_daily_prices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=500),
    include_realtime: bool = Query(default=True, description="是否包含实时价格作为最新数据点")
):
    """
    获取日线价格数据

    - 历史数据使用当日收盘价
    - 最后一个数据点使用实时价格（如果include_realtime=True）
    - limit 表示**最多返回多少个点**，保留最近的；ge=1 让 0 与负数直接 422
    """
    start = _parse_date(start_date, "start_date") if start_date else datetime(2025, 1, 1)
    end = _parse_date(end_date, "end_date") if end_date else timeutil.now()
    
    # 在线程池中执行同步数据库操作，避免阻塞事件循环
    def fetch_data():
        with get_db_context() as db:
            service = GoldService(db)
            prices = service.get_daily_prices(start, end)
            return [
                {
                    "date": p.date.strftime("%Y-%m-%d"),
                    "price": p.close_price,
                    "volume": p.volume or 0
                }
                for p in prices
            ]
    
    prices_data = await to_thread.run_sync(fetch_data)
    
    # 历史行一律日收盘口径；下面若补实时点，只改被替换 / 追加的那一点。
    result = [
        DailyPriceResponse(
            date=p["date"],
            price=p["price"],
            volume=p["volume"],
            basis=price_basis.CLOSE,
            basis_label=price_basis.label(price_basis.CLOSE),
            source="gold_prices 日线",
            as_of=p["date"],
        )
        for p in prices_data
    ]
    
    # 如果需要实时价格，将最后一个数据点替换为实时价格
    if include_realtime and result:
        def fetch_realtime():
            with get_db_context() as db:
                service = GoldService(db)
                return service.get_realtime_price_info()
        
        realtime_info = await to_thread.run_sync(fetch_realtime)
        if realtime_info:
            today = timeutil.today_str()
            current_price = realtime_info.get("price", 0)
            # 口径由 realtime_price 的 source 决定：真实时源 → 实时报价；
            # 实时源全挂退回库里的收盘 → 日收盘（不许把兜底价说成实时）。
            realtime_meta = price_basis.realtime_basis(realtime_info)
            
            # 检查最后一天是否是今天
            last_date = result[-1].date
            if last_date == today:
                # 更新今天的价格为实时价格
                result[-1] = DailyPriceResponse(
                    date=today,
                    price=current_price,
                    volume=0,
                    **realtime_meta,
                )
            else:
                # 添加今天的实时价格
                result.append(DailyPriceResponse(
                    date=today,
                    price=current_price,
                    volume=0,
                    **realtime_meta,
                ))

    # limit 此前只是被声明和校验，从未真正生效 —— 传 limit=3 照样返回全部数据。
    # 语义定为「最多返回 limit 个点，保留最近的」，所以放在实时点补完之后裁剪，
    # 保证返回条数不会超过 limit。
    if len(result) > limit:
        result = result[-limit:]

    return result

@router.get("/prices/correlation", response_model=List[CorrelationDataResponse])
async def get_correlation_data(
    limit: int = Query(default=100, ge=1, le=500),
    days: int = Query(default=180, ge=1, le=3650, description="只返回最近 N 天的数据"),
    include_realtime: bool = Query(default=True, description="是否包含实时价格作为最新数据点")
):
    """
    获取黄金与美元指数相关性数据

    - 历史数据使用当日收盘价
    - 最后一个数据点使用实时价格（如果include_realtime=True）
    - `days` 是**时间窗**（最近 N 天），`limit` 是**点数上限**，保留最近的
    - 两个都生效：先按时间窗裁，再按点数裁

    注意：`days` 此前**根本没有被声明**，而前端一直在传
    `?days=30` —— FastAPI 会静默忽略未声明的查询参数，所以那个参数
    从来没有生效过，调用方以为拿到 30 天，实际拿到最多 100 个点。
    这与本端点此前修过的 `limit` 是同一类问题（声明了却不用 / 传了却不认）。
    """
    # 在线程池中执行同步数据库操作
    def fetch_data():
        with get_db_context() as db:
            service = GoldService(db)
            return service.get_correlation_data()
    
    correlation_data = await to_thread.run_sync(fetch_data)
    
    result = [
        CorrelationDataResponse(
            date=item["date"],
            gold_price=item["gold_price"],
            dollar_index=item["dollar_index"],
            gold_basis=price_basis.CLOSE,
            gold_basis_label=price_basis.label(price_basis.CLOSE),
            gold_source="gold_prices 日线",
            dollar_basis=price_basis.CLOSE,
            dollar_basis_label=price_basis.label(price_basis.CLOSE),
            dollar_source="dollar_index 日线",
            as_of=item["date"],
        )
        for item in correlation_data
    ]
    
    # 如果需要实时价格，将最后一个数据点替换为实时价格
    #
    # 这里原本有 10 条 logger.info 的调试输出（"[Correlation] realtime gold: …"
    # 之类），每次请求都会刷一屏，属于开发期留下的脚手架。
    # 数据源失败本身已由 realtime_price 模块按级别记好，不需要在这里重复。
    if include_realtime and result:
        def fetch_realtime():
            with get_db_context() as db:
                service = GoldService(db)
                gold = service.get_realtime_price_info()
                dollar = service.get_realtime_dollar_index()
                return gold, dollar

        realtime_info, dollar_realtime = await to_thread.run_sync(fetch_realtime)

        if realtime_info:
            today = timeutil.today_str()
            current_gold_price = realtime_info.get("price", 0)
            gold_meta = price_basis.realtime_basis(realtime_info)

            if dollar_realtime:
                current_dollar_index = dollar_realtime.get("price", 0)
                # 这个接口只在真取到上游数据时才返回，所以显式按实时报价标注。
                dollar_meta = price_basis.realtime_basis(dollar_realtime, force_realtime=True)
            else:
                # 拿不到实时美元指数时沿用历史序列的最后一个值
                current_dollar_index = result[-1].dollar_index
                dollar_meta = {}

            # 检查最后一天是否是今天
            last_date = result[-1].date

            if last_date == today:
                # 更新今天的价格为实时价格
                result[-1] = CorrelationDataResponse(
                    date=today,
                    gold_price=current_gold_price,
                    dollar_index=current_dollar_index,
                    **_basis_fields("gold", gold_meta, "gold_prices 日线"),
                    **_basis_fields("dollar", dollar_meta, "dollar_index 日线"),
                    as_of=today,
                )
            else:
                # 添加今天的实时价格
                result.append(CorrelationDataResponse(
                    date=today,
                    gold_price=current_gold_price,
                    dollar_index=current_dollar_index,
                    **_basis_fields("gold", gold_meta, "gold_prices 日线"),
                    **_basis_fields("dollar", dollar_meta, "dollar_index 日线"),
                    as_of=today,
                ))

    # 先按**时间窗**裁（days 此前完全没被声明，前端传了也没用）。
    # `days=3` 表示「今天在内的最近 3 天」，所以减的是 days-1：
    # 减 days 会连边界那天一起算进来，实际返回 4 天。
    cutoff = timeutil.today() - timedelta(days=days - 1)
    result = [item for item in result if date.fromisoformat(item.date) >= cutoff]

    # 再按**点数**裁。limit 此前也完全没生效
    #（service.get_correlation_data 收了参数却从不使用），传 limit=4 照样返回全部点。
    if len(result) > limit:
        result = result[-limit:]

    return result

@router.get("/dollar-realtime")
async def get_dollar_realtime():
    """获取实时美元指数（数据源：新浪财经 ICE 美元指数 DINIW；带 30 秒缓存）。"""
    def fetch_realtime():
        with get_db_context() as db:
            service = GoldService(db)
            return service.get_realtime_dollar_index()

    dollar_data = await to_thread.run_sync(fetch_realtime)

    if not dollar_data:
        raise HTTPException(status_code=503, detail="无法获取实时美元指数")

    return dollar_data

@router.get("/stats", response_model=GoldStatsResponse)
async def get_gold_stats():
    # 在线程池中执行同步数据库操作
    """获取滚动窗口（默认近 12 个月）的金价统计（当前价、涨跌幅、高低振幅等）。"""
    def fetch_stats():
        with get_db_context() as db:
            service = GoldService(db)
            return service.get_statistics()

    stats = await to_thread.run_sync(fetch_stats)

    if not stats:
        raise HTTPException(status_code=404, detail="暂无数据")

    # 口径不靠 is_realtime 反推：service 已经知道这一价是实时还是收盘。
    basis = price_basis.REALTIME if stats.get("is_realtime") else price_basis.CLOSE
    return GoldStatsResponse(
        **stats,
        price_basis=basis,
        price_basis_label=price_basis.label(basis),
    )

@router.get("/latest")
async def get_latest_price():
    """获取数据库里最新一条金价。"""
    def fetch_latest():
        with get_db_context() as db:
            service = GoldService(db)
            latest = service.get_latest_price()
            if not latest:
                return None
            # 必须在会话仍然打开时把字段取出来。
            # 原实现直接 return ORM 对象，等到 with 块退出、会话关闭之后
            # 再访问 latest.date 就抛 DetachedInstanceError ——
            # 结果是「数据库里有数据时这个接口必然 500」，空库反而正常。
            return {
                "date": latest.date.strftime("%Y-%m-%d"),
                "price": latest.close_price,
                "change": latest.change_percent,
                # 这里读的就是库里的日收盘，口径固定是 close。
                "basis": price_basis.CLOSE,
                "basis_label": price_basis.label(price_basis.CLOSE),
                "source": "gold_prices 日线",
                "as_of": latest.date.strftime("%Y-%m-%d"),
            }

    latest = await to_thread.run_sync(fetch_latest)

    if not latest:
        raise HTTPException(status_code=404, detail="暂无数据")

    return latest
