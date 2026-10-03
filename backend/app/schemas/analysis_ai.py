"""五个 AI 分析接口的响应模型。

这些接口此前声明的是 `response_model=Dict[str, Any]` —— 等于没有模型：`/docs`
里它们只是一个空的 object，响应结构不受任何约束，服务实际返回的键与契约不符时
也没有任何东西会发现。

这不是假设的问题，是已经发生过的：`investment-advice-ai` 在缓存未命中时返回的
是一份结构完全不同的历史遗留 dict —— `market_assessment`、`strategies`、
`core_principles`、`disclaimer` 四个前端依赖的字段全部缺失，页面因此显示内置
兜底策略、市场评估一片空白、免责声明消失。而因为响应模型是 `Dict[str, Any]`，
接口照样返回 200，没有任何告警。

## 类型宽严的取舍

**顶层键一律必填。** 这些键由服务自己拼装，与 LLM 返回什么无关，是确定性的。
少一个就是 bug，应当立刻报错，而不是安静地少一个字段。

**叶子字段一律宽松。** 内容来自对 LLM 输出的 JSON 解析，个别字段缺失或类型
不合预期是可能的；把上游的不稳定变成服务端 500 只会让页面更糟。模型的职责是
把契约写下来、挡住结构漂移，不是逐字段严格校验。
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class AIMetadata(BaseModel):
    """分析结果的元信息。前端据此判断内容是不是占位。"""

    cached: Optional[bool] = None
    status: Optional[str] = None
    cache_source: Optional[str] = None
    message: Optional[str] = None
    generated_at: Optional[str] = None
    data_sources: Optional[List[str]] = None
    analysis_method: Optional[str] = None


class AIFactorItem(BaseModel):
    """看涨 / 看跌因子条目（对应前端 BullishFactor / BearishFactor）。"""

    id: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    details: List[str] = []
    impact: Optional[str] = None


class AIInstitutionItem(BaseModel):
    """机构预测条目（对应前端 InstitutionPrediction）。"""

    name: Optional[str] = None
    logo: Optional[str] = None
    rating: Optional[str] = None
    target_price: Optional[float] = None
    timeframe: Optional[str] = None
    reasoning: Optional[str] = None
    key_points: List[str] = []
    # 「最近一次可核实预测」的溯源字段：核实日期、滞后天数（后端用 timeutil
    # 计算）与线索来源（web_search / news_scan / legacy）。三者都可空 ——
    # 没有真实预测的占位行不该伪造日期。
    as_of_date: Optional[str] = None
    stale_days: Optional[int] = None
    source: Optional[str] = None


class BullishFactorsAIResponse(BaseModel):
    bullish_factors: List[AIFactorItem]
    analysis_summary: str
    last_updated: str
    metadata: Optional[AIMetadata] = None


class BearishFactorsAIResponse(BaseModel):
    bearish_factors: List[AIFactorItem]
    analysis_summary: str
    last_updated: str
    metadata: Optional[AIMetadata] = None


class InstitutionPredictionsAIResponse(BaseModel):
    institutions: List[AIInstitutionItem]
    analysis_summary: str
    last_updated: str
    metadata: Optional[AIMetadata] = None


class InvestmentAdviceAIResponse(BaseModel):
    """投资建议。

    这五个顶层键就是当初缺失的那批 —— 契约写下来之后，结构再漂移会立刻报错。
    """

    market_assessment: Dict[str, Any]
    strategies: List[Dict[str, Any]]
    core_principles: List[Dict[str, Any]]
    risk_warning: str
    disclaimer: str
    # 降级通道：输入不足时不调 LLM，只给行情统计与说明。前端据
    # `analysis_status`（与 metadata.status 对应）显示「数据不足」状态。
    analysis_status: Optional[str] = None
    price_snapshot: Optional[Dict[str, Any]] = None
    metadata: Optional[AIMetadata] = None


class MarketSummaryAIResponse(BaseModel):
    core_bullish_logic: List[str]
    main_risks: List[str]
    market_consensus: List[str]
    institution_targets: List[Dict[str, Any]]
    current_price: Optional[float] = None
    # 当前价的时间 / 口径 / 来源：与 current_price 同源同刻写入。
    # 没有它们，页面上的「$4,170」无法判断是刚才的报价还是昨天的收盘。
    # 金价取不到时四个字段一起为 null（不编价格，也不编时间）。
    price_as_of: Optional[str] = None
    price_basis: Optional[str] = None
    price_basis_label: Optional[str] = None
    price_source: Optional[str] = None
    comprehensive_judgment: Dict[str, Any]
    core_view: str
    investment_recommendation: str
    confidence_level: str
    time_horizon: str
    metadata: Optional[AIMetadata] = None
