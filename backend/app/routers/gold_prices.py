"""黄金价格 API 路由"""
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Query, HTTPException
from anyio import to_thread
from app.database import get_db_context
from app.schemas.gold_price import (
    DailyPriceResponse,
    CorrelationDataResponse,
    GoldStatsResponse
)
from app.services.gold_service import GoldService
from loguru import logger

router = APIRouter()


@router.get("/prices/daily", response_model=List[DailyPriceResponse])
async def get_daily_prices(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = Query(default=100, le=500),
    include_realtime: bool = Query(default=True, description="是否包含实时价格作为最新数据点")
):
    """
    获取日线价格数据
    
    - 历史数据使用当日收盘价
    - 最后一个数据点使用实时价格（如果include_realtime=True）
    """
    if start_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
    else:
        # 默认返回从2025年初到现在的数据
        start = datetime(2025, 1, 1)
    
    if end_date:
        end = datetime.strptime(end_date, "%Y-%m-%d")
    else:
        end = datetime.now()
    
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
            today = datetime.now().strftime("%Y-%m-%d")
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
    
    return result





@router.get("/prices/correlation", response_model=List[CorrelationDataResponse])
async def get_correlation_data(
    limit: int = Query(default=100, le=500),
    include_realtime: bool = Query(default=True, description="是否包含实时价格作为最新数据点")
):
    """
    获取黄金与美元指数相关性数据
    
    - 历史数据使用当日收盘价
    - 最后一个数据点使用实时价格（如果include_realtime=True）
    """
    # 在线程池中执行同步数据库操作
    def fetch_data():
        with get_db_context() as db:
            service = GoldService(db)
            return service.get_correlation_data(limit)
    
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
    if include_realtime and result:
        def fetch_realtime():
            with get_db_context() as db:
                service = GoldService(db)
                gold = service.get_realtime_price_info()
                dollar = service.get_realtime_dollar_index()
                logger.info(f"[Correlation] realtime gold: {gold}")
                logger.info(f"[Correlation] realtime dollar: {dollar}")
                return gold, dollar

        realtime_info, dollar_realtime = await to_thread.run_sync(fetch_realtime)

        logger.info(f"[Correlation] after fetch - realtime_info: {realtime_info}")
        logger.info(f"[Correlation] after fetch - dollar_realtime: {dollar_realtime}")

        if realtime_info:
            today = datetime.now().strftime("%Y-%m-%d")
            current_gold_price = realtime_info.get("price", 0)

            if dollar_realtime:
                current_dollar_index = dollar_realtime.get("price", 0)
                logger.info(f"[Correlation] Using realtime dollar_index: {current_dollar_index}")
            else:
                current_dollar_index = result[-1].dollar_index
                logger.info(f"[Correlation] dollar_realtime is None, using historical: {current_dollar_index}")

            # 检查最后一天是否是今天
            last_date = result[-1].date
            logger.info(f"[Correlation] last_date: {last_date}, today: {today}, equal: {last_date == today}")

            if last_date == today:
                # 更新今天的价格为实时价格
                logger.info(f"[Correlation] Updating today's data")
                result[-1] = CorrelationDataResponse(
                    date=today,
                    gold_price=current_gold_price,
                    dollar_index=current_dollar_index
                )
            else:
                # 添加今天的实时价格
                logger.info(f"[Correlation] Appending new data for today")
                result.append(CorrelationDataResponse(
                    date=today,
                    gold_price=current_gold_price,
                    dollar_index=current_dollar_index
                ))

            logger.info(f"[Correlation] Final result last item: {result[-1]}")
    
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
    def fetch_latest():
        with get_db_context() as db:
            service = GoldService(db)
            return service.get_latest_price()
    
    latest = await to_thread.run_sync(fetch_latest)
    
    if not latest:
        raise HTTPException(status_code=404, detail="暂无数据")
    
    return {
        "date": latest.date.strftime("%Y-%m-%d"),
        "price": latest.close_price,
        "change": latest.change_percent
    }
