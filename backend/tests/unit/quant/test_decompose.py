"""四层分解：恒等式、无前视、降级与已知答案。"""
from __future__ import annotations

import warnings

import numpy as np
import pandas as pd
import pytest

from app.services.quant import decompose, engine
from app.services.quant.definitions import BENCHMARK_KEY


def _known_answer_panel(calendar):
    """精确线性关系：log(price) = 2 + 0.2·real − 0.1·log(dxy) + 0.3·log(cb) − 0.02·vix。

    回归量按**可见口径**生成：`real_yield_10y` 带 1 个工作日发布滞后，t 日的价格
    只能依赖当时已可见的那条收益率（和真实世界一致）；dxy / cb / vix 无滞后。
    第一天还没有可见的收益率，价格从第二天开始，避免把 NaN 带进拟合。
    """
    rng = np.random.default_rng(5)
    real = pd.Series(np.cumsum(rng.normal(0.0, 0.02, len(calendar))) + 1.5, index=calendar)
    dxy = pd.Series(
        np.exp(np.cumsum(rng.normal(0.0, 0.005, len(calendar))) + np.log(100.0)), index=calendar
    )
    cb = pd.Series(
        np.exp(np.cumsum(rng.normal(0.0, 0.002, len(calendar))) + np.log(7000.0)), index=calendar
    )
    vix = pd.Series(np.cumsum(rng.normal(0.0, 0.1, len(calendar))) + 18.0, index=calendar)

    real_visible = engine.publication_visible(real, 1).reindex(calendar).ffill()
    usable = real_visible.notna()
    log_price = (
        2.0 + 0.2 * real_visible - 0.1 * np.log(dxy) + 0.3 * np.log(cb) - 0.02 * vix
    )
    close = pd.Series(np.exp(log_price[usable]), index=calendar[usable], name=BENCHMARK_KEY)
    factors = {
        "real_yield_10y": real,
        "dollar_index": dxy,
        "central_bank": cb,
        "vix": vix,
    }
    return factors, close


def _sabotage(series: pd.Series, cutoff: pd.Timestamp) -> pd.Series:
    sabotaged = series.copy()
    future = sabotaged.index > cutoff
    if future.any():
        sabotaged.loc[future] = [
            1e9 if index % 2 else -1e9 for index in range(int(future.sum()))
        ]
    return sabotaged


def test_blocks_sum_to_the_market_price_exactly(panel):
    factors, close = panel

    result = decompose.decompose_latest(factors, close)

    assert result.status == decompose.STATUS_OK
    by_key = {block.key: block for block in result.blocks}
    total = sum(by_key[key].usd for key in ("anchor", "demand", "risk", "residual"))
    assert total == pytest.approx(result.market_price, rel=1e-9)
    fair = sum(by_key[key].usd for key in ("anchor", "demand", "risk"))
    assert fair == pytest.approx(result.fair_value, rel=1e-9)
    assert by_key["residual"].usd == pytest.approx(
        result.market_price - result.fair_value, rel=1e-9
    )


def test_deviation_is_market_against_fair_value(panel):
    factors, close = panel

    result = decompose.decompose_latest(factors, close)

    assert result.deviation_pct == pytest.approx(
        result.market_price / result.fair_value - 1.0, rel=1e-9
    )


def test_known_answer_recovers_a_near_perfect_fit(calendar):
    factors, close = _known_answer_panel(calendar)

    result = decompose.decompose_latest(factors, close)

    assert result.status == decompose.STATUS_OK
    assert result.r2 == pytest.approx(1.0, abs=1e-9)
    assert result.deviation_pct == pytest.approx(0.0, abs=1e-6)
    assert result.samples > decompose.MIN_DECOMPOSE_SAMPLES


def test_latest_ignores_everything_after_as_of(calendar, make_panel):
    factors, close = make_panel(calendar)
    cutoff = calendar[860]

    reference = decompose.decompose_latest(factors, close, as_of=cutoff.date())
    sabotaged_factors = {key: _sabotage(series, cutoff) for key, series in factors.items()}
    sabotaged = decompose.decompose_latest(
        sabotaged_factors, _sabotage(close, cutoff), as_of=cutoff.date()
    )

    assert sabotaged.to_dict() == reference.to_dict()


def test_insufficient_history_is_unavailable(calendar, make_panel):
    factors, close = make_panel(calendar[:100])

    result = decompose.decompose_latest(factors, close)

    assert result.status == decompose.STATUS_UNAVAILABLE
    assert "样本" in result.reason
    assert result.fair_value is None


def test_missing_regressor_is_unavailable_with_its_name(panel):
    factors, close = panel
    factors.pop("central_bank")

    result = decompose.decompose_latest(factors, close)

    assert result.status == decompose.STATUS_UNAVAILABLE
    assert "央行" in result.reason
    assert result.blocks == ()


def test_out_of_support_values_are_refused_not_extrapolated(calendar, make_panel):
    """拟合窗口没见过的取值：拒答并点名，而不是 ``exp()`` 外推出一个像数字的东西。

    盯的是真实缺陷：``expm1(β·(x − x̄))`` 无界时溢出成 inf（VIX 尖峰足以触发），
    inf 一旦进了溢价，「中枢 + 需求 + 风险 + 残差 = 市场价」这条恒等式也就失去意义。
    """
    factors, close = make_panel(calendar)
    spiked = factors["vix"].copy()
    spiked.iloc[-1] = float(spiked.median()) + 400.0
    probed = dict(factors, vix=spiked)

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        frame = decompose.decompose_frame(probed, close)
        result = decompose.decompose_latest(probed, close)

    assert result.status == decompose.STATUS_UNAVAILABLE
    assert "VIX" in result.reason
    assert "支撑范围" in result.reason
    assert result.fair_value is None
    assert result.blocks == ()
    assert frame["unsupported_by"].iloc[-1] == "vix"
    for column in ("fair_value", "center", "demand_premium", "risk_premium", "residual"):
        values = frame[column].dropna().to_numpy(dtype="float64")
        assert np.isfinite(values).all(), column

def test_stale_regressor_refuses_the_decomposition_instead_of_reusing_it(calendar, make_panel):
    """分解的回归量断更超过新鲜度上限时不给公允价 —— 长尺度主输出更不能吃陈旧值。

    `central_bank` 是月度序列（上限 62 天）：删掉最后 90 天后，无界前向填充会拿
    三个月前的储备继续算「需求溢价」，而四层分解正是 250 日尺度的主输出。
    变异验证：把 `_regressor_frame` 换回 `series.reindex(calendar).ffill()`，
    第一条断言必红（会照常给出公允价）。
    """
    factors, close = make_panel(calendar)
    ok = decompose.decompose_latest(factors, close)
    assert ok.status == decompose.STATUS_OK

    stale = dict(factors, central_bank=factors["central_bank"].iloc[:-90])

    result = decompose.decompose_latest(stale, close)

    assert result.status == decompose.STATUS_UNAVAILABLE
    assert "央行" in result.reason
    assert "新鲜度" in result.reason
    assert result.fair_value is None
    assert result.blocks == ()
    # 上限之内仍照常工作：证明判定不是「月度序列一律拒绝」
    mild = dict(factors, central_bank=factors["central_bank"].iloc[:-10])
    assert decompose.decompose_latest(mild, close).status == decompose.STATUS_OK

