"""上海黄金交易所 Au99.99 日线（人民币/克）—— 上海金溢价的原始数据。

为什么值得接：SGE 成交价是亚洲实物需求最直接的可核实观察口。它和
「国际金价 × 美元兑人民币 ÷ 31.1035」的折算价之差就是上海金溢价 ——
仪表盘上这一行早就定义好，却一直没有数据源，本轮把它点亮。

接口形状（2026-10-03 实测）::

    GET https://www.sge.com.cn/graph/Dailyhq?instid=Au99.99
    → {"time": [["2016-12-19", 开盘, 最高, 最低, 收盘], ...]}   # 日期升序

- 收盘价取每行第 5 列（索引 4）；
- 行数不足、格式不认、网络失败一律抛 ``SourceError`` —— 不补值、不插值。
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd

from app.services.quant.sources.base import SourceError, clean_series, default_get

SGE_URL = "https://www.sge.com.cn/graph/Dailyhq"
DEFAULT_INSTID = "Au99.99"
SERIES_KEY = "sge_gold"

# 数据自 2016-12-19 起（约 2300+ 行）。低于这个量级说明格式或端点变了，
# 与其存一段残缺历史，不如如实报错。
MIN_DATA_ROWS = 200
CLOSE_INDEX = 4
DATE_INDEX = 0


def parse_payload(payload: Any) -> dict[str, float]:
    """把响应体解析成 ``{日期: 收盘价}``；坏行跳过，绝不填充。"""
    if isinstance(payload, dict):
        rows = payload.get("time") or payload.get("data") or []
    else:
        rows = payload or []
    if not isinstance(rows, list):
        raise SourceError(f"SGE 返回结构不认识：{type(rows).__name__}")

    values: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) <= CLOSE_INDEX:
            continue
        day = str(row[DATE_INDEX] or "").strip()
        try:
            value = float(row[CLOSE_INDEX])
        except (TypeError, ValueError):
            continue
        if day and value > 0:
            values[day] = value

    if len(values) < MIN_DATA_ROWS:
        raise SourceError(
            f"上海黄金交易所只解析出 {len(values)} 行（预期 ≥ {MIN_DATA_ROWS}），格式可能已变"
        )
    return values


def fetch(
    instid: str = DEFAULT_INSTID,
    *,
    get: Callable[..., Any] = default_get,
    timeout: float = 20.0,
) -> dict[str, pd.Series]:
    """抓取并解析 Au99.99 日线；失败抛 ``SourceError``（消息会出现在同步报告里）。"""
    try:
        response = get(SGE_URL, params={"instid": instid}, timeout=timeout)
    except Exception as exc:  # 网络 / 超时
        raise SourceError(f"上海黄金交易所抓取失败：{type(exc).__name__}: {exc}") from exc

    status = getattr(response, "status_code", 200)
    if status != 200:
        raise SourceError(f"上海黄金交易所返回 HTTP {status}")
    try:
        payload = response.json()
    except ValueError as exc:
        raise SourceError("上海黄金交易所返回的不是 JSON") from exc

    series = clean_series(parse_payload(payload), name=SERIES_KEY)
    if series is None or series.empty:
        raise SourceError("上海黄金交易所解析后没有可用观测")
    return {SERIES_KEY: series}
