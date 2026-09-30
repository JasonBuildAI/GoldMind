"""新浪财经宏观数据：央行黄金和外汇储备（月度，单位万盎司）。

接口是 JSONP 文本（不是严格 JSON），这里用「定界扫描 + json.loads」解析：
先定位 ``count:"N",data:`` 锚点，再对后面的数组做括号配平扫描，只把数组本身
交给 ``json.loads``（数组里全是双引号字符串，是合法 JSON）。

发布节奏：中国人民银行每月 7 日左右公布上月末官方储备资产，
因此报告月的值从**次月 8 日**（遇周末顺延）起可用 —— 回测按这个日期使用，
避免拿「未来才知道」的储备数据去预测过去。
"""
from __future__ import annotations

import json
import re
from typing import Callable, Optional

import pandas as pd

from app.services.quant.sources.base import (
    SourceError,
    business_day_on_or_after,
    clean_series,
    default_get,
)

SINA_URL = "https://quotes.sina.cn/mac/api/jsonp_v3.php/SINAREMOTECALLCALLBACK1601651495761/MacPage_Service.get_pagedata"
# event=5 → 「央行黄金和外汇储备」；数据列见 config.all：
#   [0] 统计时间  [1] 黄金储备（万盎司）  [2] 国家外汇储备（亿美元）
SINA_EVENT = "5"
COUNT_ANCHOR = re.compile(r'count:\s*"(\d+)"\s*,\s*data:')


def _extract_array(text: str, start: int) -> list:
    """从 ``start`` 处的 ``[`` 起做括号配平，返回解析后的数组。"""
    depth = 0
    for index in range(start, len(text)):
        character = text[index]
        if character == "[":
            depth += 1
        elif character == "]":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start : index + 1])
                except ValueError as exc:
                    raise SourceError(f"宏观数据数组不是合法 JSON：{exc}") from exc
    raise SourceError("宏观数据数组没有闭合")


def parse_payload(text: str) -> tuple[int, list[list]]:
    """返回 (总数, 行数组)。行形如 ["2026.8", "7673.00", "34383.25"]。"""
    if not text:
        raise SourceError("新浪宏观接口返回空文本")

    match = COUNT_ANCHOR.search(text)
    if not match:
        raise SourceError("新浪宏观接口没有找到 count/data 段（接口结构可能已变化）")

    total = int(match.group(1))
    array_start = text.find("[", match.end())
    if array_start == -1:
        raise SourceError("新浪宏观接口没有找到数据数组")

    rows = _extract_array(text, array_start)
    if not isinstance(rows, list):
        raise SourceError("新浪宏观接口的数据段不是数组")
    return total, rows


def parse_reserves(rows: list[list]) -> pd.Series:
    """把 ['YYYY.M', 黄金储备（万盎司）, 外汇储备] 转成按发布日索引的序列。"""
    values: dict = {}
    for row in rows or []:
        try:
            period = str(row[0]).strip()
            year_text, month_text = period.split(".", 1)
            gold_reserves = float(row[1])
        except (IndexError, TypeError, ValueError):
            continue

        month_start = pd.Timestamp(year=int(year_text), month=int(month_text), day=1)
        month_end = (month_start + pd.tseries.offsets.MonthEnd(0)).date()
        # 报告月结束 + 8 天：人行通常在次月 7 日公布上月末储备，这里再保守一天。
        publish_date = business_day_on_or_after(month_end, 8)
        values[publish_date] = gold_reserves

    if not values:
        raise SourceError("央行储备数据没有可解析的行")
    return clean_series(values, name="cb_gold_reserves")


def fetch(
    *,
    page_size: int = 200,
    max_pages: int = 4,
    get: Optional[Callable] = None,
    timeout: float = 25.0,
) -> dict[str, pd.Series]:
    http_get = get or default_get
    collected: list[list] = []
    total: Optional[int] = None

    for page in range(max_pages):
        response = http_get(
            SINA_URL,
            params={
                "cate": "fininfo",
                "event": SINA_EVENT,
                "from": str(page * page_size),
                "num": str(page_size),
                "condition": "",
            },
            timeout=timeout,
        )
        if getattr(response, "status_code", 200) != 200:
            raise SourceError(f"新浪宏观数据抓取失败：HTTP {response.status_code}")

        page_total, rows = parse_payload(response.text)
        total = page_total if total is None else total
        if not rows:
            break
        collected.extend(rows)
        if len(collected) >= total or len(rows) < page_size:
            break

    if not collected:
        raise SourceError("新浪宏观数据没有取到任何行")
    return {"cb_gold_reserves": parse_reserves(collected)}
