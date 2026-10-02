"""AI 响应载荷的契约兜底 —— ``last_updated`` 由服务端起，不问模型要。

背景（实测，2026-10-02）：``bullish-factors-ai`` 与 ``bearish-factors-ai`` 的响应模型
要求 ``last_updated``，而**缓存命中的那条路径**返回的是分析器交给缓存的原样 JSON。
提示词模板里虽然写了 ``"last_updated": "{current_time}"``，但模型不一定照抄 ——
mimo-v2.6-flash 当天那次分析就吐了 ``bullish_factors`` 与 ``analysis_summary``
而没吐这个键。结果不是少一个字段，而是整个接口 500：
``ResponseValidationError: 1 validation error ... Field required``。

响应模型把「安静地少一个键」变成「响亮地报错」是对的（这正是它该做的事），
缺的是这条兜底。规则只有一条：**这个时间只能由服务端产生** ——
优先取这份载荷自己记的生成时间（``metadata.generated_at``，缓存写入时记下的），
没有才用当前时刻；绝不采用模型输出的自由文本当时间戳。
"""
from __future__ import annotations

import functools
from typing import Any, Callable, Dict

from app.utils import timeutil

LAST_UPDATED_KEY = "last_updated"


def ensure_last_updated(payload: Any) -> Any:
    """给缺 ``last_updated`` 的载荷补一个，并把已有的值收敛成字符串。

    非 dict 的入参原样返回 —— 这一层只负责契约字段，不替调用方判断载荷是否可用。
    """
    if not isinstance(payload, dict):
        return payload

    value = payload.get(LAST_UPDATED_KEY)
    if value:
        payload[LAST_UPDATED_KEY] = str(value)
        return payload

    metadata = payload.get("metadata")
    generated = metadata.get("generated_at") if isinstance(metadata, dict) else None
    payload[LAST_UPDATED_KEY] = str(generated) if generated else timeutil.now_str()
    return payload


def with_last_updated(func: Callable[..., Dict[str, Any]]) -> Callable[..., Dict[str, Any]]:
    """把 ``ensure_last_updated`` 挂到服务的公开取数入口上。

    服务里有好几条 return（实时、缓存、占位），逐条加容易漏 —— 漏掉的那条就是
    这次 500 的成因。装饰在公开入口上，出口只有一个，漏不掉。
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        return ensure_last_updated(func(*args, **kwargs))

    return wrapper
