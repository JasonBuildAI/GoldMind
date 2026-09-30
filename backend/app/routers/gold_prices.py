"""黄金价格 API 路由"""
from datetime import datetime, timedelta
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
from app.services.gold_service import GoldService

router = APIRouter()


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
    
    result = [
        DailyPriceResponse(
            date=p["date"],
            price=p["price"],
            volume=p["volume"]
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
            
            # 检查最后一天是否是今天
            last_date = result[-1].date
            if last_date == today:
                # 更新今天的价格为实时价格
                result[-1] = DailyPriceResponse(
                    date=today,
                    price=current_price,
                    volume=0
                )
            else:
                # 添加今天的实时价格
                result.append(DailyPriceResponse(
                    date=today,
                    price=current_price,
                    volume=0
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
    include_realtime: bool = Query(default=True, description="是否包含实时价格作为最新数据点")
):
    """
    获取黄金与美元指数相关性数据

    - 历史数据使用当日收盘价
    - 最后一个数据点使用实时价格（如果include_realtime=True）
    - limit 表示**最多返回多少个点**，保留最近的
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
            dollar_index=item["dollar_index"]
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

            if dollar_realtime:
                current_dollar_index = dollar_realtime.get("price", 0)
            else:
                # 拿不到实时美元指数时沿用历史序列的最后一个值
                current_dollar_index = result[-1].dollar_index

            # 检查最后一天是否是今天
            last_date = result[-1].date

            if last_date == today:
                # 更新今天的价格为实时价格
                result[-1] = CorrelationDataResponse(
                    date=today,
                    gold_price=current_gold_price,
                    dollar_index=current_dollar_index
                )
            else:
                # 添加今天的实时价格
                result.append(CorrelationDataResponse(
                    date=today,
                    gold_price=current_gold_price,
                    dollar_index=current_dollar_index
                ))

    # 与 daily 一致：limit 此前完全没生效（service.get_correlation_data 收了参数
    # 却从不使用），传 limit=4 照样返回全部点。
    if len(result) > limit:
        result = result[-limit:]

    return result


@router.get("/dollar-realtime")
async def get_dollar_realtime():
    """获取实时美元指数（直接调用东方财富API）"""
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
    """获取 2025 年至今的金价统计（当前价、涨跌幅、波动区间等）。"""
    def fetch_stats():
        with get_db_context() as db:
            service = GoldService(db)
            return service.get_statistics()

    stats = await to_thread.run_sync(fetch_stats)

    if not stats:
        raise HTTPException(status_code=404, detail="暂无数据")

    return GoldStatsResponse(**stats)


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
            }

    latest = await to_thread.run_sync(fetch_latest)

    if not latest:
        raise HTTPException(status_code=404, detail="暂无数据")

    return latest
