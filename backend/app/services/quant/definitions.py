"""因子与权重的**唯一**定义处。

基准是「影响国际金价的主要因素」四类框架：货币政策与利率（最核心）、
避险与信用、供需结构、市场与技术面。每个因子的口径、单位、方向假设与权重
只在这里写一次；文档与界面都从这里派生，不另抄一份。

两个必须说清的约定：

``sign``
    +1 表示「该因子值上升利多黄金」，-1 表示「上升利空黄金」。
    方向先验来自经济机理，**不保证成立** —— 回测会逐因子报告单独命中率，
    方向与实际相反时页面照样如实展示。

``transform``
    因子值 → 平稳信号的变换方式（见 ``engine.build_signals``）。
    ``change_Nd`` 取 N 个交易日的变化再做滚动 z 分数；``level`` 直接对水平值做 z。

``horizon_weights``
    分尺度权重覆盖：不同时间尺度上主导项不同（短尺度看资金流与技术面，
    中尺度看政策预期与美元，长尺度看央行购金与需求结构），因此每个因子
    给出 1 / 5 / 20 / 60 / 250 个交易日的权重；未列出的尺度回落到 ``weight``。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# 四类因素（与产品文档、前端分区一一对应）
CATEGORY_MONETARY = "monetary"
CATEGORY_RISK = "risk"
CATEGORY_SUPPLY = "supply"
CATEGORY_TECHNICAL = "technical"

CATEGORY_NAMES = {
    CATEGORY_MONETARY: "货币政策与利率",
    CATEGORY_RISK: "避险与信用",
    CATEGORY_SUPPLY: "供需结构",
    CATEGORY_TECHNICAL: "市场与技术面",
}

# 模型版本：改动因子集合、权重或变换方式时必须同时修改它 ——
# 预测与回测记录都带着版本号，改口径不会污染历史评估。
# v2：分尺度权重（同一因子在不同周期的权重不同），得分按周期取权重。
# v3：方向 / 概率 / 区间出自同一个走查校准分布（见 docs/specs/2026-10-01-预测口径统一.md）
# v4：区间宽度再按预测误差的经验分位校准（正态分位在长尺度系统性偏窄）。
MODEL_VERSION = "quant-v4"

# 用于计算收益与目标价的基准价格序列（COMEX 主力期货日收盘）
BENCHMARK_KEY = "gold_close"

@dataclass(frozen=True)
class HorizonSpec:
    """一个预测尺度的元数据：方法论的「先选尺度，再选变量」。"""

    horizon: int
    label: str
    scale: str
    description: str
    dominant_layers: tuple[str, ...]


# 预测周期（交易日）与方法论第一步的时间尺度一一对应：
#   日内～一周：资金流、技术面、仓位拥挤度主导；
#   1～3 个月：政策预期、经济数据、美元指数主导；
#   6～18 个月：实际利率周期、降息路径、央行购金趋势主导。
HORIZON_SPECS: tuple[HorizonSpec, ...] = (
    HorizonSpec(1, "1 日", "日内～一周", "资金流、技术面、仓位拥挤度主导，宏观基本面权重最低", ("市场与技术面", "供需结构")),
    HorizonSpec(5, "1 周", "日内～一周", "一周资金流与事件脉冲主导，宏观仍居次席", ("市场与技术面", "避险与信用")),
    HorizonSpec(20, "1 月", "1～3 个月", "政策预期、经济数据、美元指数主导", ("货币政策与利率", "供需结构")),
    HorizonSpec(60, "1 季", "1～3 个月", "政策路径与需求结构并重", ("货币政策与利率", "供需结构")),
    HorizonSpec(250, "1 年", "6～18 个月", "实际利率周期、降息路径、央行购金趋势主导", ("供需结构", "货币政策与利率")),
)

HORIZONS: tuple[int, ...] = tuple(spec.horizon for spec in HORIZON_SPECS)

horizon_spec = {spec.horizon: spec for spec in HORIZON_SPECS}


@dataclass(frozen=True)
class FactorDefinition:
    key: str
    name: str
    category: str
    unit: str
    source: str
    transform: str
    sign: int
    weight: float
    horizon_weights: tuple[tuple[int, float], ...]
    # 该因子的新鲜度上限（天）：超过就把状态标成「陈旧」而不是继续用旧值。
    # 取值按各源的发布节奏留出余量（日频 7 天覆盖长假，月度 62 天覆盖发布推迟）。
    max_age_days: int
    description: str

    def weight_for(self, horizon: Optional[int]) -> float:
        """该尺度下的权重；未列出的尺度（或 horizon=None）回落到基础权重。"""
        if horizon is not None:
            for declared, weight in self.horizon_weights:
                if declared == horizon:
                    return weight
        return self.weight


FACTORS: tuple[FactorDefinition, ...] = (
    FactorDefinition(
        key="real_yield_10y",
        name="美债 10 年期实际利率",
        category=CATEGORY_MONETARY,
        unit="%",
        source="美国财政部（TIPS 实际收益率曲线）",
        transform="change_20d",
        sign=-1,
        weight=1.0,
        horizon_weights=((1, 0.25), (5, 0.5), (20, 1.0), (60, 1.0), (250, 0.8)),
        max_age_days=7,
        description="持有黄金的机会成本，实际利率下行通常利多金价。",
    ),
    FactorDefinition(
        key="policy_expectation",
        name="市场隐含政策预期",
        category=CATEGORY_MONETARY,
        unit="%",
        source="美国财政部（2 年期收益率）− 纽约联储（EFFR）",
        transform="change_20d",
        sign=-1,
        weight=0.8,
        horizon_weights=((1, 0.2), (5, 0.4), (20, 1.0), (60, 0.8), (250, 0.6)),
        max_age_days=7,
        description="2 年期收益率相对有效联邦基金利率的溢价，上行代表市场预期更紧。",
    ),
    FactorDefinition(
        key="inflation_expectation",
        name="10 年期通胀预期",
        category=CATEGORY_MONETARY,
        unit="%",
        source="美国财政部（名义 − 实际收益率）",
        transform="change_20d",
        sign=1,
        weight=0.6,
        horizon_weights=((1, 0.1), (5, 0.2), (20, 0.5), (60, 0.5), (250, 0.4)),
        max_age_days=7,
        description="盈亏平衡通胀率，反映市场对未来通胀的定价。",
    ),
    FactorDefinition(
        key="dollar_index",
        name="美元指数",
        category=CATEGORY_MONETARY,
        unit="点",
        source="Yahoo Finance（DX-Y.NYB）",
        transform="change_20d",
        sign=-1,
        weight=0.7,
        horizon_weights=((1, 0.3), (5, 0.5), (20, 0.9), (60, 0.7), (250, 0.5)),
        max_age_days=7,
        description="美元走强通常压制以美元计价的黄金。",
    ),
    FactorDefinition(
        key="vix",
        name="VIX 波动率指数",
        category=CATEGORY_RISK,
        unit="点",
        source="Yahoo Finance（^VIX）",
        transform="level",
        sign=1,
        weight=0.4,
        horizon_weights=((1, 0.6), (5, 0.5), (20, 0.4), (60, 0.3), (250, 0.2)),
        max_age_days=7,
        description="市场恐慌程度，避险情绪升温时黄金通常受益。",
    ),
    FactorDefinition(
        key="credit_appetite",
        name="信用市场风险偏好",
        category=CATEGORY_RISK,
        unit="%（20 日）",
        source="Yahoo Finance（HYG/IEF 比值）",
        transform="level",
        sign=-1,
        weight=0.3,
        horizon_weights=((1, 0.5), (5, 0.4), (20, 0.3), (60, 0.2), (250, 0.2)),
        max_age_days=7,
        description="高收益债相对国债的 20 日表现，改善代表风险偏好回升、避险需求下降。",
    ),
    FactorDefinition(
        key="geopolitical",
        name="地缘风险强度",
        category=CATEGORY_RISK,
        unit="%（新闻占比）",
        source="本系统 RSS 语料（关键词强度代理指标）",
        transform="level",
        sign=1,
        weight=0.4,
        horizon_weights=((1, 0.5), (5, 0.5), (20, 0.4), (60, 0.3), (250, 0.3)),
        max_age_days=3,
        description="最近新闻中地缘冲突相关报道占比，相对历史水平的 z 分数；"
        "这是语料代理指标，不是 GPR 官方指数。",
    ),
    FactorDefinition(
        key="central_bank",
        name="央行购金（中国官方储备）",
        category=CATEGORY_SUPPLY,
        unit="万盎司",
        source="新浪财经宏观数据（中国人民银行官方储备资产）",
        transform="change_63d",
        sign=1,
        weight=0.7,
        horizon_weights=((1, 0.2), (5, 0.4), (20, 0.7), (60, 1.0), (250, 1.0)),
        max_age_days=62,
        description="央行持续增持是近年金价最重要的边际需求，按月更新、按发布滞后生效。",
    ),
    FactorDefinition(
        key="cftc_positioning",
        name="COMEX 投机净多头",
        category=CATEGORY_SUPPLY,
        unit="张",
        source="CFTC 持仓报告（合约代码 088691）",
        transform="change_20d",
        sign=1,
        weight=0.4,
        horizon_weights=((1, 0.8), (5, 0.7), (20, 0.4), (60, 0.3), (250, 0.2)),
        max_age_days=14,
        description="非商业净头寸，反映期货市场的投机资金方向。",
    ),
    FactorDefinition(
        key="etf_shares",
        name="黄金 ETF 份额（GLD）",
        category=CATEGORY_SUPPLY,
        unit="份",
        source="Yahoo Finance（GLD 份额快照，自采集日起积累）",
        transform="change_20d",
        sign=1,
        weight=0.4,
        horizon_weights=((1, 0.3), (5, 0.4), (20, 0.5), (60, 0.7), (250, 0.8)),
        max_age_days=7,
        description="份额申赎即资金进出，是投资需求的高频写照。",
    ),
    FactorDefinition(
        key="momentum",
        name="黄金趋势动量",
        category=CATEGORY_TECHNICAL,
        unit="%（60 日）",
        source="Yahoo Finance（GC=F 收盘）",
        transform="level",
        sign=1,
        weight=0.6,
        horizon_weights=((1, 1.0), (5, 1.0), (20, 0.4), (60, 0.3), (250, 0.2)),
        max_age_days=7,
        description="过去 60 个交易日的累计收益，趋势跟踪资金的基本输入。",
    ),
    FactorDefinition(
        key="seasonality",
        name="季节性（当月历史平均）",
        category=CATEGORY_TECHNICAL,
        unit="%（历史均值）",
        source="自有价格序列（按公历月份，只用往年的数据）",
        transform="level",
        sign=1,
        weight=0.2,
        horizon_weights=((1, 0.2), (5, 0.3), (20, 0.2), (60, 0.2), (250, 0.2)),
        max_age_days=7,
        description="印度婚季、中国春节等实物需求带来的月度效应，按往年同月收益估计。",
    ),
    FactorDefinition(
        key="bitcoin",
        name="比特币（数字黄金叙事）",
        category=CATEGORY_TECHNICAL,
        unit="点",
        source="Yahoo Finance（BTC-USD）",
        transform="change_20d",
        sign=-1,
        weight=0.2,
        horizon_weights=((1, 0.2), (5, 0.2), (20, 0.2), (60, 0.2), (250, 0.3)),
        max_age_days=7,
        description="替代品竞争：比特币走强可能分流部分黄金配置资金，方向先验较弱，以回测为准。",
    ),
    FactorDefinition(
        key="risk_appetite",
        name="股市风险偏好",
        category=CATEGORY_TECHNICAL,
        unit="点",
        source="Yahoo Finance（SPY）",
        transform="change_20d",
        sign=-1,
        weight=0.3,
        horizon_weights=((1, 0.5), (5, 0.4), (20, 0.3), (60, 0.2), (250, 0.2)),
        max_age_days=7,
        description="资金在风险资产与黄金之间的配置摆动。",
    ),
)

factor_by_key = {factor.key: factor for factor in FACTORS}

assert len(factor_by_key) == len(FACTORS), "因子 key 必须唯一"


@dataclass(frozen=True)
class ExtraSeries:
    """监控仪表盘专用序列：与因子同表存储（``factor_observations``），
    但**不参与**信号合成 —— 它们是「给你看的水位」，不是打分项。"""

    key: str
    name: str
    source: str
    frequency: str


EXTRA_SERIES: tuple[ExtraSeries, ...] = (
    ExtraSeries("usdcny", "美元兑人民币（USDCNY）", "Yahoo Finance（CNY=X）", "日"),
    ExtraSeries("cny_gold", "人民币金价参考", "黄金收盘 × USDCNY ÷ 31.1035", "日"),
    ExtraSeries("tga", "美国财政部 TGA 余额", "美国财政部 Fiscal Data（每日报表）", "日"),
    ExtraSeries("rrp", "纽约联储逆回购（RRP）", "纽约联储公开市场操作结果", "日"),
    ExtraSeries("cftc_oi", "COMEX 黄金未平仓合约", "CFTC 持仓报告", "周"),
)

extra_series_by_key = {item.key: item for item in EXTRA_SERIES}

assert len(extra_series_by_key) == len(EXTRA_SERIES), "额外序列 key 必须唯一"
