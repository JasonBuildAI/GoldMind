"""M 族：walk-forward Ridge 的走查纪律、可学习性与研究台接线。

判据（评审整改 spec R4）：M 族在假面板上产出与基线不同的分数，且不使用未来数据 ——
后半条由「改坏未来、早段预测逐点不变」的守卫钉住。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.quant import backtest, engine, multivariate
from scripts import quant_lab


def _known_answer_panel(*, periods: int = 1200, slope: float = 3.0, seed: int = 5):
    """y_t = slope·x_t + eps 的确定性 DGP：价格由 y 反推，答案已知。"""
    index = pd.bdate_range("2019-01-01", periods=periods, freq="B")
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, periods)
    y = slope * x + rng.normal(0.0, 0.15, periods)
    close = pd.Series(100.0 * np.cumprod(1.0 + np.concatenate([[0.0], y[:-1]])), index=index)
    signals = pd.DataFrame(
        {
            "informative": x,
            "noise_a": rng.normal(0.0, 1.0, periods),
            "noise_b": rng.normal(0.0, 1.0, periods),
        },
        index=index,
    )
    return signals, close, pd.Series(y, index=index)


def test_ridge_learns_the_known_linear_relation():
    signals, close, y = _known_answer_panel()

    expected = multivariate.walk_forward_ridge(signals, close, horizon=1)

    valid = expected.notna()
    assert int(valid.sum()) > 1000
    correlation = float(np.corrcoef(expected[valid], y[valid])[0, 1])
    assert correlation > 0.8, f"走查 Ridge 没学到已知关系：corr={correlation:.3f}"


def test_stronger_alpha_shrinks_the_prediction_dispersion():
    signals, close, _ = _known_answer_panel()

    weak = multivariate.walk_forward_ridge(signals, close, horizon=1, alpha=0.01)
    strong = multivariate.walk_forward_ridge(signals, close, horizon=1, alpha=1000.0)

    valid = weak.notna() & strong.notna()
    assert float(strong[valid].std()) < 0.8 * float(weak[valid].std())


def test_predictions_use_only_realized_pairs(make_panel):
    calendar = pd.date_range("2019-01-01", "2026-09-30", freq="B")
    factors, close = make_panel(calendar)
    horizon = 5
    cut = 700

    def expected_for(factor_map, price):
        signals = engine.build_signals(
            engine.align_factors(factor_map, price.index), price.index
        )
        return multivariate.walk_forward_ridge(signals, price, horizon=horizon)

    baseline = expected_for(factors, close)
    mutated_factors = {key: series.copy() for key, series in factors.items()}
    for series in mutated_factors.values():
        series.iloc[cut + 1 :] = series.iloc[cut + 1 :] * 3.0
    mutated_close = close.copy()
    mutated_close.iloc[cut + 1 :] = mutated_close.iloc[cut + 1 :] * 3.0
    mutated = expected_for(mutated_factors, mutated_close)

    head = baseline.iloc[: cut + 1]
    assert int(head.notna().sum()) > 100, "早段没有足够预测，守卫会假绿"
    pd.testing.assert_series_equal(head, mutated.iloc[: cut + 1])
    assert not baseline.iloc[cut + 1 :].equals(mutated.iloc[cut + 1 :]), (
        "未来被改坏却没有影响后段预测，说明改动没生效，这个守卫什么都守不住"
    )


def test_warmup_stays_nan_until_enough_realized_pairs():
    signals, close, _ = _known_answer_panel()

    expected = multivariate.walk_forward_ridge(
        signals, close, horizon=5, min_train_pairs=60
    )

    assert expected.iloc[:64].isna().all()
    assert pd.notna(expected.iloc[100])


def test_m_candidates_run_through_the_lab_and_differ_from_b0(make_panel, monkeypatch):
    monkeypatch.setattr(backtest, "BOOTSTRAP_DRAWS", 25)
    calendar = pd.date_range("2019-01-01", "2026-09-30", freq="B")
    factors, close = make_panel(calendar)
    subset = tuple(quant_lab.CANDIDATES_BY_KEY[key] for key in ("B0", "M1"))

    rows = quant_lab.run_lab(factors, close, horizons=(20,), candidates=subset)

    holdout = {row["candidate"]: row for row in rows if row["period"] == "holdout"}
    assert holdout["B0"]["accuracy"] is not None
    assert holdout["M1"]["accuracy"] is not None
    assert holdout["M1"]["accuracy"] != holdout["B0"]["accuracy"], (
        "M 族候选必须真的走 Ridge 分支 —— 与基线逐位相同说明接线没生效"
    )
