"""量化预测引擎：把金价的四类影响因素变成可回测的信号。

目录结构：

- ``definitions``  —— 因子与权重的唯一定义处（改因子先改这里）
- ``sources/``     —— 各数据源的抓取与解析（每个源都可注入假客户端，便于测试）
- ``derive``       —— 原始序列 → 因子值（单位与口径在这一层固定）
- ``storage``      —— factor_observations 的读写
- ``sync``         —— 编排：抓取 → 派生 → 落库
- ``engine``       —— 滚动 z 分数、合成得分、概率与目标价
- ``backtest``     —— 走查式回测与基准对比
- ``service``      —— 对 API / 调度器暴露的高层入口

红线（与项目一致）：

1. 不编造数据：源不可用就标记不可用，合成时按可用因子归一，可用因子不足则拒绝出预测。
2. 不用未来数据：所有滚动统计只用 t 之前的数据；收盘后发布的数据源整体平移到次日。
"""

from app.services.quant.definitions import (  # noqa: F401
    BENCHMARK_KEY,
    FACTORS,
    MODEL_VERSION,
    FactorDefinition,
    factor_by_key,
)

__all__ = [
    "BENCHMARK_KEY",
    "FACTORS",
    "MODEL_VERSION",
    "FactorDefinition",
    "factor_by_key",
]
