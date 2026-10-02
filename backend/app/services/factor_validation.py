"""因子输出的结构校验 —— 不合格就降级，不把 LLM 输出原样透传。

背景：prompt 要求「最多 5 个因子、id 在允许集合内、details 非空、必须有新闻
支撑」，但代码此前 `json.loads` 后直接 return —— 模型给出重复因子、拼错的 id、
或凭空引用一个新闻里没有的数字时，页面、缓存与数据库照单全收。

校验分四层，全部确定性、可单测：

1. 结构：必须是对象，标题与描述非空，details 至少有一条非空要点；
2. 枚举：id 必须在允许集合内（拼错即丢弃），impact 非法时归一到 medium；
3. 去重与截断：按 id、标题去重（保留先出现的），最多 ``max_factors`` 条；
4. 引用（best-effort）：因子正文出现的数字在任何参考文本里都找不到时，
   视为编造，丢弃该因子；没有参考文本（如联网搜索路径）时跳过本层。

任何一层把全部因子清空的，调用方降级为空结构（前端显示「暂不可用」），
不摆半份脏数据。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

ALLOWED_FACTOR_IDS = {
    "bullish": frozenset(
        {"fed-policy", "central-bank", "dollar-credit", "geopolitical", "supply-demand"}
    ),
    "bearish": frozenset(
        {
            "rate-hike",
            "profit-taking",
            "geopolitical-ease",
            "dollar-strength",
            "economic-growth",
        }
    ),
}

_VALID_IMPACTS = ("high", "medium", "low")
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_text(value: Any) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _factor_text(item: Dict[str, Any]) -> str:
    parts = [item.get("title"), item.get("subtitle"), item.get("description")]
    details = item.get("details")
    if isinstance(details, list):
        parts.extend(details)
    elif details:
        parts.append(details)
    return " ".join(_clean_text(part) for part in parts if _clean_text(part))


def _numbers_have_support(text: str, reference_text: str) -> bool:
    numbers = _NUMBER_RE.findall(text)
    if not numbers:
        return True
    return any(number in reference_text for number in numbers)


def validate_factor_response(
    result: Any,
    *,
    side: str,
    reference_text: str = "",
    max_factors: int = 5,
) -> Tuple[Any, List[str]]:
    """校验并清洗因子输出，返回 ``(清洗后的结果, 丢弃原因列表)``。

    ``side`` 取 ``"bullish"`` / ``"bearish"``；``reference_text`` 是本次调用
    实际喂给模型的新闻原文，用于第 4 层数字引用校验。
    """
    if not isinstance(result, dict):
        return result, []
    key = f"{side}_factors"
    factors = result.get(key)
    if factors is None:
        return {**result, key: []}, [f"{key} 缺失，已降级为空"]
    if not isinstance(factors, list):
        return {**result, key: []}, [f"{key} 不是列表，已降级为空"]

    allowed = ALLOWED_FACTOR_IDS.get(side, frozenset())
    dropped: List[str] = []
    seen_ids = set()
    seen_titles = set()
    cleaned: List[Dict[str, Any]] = []

    for index, item in enumerate(factors):
        if not isinstance(item, dict):
            dropped.append(f"第 {index + 1} 条不是对象")
            continue
        title = _clean_text(item.get("title"))
        description = _clean_text(item.get("description"))
        if not title or not description:
            dropped.append(f"第 {index + 1} 条缺少标题或描述")
            continue
        factor_id = _clean_text(item.get("id"))
        if factor_id not in allowed:
            dropped.append(f"{title}：id「{factor_id}」不在允许集合")
            continue
        details = item.get("details")
        if not isinstance(details, list) or not any(_clean_text(entry) for entry in details):
            dropped.append(f"{title}：details 为空")
            continue
        title_key = title.casefold()
        if factor_id in seen_ids or title_key in seen_titles:
            dropped.append(f"{title}：重复因子")
            continue
        if reference_text and not _numbers_have_support(_factor_text(item), reference_text):
            dropped.append(f"{title}：正文数字在新闻里找不到依据")
            continue

        seen_ids.add(factor_id)
        seen_titles.add(title_key)
        impact = _clean_text(item.get("impact")).lower()
        cleaned.append(
            {
                **item,
                "title": title,
                "description": description,
                "impact": impact if impact in _VALID_IMPACTS else "medium",
            }
        )

    if len(cleaned) > max_factors:
        dropped.append(f"超出 {max_factors} 条上限，截断 {len(cleaned) - max_factors} 条")
        cleaned = cleaned[:max_factors]

    return {**result, key: cleaned}, dropped
