"""原始序列 → 因子值。

单位与口径只在这一层固定，界面、回测、文档都以此为准：

- 利率类：百分数（2.91 表示 2.91%）
- 指数类：点位
- 央行储备：万盎司
- 动量 / 季节性 / 信用偏好：百分数
- CFTC：净头寸张数

缺哪个原始序列，就少产出哪个因子 —— 不补零、不用默认值。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from app.services.quant.definitions import BENCHMARK_KEY, FACTORS
from app.services.quant.sources.base import SourceError, clean_series

SEASONAL_LOOKBACK_YEARS = 6
SEASONAL_MIN_YEARS = 3
# 金衡盎司 → 克（人民币金价参考的唯一换算口径）
GRAMS_PER_TROY_OUNCE = 31.1035


def seasonal_expectation(prices: pd.Series) -> pd.Series:
    """当月历史平均收益（%，只用往年的数据，逐年扩展）。

    实现：先算每个 (年, 月) 的平均日收益，再对每个月取**之前**至多 6 年
    （至少 3 年）的均值。当年与未来的月份不会进入计算 —— 这是一条
    无前视的滚动估计，而不是「用全样本算出来的季节因子」。
    """
    if prices is None or prices.empty:
        return pd.Series(dtype="float64", name="seasonality")

    frame = pd.DataFrame({"ret": prices.pct_change()})
    frame["year"] = frame.index.year
    frame["month"] = frame.index.month
    frame = frame.dropna()
    if frame.empty:
        return pd.Series(dtype="float64", name="seasonality")

    monthly = (
        frame.groupby(["month", "year"])["ret"]
        .mean()
        .reset_index()
        .sort_values(["month", "year"])
    )
    monthly["seasonal"] = monthly.groupby("month")["ret"].transform(
        lambda series: series.shift(1)
        .rolling(SEASONAL_LOOKBACK_YEARS, min_periods=SEASONAL_MIN_YEARS)
        .mean()
    )
    monthly = monthly.dropna(subset=["seasonal"])

    estimates = {
        (int(row.year), int(row.month)): float(row.seasonal)
        for row in monthly.itertuples()
    }
    values = {}
    for timestamp in prices.index:
        estimate = estimates.get((timestamp.year, timestamp.month))
        if estimate is not None:
            values[timestamp] = estimate * 100
    return clean_series(values, "seasonality")


def derive_factors(raw: dict[str, pd.Series]) -> dict[str, pd.Series]:
    """把原始序列映射为因子值；缺失的因子不会出现在返回值里。"""
    derived: dict[str, pd.Series] = {}

    def add(key: str, series: Optional[pd.Series]) -> None:
        if series is None:
            return
        cleaned = series.dropna().astype("float64")
        if not cleaned.empty:
            derived[key] = clean_series(cleaned.to_dict(), key)

    gold = raw.get("gold_close")

    add("real_yield_10y", raw.get("ust_real_10y"))

    nominal_2y = raw.get("ust_nominal_2y")
    effr = raw.get("effr")
    if nominal_2y is not None and effr is not None:
        combined = nominal_2y.align(effr, join="inner")
        add("policy_expectation", combined[0] - combined[1])

    nominal_10y = raw.get("ust_nominal_10y")
    real_10y = raw.get("ust_real_10y")
    if nominal_10y is not None and real_10y is not None:
        combined = nominal_10y.align(real_10y, join="inner")
        add("inflation_expectation", combined[0] - combined[1])

    add("dollar_index", raw.get("dxy"))
    add("vix", raw.get("vix"))

    hyg = raw.get("hyg")
    ief = raw.get("ief")
    if hyg is not None and ief is not None:
        # pandas 按索引对齐：两边都有的交易日才参与计算，其余为 NaN 并被丢弃。
        ratio = hyg / ief
        add("credit_appetite", (ratio / ratio.shift(20) - 1) * 100)

    add("geopolitical", raw.get("news_geo_intensity"))
    add("central_bank", raw.get("cb_gold_reserves"))
    add("cftc_positioning", raw.get("cftc_net"))
    add("etf_shares", raw.get("gld_shares"))

    if gold is not None:
        add("momentum", (gold / gold.shift(60) - 1) * 100)
        add("seasonality", seasonal_expectation(gold))
        add(BENCHMARK_KEY, gold)

    add("bitcoin", raw.get("btc"))
    add("risk_appetite", raw.get("spy"))

    # 监控仪表盘的额外序列：同表存储、不参与信号合成
    usdcny = raw.get("usdcny")
    add("usdcny", usdcny)
    if gold is not None and usdcny is not None:
        combined = gold.align(usdcny, join="inner")
        add("cny_gold", combined[0] * combined[1] / GRAMS_PER_TROY_OUNCE)
    add("tga", raw.get("tga"))
    add("rrp", raw.get("rrp"))
    add("cftc_oi", raw.get("cftc_oi"))

    # 下一轮候选信息源：与因子同表入库、只积累覆盖，本轮不参与信号合成。
    add("gvz", raw.get("gvz"))
    add("gpr_daily", raw.get("gpr_daily"))
    # 基准对照序列（第四轮）：只做研究台的基准敏感性对照，不参与信号合成。
    add("gld_close", raw.get("gld_close"))
    if gold is not None:
        silver = raw.get("silver_close")
        if silver is not None:
            gold_silver = gold.align(silver, join="inner")
            add("gold_silver_ratio", gold_silver[0] / gold_silver[1])
        copper = raw.get("copper_close")
        if copper is not None:
            copper_gold = gold.align(copper, join="inner")
            add("copper_gold_ratio", copper_gold[1] / copper_gold[0])
    cftc_net = raw.get("cftc_net")
    cftc_oi = raw.get("cftc_oi")
    if cftc_net is not None and cftc_oi is not None:
        net_oi = cftc_net.align(cftc_oi, join="inner")
        add("cftc_net_oi_ratio", net_oi[0] / net_oi[1])

    # 第四轮预注册候选（2.0.2）：高权威消息强度（消息板块每日入库条数）。
    # 只存储、上监测表，本轮不进信号合成；是否进因子集由下一轮预注册决定。
    add("digest_intensity", raw.get("digest_gold_count"))

    return derived


# 每个因子/额外序列依赖哪些原始序列 —— 与上面的 `add(...)` 一一对应。
# 为什么要单独列一张表：同步层要把「这个因子为什么没数据」归因到**真正喂它的源**，
# 而 `required_raw_keys()` 是一个扁平集合，说不出「谁喂谁」。旧实现因此罗列所有
# 出问题的源，把无关源写进原因（张冠李戴）。
# 守卫：`tests/unit/test_quant_sync.py` 断言它与 FACTORS + EXTRA_SERIES 完全对齐、
# 且每个原始序列都在 `required_raw_keys()` 里。
FACTOR_RAW_KEYS: dict[str, tuple[str, ...]] = {
    "real_yield_10y": ("ust_real_10y",),
    "policy_expectation": ("ust_nominal_2y", "effr"),
    "inflation_expectation": ("ust_nominal_10y", "ust_real_10y"),
    "dollar_index": ("dxy",),
    "vix": ("vix",),
    "credit_appetite": ("hyg", "ief"),
    "geopolitical": ("news_geo_intensity",),
    "central_bank": ("cb_gold_reserves",),
    "cftc_positioning": ("cftc_net",),
    "etf_shares": ("gld_shares",),
    "momentum": ("gold_close",),
    "seasonality": ("gold_close",),
    "bitcoin": ("btc",),
    "risk_appetite": ("spy",),
    # 监控专用序列（同表存储、不参与信号合成）
    "usdcny": ("usdcny",),
    "cny_gold": ("gold_close", "usdcny"),
    "tga": ("tga",),
    "rrp": ("rrp",),
    "cftc_oi": ("cftc_oi",),
    # 下一轮候选信息源
    "gvz": ("gvz",),
    "gpr_daily": ("gpr_daily",),
    "gold_silver_ratio": ("gold_close", "silver_close"),
    "copper_gold_ratio": ("gold_close", "copper_close"),
    "cftc_net_oi_ratio": ("cftc_net", "cftc_oi"),
    # 基准对照序列（第四轮，只进研究台）
    "gld_close": ("gld_close",),
    # 第四轮预注册候选：高权威消息强度（本库消息板块计数）
    "digest_intensity": ("digest_gold_count",),
}


def required_raw_keys() -> set[str]:
    """列出定义里每个因子依赖的原始序列，供同步层做可用性报告。"""
    _ = FACTORS  # 定义来自 definitions，这里只是提醒调用方：因子集合以它为准
    return {
        "ust_real_10y",
        "ust_nominal_2y",
        "ust_nominal_10y",
        "effr",
        "dxy",
        "vix",
        "hyg",
        "ief",
        "news_geo_intensity",
        "cb_gold_reserves",
        "cftc_net",
        "gld_shares",
        "gold_close",
        "usdcny",
        "tga",
        "rrp",
        "cftc_oi",
        "gvz",
        "silver_close",
        "copper_close",
        "gpr_daily",
        "btc",
        "spy",
        "gld_close",
        "digest_gold_count",
    }
