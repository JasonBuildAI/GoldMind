"""四层分解：把金价拆成「宏观锚 + 需求溢价 + 风险溢价 + 情绪残差」。

方法论第四节的推荐做法：把价格拆成四块分别判断走向，能解释
「利率涨金价也涨」这类反常现象（2022 年后央行购金改变了定价函数）。

模型（走查式，无前视）::

    log(金价)_t = α + β_锚·X_锚,t + β_需求·X_需求,t + β_风险·X_风险,t + ε_t

  - 系数 (α, β) 在 t 时刻只用 ``s ≤ t−1`` 的已实现样本拟合（扩展窗口）；
  - X_锚 = [10Y 实际利率, log(美元指数)]，X_需求 = log(央行储备)，
    X_风险 = VIX 水平；
  - 展示口径：
      中枢   = exp(α + β_锚·X_锚,t + β_需求·x̄_需求 + β_风险·x̄_风险)
               （需求与避险取拟合窗口均值、宏观锚取当前值）
      需求溢价 = 中枢 × (exp(β_需求·(X_需求,t − x̄_需求)) − 1)
      风险溢价 = (中枢 + 需求溢价) × (exp(β_风险·(X_风险,t − x̄_风险)) − 1)
      公允价  = 中枢 + 需求溢价 + 风险溢价（链式相乘后恒等于 exp(α + β·X_t)）
      情绪残差 = 市场价 − 公允价（残差越宽，说明模型外因素在定价）

恒等式 ``中枢 + 需求溢价 + 风险溢价 + 情绪残差 = 市场价`` 按定义成立，有测试钉住；
把实现改成做空头样本的「全样本拟合」会被未来的垃圾数据打红（no-lookahead 测试）。

当前取值落在拟合窗口的支撑范围之外时，这一行**不给数**（``unavailable`` + 是哪个回归量），
而不是把指数外推成一个看起来像数字的东西。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from app.services.quant import engine
from app.services.quant.definitions import factor_by_key

# 水平回归至少要有这么多个已实现样本，否则返回「不可用 + 原因」
MIN_DECOMPOSE_SAMPLES = 120
# 支撑范围：溢价是 ``exp(β·(x − x̄))``，把拟合窗口没覆盖过的取值指数外推，
# 得到的就不是「溢价」而是一个没法解释的天文数字（vix 尖峰会真的把 expm1 打到 inf）。
# 判据用该回归量**自己**在拟合窗口内的散布，不引入魔数：偏离超过 6 个标准差即视为外推；
# 另有一条 β 兜底，防止共线解出的巨大系数把指数推到溢出。
MAX_SUPPORT_SIGMAS = 6.0
MAX_LOG_PREMIUM = 12.0


@dataclass(frozen=True)
class RegressorSpec:
    key: str
    transform: str  # "level" / "log"
    block: str  # "anchor" / "demand" / "risk"

    @property
    def max_age_days(self) -> int:
        """新鲜度上限沿用因子表的定义，不在这里抄第二份。"""
        return factor_by_key[self.key].max_age_days

    @property
    def publication_lag_days(self) -> int:
        """发布滞后同样沿用因子表定义：分解与信号用同一套可见性口径。"""
        return factor_by_key[self.key].publication_lag_days


REGRESSORS: tuple[RegressorSpec, ...] = (
    RegressorSpec("real_yield_10y", "level", "anchor"),
    RegressorSpec("dollar_index", "log", "anchor"),
    RegressorSpec("central_bank", "log", "demand"),
    RegressorSpec("vix", "level", "risk"),
)

BLOCK_NAMES = {
    "anchor": "宏观锚（实际利率 + 美元）",
    "demand": "需求结构（央行购金）",
    "risk": "风险溢价（VIX）",
    "residual": "情绪残差",
}

STATUS_OK = "ok"
STATUS_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class BlockValue:
    key: str
    name: str
    usd: Optional[float]
    share_pct: Optional[float]
    drivers: tuple[dict, ...]

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "name": self.name,
            "usd": self.usd,
            "share_pct": self.share_pct,
            "drivers": list(self.drivers),
        }


@dataclass(frozen=True)
class Decomposition:
    status: str
    reason: Optional[str]
    as_of: Optional[date]
    market_price: Optional[float]
    fair_value: Optional[float]
    deviation_pct: Optional[float]
    r2: Optional[float]
    samples: int
    blocks: tuple[BlockValue, ...]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "reason": self.reason,
            "as_of": self.as_of.isoformat() if self.as_of else None,
            "market_price": self.market_price,
            "fair_value": self.fair_value,
            "deviation_pct": self.deviation_pct,
            "r2": self.r2,
            "samples": self.samples,
            "blocks": [block.to_dict() for block in self.blocks],
        }


def _regressor_frame(factors: dict[str, pd.Series], calendar: pd.DatetimeIndex) -> pd.DataFrame:
    """把回归量对齐到价格日历；缺任一列都会让该行不可用（不补默认值）。

    对齐必须走 `engine.align_series`：它按该因子的 `max_age_days` 停止前向填充。
    分解用的四个回归量里 `central_bank` 是月度序列（上限 62 天），无界 ffill 会让
    「央行三个月没更新」照常参与公允价 —— 而四层分解正是长尺度的主输出，
    拿陈旧水位算出的「公允价值偏离」比没有这个数更有害（同一个缺陷在信号层已修）。
    """
    columns: dict[str, pd.Series] = {}
    for spec in REGRESSORS:
        series = factors.get(spec.key)
        if series is None or series.empty:
            continue
        aligned = engine.align_series(
            series,
            calendar,
            max_age_days=spec.max_age_days,
            publication_lag_days=spec.publication_lag_days,
        )
        if spec.transform == "log":
            aligned = np.log(aligned.where(aligned > 0))
        columns[spec.key] = aligned.astype("float64")
    return pd.DataFrame(columns, index=calendar)


def decompose_frame(factors: dict[str, pd.Series], close: pd.Series) -> pd.DataFrame:
    """逐日的四层分解（向量化累计矩 + 逐步求解 5×5 正规方程）。"""
    frame = pd.DataFrame(index=close.index)
    if close is None or close.empty:
        return frame

    x = _regressor_frame(factors, close.index)
    keys = [spec.key for spec in REGRESSORS]
    if not set(keys).issubset(x.columns):
        return frame  # 缺回归量：整体不可用，由 latest 层给出原因

    y = np.log(close.astype("float64").where(close > 0))
    design = np.column_stack([np.ones(len(close)), x[keys].to_numpy(dtype="float64")])
    y_values = y.to_numpy(dtype="float64")
    valid = np.isfinite(y_values) & np.all(np.isfinite(design), axis=1)

    masked_x = np.where(valid[:, None], design, 0.0)
    masked_y = np.where(valid, y_values, 0.0)
    cum_n = np.cumsum(valid)
    cum_sxx = np.cumsum(masked_x[:, :, None] * masked_x[:, None, :], axis=0)
    cum_sxy = np.cumsum(masked_x * masked_y[:, None], axis=0)
    cum_sy = np.cumsum(masked_y)
    cum_syy = np.cumsum(np.where(valid, y_values * y_values, 0.0))

    rows = len(close)
    fair = np.full(rows, np.nan)
    center = np.full(rows, np.nan)
    demand_premium = np.full(rows, np.nan)
    risk_premium = np.full(rows, np.nan)
    residual = np.full(rows, np.nan)
    deviation = np.full(rows, np.nan)
    r_squared = np.full(rows, np.nan)
    samples = np.zeros(rows, dtype="int64")
    unsupported: list[Optional[str]] = [None] * rows
    driver_logs = {key: np.full(rows, np.nan) for key in ("real_yield_10y", "dollar_index")}

    demand_index = 1 + keys.index("central_bank")
    risk_index = 1 + keys.index("vix")
    # 锚块包含 real_yield 与 log(dollar)，两个系数
    anchor_indices = [1 + keys.index(key) for key in ("real_yield_10y", "dollar_index")]

    for position in range(rows):
        fit_rows = position  # 只用 s ≤ t−1
        count = int(cum_n[fit_rows - 1]) if fit_rows >= 1 else 0
        samples[position] = count
        if count < MIN_DECOMPOSE_SAMPLES or not valid[position]:
            continue

        sxx = cum_sxx[fit_rows - 1]
        sxy = cum_sxy[fit_rows - 1]
        try:
            beta = np.linalg.solve(sxx, sxy)
        except np.linalg.LinAlgError:
            continue

        mean = np.concatenate([[1.0], (sxx[1:, 0] / count)])
        current = design[position]
        spread = np.sqrt(np.clip(np.diag(sxx)[1:] / count - mean[1:] ** 2, 0.0, None))
        deviations = current[1:] - mean[1:]
        violation = next(
            (
                spec.key
                for index, spec in enumerate(REGRESSORS)
                if abs(deviations[index]) > MAX_SUPPORT_SIGMAS * spread[index]
                or abs(beta[1 + index] * deviations[index]) > MAX_LOG_PREMIUM
            ),
            None,
        )
        if violation is not None:
            # 外推越远，exp() 越大方：这一行不是「溢价很大」，是「模型没看过这种取值」。
            unsupported[position] = violation
            continue
        log_center = float(
            beta[0]
            + sum(beta[index] * current[index] for index in anchor_indices)
            + beta[demand_index] * mean[demand_index]
            + beta[risk_index] * mean[risk_index]
        )
        center_value = float(np.exp(log_center))
        demand_factor = float(
            np.exp(beta[demand_index] * (current[demand_index] - mean[demand_index]))
        )
        demand_value = center_value * (demand_factor - 1.0)
        risk_base = center_value * demand_factor
        risk_value = risk_base * float(
            np.expm1(beta[risk_index] * (current[risk_index] - mean[risk_index]))
        )
        # 链式口径：三块相加按构造成立，且望远镜相乘后等于 exp(α + β·X_t)
        fair_value = center_value + demand_value + risk_value
        driver_logs["real_yield_10y"][position] = beta[anchor_indices[0]] * (
            current[anchor_indices[0]] - mean[anchor_indices[0]]
        )
        driver_logs["dollar_index"][position] = beta[anchor_indices[1]] * (
            current[anchor_indices[1]] - mean[anchor_indices[1]]
        )

        market = float(np.exp(y_values[position]))
        fair[position] = fair_value
        center[position] = center_value
        demand_premium[position] = demand_value
        risk_premium[position] = risk_value
        residual[position] = market - fair_value
        deviation[position] = market / fair_value - 1.0 if fair_value > 0 else np.nan

        sy = cum_sy[fit_rows - 1]
        syy = cum_syy[fit_rows - 1]
        sse = max(syy - 2.0 * float(beta @ sxy) + float(beta @ (sxx @ beta)), 0.0)
        sst = syy - sy * sy / count
        if sst > 0:
            r_squared[position] = 1.0 - sse / sst

    frame["market_price"] = close.astype("float64")
    frame["fair_value"] = fair
    frame["center"] = center
    frame["demand_premium"] = demand_premium
    frame["risk_premium"] = risk_premium
    frame["residual"] = residual
    frame["deviation_pct"] = deviation
    frame["r2"] = r_squared
    frame["samples"] = samples
    frame["unsupported_by"] = unsupported
    for key, values in driver_logs.items():
        frame[f"driver_{key}"] = values
    return frame


def _position_of(calendar: pd.DatetimeIndex, as_of: Optional[date]) -> int:
    if as_of is None:
        return len(calendar) - 1
    target = pd.Timestamp(as_of)
    position = int(calendar.searchsorted(target, side="right")) - 1
    return max(position, 0)


def _block_payload(
    key: str,
    usd: Optional[float],
    market: Optional[float],
    drivers: tuple[dict, ...],
) -> BlockValue:
    share = None
    if usd is not None and market:
        share = usd / market * 100.0
    return BlockValue(key=key, name=BLOCK_NAMES[key], usd=usd, share_pct=share, drivers=drivers)


def decompose_latest(
    factors: dict[str, pd.Series],
    close: pd.Series,
    *,
    as_of: Optional[date] = None,
) -> Decomposition:
    """最新一行的四层分解；算不出来就返回不可用 + 原因。"""
    missing = [spec.key for spec in REGRESSORS if spec.key not in factors or factors[spec.key].empty]
    if close is None or close.empty:
        return Decomposition(STATUS_UNAVAILABLE, "缺少黄金价格序列", None, None, None, None, None, 0, ())
    if missing:
        names = [factor_by_key[key].name if key in factor_by_key else key for key in missing]
        return Decomposition(
            STATUS_UNAVAILABLE,
            "缺少回归量：" + "、".join(names),
            None, None, None, None, None, 0, (),
        )

    x = _regressor_frame(factors, close.index)
    frame = decompose_frame(factors, close)
    position = _position_of(close.index, as_of)
    row = frame.iloc[position]
    violation = row.get("unsupported_by")
    if isinstance(violation, str) and violation:
        name = factor_by_key[violation].name if violation in factor_by_key else violation
        return Decomposition(
            STATUS_UNAVAILABLE,
            f"当前{name}的取值超出拟合窗口的支撑范围（{int(row['samples'])} 组样本），"
            "四层分解不外推，因此不给公允价",
            close.index[position].date(),
            float(row["market_price"]),
            None, None, None, int(row["samples"]), (),
        )
    if pd.isna(row["fair_value"]) or pd.isna(row["residual"]):
        count = int(row["samples"]) if "samples" in row and pd.notna(row["samples"]) else 0
        as_of = close.index[position].date()
        missing = [
            spec.key
            for spec in REGRESSORS
            if spec.key in x.columns and pd.isna(x.at[close.index[position], spec.key])
        ]
        if missing and count >= MIN_DECOMPOSE_SAMPLES:
            names = "、".join(factor_by_key[key].name for key in missing)
            return Decomposition(
                STATUS_UNAVAILABLE,
                f"{names} 在该日已超过新鲜度上限（数据源没有新观测），四层分解不外推陈旧值",
                as_of,
                float(row["market_price"]),
                None, None, None, count, (),
            )
        return Decomposition(
            STATUS_UNAVAILABLE,
            f"已实现样本只有 {count} 组（至少需要 {MIN_DECOMPOSE_SAMPLES} 组）",
            as_of, None, None, None, None, count, (),
        )

    market = float(row["market_price"])
    drivers_anchor = tuple(
        {
            "key": key,
            "name": factor_by_key[key].name,
            "log_contribution": float(row[f"driver_{key}"]) if f"driver_{key}" in row else None,
        }
        for key in ("real_yield_10y", "dollar_index")
    )
    blocks = (
        _block_payload("anchor", float(row["center"]), market, drivers_anchor),
        _block_payload("demand", float(row["demand_premium"]), market, (
            {"key": "central_bank", "name": factor_by_key["central_bank"].name},
        )),
        _block_payload("risk", float(row["risk_premium"]), market, (
            {"key": "vix", "name": factor_by_key["vix"].name},
        )),
        _block_payload("residual", float(row["residual"]), market, ()),
    )
    return Decomposition(
        STATUS_OK,
        None,
        close.index[position].date(),
        market,
        float(row["fair_value"]),
        float(row["deviation_pct"]),
        float(row["r2"]) if pd.notna(row["r2"]) else None,
        int(row["samples"]),
        blocks,
    )


__all__ = [
    "BLOCK_NAMES",
    "Decomposition",
    "MAX_LOG_PREMIUM",
    "MAX_SUPPORT_SIGMAS",
    "MIN_DECOMPOSE_SAMPLES",
    "REGRESSORS",
    "decompose_frame",
    "decompose_latest",
]
