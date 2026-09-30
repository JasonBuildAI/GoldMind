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


# 共享的 httpx 客户端（复用连接；trust_env 由配置决定）
_http_client: Any = None
_async_http_client: Any = None


def get_http_client() -> Any:
    """返回所有 LLM 客户端共用的同步 httpx 客户端。

    显式传入该客户端的目的，是把「是否读取宿主代理环境变量」这件事握在自己手里：

    宿主若设置了 ``ALL_PROXY=socks5://...`` 而未安装 socksio，或 ``NO_PROXY`` 里含
    ``[::1]`` 这类 httpx 无法解析的写法，构造 httpx 客户端时会直接抛异常。
    由于上层把 LLM 异常吞掉并回退到硬编码默认值，最终表现成
    「页面有分析内容，其实一次模型都没调用」—— 极难排查。

    默认 ``trust_env=False``（见 ``MIMO_TRUST_ENV``），需要走代理时再打开。
    """
    global _http_client
    if _http_client is None:
        import httpx

        _http_client = httpx.Client(
            trust_env=settings.MIMO_TRUST_ENV,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
    return _http_client


def get_async_http_client() -> Any:
    """返回异步 httpx 客户端。

    **必须与同步客户端一起提供**：`ChatOpenAI` 在构造时会同时准备同步与异步
    两个客户端，只给同步的那个，它仍会去创建默认的异步客户端 ——
    而默认客户端会读取宿主代理配置，于是照样抛异常。
    """
    global _async_http_client
    if _async_http_client is None:
        import httpx

        _async_http_client = httpx.AsyncClient(
            trust_env=settings.MIMO_TRUST_ENV,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
    return _async_http_client


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
        http_client=get_http_client(),
        http_async_client=get_async_http_client(),
    )


def get_search_client() -> Any:
    """返回用于联网搜索的原生 OpenAI 客户端。"""
    return _openai_class()(
        api_key=settings.MIMO_API_KEY,
        base_url=settings.MIMO_BASE_URL,
        http_client=get_http_client(),
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
