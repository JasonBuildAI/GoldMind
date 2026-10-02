"""ACI 的自适应必须判「自己当时发出的那条区间」，不是判现在这条。

``ratio``（studentized 误差）传进 ``calibrate_distribution`` 时已经按实现时间右移过：
第 t 行那条误差属于 ``t - horizon`` 行发出的那一注。拿第 t 行**现在**的区间去判它，
等于让 α 反应在它自己没发过的区间上 —— 尺度越长偏得越多，而且是往「覆盖不足」的方向偏
（26 年面板开发期实测：20 日 0.767 → 0.791、60 日 0.726 → 0.742，见 spec 第二轮 §六）。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import engine

GAMMA = 0.05
TARGET = 0.20
LAG = 20


def _regime_shifting_errors() -> np.ndarray:
    """60 行一换的平静 / 动荡交替 —— 让「当时那条区间」和「现在这条区间」经常不同。"""
    rng = np.random.default_rng(2)
    return np.concatenate(
        [rng.normal(0.0, 0.5 if block % 2 == 0 else 6.0, 60) for block in range(12)]
    )


def _calibrate(values: np.ndarray, issued_lag: int) -> pd.DataFrame:
    index = pd.date_range("2020-01-01", periods=len(values), freq="B")
    return engine.calibrate_distribution(
        pd.Series(values, index=index),
        pd.Series(np.zeros(len(values)), index=index),
        gamma=GAMMA,
        half_life=30,
        window=None,
        min_samples=40,
        issued_lag=issued_lag,
    )


def _implied_misses(
    calibration: pd.DataFrame, *, gamma: float = GAMMA, target: float = TARGET
) -> list[tuple[int, float]]:
    """从 α 的逐步变化反推引擎当时判出的 miss（被 α 上下限截断的那些步跳过）。"""
    alpha = calibration["alpha"].to_numpy()
    steps: list[tuple[int, float]] = []
    for position in range(1, len(alpha)):
        if not (np.isfinite(alpha[position]) and np.isfinite(alpha[position - 1])):
            continue
        implied = target - (alpha[position] - alpha[position - 1]) / gamma
        if abs(implied) < 1e-9 or abs(implied - 1.0) < 1e-9:
            steps.append((position - 1, implied))  # 这一步判的是前一行的那一注
    return steps


@pytest.mark.unit
def test_alpha_updates_from_the_band_that_was_in_force_at_issue_time():
    values = _regime_shifting_errors()
    calibration = _calibrate(values, LAG)
    lower = calibration["lower"].to_numpy()
    upper = calibration["upper"].to_numpy()
    steps = _implied_misses(calibration)

    lagged_hits = current_hits = differing = 0
    for position, implied in steps:
        value = values[position]
        miss_lagged = 1.0 if (value < lower[position - LAG] or value > upper[position - LAG]) else 0.0
        miss_current = 1.0 if (value < lower[position] or value > upper[position]) else 0.0
        lagged_hits += abs(miss_lagged - implied) < 1e-9
        current_hits += abs(miss_current - implied) < 1e-9
        differing += miss_lagged != miss_current

    assert len(steps) > 200 and differing > 20, "构造没有把两种判法分开，测试是空的"
    assert lagged_hits / len(steps) > 0.98, "α 不是在按「当时发出的区间」更新"
    assert current_hits / len(steps) < lagged_hits / len(steps) - 0.05, (
        "α 用的是现在这条区间 —— 那是事后信息，长尺度会把自适应带偏"
    )


@pytest.mark.unit
def test_a_band_that_has_not_been_issued_yet_falls_back_to_the_current_one():
    """预热阶段 ``t - lag`` 那行还没有区间：退回用当前这条，而不是把 α 冻住或抛错。"""
    values = _regime_shifting_errors()

    calibration = _calibrate(values, LAG)
    alpha = calibration["alpha"]

    assert bool(alpha.isna().iloc[:40].all()), "样本不足 40 条之前不该有 α"
    warm = alpha.iloc[40 : 40 + LAG + 5]
    assert warm.notna().all()
    # 退回当前区间时，α 仍然在动（不是一路上限也不是一路下限）
    assert warm.nunique() > 1, "预热段 α 一动不动，多半是更新被跳过了"


@pytest.mark.unit
def test_prediction_frame_keeps_its_walk_forward_coverage_on_the_pre_fix_floor(make_panel):
    """接线守卫：`build_prediction_frame` 必须把 ``issued_lag`` 设成尺度本身。

    这条不靠反推 α，直接钉住**结果**：在同一条确定性合成面板上走查，
    对齐版（issued_lag=horizon）的 80% 区间覆盖率是 20 日 0.790 / 60 日 0.735，
    而退回 issued_lag=0 会变成 0.772 / 0.703 —— 偏的方向正是「覆盖不足」。
    阈值取两者之间：任何把接线改回去的改动都会红。

    变异验证：把 ``issued_lag=horizon`` 改成 0，本测试红（实测 0.772 < 0.78、0.703 < 0.72）。
    """
    factors, close = make_panel(pd.date_range("2006-01-02", "2026-09-30", freq="B"))
    signals = engine.build_signals(factors, close.index)

    floors = {5: 0.77, 20: 0.78, 60: 0.72}
    for horizon, floor in floors.items():
        frame = engine.build_prediction_frame(
            engine.composite_score(signals, horizon=horizon), close, horizon
        )
        forward = close.shift(-horizon) / close - 1.0
        usable = frame["lower_return"].notna() & forward.notna()
        coverage = float(
            (
                (forward[usable] >= frame["lower_return"][usable])
                & (forward[usable] <= frame["upper_return"][usable])
            ).mean()
        )
        assert coverage >= floor, f"{horizon} 日覆盖率 {coverage:.4f} 掉到 {floor} 以下"
