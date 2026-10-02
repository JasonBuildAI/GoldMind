"""LLM 客户端工厂 —— 全项目唯一构造 LLM 客户端的地方。

供应商：任何 OpenAI 兼容端点。代码不绑定具体厂商 —— 端点、密钥、模型
全部来自 `.env`（`LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`）。

为什么要有这个模块：迁移前有 6 处各自独立构造 `ChatOpenAI`、4 处各自拼
`web_search` 工具参数，改一个供应商要动 9 个地方，且极易漏改。现在所有调用点
都从这里取实例，换供应商/换端点/换模型只改 `app/config.py` 或 `.env`。

约定：
    - 不要在业务代码里直接 `ChatOpenAI(...)` 或 `OpenAI(...)`，一律走本模块。
    - langchain / openai 都是延迟导入，避免拖慢进程启动。
    - 密钥 / 端点 / 模型三项缺一即为「未配置」：调用方如实返回「暂不可用」，
      不得编造内容（AGENTS.md 红线 1）。

联网搜索（可选，默认关闭，见 `LLM_SEARCH_ENABLED`）：
    只有支持「MiMo 插件式 web_search 工具」的端点才能开启。账号未开通时
    端点会返回 HTTP 400 `webSearchEnabled is false` —— 这是账号侧的开关
    （控制台开通），不是参数写法问题；关闭时搜索链路直接走数据库 / RSS 回退。

Token Plan 端点（`tp-` key + 含 `token-plan` 的主机）属条款外用法：
    构造客户端时警告并给出切换指引，但**不自动换 key**
    （见下文「Token Plan 端点合规」）。
"""
from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.services import llm_gate

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

    默认 ``trust_env=False``（见 ``LLM_TRUST_ENV``），需要走代理时再打开。
    """
    global _http_client
    if _http_client is None:
        import httpx

        _http_client = httpx.Client(
            trust_env=settings.LLM_TRUST_ENV,
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
            trust_env=settings.LLM_TRUST_ENV,
            timeout=httpx.Timeout(120.0, connect=10.0),
        )
    return _async_http_client


# --------------------------------------------------------------------------- #
# 配置读取
# --------------------------------------------------------------------------- #
def get_model_name() -> str:
    """推理模型名。"""
    return settings.LLM_MODEL


def get_search_model_name() -> str:
    """联网搜索所用模型名；未单独配置时跟随推理模型。"""
    return settings.LLM_SEARCH_MODEL or settings.LLM_MODEL


def get_search_api_key() -> str:
    """联网搜索所用密钥；未单独配置时跟随推理密钥。"""
    override = settings.LLM_SEARCH_API_KEY.get_secret_value()
    return override or settings.LLM_API_KEY.get_secret_value()


def get_search_base_url() -> str:
    """联网搜索所用端点；未单独配置时跟随推理端点。"""
    return settings.LLM_SEARCH_BASE_URL or settings.LLM_BASE_URL


# --------------------------------------------------------------------------- #
# 客户端构造
# --------------------------------------------------------------------------- #
def get_chat_llm(*, temperature: float = 0.7, max_tokens: int | None = None) -> Any:
    """返回用于结构化推理的 ChatOpenAI 实例。

    Args:
        temperature: 采样温度。
        max_tokens: 单次最大输出 token；留空取 `LLM_MAX_TOKENS`（默认 8192）。
            推理模型的思考与正文共用这份额度 —— 调得太小，长 JSON 会在半途
            被截断、解析失败，页面只能如实显示「暂不可用」。

    Returns:
        已按 .env 配置好端点与密钥的 ChatOpenAI，调用方式为 `llm.invoke(prompt)`，
        取正文用 `response.content`。

    Raises:
        RuntimeError: 三项配置未齐 —— 消息直接说明缺什么，便于排查；
            各分析服务会捕获它并如实返回「不可用」。
    """
    if not is_configured():
        raise RuntimeError(
            "LLM 未配置：请在 .env 里同时设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL"
        )
    warn_if_token_plan_combo(
        settings.LLM_BASE_URL, settings.LLM_API_KEY.get_secret_value()
    )
    return _chat_openai_class()(
        model=get_model_name(),
        api_key=settings.LLM_API_KEY.get_secret_value(),
        base_url=settings.LLM_BASE_URL,
        temperature=temperature,
        max_tokens=max_tokens if max_tokens is not None else settings.LLM_MAX_TOKENS,
        http_client=get_http_client(),
        http_async_client=get_async_http_client(),
    )


def reset_clients() -> None:
    """丢弃共享的 httpx 客户端（配置热更新后旧端点 / 代理设置不再复用）。

    同步客户端显式关闭；异步客户端只解除引用（其 close 是协程，在没有事件
    循环的监听线程里无法安全 await，交给 GC 回收）。
    """
    global _http_client, _async_http_client
    old_sync, _http_client = _http_client, None
    _async_http_client = None
    if old_sync is not None:
        try:
            old_sync.close()
        except Exception as exc:  # noqa: BLE001 —— 旧客户端关不掉不该影响重载
            logger.debug(f"关闭旧 LLM http 客户端失败（忽略）：{exc}")


def get_search_client() -> Any:
    """返回用于联网搜索的原生 OpenAI 客户端。

    凭据与端点默认跟随推理配置，可用 LLM_SEARCH_API_KEY /
    LLM_SEARCH_BASE_URL 单独覆盖（推理与搜索不必是同一家）。
    """
    if not is_search_enabled():
        raise RuntimeError(
            "联网搜索未启用：如需使用请在 .env 里设置 LLM_SEARCH_ENABLED=true，"
            "并确认端点支持 MiMo 插件式 web_search 工具"
        )
    warn_if_token_plan_combo(get_search_base_url(), get_search_api_key())
    return _openai_class()(
        api_key=get_search_api_key(),
        base_url=get_search_base_url(),
        http_client=get_http_client(),
    )


# --------------------------------------------------------------------------- #
# 联网搜索
# --------------------------------------------------------------------------- #
def build_web_search_tool() -> dict[str, Any]:
    """构造 MiMo 插件格式的 web_search 工具定义（仅该格式的端点可用）。

    注意：该工具需要账号已开通「联网搜索插件」
    （https://platform.xiaomimimo.com/#/console/plugin），且按次独立计费。
    未开通时端点返回 HTTP 400 `webSearchEnabled is false`（实测）。
    `max_keyword` 是一轮搜索并发展开的最大关键词数，是主要的成本旋钮。
    """
    return {
        "type": "web_search",
        "force_search": True,
        "max_keyword": settings.LLM_SEARCH_MAX_KEYWORD,
        "limit": 2,
        "user_location": {"type": "approximate", "country": "China"},
    }


def is_configured() -> bool:
    """密钥 / 端点 / 模型三项齐备才算已配置。

    SecretStr 对象本身恒为真，必须看里面的值。
    """
    return bool(
        settings.LLM_API_KEY.get_secret_value()
        and settings.LLM_BASE_URL.strip()
        and settings.LLM_MODEL.strip()
    )


def is_search_enabled() -> bool:
    """联网搜索是否开启（默认关闭；见模块文档）。"""
    return bool(settings.LLM_SEARCH_ENABLED)


# --------------------------------------------------------------------------- #
# Token Plan 端点合规
# --------------------------------------------------------------------------- #
# 背景：小米 Token Plan 条款限定「仅可在编程工具中使用，禁止用于自定义应用
# 后端」。该套餐的端点主机含 `token-plan`、密钥以 `tp-` 开头，两个条件同时
# 命中即属条款外用法，存在被暂停服务或封禁 key 的风险
# （见 docs/00-产品方向.md 第四节第 2 条）。
# 代码不替持有人换 key（那是账号侧动作），只做两件事：构造客户端时警告一次；
# `/health` 里如实带出标记，让部署方在日志之外也能发现。
TOKEN_PLAN_HOST_MARKER = "token-plan"
COMPLIANT_MIMO_BASE_URL = "https://api.xiaomimimo.com/v1"

_token_plan_warned = False


def is_token_plan_combo(base_url: str, api_key: str) -> bool:
    """端点 + 密钥是否构成 Token Plan 组合（双条件，缺一不算）。"""
    return TOKEN_PLAN_HOST_MARKER in base_url.lower() and api_key.startswith("tp-")


def is_token_plan_backend() -> bool:
    """当前**推理**配置是否在用 Token Plan 端点当后端。"""
    return is_token_plan_combo(
        settings.LLM_BASE_URL, settings.LLM_API_KEY.get_secret_value()
    )


def warn_if_token_plan_combo(base_url: str, api_key: str) -> bool:
    """命中 Token Plan 组合时记一条警告（进程内只记一次），返回是否命中。

    警告文本给切换指引，但**不含密钥本身** —— 红线 2：密钥永不进日志。
    """
    global _token_plan_warned
    if not is_token_plan_combo(base_url, api_key):
        return False
    if not _token_plan_warned:
        _token_plan_warned = True
        logger.warning(
            "LLM 端点疑似 Token Plan 后端用法（密钥以 tp- 开头且端点含 token-plan）："
            "该套餐条款限定仅用于编程工具，后端调用属条款外用法，"
            "存在被暂停服务或封禁 key 的风险。合规做法是改用按量付费端点 %s + sk- 密钥"
            "（密钥由持有人更换，代码不自动替换）。",
            COMPLIANT_MIMO_BASE_URL,
        )
    return True


def describe_completion(response: Any) -> str:
    """把一次模型响应的「结束原因 + token 用量」压成一行，供解析失败时记日志。

    截断（finish_reason=length）与格式错误是两类完全不同的故障：前者要调大
    LLM_MAX_TOKENS，后者要修解析。日志里没有这一行，排查时只能靠猜。
    取不到的字段如实省略，不猜。
    """
    if response is None:
        return "无响应元数据"
    meta = getattr(response, "response_metadata", None) or {}
    usage = meta.get("token_usage") or getattr(response, "usage_metadata", None) or {}

    bits: list[str] = []
    finish = meta.get("finish_reason")
    if finish:
        bits.append(f"finish_reason={finish}")
    output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
    if output_tokens is not None:
        bits.append(f"output_tokens={output_tokens}")
    total_tokens = usage.get("total_tokens")
    if total_tokens is not None:
        bits.append(f"total_tokens={total_tokens}")
    bits.append(f"content_chars={len(getattr(response, 'content', '') or '')}")
    return ", ".join(bits)


COMPACT_JSON_HINT = (
    "\n\n【系统提示】上一次输出因超出单次输出上限被截断（finish_reason=length）。"
    "请压缩本次输出：数组每类最多 3 项、每个文本字段不超过 40 个字，"
    "省略解释性套话；只输出一个完整、可解析的 JSON。"
)


def _finish_reason(response: Any) -> Any:
    """一次响应的结束原因；取不到时如实返回 None（不猜）。"""
    meta = getattr(response, "response_metadata", None) or {}
    return meta.get("finish_reason")


def invoke_with_retries(
    llm: Any,
    prompt: str,
    *,
    attempts: int = 2,
    compact_hint: str | None = COMPACT_JSON_HINT,
) -> Any:
    """调用一次模型；遇到两类已知的「可重试故障」各重试一次。

    1. `finish_reason=content_filter`：MiMo 端点会把部分市场分析请求判成
       高风险（正文固定为 "The request was rejected because it was considered
       high risk"）。实测触发与新闻语料里的冲突类内容相关，而且**不稳定** ——
       同样长度的 prompt 有时通过、有时被拒（15 条新闻的看跌请求连续两次被拒，
       10 条通过）。重试一次，避免把一次随机拒绝当成「分析不可用」。
    2. `finish_reason=length`：输出撞上单次输出上限、JSON 被截断。
       实测案例（2026-10-03 冷启动验收）：投资策略的四档策略 schema 在
       8192 输出上限下被截断，整块策略降级为空。此时把压缩提示追加到原
       prompt 后重试一次 —— 条目变少、字段变短，让完整 JSON 装进上限。
       仍截断就如实返回，由上层降级为「暂不可用」，绝不拼接残缺 JSON。
       传 `compact_hint=None` 可关闭第二条。

    两种重试都计入每日预算（失败 / 被风控的尝试同样计费）。
    """
    def _invoke_once(text: str) -> Any:
        """真实调用一次：先过每日预算，再计入次数。"""
        llm_gate.gate.ensure_budget()
        llm_gate.gate.note_call()
        return llm.invoke(text)

    response = _invoke_once(prompt)
    for _ in range(max(0, attempts - 1)):
        reason = _finish_reason(response)
        if reason == "content_filter":
            logger.warning(
                "LLM 输出被端点内容风控拦截（finish_reason=content_filter），重试一次"
            )
            response = _invoke_once(prompt)
            continue
        if reason == "length" and compact_hint:
            logger.warning(
                "LLM 输出被单次输出上限截断（finish_reason=length），改用压缩提示重试一次"
            )
            response = _invoke_once(prompt + compact_hint)
            compact_hint = None
            continue
        break
    return response


def describe() -> dict[str, Any]:
    """供健康检查使用的供应商描述（不含密钥，含 Token Plan 合规标记）。"""
    return {
        "provider": settings.LLM_PROVIDER,
        "model": get_model_name(),
        "search_model": get_search_model_name(),
        "base_url": settings.LLM_BASE_URL,
        "configured": is_configured(),
        "token_plan_backend": is_token_plan_backend(),
    }
