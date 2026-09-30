"""LLM 供应商工厂 —— 全项目唯一构造 LLM 客户端的地方。

供应商：小米 MiMo（OpenAI 兼容协议）。

为什么要有这个模块：迁移前有 6 处各自独立构造 `ChatOpenAI`、4 处各自拼
`web_search` 工具参数，改一个供应商要动 9 个地方，且极易漏改。现在所有调用点
都从这里取实例，换供应商/换端点/换模型只改 `app/config.py` 或 `.env`。

约定：
    - 不要在业务代码里直接 `ChatOpenAI(...)` 或 `OpenAI(...)`，一律走本模块。
    - langchain / openai 都是延迟导入，避免拖慢进程启动。

已知限制（实测，见 scripts/smoke_mimo.py）：
    - 推理：可用。
    - 联网搜索：Token Plan 的 `tp-` key 调用 `web_search` 工具一律返回
      HTTP 400 `Param Incorrect`（已二分排除参数写法问题）。因此
      `web_search_available()` 在运行时探测，搜索链路必须能降级而不是崩掉。
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)

# 延迟导入缓存（None 表示尚未导入）
_ChatOpenAI: Any = None
_OpenAIClient: Any = None


def _chat_openai_class() -> Any:
    """延迟加载 langchain_openai.ChatOpenAI。"""
    global _ChatOpenAI
    if _ChatOpenAI is None:
        from langchain_openai import ChatOpenAI

        _ChatOpenAI = ChatOpenAI
    return _ChatOpenAI


def _openai_class() -> Any:
    """延迟加载 openai.OpenAI（用于联网搜索等原生调用）。"""
    global _OpenAIClient
    if _OpenAIClient is None:
        from openai import OpenAI

        _OpenAIClient = OpenAI
    return _OpenAIClient


# --------------------------------------------------------------------------- #
# 模型名
# --------------------------------------------------------------------------- #
def get_model_name() -> str:
    """推理模型名。"""
    return settings.MIMO_MODEL


def get_search_model_name() -> str:
    """联网搜索所用模型名。"""
    return settings.MIMO_SEARCH_MODEL


# --------------------------------------------------------------------------- #
# 客户端构造
# --------------------------------------------------------------------------- #
def get_chat_llm(*, temperature: float = 0.7, max_tokens: int = 4096) -> Any:
    """返回用于结构化推理的 ChatOpenAI 实例。

    Args:
        temperature: 采样温度。
        max_tokens: 单次最大输出 token。实测 MiMo 同时接受 `max_tokens` 与
            `max_completion_tokens`，这里沿用 `max_tokens` 以保持与迁移前一致。

    Returns:
        已配置好 MiMo 端点与密钥的 ChatOpenAI，调用方式为 `llm.invoke(prompt)`，
        取正文用 `response.content`。
    """
    return _chat_openai_class()(
        model=get_model_name(),
        api_key=settings.MIMO_API_KEY,
        base_url=settings.MIMO_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def get_search_client() -> Any:
    """返回用于联网搜索的原生 OpenAI 客户端。"""
    return _openai_class()(
        api_key=settings.MIMO_API_KEY,
        base_url=settings.MIMO_BASE_URL,
    )


# --------------------------------------------------------------------------- #
# 联网搜索
# --------------------------------------------------------------------------- #
def build_web_search_tool() -> dict[str, Any]:
    """构造 MiMo 格式的 web_search 工具定义。

    注意：该工具需要账号已开通「联网搜索插件」
    （https://platform.xiaomimimo.com/#/console/plugin），且按次独立计费。
    `max_keyword` 是一轮搜索并发展开的最大关键词数，是主要的成本旋钮。
    """
    return {
        "type": "web_search",
        "force_search": True,
        "max_keyword": settings.MIMO_SEARCH_MAX_KEYWORD,
        "limit": 2,
        "user_location": {"type": "approximate", "country": "China"},
    }


def is_configured() -> bool:
    """是否已配置密钥。"""
    return bool(settings.MIMO_API_KEY)


def describe() -> dict[str, Any]:
    """供健康检查使用的供应商描述（不含密钥）。"""
    return {
        "provider": settings.LLM_PROVIDER,
        "model": get_model_name(),
        "search_model": get_search_model_name(),
        "base_url": settings.MIMO_BASE_URL,
        "configured": is_configured(),
    }
