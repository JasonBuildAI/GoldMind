"""llm_provider 工厂的单元测试。

工厂是全项目唯一构造 LLM 客户端的地方，所以这里的断言就是
「供应商是否真的切到了 MiMo」的判据。
"""
import pytest

from app.config import settings
from app.services import llm_provider


@pytest.mark.unit
def test_model_name_comes_from_settings():
    assert llm_provider.get_model_name() == settings.MIMO_MODEL
    assert llm_provider.get_search_model_name() == settings.MIMO_SEARCH_MODEL


@pytest.mark.unit
def test_get_chat_llm_passes_mimo_endpoint_and_key(monkeypatch):
    """ChatOpenAI 必须以 MiMo 的端点、密钥、模型构造。"""
    captured: dict = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider, "_chat_openai_class", lambda: _FakeChatOpenAI)

    llm_provider.get_chat_llm(temperature=0.3, max_tokens=128)

    assert captured["model"] == settings.MIMO_MODEL
    assert captured["base_url"] == settings.MIMO_BASE_URL
    assert captured["api_key"] == settings.MIMO_API_KEY
    assert captured["temperature"] == 0.3
    assert captured["max_tokens"] == 128


@pytest.mark.unit
def test_get_chat_llm_defaults(monkeypatch):
    captured: dict = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider, "_chat_openai_class", lambda: _FakeChatOpenAI)

    llm_provider.get_chat_llm()

    assert captured["temperature"] == 0.7
    assert captured["max_tokens"] == 4096


@pytest.mark.unit
def test_get_search_client_passes_mimo_endpoint(monkeypatch):
    captured: dict = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider, "_openai_class", lambda: _FakeOpenAI)

    llm_provider.get_search_client()

    assert captured["base_url"] == settings.MIMO_BASE_URL
    assert captured["api_key"] == settings.MIMO_API_KEY


@pytest.mark.unit
def test_build_web_search_tool_matches_mimo_format():
    """工具定义必须是 MiMo 的格式（不是智谱那套 enable/search_result）。"""
    tool = llm_provider.build_web_search_tool()

    assert tool["type"] == "web_search"
    assert tool["force_search"] is True
    assert tool["max_keyword"] == settings.MIMO_SEARCH_MAX_KEYWORD
    assert "web_search" not in tool  # 智谱的嵌套写法不应出现
    assert tool["user_location"]["country"] == "China"


@pytest.mark.unit
def test_describe_exposes_no_secret():
    info = llm_provider.describe()

    assert info["provider"] == "mimo"
    assert info["model"] == settings.MIMO_MODEL
    assert set(info) == {"provider", "model", "search_model", "base_url", "configured"}
    # 任何字段都不得包含密钥
    assert all(settings.MIMO_API_KEY not in str(v) for v in info.values())


@pytest.mark.unit
def test_is_configured_follows_api_key(monkeypatch):
    monkeypatch.setattr(settings, "MIMO_API_KEY", "")
    assert llm_provider.is_configured() is False

    monkeypatch.setattr(settings, "MIMO_API_KEY", "tp-fake")
    assert llm_provider.is_configured() is True


# --------------------------------------------------------------------------- #
# 宿主代理环境
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_http_clients_do_not_read_host_proxy_env(monkeypatch):
    """两个 httpx 客户端都必须显式关闭 trust_env。"""
    monkeypatch.setattr(llm_provider, "_http_client", None)
    monkeypatch.setattr(llm_provider, "_async_http_client", None)

    assert llm_provider.get_http_client().trust_env is False
    assert llm_provider.get_async_http_client().trust_env is False


@pytest.mark.unit
def test_llm_clients_construct_under_hostile_proxy_env(monkeypatch):
    """回归：宿主环境里一个坏代理配置曾让整个 AI 功能静默失效。

    两种写法都会让 httpx 在**构造客户端**时抛异常：
      - ALL_PROXY 指向 SOCKS 代理
      - NO_PROXY 里含 ``[::1]``（httpx 解析不了这个写法）

    而 `ChatOpenAI` 会同时准备同步与异步两个客户端；只显式提供同步的那个，
    它仍会去创建默认的异步客户端并读环境，于是照样抛异常。
    异常随后被各分析服务吞掉并回退到硬编码默认值 ——
    表现为「页面上有分析内容，其实一次模型都没调用」。
    """
    monkeypatch.setattr(llm_provider, "_http_client", None)
    monkeypatch.setattr(llm_provider, "_async_http_client", None)
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:9")
    monkeypatch.setenv("NO_PROXY", "localhost,127.0.0.1,::1,[::1]")

    # 构造阶段必须不抛异常
    assert llm_provider.get_chat_llm() is not None
    assert llm_provider.get_search_client() is not None
