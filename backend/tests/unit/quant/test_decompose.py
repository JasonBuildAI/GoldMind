"""四层分解：恒等式、无前视、降级与已知答案。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import decompose
from app.services.quant.definitions import BENCHMARK_KEY


def _known_answer_panel(calendar):
    """精确线性关系：log(price) = 2 + 0.2·real − 0.1·log(dxy) + 0.3·log(cb) − 0.02·vix。"""
    rng = np.random.default_rng(5)
    real = pd.Series(np.cumsum(rng.normal(0.0, 0.02, len(calendar))) + 1.5, index=calendar)
    dxy = pd.Series(
        np.exp(np.cumsum(rng.normal(0.0, 0.005, len(calendar))) + np.log(100.0)), index=calendar
    )
    cb = pd.Series(
        np.exp(np.cumsum(rng.normal(0.0, 0.002, len(calendar))) + np.log(7000.0)), index=calendar
    )
    vix = pd.Series(np.cumsum(rng.normal(0.0, 0.1, len(calendar))) + 18.0, index=calendar)

    log_price = 2.0 + 0.2 * real - 0.1 * np.log(dxy) + 0.3 * np.log(cb) - 0.02 * vix
    close = pd.Series(np.exp(log_price), index=calendar, name=BENCHMARK_KEY)
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
