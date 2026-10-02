"""分布校准：非对称经验分位 + ACI 把覆盖率拉回名义值。

变异验证（见 commit 前的验证记录）：
- 把 ``ACI_GAMMA`` 置 0（去掉自适应）→ ACI 两条断言必红；
- 把区间改回 μ ± 1.2816σ → 波动换挡下的覆盖率断言必红。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import engine
from app.services.quant.definitions import HORIZON_SPECS


def _ratio(values) -> pd.Series:
    return pd.Series(values, index=pd.date_range("2020-01-01", periods=len(values), freq="B"))


def _calibrate(values, **kwargs):
    """跑一次校准分布；``flat_z`` 取 0（即「期望收益恰好等于 0」的位置）。"""
    ratio = _ratio(values)
    return engine.calibrate_distribution(ratio, _ratio(np.zeros(len(values))), **kwargs)


def test_interval_factors_are_asymmetric_for_skewed_errors():
    rng = np.random.default_rng(4)
    values = np.concatenate([rng.normal(0.0, 1.0, 350), rng.normal(3.0, 1.0, 150)])

    calibration = _calibrate(values, min_samples=60)
    lower = float(calibration["lower"].iloc[-1])
    upper = float(calibration["upper"].iloc[-1])

    assert lower < 0.0 < upper
    assert upper > abs(lower) * 1.2, "右偏误差的上界必须比下界离 0 更远"


def test_aci_widens_the_interval_after_a_volatility_jump():
    calm = np.random.default_rng(1).normal(0.0, 1.0, 300)
    wild = np.random.default_rng(2).normal(0.0, 8.0, 300)

    calibration = _calibrate(np.concatenate([calm, wild]), min_samples=60)

    assert float(calibration["alpha"].iloc[-1]) < 0.10, "连续落在区间外时 α 必须显著调小"
    width = float(calibration["upper"].iloc[-1]) - float(calibration["lower"].iloc[-1])
    assert width > 5.0, "波动换挡后区间必须变宽"


def test_aci_narrows_the_interval_when_errors_stay_inside():
    quiet = np.random.default_rng(9).normal(0.0, 0.05, 300)
    history = np.concatenate([np.random.default_rng(8).normal(0.0, 1.0, 200), quiet])

    calibration = _calibrate(history, min_samples=60)

    assert float(calibration["alpha"].iloc[-1]) > 0.25, "长期命中时 α 必须调大（区间收紧）"


def test_calibrated_bounds_beat_the_normal_interval_after_a_volatility_shift():
    horizon = 1
    calendar = pd.date_range("2019-01-01", "2026-09-30", freq="B")
    rng = np.random.default_rng(2026)
    regime = np.where(np.arange(len(calendar)) < 1200, 0.0004, 0.0016)
    returns = rng.normal(0.0, 1.0, len(calendar)) * regime
    close = pd.Series(2000.0 * np.cumprod(1.0 + returns), index=calendar)
    score = pd.Series(rng.normal(0.0, 1.0, len(calendar)), index=calendar)

    frame = engine.build_prediction_frame(score, close, horizon)
    forward = close.shift(-horizon) / close - 1.0
    mu = frame["expected_return"]
    sigma = (forward - mu).shift(horizon).expanding(min_periods=engine.MIN_ERRORS_FOR_SIGMA).std()
    valid = (
        mu.notna()
        & forward.notna()
        & frame["lower_return"].notna()
        & frame["upper_return"].notna()
        & sigma.notna()
    )
    tail = valid[valid].index[-250:]
    assert len(tail) >= 100

    calibrated = (
        (forward >= frame["lower_return"]) & (forward <= frame["upper_return"])
    )[tail].mean()
    vanilla = (
        (forward >= mu - engine.INTERVAL_Z_80 * sigma)
        & (forward <= mu + engine.INTERVAL_Z_80 * sigma)
    )[tail].mean()

    assert calibrated > vanilla + 0.05, f"校准={calibrated:.3f} 没有比正态区间={vanilla:.3f} 更接近名义值"
    assert calibrated > 0.60


def test_every_horizon_declares_a_headline():
    assert all(spec.headline for spec in HORIZON_SPECS)
    long_spec = next(spec for spec in HORIZON_SPECS if spec.horizon == 250)
    assert "公允价值" in long_spec.headline
    assert "区间" in long_spec.headline
    assert "区间" in next(spec for spec in HORIZON_SPECS if spec.horizon == 1).headline

def test_probability_and_bounds_come_from_one_distribution():
    """上行概率必须与分位数问同一张分布：p_up = 1 - 经验分布(flat_z) 之上的比例。

    变异验证：把 probability_up 换回 Φ(μ/σ)，右偏样本上的这条必红。
    """
    rng = np.random.default_rng(4)
    values = np.concatenate([rng.normal(0.0, 1.0, 350), rng.normal(3.0, 1.0, 150)])
    ratio = _ratio(values)

    def probe(point: float):
        # gamma=0 → α 不漂移；half_life/window 关掉 → 经验分布就是这批样本本身
        return engine.calibrate_distribution(
            ratio,
            _ratio(np.full(len(values), point)),
            min_samples=60,
            gamma=0.0,
            half_life=None,
            window=None,
        )

    last = probe(0.0).iloc[-1]
    # 第 -1 行用的是「它之前」的样本（history 在本行算完才 append），所以对比 values[:-1]
    sample = values[:-1]
    assert float(last["lower"]) == pytest.approx(float(np.quantile(sample, 0.10)), abs=0.05)
    assert float(last["upper"]) == pytest.approx(float(np.quantile(sample, 0.90)), abs=0.05)
    assert last["lower"] < last["q25"] < last["q75"] < last["upper"]
    for point in (-2.0, 0.0, 2.0):
        manual = float((sample > point).mean())
        assert float(probe(point).iloc[-1]["probability_up"]) == pytest.approx(
            manual, abs=1.0 / len(sample)
        )
    # flat_z 越靠右，上行概率越小：概率与分位问的是同一个分布，不是两条曲线
    tails = [float(probe(point).iloc[-1]["probability_up"]) for point in (-2.0, 0.0, 2.0)]
    assert tails == sorted(tails, reverse=True)
