"""GPR 官方日度地缘风险指数（Iacoviello & Papaioannou，自由学术数据）。

来源是官方 .xls 文件，需要 xlrd 解析（已钉进 requirements.txt）。
其中的 GPRD 是日度主序列；它与因子的关系是**只入库、先不入模型** ——
是否进因子集由下一轮预注册决定（见 docs/specs/2026-10-02-量化策略提升路线图.md）。

测试通过注入 get 与假 sheet 对象完成，不出网、不依赖真实文件。
"""
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd

from app.services.quant.sources.base import SourceError, clean_series, default_get

GPR_URL = "https://www.matteoiacoviello.com/gpr_files/data_gpr_daily_recent.xls"
GPR_VALUE_COLUMN = "GPRD"
# 官方文件是 1985 年至今的日度序列（一万多行）；行数明显偏少说明格式变了。
MIN_DATA_ROWS = 1000


def _normalize_day(raw) -> Optional[pd.Timestamp]:
    """DAY 列可能是 'YYYYMMDD' 字符串或数字；解析不了返回 None。"""
    if raw is None:
        return None
    text = str(raw).strip()
    if text.endswith(".0"):
        text = text[:-2]
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return pd.Timestamp(text)
    except ValueError:
        return None


def parse_rows(rows: list[dict]) -> pd.Series:
    """{列名: 值} 行数组 → gpr_daily；坏行跳过，不补值、不插值。"""
    values: dict[pd.Timestamp, float] = {}
    for row in rows or []:
        day = _normalize_day(row.get("DAY"))
        if day is None:
            continue
        try:
            value = float(row.get(GPR_VALUE_COLUMN))
        except (TypeError, ValueError):
            continue
        if pd.isna(value):
            continue
        values[day] = value

    if not values:
        raise SourceError("GPR 数据里没有可解析的 GPRD 行")
    return clean_series(values, name="gpr_daily")


def parse_sheet(sheet) -> pd.Series:
    """把 xlrd 的 sheet 读成行数组再交给 parse_rows。

    单独一层是为了让表头映射与坏行处理可以用假 sheet 单测，
    不必依赖真实 .xls 文件。
    """
    if sheet.nrows < MIN_DATA_ROWS + 1:
        raise SourceError(
            f"GPR .xls 只有 {sheet.nrows} 行，格式可能已变（预期 ≥ {MIN_DATA_ROWS + 1} 行）"
        )
    headers = [str(sheet.cell_value(0, column)).strip() for column in range(sheet.ncols)]
    rows = [
        {headers[column]: sheet.cell_value(row, column) for column in range(sheet.ncols)}
        for row in range(1, sheet.nrows)
    ]
    return parse_rows(rows)


def parse_workbook(content: bytes) -> pd.Series:
    try:
        import xlrd
    except ImportError as exc:  # requirements.txt 已钉住 xlrd；缺失时给出可执行提示
        raise SourceError("解析 GPR .xls 需要 xlrd：pip install -r requirements.txt") from exc
    try:
        book = xlrd.open_workbook(file_contents=content)
    except Exception as exc:
        raise SourceError(f"GPR .xls 解析失败：{type(exc).__name__}: {exc}") from exc
    return parse_sheet(book.sheet_by_index(0))


def fetch(
    *,
    get: Optional[Callable] = None,
    timeout: float = 60.0,
) -> dict[str, pd.Series]:
    http_get = get or default_get
    response = http_get(GPR_URL, timeout=timeout)
    if getattr(response, "status_code", 200) != 200:
        raise SourceError(f"GPR 官方文件抓取失败：HTTP {response.status_code}")
    return {"gpr_daily": parse_workbook(response.content)}

