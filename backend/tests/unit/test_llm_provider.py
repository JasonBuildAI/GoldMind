"""llm_provider 工厂的单元测试。

工厂是全项目唯一构造 LLM 客户端的地方，所以这里的断言就是
「供应商是否真的切到了 MiMo」的判据。
"""
from pydantic import SecretStr
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
    assert captured["api_key"] == settings.MIMO_API_KEY.get_secret_value()
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
    assert captured["api_key"] == settings.MIMO_API_KEY.get_secret_value()


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
    secret = settings.MIMO_API_KEY.get_secret_value()
    assert all(secret not in str(v) for v in info.values())


@pytest.mark.unit
def test_is_configured_follows_api_key(monkeypatch):
    monkeypatch.setattr(settings, "MIMO_API_KEY", SecretStr(""))
    assert llm_provider.is_configured() is False

    monkeypatch.setattr(settings, "MIMO_API_KEY", SecretStr("tp-fake"))
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

# --------------------------------------------------------------------------- #
# 密钥不得从 repr / str / model_dump 泄露
# --------------------------------------------------------------------------- #
# 红线第 2 条：密钥永不进日志。`test_no_secrets_in_repo` 守的是「不入库」，
# 这里守的是「不因为一句 logger.info(settings) 就漏出去」。
#
# 用 `SecretStr` 而不是 `str` 的意义正在于此：pydantic 的 repr / str /
# model_dump 都会把它显示成 `**********`。明文 str 时三者都会带出真值。
@pytest.mark.unit
def test_settings_repr_masks_secrets(monkeypatch):
    from pydantic import SecretStr

    from app.config import settings

    monkeypatch.setattr(settings, "MIMO_API_KEY", SecretStr("tp-CANARY-abcdef"))
    monkeypatch.setattr(
        settings, "DATABASE_URL", SecretStr("mysql+pymysql://root:canarypw@h/db")
    )

    for label, rendered in (
        ("repr", repr(settings)),
        ("str", str(settings)),
        ("model_dump", str(settings.model_dump())),
        ("model_dump_json", settings.model_dump_json()),
    ):
        assert "tp-CANARY-abcdef" not in rendered, f"{label} 泄露了 API key"
        assert "canarypw" not in rendered, f"{label} 泄露了数据库密码"


@pytest.mark.unit
def test_secrets_are_still_readable_when_needed(monkeypatch):
    """遮蔽不能妨碍正常取用。"""
    from pydantic import SecretStr

    from app.config import settings

    monkeypatch.setattr(settings, "MIMO_API_KEY", SecretStr("tp-real-value"))

    assert settings.MIMO_API_KEY.get_secret_value() == "tp-real-value"


@pytest.mark.unit
def test_is_configured_reads_the_value_not_the_object():
    """`SecretStr("")` 这个**对象**是真值 —— 判断有没有配置必须看里面的值。

    这是个很容易写错的地方：`bool(SecretStr(""))` 是 True。
    """
    from pydantic import SecretStr

    from app.config import settings
    from app.services.llm_provider import is_configured

    settings.MIMO_API_KEY = SecretStr("")
    assert is_configured() is False, "空密钥被判成「已配置」"

    settings.MIMO_API_KEY = SecretStr("tp-x")
    assert is_configured() is True
