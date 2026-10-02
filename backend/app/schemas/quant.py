"""量化预测 API 的响应模型。

所有可能算不出来的字段都是 ``Optional``：宁可让页面显示「不可用 + 原因」，
也不填一个看起来像预测的默认值。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

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
    publication_lag_days: int
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
    headline: Optional[str] = None
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
    # 区间是自适应的：名义 80% 只是起点，实际水平 = 1 − interval_alpha。
    # distribution_mode 记录这一行用的是经验分布（aci）还是正态兜底（normal）。
    distribution_mode: Optional[str] = None
    interval_alpha: Optional[float] = None
    interval_nominal: Optional[float] = None
    expected_capped: bool = False
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


class ResearchPeriod(BaseModel):
    """一个样本期（开发 / 留出 / 全样本）的技能指标；算不出来就是 None + reason。"""

    label: str
    window_start: Optional[date] = None
    window_end: Optional[date] = None
    sample_size: int = 0
    accuracy: Optional[float] = None
    baseline_up_accuracy: Optional[float] = None
    baseline_momentum_accuracy: Optional[float] = None
    brier_score: Optional[float] = None
    brier_skill_score: Optional[float] = None
    brier_skill_p_value: Optional[float] = None
    # 分布级评分：Brier 只看涨/跌，CRPS 评整张分布对实现收益的匹配
    mean_crps: Optional[float] = None
    crps_skill_vs_flat: Optional[float] = None
    accuracy_diff_vs_up: Optional[float] = None
    accuracy_ci95: Optional[List[float]] = None
    p_value_vs_up: Optional[float] = None
    interval_coverage_80: Optional[float] = None
    interval_coverage_ci95: Optional[List[float]] = None
    effective_sample_size: Optional[float] = None
    # 独立下注口径（stride = 尺度）：重叠样本折算出的可信度。长尺度上两者差距
    # 巨大（250 日留出期 506 个重叠样本其实只有 2 次下注），所以单列而不是折算。
    independent_bets: Optional[int] = None
    independent_bet_stride: Optional[int] = None
    accuracy_independent_bets: Optional[float] = None
    interval_coverage_80_independent_bets: Optional[float] = None
    reason: Optional[str] = None


class ResearchFactor(BaseModel):
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


class HorizonResearch(BaseModel):
    horizon_days: int
    label: str
    headline: str
    # 裁决窗口（前向留出期）够不够判、还差多少：页面据此说明「为什么还没有结论」
    forward_readiness: Dict[str, Any] = {}
    periods: Dict[str, ResearchPeriod]
    reliability_bins: List[Dict[str, Any]] = []
    factors: List[ResearchFactor] = []


class ResearchVerdict(BaseModel):
    status: str          # ok / no_edge / candidate / unavailable
    label: str
    detail: str


class ResearchDataWindow(BaseModel):
    """研究页数字实际来自的库内窗口（页面显著标注；与 README 快照口径冲突时以它为准）。"""

    start: date
    end: date
    trading_days: int
    years: float


class QuantResearchResponse(BaseModel):
    model_version: str
    status: str
    reason: Optional[str] = None
    as_of: Optional[date] = None
    # 本页数字实际基于哪一段数据：起止 + 交易日数 + 年数（研究页显著标注）
    data_window: Optional[ResearchDataWindow] = None
    holdout_start: date
    active_holdout_start: date
    generated_at: datetime
    cached: bool = False
    verdict: ResearchVerdict
    horizons: List[HorizonResearch] = []

