"""定时任务调度器"""
from datetime import datetime, date
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger
from app.config import settings

scheduler = AsyncIOScheduler(timezone=settings.SCHEDULER_TIMEZONE)


def init_scheduler():
    logger.info(f"[调度器] SCHEDULER_ENABLED={settings.SCHEDULER_ENABLED}, 时区={settings.SCHEDULER_TIMEZONE}")
    
    if not settings.SCHEDULER_ENABLED:
        logger.info("[调度器] 定时任务已禁用，跳过初始化")
        return
    
    try:
        scheduler.add_job(
            update_prices_job,
            CronTrigger.from_crontab(settings.UPDATE_PRICE_CRON),
            id='update_prices',
            name='更新黄金价格数据',
            replace_existing=True
        )
        logger.info(f"[调度器] 已添加任务: update_prices ({settings.UPDATE_PRICE_CRON})")
        
        # 添加美元指数定时更新任务（与黄金价格同时更新）
        scheduler.add_job(
            update_dollar_index_job,
            CronTrigger.from_crontab(settings.UPDATE_PRICE_CRON),
            id='update_dollar_index',
            name='更新美元指数数据',
            replace_existing=True
        )
        logger.info(f"[调度器] 已添加任务: update_dollar_index")
        
        scheduler.add_job(
            update_news_job,
            CronTrigger.from_crontab(settings.UPDATE_NEWS_CRON),
            id='update_news',
            name='更新新闻资讯',
            replace_existing=True
        )
        logger.info(f"[调度器] 已添加任务: update_news ({settings.UPDATE_NEWS_CRON})")
        
        # 添加AI分析后台更新任务（偶数整点执行）
        # 包含：看涨因子、看跌因子、机构预测、投资建议
        scheduler.add_job(
            update_ai_analysis_job,
            CronTrigger.from_crontab(settings.UPDATE_AI_ANALYSIS_CRON),
            id='update_ai_analysis',
            name='后台更新AI分析（看涨/看跌/机构/建议）',
            replace_existing=True
        )
        logger.info(f"[调度器] 已添加任务: update_ai_analysis ({settings.UPDATE_AI_ANALYSIS_CRON})")
        
        scheduler.start()
        logger.info(f"[调度器] 定时任务调度器已启动，当前时间: {datetime.now()}")
        
        # 打印所有任务信息
        jobs = scheduler.get_jobs()
        logger.info(f"[调度器] 当前共有 {len(jobs)} 个定时任务:")
        for job in jobs:
            logger.info(f"  - {job.id}: {job.name}, 下次执行: {job.next_run_time}")
            
    except Exception as e:
        logger.error(f"[调度器] 初始化失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("定时任务调度器已关闭")


def is_trading_day(date=None) -> bool:
    """
    判断是否为交易日（周一至周五，排除周末）
    
    Args:
        date: 日期，默认为今天
    
    Returns:
        True如果是交易日，False如果是周末
    """
    from datetime import datetime
    if date is None:
        date = datetime.now().date()
    
    # 0=周一, 6=周日
    weekday = date.weekday()
    return weekday < 5  # 周一到周五是交易日


async def calculate_period_statistics(db, today: date) -> dict:
    """
    计算期间统计信息（期间最高、期间最低、波动区间）
    
    Args:
        db: 数据库会话
        today: 当前日期
    
    Returns:
        包含期间统计信息的字典
    """
    from sqlalchemy import func
    from app.models.gold_price import GoldPrice
    
    # 查询所有历史数据的最高最低价
    result = db.query(
        func.max(GoldPrice.high_price).label('period_high'),
        func.min(GoldPrice.low_price).label('period_low')
    ).filter(
        GoldPrice.date <= today
    ).first()
    
    period_high = result.period_high or 0
    period_low = result.period_low or 0
    
    # 计算波动区间（百分比）
    volatility_range = 0
    if period_low > 0:
        volatility_range = ((period_high - period_low) / period_low) * 100
    
    # 获取期间最高和最低对应的日期
    high_date_record = db.query(GoldPrice).filter(
        GoldPrice.high_price == period_high
    ).order_by(GoldPrice.date.desc()).first()
    
    low_date_record = db.query(GoldPrice).filter(
        GoldPrice.low_price == period_low
    ).order_by(GoldPrice.date.desc()).first()
    
    stats = {
        'period_high': period_high,
        'period_high_date': high_date_record.date if high_date_record else None,
        'period_low': period_low,
        'period_low_date': low_date_record.date if low_date_record else None,
        'volatility_range': round(volatility_range, 2)
    }
    
    return stats


async def update_prices_job():
    """
    更新黄金价格数据 - 每日收盘后获取当日完整OHLC数据
    
    伦敦金交易时间（北京时间）：
    - 夏令时：06:00 - 05:00（次日）
    - 冬令时：07:00 - 06:00（次日）
    
    每日收盘时间约为北京时间凌晨5-6点
    我们在每天早上6:30获取前一日收盘价
    
    功能：
    1. 判断是否为交易日（周末跳过）
    2. 获取当日完整OHLC数据（开盘价、最高价、最低价、收盘价）
    3. 保存到数据库，如果已有记录则更新
    4. 重新计算期间统计（期间最高、期间最低、波动区间）
    """
    from datetime import datetime, date
    
    today = datetime.now().date()
    
    # 1. 检查是否为交易日
    if not is_trading_day(today):
        logger.info(f"{today} 是周末，黄金市场休市，跳过数据更新")
        return
    
    logger.info(f"开始更新黄金价格数据 - 交易日: {today}")
    
    try:
        from app.services.gold_price_service import get_london_gold_price
        from app.services.gold_service import GoldService
        from app.database import SessionLocal
        from app.models.gold_price import GoldPrice
        
        # 2. 获取伦敦金实时价格（包含完整OHLC数据）
        realtime_data = get_london_gold_price()
        
        if not realtime_data:
            logger.warning("未能获取实时金价，尝试使用备用数据源...")
            # 这里可以添加备用数据源逻辑
            return
        
        # 3. 提取完整OHLC数据
        price = realtime_data.get('price', 0)
        open_price = realtime_data.get('open', price)
        high_price = realtime_data.get('high', price)
        low_price = realtime_data.get('low', price)
        prev_close = realtime_data.get('previous_close', price)
        change_percent = realtime_data.get('change_percent', 0)
        source_name = realtime_data.get('source_name', '未知来源')
        
        logger.info(f"获取到伦敦金数据:")
        logger.info(f"  来源: {source_name}")
        logger.info(f"  开盘: ${open_price:.2f}")
        logger.info(f"  最高: ${high_price:.2f}")
        logger.info(f"  最低: ${low_price:.2f}")
        logger.info(f"  收盘: ${price:.2f}")
        logger.info(f"  涨跌: {change_percent:.2f}%")
        
        # 4. 保存到数据库
        db = SessionLocal()
        try:
            # 检查今天是否已有记录
            existing = db.query(GoldPrice).filter(GoldPrice.date == today).first()
            
            if existing:
                # 更新今天的记录（保留开盘价，更新最高/最低/收盘价）
                existing.open_price = open_price if open_price else existing.open_price
                existing.high_price = max(existing.high_price or high_price, high_price) if high_price else existing.high_price
                existing.low_price = min(existing.low_price or low_price, low_price) if low_price else existing.low_price
                existing.close_price = price
                existing.change_percent = change_percent
                existing.updated_at = datetime.now()
                logger.info(f"更新 {today} 的金价记录")
            else:
                # 创建新记录
                gold_price = GoldPrice(
                    date=today,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=price,
                    volume=0,  # 实时数据通常没有成交量
                    change_percent=change_percent
                )
                db.add(gold_price)
                logger.info(f"创建 {today} 的新金价记录")
            
            db.commit()
            logger.info(f"✅ 金价数据已成功保存到数据库: OHLC (${open_price:.2f}, ${high_price:.2f}, ${low_price:.2f}, ${price:.2f})")
            
            # 5. 重新计算期间统计
            logger.info("开始计算期间统计信息...")
            stats = await calculate_period_statistics(db, today)
            
            logger.info("=" * 60)
            logger.info("📊 期间统计信息（每日更新）")
            logger.info("=" * 60)
            logger.info(f"  期间最高: ${stats['period_high']:.2f} ({stats['period_high_date']})")
            logger.info(f"  期间最低: ${stats['period_low']:.2f} ({stats['period_low_date']})")
            logger.info(f"  波动区间: {stats['volatility_range']:.2f}%")
            logger.info("=" * 60)
            
            # 保存统计信息到缓存文件，供前端使用
            from pathlib import Path
            import json
            
            cache_dir = Path(__file__).parent.parent / "cache"
            cache_dir.mkdir(exist_ok=True)
            stats_file = cache_dir / "period_statistics.json"
            
            stats_data = {
                'period_high': stats['period_high'],
                'period_high_date': stats['period_high_date'].isoformat() if stats['period_high_date'] else None,
                'period_low': stats['period_low'],
                'period_low_date': stats['period_low_date'].isoformat() if stats['period_low_date'] else None,
                'volatility_range': stats['volatility_range'],
                'updated_at': datetime.now().isoformat()
            }
            
            with open(stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ 期间统计信息已保存到缓存: {stats_file}")
            
        finally:
            db.close()
                
    except Exception as e:
        logger.error(f"❌ 价格数据更新失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def update_news_job():
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
            
            logger.info(f"新闻数据更新完成，共{len(news_list)}条")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"新闻数据更新失败: {e}")


async def update_ai_analysis_job():
    """后台更新AI分析（看涨因子、看跌因子、机构预测、投资建议）- 异步执行不阻塞调度器"""
    logger.info("开始后台更新AI分析...")
    
    # 使用后台线程执行AI分析，不阻塞主调度器
    import asyncio
    loop = asyncio.get_event_loop()
    
    try:
        # 在线程池中执行同步的AI分析任务
        await loop.run_in_executor(None, _run_ai_analysis_sync)
        logger.info("后台AI分析任务已提交到线程池")
    except Exception as e:
        logger.error(f"提交AI分析任务失败: {e}")

def _run_ai_analysis_sync():
    """在线程池中同步执行AI分析（避免阻塞主事件循环）"""
    import threading
    logger.info(f"[AI分析线程] 启动，线程ID: {threading.current_thread().ident}")
    
    try:
        from app.database import SessionLocal
        from app.services.bullish_factor_service import BullishFactorService
        from app.services.bearish_factor_service import BearishFactorService
        from app.services.institution_prediction_service import InstitutionPredictionService
        from app.services.investment_advice_service import InvestmentAdviceService
        
        db = SessionLocal()
        try:
            # 1. 更新看涨因子
            logger.info("[AI分析线程] 更新看涨因子...")
            bullish_service = BullishFactorService(db)
            bullish_service.refresh_analysis_sync()
            logger.info("[AI分析线程] 看涨因子更新完成")
            
            # 2. 更新看跌因子
            logger.info("[AI分析线程] 更新看跌因子...")
            bearish_service = BearishFactorService(db)
            bearish_service.refresh_analysis_sync()
            logger.info("[AI分析线程] 看跌因子更新完成")
            
            # 3. 更新机构预测
            logger.info("[AI分析线程] 更新机构预测...")
            institution_service = InstitutionPredictionService(db)
            institution_service.refresh_analysis_sync()
            logger.info("[AI分析线程] 机构预测更新完成")
            
            # 4. 更新投资建议
            logger.info("[AI分析线程] 更新投资建议...")
            advice_service = InvestmentAdviceService(db)
            advice_service.refresh_analysis_sync()
            logger.info("[AI分析线程] 投资建议更新完成")
            
            logger.info("[AI分析线程] 全部AI分析更新完成")
            
        finally:
            db.close()
    except Exception as e:
        logger.error(f"[AI分析线程] 执行失败: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def update_dollar_index_job():
    """
    更新美元指数数据 - 每日收盘后获取当日完整OHLC数据
    
    与黄金价格更新同步执行，确保数据一致性
    """
    from datetime import datetime, date
    
    today = datetime.now().date()
    
    # 1. 检查是否为交易日
    if not is_trading_day(today):
        logger.info(f"{today} 是周末，美元指数市场休市，跳过数据更新")
        return
    
    logger.info(f"开始更新美元指数数据 - 交易日: {today}")
    
    try:
        from app.services.gold_service import GoldService
        from app.database import SessionLocal
        from app.models.gold_price import DollarIndex
        
        # 2. 获取实时美元指数（包含完整OHLC数据）
        db = SessionLocal()
        try:
            service = GoldService(db)
            dollar_data = service.get_realtime_dollar_index()
            
            if not dollar_data:
                logger.warning("未能获取实时美元指数数据")
                return
            
            # 3. 提取数据
            price = dollar_data.get('price', 0)
            prev_close = dollar_data.get('previous_close', price)
            
            # 腾讯财经API返回的数据格式中，没有单独的OHLC，使用价格作为近似
            # 实际应用中可能需要更专业的数据源
            open_price = prev_close  # 使用昨收作为开盘近似
            high_price = max(price, prev_close)  # 使用最高价近似
            low_price = min(price, prev_close)  # 使用最低价近似
            
            logger.info(f"获取到美元指数数据:")
            logger.info(f"  收盘: {price:.2f}")
            logger.info(f"  昨收: {prev_close:.2f}")
            
            # 4. 保存到数据库
            existing = db.query(DollarIndex).filter(DollarIndex.date == today).first()
            
            if existing:
                # 更新今天的记录
                existing.open_price = open_price
                existing.high_price = max(existing.high_price or high_price, high_price)
                existing.low_price = min(existing.low_price or low_price, low_price)
                existing.close_price = price
                existing.updated_at = datetime.now()
                logger.info(f"更新 {today} 的美元指数记录")
            else:
                # 创建新记录
                dollar_index = DollarIndex(
                    date=today,
                    open_price=open_price,
                    high_price=high_price,
                    low_price=low_price,
                    close_price=price
                )
                db.add(dollar_index)
                logger.info(f"创建 {today} 的美元指数新记录")
            
            db.commit()
            logger.info(f"✅ 美元指数数据已成功保存到数据库: {price:.2f}")
            
        finally:
            db.close()
                
    except Exception as e:
        logger.error(f"❌ 美元指数数据更新失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
