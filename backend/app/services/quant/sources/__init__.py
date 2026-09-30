"""量化因子数据源。

每个源都是一个小模块，暴露 ``fetch(...)``，返回 ``dict[str, pd.Series]``
（键 = 序列名，值 = 以交易日为索引的浮点序列）。约定：

- 所有函数接受可注入的 HTTP 客户端 / 下载器，测试用假实现，永不真出网；
- 失败时抛 ``SourceError``，由 ``sync`` 逐源捕获并降级；
- 收盘后才会发布的数据（收益率曲线、EFFR、CFTC 持仓）在源内整体平移到
  下一个交易日，保证回测不出现前视。
"""

from app.services.quant.sources.base import SourceError, SourceResult  # noqa: F401

__all__ = ["SourceError", "SourceResult"]
