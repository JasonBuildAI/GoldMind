"""价格预测 API 路由"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.analysis import PredictionResponse

router = APIRouter()


@router.get("/predictions", response_model=List[PredictionResponse])
async def get_predictions(limit: int = 10, db: Session = Depends(get_db)):
    """价格预测列表。表里现在有真实数据：量化引擎（services/quant）每次刷新写入。

    想读「此刻重算」的预测与逐因子贡献，用 `/quant/predictions`；这里返回的是
    落库的历史记录。
    """
    from app.models.analysis import Prediction
    
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
            created_at=p.created_at,
            direction=p.direction,
            horizon_days=p.horizon_days,
            as_of=p.as_of,
            base_price=p.base_price,
            score=p.score,
            expected_return=p.expected_return,
            uncertainty=p.uncertainty,
            model_version=p.model_version,
        )
        for p in predictions
    ]


@router.get("/predictions/latest")
async def get_latest_prediction(db: Session = Depends(get_db)):
    """最新一条已落库的价格预测。"""
    from app.models.analysis import Prediction
    
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
        "created_at": prediction.created_at,
        "direction": prediction.direction,
        "horizon_days": prediction.horizon_days,
        "as_of": prediction.as_of,
        "base_price": prediction.base_price,
        "score": prediction.score,
        "expected_return": prediction.expected_return,
        "uncertainty": prediction.uncertainty,
        "model_version": prediction.model_version,
    }
