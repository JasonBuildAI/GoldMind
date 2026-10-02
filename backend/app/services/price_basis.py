"""价格口径（basis）—— 全项目唯一的三个口径名、中文标签与折算入口。

同一个「金价」在产品里出现在三个位置，口径并不相同：

- ``realtime``：行情里的实时报价，来自腾讯 / 新浪 / 东方财富（盘中会变动）；
- ``close``：日收盘序列，量化基准、回测与统计窗口都用它；
- ``quant_basis``：量化预测里的基准价，取的就是 ``close`` 序列的最后一点，
  目标价、区间与情景全部由它派生。

前端要逐处标注、数据体检要拿实时报价与收盘对账，所以口径名只在这里定义一次。
新增口径必须先加进 ``LABELS``，否则界面会显示生 id。
"""
from __future__ import annotations

from typing import Any, Optional

REALTIME = "realtime"
CLOSE = "close"
QUANT = "quant_basis"

LABELS = {
    REALTIME: "实时报价",
    CLOSE: "日收盘",
    QUANT: "量化基准",
}

# 实时报价的提供方短 id（与 realtime_price 的 source 字段一致）。
# 其它取值（例如 database）都意味着上游实时源没拿到，退回的是收盘口径。
REALTIME_SOURCES = frozenset({"tencent", "sina", "eastmoney"})


def label(basis: str) -> str:
    """口径的中文标签；未知口径原样返回，不猜也不编。"""
    return LABELS.get(basis, basis)


def realtime_basis(
    quote: Optional[dict[str, Any]], *, force_realtime: bool = False
) -> dict[str, Any]:
    """把一路行情返回结构折算成 basis / basis_label / source / as_of。

    ``realtime_price`` 在三个实时源都失败时会退回数据库最新收盘，并用
    ``source=database`` 标明 —— 那条不是实时报价，必须按日收盘口径展示。
    """
    if not quote:
        return {}
    source = str(quote.get("source") or "")
    # force_realtime：调用点已经确认这一路只在真拿到上游数据时才存在
    # （例如美元指数接口），此时 source 是人可读的中文名、没有短 id。
    basis = REALTIME if (force_realtime or source in REALTIME_SOURCES) else CLOSE
    return {
        "basis": basis,
        "basis_label": label(basis),
        "source": quote.get("source_name") or source or None,
        "as_of": quote.get("date") or quote.get("updated_at") or None,
    }
