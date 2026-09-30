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
"""
from __future__ import annotations

from dataclasses import dataclass

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
MODEL_VERSION = "quant-v1"

# 用于计算收益与目标价的基准价格序列（COMEX 主力期货日收盘）
BENCHMARK_KEY = "gold_close"


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
    description: str


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
        description="资金在风险资产与黄金之间的配置摆动。",
    ),
)

factor_by_key = {factor.key: factor for factor in FACTORS}

assert len(factor_by_key) == len(FACTORS), "因子 key 必须唯一"
