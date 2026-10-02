"""M 族候选：多因子直接建模（walk-forward Ridge），不动线上口径。

线上 ``quant-v6`` 先用固定权重把因子合成一个得分、再对得分做一元扩展窗口回归；
M 族把这两步并成一步：直接对（标准化后的）因子矩阵做岭回归，回答「先合成再
回归」是不是丢掉了横截面信息。候选定义（M1/M2）注册在
``docs/specs/2026-10-02-量化策略提升路线图.md`` 6.1 与
``docs/specs/2026-10-02-评审整改.md`` R4；M 族只进研究台。

**走查纪律**：预测 t 时刻的期望收益，只用 ``j + horizon ≤ t`` 的已实现样本对
``(X_j, y_j)``；列均值 / 标准差也只用同一段训练样本估计。t 当天的因子值只进
预测、不进拟合 —— 这是 M 族与「全样本一次拟合」的全部区别，也是
``test_multivariate.py::test_predictions_use_only_realized_pairs`` 钉住的东西。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.quant import engine

DEFAULT_ALPHA = 1.0
# 与一元口径同一个暖机阈值（engine.expanding_ols 的 min_samples 默认值）：
# 训练样本对不足就先不给预测，NaN 比「先验 0」诚实。
DEFAULT_MIN_TRAIN_PAIRS = engine.MIN_ERRORS_FOR_SIGMA


def walk_forward_ridge(
    signals: pd.DataFrame,
    close: pd.Series,
    *,
    horizon: int,
    alpha: float = DEFAULT_ALPHA,
    min_train_pairs: int = DEFAULT_MIN_TRAIN_PAIRS,
) -> pd.Series:
    """逐日走查的岭回归期望收益（与 ``close.index`` 对齐；未拟合处为 NaN）。

    ``alpha`` 与 ``sklearn.linear_model.Ridge`` 同口径（标准化后、对 n 归一的目标函数）。
    实现维护增量充分统计量：每加入一个已实现样本对更新一次和式，预测点只做一次
    p×p 求解，不在循环里重算矩阵乘法。
    """
    calendar = close.index
    expected = pd.Series(np.nan, index=calendar, dtype="float64")
    if signals is None or signals.empty:
        return expected
    values = signals.reindex(calendar).to_numpy(dtype="float64")
    forward = (close.shift(-horizon) / close - 1.0).to_numpy(dtype="float64")
    rows, columns = values.shape

    complete = np.isfinite(values).all(axis=1) & np.isfinite(forward)
    sums_x = np.zeros(columns, dtype="float64")
    sums_xx = np.zeros((columns, columns), dtype="float64")
    sums_xy = np.zeros(columns, dtype="float64")
    sum_y = 0.0
    count = 0
    next_pair = 0

    for position in range(rows):
        limit = position - horizon
        while next_pair <= limit:
            if complete[next_pair]:
                row = values[next_pair]
                outcome = forward[next_pair]
                sums_x += row
                sums_xx += np.outer(row, row)
                sums_xy += row * outcome
                sum_y += outcome
                count += 1
            next_pair += 1
        if not complete[position] or count < min_train_pairs:
            continue
        mean_x = sums_x / count
        mean_y = sum_y / count
        centered_xx = sums_xx / count - np.outer(mean_x, mean_x)
        centered_xy = sums_xy / count - mean_x * mean_y
        std = np.sqrt(np.clip(np.diag(centered_xx), 0.0, None))
        std = np.where(std > engine.EPS, std, 1.0)
        correlation = centered_xx / np.outer(std, std)
        rhs = centered_xy / std
        system = correlation + (alpha / count) * np.eye(columns)
        try:
            beta = np.linalg.solve(system, rhs)
        except np.linalg.LinAlgError:  # pragma: no cover - 有岭项时几乎不可能
            beta = np.linalg.pinv(system) @ rhs
        z = (values[position] - mean_x) / std
        expected.iloc[position] = mean_y + float(z @ beta)
    return expected
