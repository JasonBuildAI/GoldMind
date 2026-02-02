"""价格预测 API 路由"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.analysis import PredictionResponse

router = APIRouter()


@router.get("/predictions", response_model=List[PredictionResponse])
async def get_predictions(limit: int = 10, db: Session = Depends(get_db)):
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
            created_at=p.created_at
        )
        for p in predictions
    ]


@router.get("/predictions/latest")
async def get_latest_prediction(db: Session = Depends(get_db)):
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
        "created_at": prediction.created_at
    }
