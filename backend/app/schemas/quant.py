"""量化预测 API 的响应模型。

所有可能算不出来的字段都是 ``Optional``：宁可让页面显示「不可用 + 原因」，
也不填一个看起来像预测的默认值。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class FactorSnapshot(BaseModel):
    key: str
    name: str
    category: str
    category_name: str
    unit: str
    source: str
    description: str
    sign: int
    weight: float
    value: Optional[float] = None
    obs_date: Optional[date] = None
    age_days: Optional[int] = None
    max_age_days: int
    z: Optional[float] = None
    signed_z: Optional[float] = None
    contribution: Optional[float] = None
    status: str
    reason: Optional[str] = None


class CategoryStatus(BaseModel):
    key: str
    name: str
    total: int
    available: int


class SourceStatus(BaseModel):
    name: str
    label: Optional[str] = None
    status: str
    error: Optional[str] = None
    reason: Optional[str] = None


class SyncStatus(BaseModel):
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    sources_ok: Optional[int] = None
    sources_total: Optional[int] = None


class FactorDashboardResponse(BaseModel):
    model_version: str
    as_of: Optional[date] = None
    available_factors: int
    total_factors: int
    categories: List[CategoryStatus]
    factors: List[FactorSnapshot]
    sources: List[SourceStatus]
    sync: SyncStatus
    unavailable_reason: Optional[str] = None


class FactorContribution(BaseModel):
    key: str
    name: str
    category: str
    category_name: str
    weight: float
    sign: int
    value: Optional[float] = None
    obs_date: Optional[date] = None
    z: Optional[float] = None
    signed_z: Optional[float] = None
    contribution: Optional[float] = None
    status: str
    reason: Optional[str] = None


class Scenario(BaseModel):
    key: str
    label: str
    probability: float
    price_low: Optional[float] = None
    price_high: Optional[float] = None
    trigger: str
    invalidation: str


class QuantPredictionItem(BaseModel):
    horizon_days: int
    scale_label: Optional[str] = None
    scale: Optional[str] = None
    scale_description: Optional[str] = None
    status: str
    reason: Optional[str] = None
    direction: Optional[str] = None
    direction_label: Optional[str] = None
    as_of: Optional[date] = None
    base_price: Optional[float] = None
    target_price: Optional[float] = None
    expected_return: Optional[float] = None
    uncertainty: Optional[float] = None
    probability_up: Optional[float] = None
    range_low: Optional[float] = None
    range_high: Optional[float] = None
    scenarios: List[Scenario] = []
    scenario_reason: Optional[str] = None
    score: Optional[float] = None
    model_version: str
    available_factors: int
    total_factors: int
    factors: List[FactorContribution]


class DecompositionDriver(BaseModel):
    key: str
    name: str
    log_contribution: Optional[float] = None


class DecompositionBlock(BaseModel):
    key: str
    name: str
    usd: Optional[float] = None
    share_pct: Optional[float] = None
    drivers: List[DecompositionDriver] = []


class Decomposition(BaseModel):
    status: str
    reason: Optional[str] = None
    as_of: Optional[date] = None
    market_price: Optional[float] = None
    fair_value: Optional[float] = None
    deviation_pct: Optional[float] = None
    r2: Optional[float] = None
    samples: int = 0
    blocks: List[DecompositionBlock] = []


class QuantPredictionsResponse(BaseModel):
    model_version: str
    as_of: Optional[date] = None
    fair_value: Decomposition
    predictions: List[QuantPredictionItem]


class FactorPerformance(BaseModel):
    key: str
    name: str
    category: str
    category_name: str
    weight: float
    sign: int
    samples: int
    hit_rate: Optional[float] = None
    ic: Optional[float] = None
    rank_ic: Optional[float] = None


class AccuracyRow(BaseModel):
    horizon_days: int
    evaluated_at: Optional[datetime] = None
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    sample_size: int
    accuracy: Optional[float] = None
    baseline_up_accuracy: Optional[float] = None
    baseline_momentum_accuracy: Optional[float] = None
    brier_score: Optional[float] = None
    metrics: dict
    factors: List[FactorPerformance]
    reason: Optional[str] = None


class AccuracyResponse(BaseModel):
    model_version: str
    latest: List[AccuracyRow]
    history: List[AccuracyRow]


class MonitorRow(BaseModel):
    key: str
    name: str
    frequency: str
    source: str
    value: Optional[float] = None
    unit: str
    change: Optional[float] = None
    obs_date: Optional[date] = None
    signal: Optional[str] = None
    signal_label: str
    note: str
    status: str
    reason: Optional[str] = None


class MonitorResponse(BaseModel):
    as_of: Optional[date] = None
    rows: List[MonitorRow] = []


class RefreshResponse(BaseModel):
    success: bool
    message: str
    sources: List[SourceStatus]
    factor_status: dict
    predictions: List[QuantPredictionItem]
    evaluations: List[AccuracyRow]

