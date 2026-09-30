"""量化预测 API 路由。

四个端点对应页面上的四个问题：因子现在是多少（`/factors`）、接下来怎么走
（`/predictions`）、历史上到底准不准（`/accuracy`）、现在能不能刷一次
（`/refresh`，路径以 `/refresh` 结尾 → 自动落到更严的限流档）。
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.quant import (
    AccuracyResponse,
    FactorDashboardResponse,
    QuantPredictionsResponse,
    RefreshResponse,
)
from app.services.quant import service

router = APIRouter()


@router.get("/quant/factors", response_model=FactorDashboardResponse)
async def get_quant_factors(
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """四类影响因素的当前快照：值、方向、贡献、来源与数据截至时间。

    任一因子不可用都会带 `status` 与 `reason`，页面照实显示，不补数字。
    """
    return service.factor_dashboard(db, category=category)


@router.get("/quant/predictions", response_model=QuantPredictionsResponse)
async def get_quant_predictions(
    horizon_days: Optional[int] = Query(default=None, ge=1, le=60),
    db: Session = Depends(get_db),
):
    """量化预测：方向、上行概率、目标价与逐因子贡献。

    不传 `horizon_days` 返回 1 / 5 / 20 三个周期；算不出来的周期给出原因，
    不返回方向与数字。
    """
    return service.live_predictions(db, horizon=horizon_days)


@router.get("/quant/accuracy", response_model=AccuracyResponse)
async def get_quant_accuracy(db: Session = Depends(get_db)):
    """走查式回测的命中率：与「永远看多 / 动量 / 抛硬币」并排对照。

    `latest` 是每个周期最新的一条评估，`history` 是历次评估（准确率的时间序列）。
    从未回测过时返回空样本与原因，不返回 0% 之类的假数字。
    """
    return service.accuracy_report(db)


@router.post("/quant/refresh", response_model=RefreshResponse)
async def refresh_quant(db: Session = Depends(get_db)):
    """立即抓取因子、重算预测并追加一次回测（耗时数十秒，已按付费档限流）。"""
    return await run_in_threadpool(service.full_refresh, db)
