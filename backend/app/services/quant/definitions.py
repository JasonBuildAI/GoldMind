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
from datetime import date
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
# v5：ACI 的 α 更新改成判「这一注发出时的那条区间」（engine.calibrate_distribution
#     的 issued_lag）—— v4 拿当前这行的区间去判 h 天前发出的那一注，尺度越长偏得越多，
#     方向正是覆盖不足。这是一次只改数值、不改因子集的修复，但发出的区间确实变了，
#     所以版本号必须跟着动（见 docs/specs/2026-10-02-量化引擎第三轮预注册.md §三）。
#     第三轮候选 C2（每注取样 + 回看窗）按预注册判据淘汰，线上一字未动，因此没有 v6。
# v6：2026-10-02 引擎加固。三处改变**输出**的修复：① `align_series` 不再丢弃日期不在
#     价格日历里的观测（26 年面板上 1106 行的取值因此变了）；② ACI 的 α 上界从 0.6
#     收到 0.5（区间与情景重新嵌套，长尺度区间变宽）；③ 快照多带
#     `interval_alpha` / `expected_capped`。口径变了，历史 `quant-v5` 记录里的
#     命中率与覆盖率**不再可比** —— 需要对照时必须带版本号看。
# v7：2026-10-03 发布滞后对齐。`real_yield_10y` / `policy_expectation` /
#     `inflation_expectation` 三个因子的观测要到「观测日 + N 个工作日」才可见
#     （H.15 在当日收盘后发布、EFFR 在次日发布），引擎按可见时点对齐。此前它们
#     与当日收盘价对齐使用，等于提前用了当时还看不到的数 —— 回测因此有乐观偏差。
#     口径变了，`quant-v6` 及更早的命中率与覆盖率记录不再可比。
MODEL_VERSION = "quant-v7"

# 留出期起点：此日期起的样本只用于汇报与预注册裁决，不参与任何调参。
# 「开发期 / 留出期 / 全样本」三列的口径见 backtest.evaluate_periods；
# 预注册硬规则写死在 docs/specs/2026-10-02-量化策略提升路线图.md。
HOLDOUT_START = date(2023, 10, 2)

# 前向留出期起点：预注册封板日（第二轮结论写进 spec 的那一天）。
# HOLDOUT_START 起的那一段已经被第一/二轮裁决看过、汇报过 —— 再看它一眼就
# 不再是样本外，只能当历史记录。只有这一天之后**新增**的观测才是干净的裁决样本，
# 所以裁决只认这一段；样本不够时状态是 pending（还差多少交易日照实报），
# 而不是拿历史那一段顶替。屏幕层第 ③ 道闸门用的是同一个日期，只在这里定义一次。
# v7 换版重新封板（2026-10-03）：发布滞后修正改写了可见性，封板前发出的 v6 注单
# 在新口径下作废，前向窗口从这一天重新计数。
ACTIVE_HOLDOUT_START = date(2026, 10, 3)

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
    # 该尺度的主输出（页面与研究页的标题口径）：短尺度是方向 + 校准区间，
    # 长尺度是公允价值偏离 + 校准区间 —— 与「先选尺度，再选变量」一致。
    headline: str


# 预测周期（交易日）与方法论第一步的时间尺度一一对应：
#   日内～一周：资金流、技术面、仓位拥挤度主导；
#   1～3 个月：政策预期、经济数据、美元指数主导；
#   6～18 个月：实际利率周期、降息路径、央行购金趋势主导。
HORIZON_SPECS: tuple[HorizonSpec, ...] = (
    HorizonSpec(1, "1 日", "日内～一周", "资金流、技术面、仓位拥挤度主导，宏观基本面权重最低", ("市场与技术面", "供需结构"), "方向 / 次日校准区间"),
    HorizonSpec(5, "1 周", "日内～一周", "一周资金流与事件脉冲主导，宏观仍居次席", ("市场与技术面", "避险与信用"), "方向 / 一周校准区间"),
    HorizonSpec(20, "1 月", "1～3 个月", "政策预期、经济数据、美元指数主导", ("货币政策与利率", "供需结构"), "方向 / 月度校准区间"),
    HorizonSpec(60, "1 季", "1～3 个月", "政策路径与需求结构并重", ("货币政策与利率", "供需结构"), "方向 / 季度校准区间"),
    HorizonSpec(250, "1 年", "6～18 个月", "实际利率周期、降息路径、央行购金趋势主导", ("供需结构", "货币政策与利率"), "公允价值偏离 / 年度校准区间"),
)

HORIZONS: tuple[int, ...] = tuple(spec.horizon for spec in HORIZON_SPECS)

horizon_spec = {spec.horizon: spec for spec in HORIZON_SPECS}

# 方向发布策略：算得出方向 ≠ 该发布方向。
# 留出期里 1 年尺度的方向与「永远看多」逐日一致（+0.0pp）、Brier 技能分为负 ——
# 拿不出可核实的信息优势就不发，只保留公允价值偏离与校准区间（2026-10-02 第三轮
# 预注册裁决，见 docs/specs/2026-10-02-量化策略提升路线图.md 第五节）。
# 引擎内部仍算方向供回测评估，只是不在产品里发布。
DIRECTION_PUBLISHED = "published"
DIRECTION_NOT_PUBLISHED = "not_published"
NOT_PUBLISHED_DIRECTION_REASONS: dict[int, str] = {
    250: (
        "1 年尺度在留出期与「永远看多」逐日一致（差 +0.0pp），Brier 技能分为负："
        "方向拿不出可核实的信息优势，按预注册规则停发；公允价值偏离与校准区间照常发布"
    ),
}


def direction_publication(horizon: int) -> tuple[str, Optional[str]]:
    """该尺度发不发方向：返回 ``(status, reason)``；发布时 reason 为 None。"""
    reason = NOT_PUBLISHED_DIRECTION_REASONS.get(horizon)
    if reason is None:
        return DIRECTION_PUBLISHED, None
    return DIRECTION_NOT_PUBLISHED, reason


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
    # 发布滞后（工作日）：观测日之后还要等这么久，这个数**才可见**。
    # 0 = 收盘即可用（价格类）；1 = 次日发布（H.15 当日收盘后挂网、EFFR 次日 9 点）。
    # 引擎按「观测日 + lag 个工作日」对齐到价格日历，展示层的年龄用同一口径。
    publication_lag_days: int = 0

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
        publication_lag_days=1,  # H.15 在当日收盘后发布，次日才可用于决策
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
        publication_lag_days=1,  # EFFR 次日 9 点发布，2 年期收益率收盘后挂网
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
        publication_lag_days=1,  # 名义与实际收益率都来自 H.15，次日可见
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
    ExtraSeries("sge_gold", "上海金 Au99.99", "上海黄金交易所（公开日线）", "日"),
    ExtraSeries("tga", "美国财政部 TGA 余额", "美国财政部 Fiscal Data（每日报表）", "日"),
    ExtraSeries("rrp", "纽约联储逆回购（RRP）", "纽约联储公开市场操作结果", "日"),
    ExtraSeries("cftc_oi", "COMEX 黄金未平仓合约", "CFTC 持仓报告", "周"),
    # 2026-10-02 起入库的下一轮候选信息源：只存储、只积累覆盖，不参与信号合成；
    # 是否进因子集由下一轮预注册决定（spec：量化策略提升路线图，第五节）。
    ExtraSeries("gvz", "黄金波动率指数（GVZ）", "Yahoo Finance（^GVZ）", "日"),
    ExtraSeries("gold_silver_ratio", "金银比（金价 ÷ 银价）", "Yahoo Finance（GC=F ÷ SI=F）", "日"),
    ExtraSeries("copper_gold_ratio", "铜金比（铜价 ÷ 金价）", "Yahoo Finance（HG=F ÷ GC=F）", "日"),
    ExtraSeries("cftc_net_oi_ratio", "CFTC 净头寸占未平仓比", "CFTC 持仓报告（净头寸 ÷ 未平仓）", "周"),
    ExtraSeries("gpr_daily", "GPR 官方日度地缘风险指数", "Iacoviello & Papaioannou GPR（官方 .xls）", "日"),
    # 基准对照序列（第四轮）：只供研究台做「生产基准 vs ETF 基准」的敏感性对照，
    # 不参与信号合成、不进仪表盘。口径见 regimes.BENCHMARK_CHOICES。
    ExtraSeries("gld_close", "GLD 收盘价（基准对照）", "Yahoo Finance（GLD）", "日"),
    # 第四轮预注册候选（2.0.2 第 16 条整改）：高权威消息强度 —— 消息板块每日
    # 入库条数。只存储、上监测表（信息行）；不进本轮信号合成，是否进因子集
    # 由下一轮预注册写死后再执行。
    ExtraSeries(
        "digest_intensity",
        "高权威消息强度（每日条数）",
        "消息板块（13 个高权威源，本库统计）",
        "日",
    ),
)

extra_series_by_key = {item.key: item for item in EXTRA_SERIES}

assert len(extra_series_by_key) == len(EXTRA_SERIES), "额外序列 key 必须唯一"
