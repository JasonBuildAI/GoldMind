"""量化引擎测试用的合成面板。

真实行情不进单元测试（conftest 也有出网兜底）：这里只需要一组长度、频率、
量级都像真实数据的确定性序列，让「口径与时间方向」可以被逐位核对。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant.definitions import BENCHMARK_KEY, FACTORS

DAYS = 900
END = "2026-09-30"


def _panel(calendar: pd.DatetimeIndex, *, seed: int = 7):
    rng = np.random.default_rng(seed)
    factors = {}
    for position, definition in enumerate(FACTORS):
        noise = rng.normal(0.0, 1.0, len(calendar))
        drift = rng.normal(0.0, 0.05)
        level = 100.0 + position * 5.0 + np.cumsum(noise * 0.5 + drift)
        factors[definition.key] = pd.Series(level, index=calendar, name=definition.key)

    returns = rng.normal(0.0, 0.008, len(calendar))
    close = pd.Series(2000.0 * np.exp(np.cumsum(returns)), index=calendar, name=BENCHMARK_KEY)
    return factors, close


# 真实因子的形状：不是所有源都每天更新。周度（CFTC）、月度（央行储备）、
# 单点快照（ETF 份额）、只有近期历史（新闻语料）都必须出现在测试面板里 ——
# 否则「对齐时只向前填充」这条守卫会因为合成数据每天都更新而永远绿着。
SPARSE_SHAPES = {
    "cftc_positioning": {"step": 5},
    "central_bank": {"step": 21},
    "etf_shares": {"only_last": 1},
    "geopolitical": {"tail": 60},
}


def _sparse_panel(calendar: pd.DatetimeIndex, *, seed: int = 11):
    factors, close = _panel(calendar, seed=seed)
    for key, shape in SPARSE_SHAPES.items():
        series = factors[key]
        if "step" in shape:
            factors[key] = series.iloc[:: shape["step"]]
        elif "tail" in shape:
            factors[key] = series.iloc[-shape["tail"] :]
        elif "only_last" in shape:
            factors[key] = series.iloc[-shape["only_last"] :]
    return factors, close


@pytest.fixture(scope="session")
def calendar() -> pd.DatetimeIndex:
    return pd.date_range(end=END, periods=DAYS, freq="B")


@pytest.fixture()
def make_panel():
    return _panel


@pytest.fixture()
def panel(calendar):
    return _panel(calendar)


@pytest.fixture()
def make_sparse_panel():
    return _sparse_panel


@pytest.fixture()
def sparse_panel(calendar):
    return _sparse_panel(calendar)
