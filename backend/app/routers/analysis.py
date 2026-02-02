"""市场分析 API 路由"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.analysis import FactorResponse, InstitutionResponse

router = APIRouter()


@router.get("/factors", response_model=List[FactorResponse])
async def get_market_factors(
    factor_type: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    from app.models.analysis import MarketFactor
    
    query = db.query(MarketFactor)
    
    if factor_type:
        query = query.filter(MarketFactor.type == factor_type)
    
    factors = query.order_by(MarketFactor.created_at.desc()).limit(limit).all()
    
    return [
        FactorResponse(
            id=f.id,
            factor_type=f.type,
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
async def get_bullish_factors(limit: int = 10, db: Session = Depends(get_db)):
    from app.models.analysis import MarketFactor
    
    factors = db.query(MarketFactor).filter(
        MarketFactor.type == "bullish"
    ).order_by(MarketFactor.created_at.desc()).limit(limit).all()
    
    return [
        FactorResponse(
            id=f.id,
            factor_type=f.type,
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
async def get_bearish_factors(limit: int = 10, db: Session = Depends(get_db)):
    from app.models.analysis import MarketFactor
    
    factors = db.query(MarketFactor).filter(
        MarketFactor.type == "bearish"
    ).order_by(MarketFactor.created_at.desc()).limit(limit).all()
    
    return [
        FactorResponse(
            id=f.id,
            factor_type=f.type,
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
async def get_institution_views(limit: int = 10, db: Session = Depends(get_db)):
    from app.models.analysis import InstitutionView
    
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


@router.get("/bullish-factors-ai", response_model=Dict[str, Any])
async def get_bullish_factors_analysis(
    refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    获取AI分析的看涨因子 - 优化版（快速响应）
    
    基于24小时内的新闻资讯，使用LangChain Agent进行智能分析
    
    优化策略：
    - 优先从内存缓存读取（<10ms）
    - 其次从数据库缓存读取（<50ms）
    - 无缓存时返回默认数据并触发后台分析
    - AI分析在后台线程池执行，不阻塞API响应
    
    Args:
        refresh: 是否强制刷新（重新分析），默认使用缓存
    
    Returns:
        看涨因子分析结果，包含5个核心看涨因素
    """
    from app.services.bullish_factor_service import BullishFactorService
    
    service = BullishFactorService(db)
    
    # 如果需要强制刷新，使用异步方式（不阻塞）
    if refresh:
        result = await service.refresh_analysis_async()
    else:
        # 快速获取缓存数据
        result = service.get_bullish_factors(use_cache=True)
    
    return result


@router.post("/bullish-factors-ai/refresh")
async def refresh_bullish_factors(db: Session = Depends(get_db)):
    """
    手动刷新看涨因子分析
    
    强制重新获取24小时内新闻并使用AI进行分析
    """
    from app.services.bullish_factor_service import BullishFactorService
    
    service = BullishFactorService(db)
    result = service.get_bullish_factors(use_cache=False)
    
    return {
        "success": True,
        "message": "看涨因子分析已刷新",
        "data": result
    }


@router.get("/bearish-factors-ai", response_model=Dict[str, Any])
async def get_bearish_factors_analysis(
    refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    获取AI分析的看空因子 - 优化版（快速响应）
    
    基于24小时内的新闻资讯，使用LangChain Agent进行智能分析
    
    优化策略：
    - 优先从内存缓存读取（<10ms）
    - 其次从数据库缓存读取（<50ms）
    - 无缓存时返回默认数据并触发后台分析
    - AI分析在后台线程池执行，不阻塞API响应
    
    Args:
        refresh: 是否强制刷新（重新分析），默认使用缓存
    
    Returns:
        看空因子分析结果，包含5个核心看空因素
    """
    from app.services.bearish_factor_service import BearishFactorService
    
    service = BearishFactorService(db)
    
    # 如果需要强制刷新，使用异步方式（不阻塞）
    if refresh:
        result = await service.refresh_analysis_async()
    else:
        # 快速获取缓存数据
        result = service.get_bearish_factors(use_cache=True)
    
    return result


@router.post("/bearish-factors-ai/refresh")
async def refresh_bearish_factors(db: Session = Depends(get_db)):
    """
    手动刷新看空因子分析
    
    强制重新获取24小时内新闻并使用AI进行分析
    """
    from app.services.bearish_factor_service import BearishFactorService
    
    service = BearishFactorService(db)
    result = service.get_bearish_factors(use_cache=False)
    
    return {
        "success": True,
        "message": "看空因子分析已刷新",
        "data": result
    }


@router.get("/institution-predictions-ai", response_model=Dict[str, Any])
async def get_institution_predictions_analysis(
    refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    获取AI分析的机构预测

    基于24小时内的新闻资讯，使用LangChain Agent抓取四大机构最新预测

    Args:
        refresh: 是否强制刷新（重新分析），默认使用缓存

    Returns:
        机构预测分析结果，包含高盛、瑞银、摩根士丹利、花旗的预测
    """
    from app.services.institution_prediction_service import InstitutionPredictionService

    service = InstitutionPredictionService(db)
    result = service.get_institution_predictions(use_cache=not refresh)

    return result


@router.post("/institution-predictions-ai/refresh")
async def refresh_institution_predictions(db: Session = Depends(get_db)):
    """
    手动刷新机构预测分析

    强制重新获取24小时内新闻并使用AI抓取机构最新预测
    """
    from app.services.institution_prediction_service import InstitutionPredictionService

    service = InstitutionPredictionService(db)
    result = service.get_institution_predictions(use_cache=False)

    return {
        "success": True,
        "message": "机构预测分析已刷新",
        "data": result
    }


@router.get("/investment-advice-ai", response_model=Dict[str, Any])
async def get_investment_advice_analysis(
    refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    获取AI生成的投资建议

    基于实时市场数据、看涨/看跌因子、机构预测和24小时新闻，
    使用LangChain Agent生成个性化的保守型投资策略建议

    Args:
        refresh: 是否强制刷新（重新分析），默认使用缓存

    Returns:
        投资建议分析结果，包含三种策略（保守/均衡/机会型）
    """
    from app.services.investment_advice_service import InvestmentAdviceService
    from app.services.bullish_factor_service import BullishFactorService
    from app.services.bearish_factor_service import BearishFactorService
    from app.services.institution_prediction_service import InstitutionPredictionService
    from app.services.gold_service import GoldService

    # 获取市场状态
    gold_service = GoldService(db)
    stats = gold_service.get_statistics()
    market_status = f"当前金价: ${stats.get('current_price', 0):.2f}, " \
                   f"2025年至今涨幅: {stats.get('ytd_change', 0):+.2f}%, " \
                   f"波动区间: {stats.get('volatility_range', 0):.2f}%"

    # 获取看涨因子
    bullish_service = BullishFactorService(db)
    bullish_result = bullish_service.get_bullish_factors(use_cache=not refresh)
    bullish_factors = bullish_result.get("factors", [])

    # 获取看跌因子
    bearish_service = BearishFactorService(db)
    bearish_result = bearish_service.get_bearish_factors(use_cache=not refresh)
    bearish_factors = bearish_result.get("factors", [])

    # 获取机构预测
    institution_service = InstitutionPredictionService(db)
    institution_result = institution_service.get_institution_predictions(use_cache=not refresh)
    institution_predictions = institution_result.get("institutions", [])

    # 生成投资建议
    advice_service = InvestmentAdviceService(db)
    result = advice_service.get_investment_advice(
        market_status=market_status,
        bullish_factors=bullish_factors,
        bearish_factors=bearish_factors,
        institution_predictions=institution_predictions,
        use_cache=not refresh
    )

    return result


@router.post("/investment-advice-ai/refresh")
async def refresh_investment_advice_analysis(db: Session = Depends(get_db)):
    """
    手动刷新投资建议分析

    强制重新分析所有市场数据并生成最新投资建议
    """
    from app.services.investment_advice_service import InvestmentAdviceService
    from app.services.bullish_factor_service import BullishFactorService
    from app.services.bearish_factor_service import BearishFactorService
    from app.services.institution_prediction_service import InstitutionPredictionService
    from app.services.gold_service import GoldService

    # 获取市场状态
    gold_service = GoldService(db)
    stats = gold_service.get_statistics()
    market_status = f"当前金价: ${stats.get('current_price', 0):.2f}, " \
                   f"2025年至今涨幅: {stats.get('ytd_change', 0):+.2f}%, " \
                   f"波动区间: {stats.get('volatility_range', 0):.2f}%"

    # 获取看涨因子（强制刷新）
    bullish_service = BullishFactorService(db)
    bullish_result = bullish_service.get_bullish_factors(use_cache=False)
    bullish_factors = bullish_result.get("factors", [])

    # 获取看跌因子（强制刷新）
    bearish_service = BearishFactorService(db)
    bearish_result = bearish_service.get_bearish_factors(use_cache=False)
    bearish_factors = bearish_result.get("factors", [])

    # 获取机构预测（强制刷新）
    institution_service = InstitutionPredictionService(db)
    institution_result = institution_service.get_institution_predictions(use_cache=False)
    institution_predictions = institution_result.get("institutions", [])

    # 生成投资建议
    advice_service = InvestmentAdviceService(db)
    result = advice_service.get_investment_advice(
        market_status=market_status,
        bullish_factors=bullish_factors,
        bearish_factors=bearish_factors,
        institution_predictions=institution_predictions,
        use_cache=False
    )

    return {
        "success": True,
        "message": "投资建议分析已刷新",
        "data": result
    }


@router.get("/market-summary-ai", response_model=Dict[str, Any])
async def get_market_summary_analysis(
    refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    获取AI生成的黄金市场综合分析

    基于实时市场数据、看涨/看跌因子、机构预测和新闻，
    使用DeepSeek LLM生成全面的市场总结和综合判断

    Args:
        refresh: 是否强制刷新（重新分析），默认使用缓存

    Returns:
        市场综合分析结果，包含核心逻辑、风险因素、机构目标和综合判断
    """
    from app.services.market_summary_service import MarketSummaryService
    from app.services.bullish_factor_service import BullishFactorService
    from app.services.bearish_factor_service import BearishFactorService
    from app.services.institution_prediction_service import InstitutionPredictionService
    from app.services.gold_service import GoldService

    # 获取市场状态
    gold_service = GoldService(db)
    stats = gold_service.get_statistics()
    market_status = f"当前金价: ${stats.get('current_price', 0):.2f}, " \
                   f"2025年至今涨幅: {stats.get('ytd_change', 0):+.2f}%, " \
                   f"波动区间: {stats.get('volatility_range', 0):.2f}%"

    # 获取看涨因子
    bullish_service = BullishFactorService(db)
    bullish_result = bullish_service.get_bullish_factors(use_cache=not refresh)
    bullish_factors = bullish_result.get("bullish_factors", [])

    # 获取看跌因子
    bearish_service = BearishFactorService(db)
    bearish_result = bearish_service.get_bearish_factors(use_cache=not refresh)
    bearish_factors = bearish_result.get("bearish_factors", [])

    # 获取机构预测
    institution_service = InstitutionPredictionService(db)
    institution_result = institution_service.get_institution_predictions(use_cache=not refresh)
    institution_predictions = institution_result.get("institutions", [])

    # 生成市场综合分析
    summary_service = MarketSummaryService(db)
    result = summary_service.get_market_summary(
        market_status=market_status,
        bullish_factors=bullish_factors,
        bearish_factors=bearish_factors,
        institution_predictions=institution_predictions,
        use_cache=not refresh
    )

    return result


@router.post("/market-summary-ai/refresh")
async def refresh_market_summary_analysis(db: Session = Depends(get_db)):
    """
    手动刷新黄金市场综合分析

    强制重新分析所有市场数据并生成最新综合总结
    """
    from app.services.market_summary_service import MarketSummaryService
    from app.services.bullish_factor_service import BullishFactorService
    from app.services.bearish_factor_service import BearishFactorService
    from app.services.institution_prediction_service import InstitutionPredictionService
    from app.services.gold_service import GoldService

    # 获取市场状态
    gold_service = GoldService(db)
    stats = gold_service.get_statistics()
    market_status = f"当前金价: ${stats.get('current_price', 0):.2f}, " \
                   f"2025年至今涨幅: {stats.get('ytd_change', 0):+.2f}%, " \
                   f"波动区间: {stats.get('volatility_range', 0):.2f}%"

    # 获取看涨因子（强制刷新）
    bullish_service = BullishFactorService(db)
    bullish_result = bullish_service.get_bullish_factors(use_cache=False)
    bullish_factors = bullish_result.get("bullish_factors", [])

    # 获取看跌因子（强制刷新）
    bearish_service = BearishFactorService(db)
    bearish_result = bearish_service.get_bearish_factors(use_cache=False)
    bearish_factors = bearish_result.get("bearish_factors", [])

    # 获取机构预测（强制刷新）
    institution_service = InstitutionPredictionService(db)
    institution_result = institution_service.get_institution_predictions(use_cache=False)
    institution_predictions = institution_result.get("institutions", [])

    # 生成市场综合分析
    summary_service = MarketSummaryService(db)
    result = summary_service.get_market_summary(
        market_status=market_status,
        bullish_factors=bullish_factors,
        bearish_factors=bearish_factors,
        institution_predictions=institution_predictions,
        use_cache=False
    )

    return {
        "success": True,
        "message": "市场综合分析已刷新",
        "data": result
    }
