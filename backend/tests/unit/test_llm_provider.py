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
