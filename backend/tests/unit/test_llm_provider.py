"""llm_provider 工厂的单元测试。

工厂是全项目唯一构造 LLM 客户端的地方，所以这里的断言就是
「.env 里的配置是否真的生效」与「没配置时是否如实拒绝」的判据。
"""
import logging

from pydantic import SecretStr
import pytest

from app.config import settings
from app.services import llm_provider


@pytest.mark.unit
def test_model_name_comes_from_settings():
    assert llm_provider.get_model_name() == settings.LLM_MODEL


@pytest.mark.unit
def test_search_model_falls_back_to_the_reasoning_model(monkeypatch):
    monkeypatch.setattr(settings, "LLM_SEARCH_MODEL", "")
    assert llm_provider.get_search_model_name() == settings.LLM_MODEL

    monkeypatch.setattr(settings, "LLM_SEARCH_MODEL", "search-model-x")
    assert llm_provider.get_search_model_name() == "search-model-x"


@pytest.mark.unit
def test_get_chat_llm_passes_configured_endpoint_and_key(monkeypatch):
    """ChatOpenAI 必须以 .env 的端点、密钥、模型构造。"""
    captured: dict = {}

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider, "_chat_openai_class", lambda: _FakeChatOpenAI)

    llm_provider.get_chat_llm(temperature=0.3, max_tokens=128)

    assert captured["model"] == settings.LLM_MODEL
    assert captured["base_url"] == settings.LLM_BASE_URL
    assert captured["api_key"] == settings.LLM_API_KEY.get_secret_value()
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
    # 默认输出上限来自配置：写死的 4096 曾把三档策略这类大 JSON 截断。
    assert captured["max_tokens"] == settings.LLM_MAX_TOKENS


@pytest.mark.unit
def test_get_chat_llm_refuses_when_unconfigured(monkeypatch):
    """三项配置缺任意一项都必须明确报错，而不是构造一个半成品客户端。"""
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr(""))
    with pytest.raises(RuntimeError, match="LLM 未配置"):
        llm_provider.get_chat_llm()

    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("test-key"))
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    with pytest.raises(RuntimeError, match="LLM 未配置"):
        llm_provider.get_chat_llm()

    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "")
    with pytest.raises(RuntimeError, match="LLM 未配置"):
        llm_provider.get_chat_llm()


@pytest.mark.unit
def test_get_search_client_uses_search_overrides(monkeypatch):
    """搜索凭据默认跟随推理配置，可被 LLM_SEARCH_* 单独覆盖。"""
    captured: dict = {}

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(llm_provider, "_openai_class", lambda: _FakeOpenAI)
    monkeypatch.setattr(settings, "LLM_SEARCH_ENABLED", True)

    llm_provider.get_search_client()
    assert captured["base_url"] == settings.LLM_BASE_URL
    assert captured["api_key"] == settings.LLM_API_KEY.get_secret_value()

    captured.clear()
    monkeypatch.setattr(
        settings, "LLM_SEARCH_BASE_URL", "https://search.example.invalid/v1"
    )
    monkeypatch.setattr(settings, "LLM_SEARCH_API_KEY", SecretStr("search-key"))
    llm_provider.get_search_client()
    assert captured["base_url"] == "https://search.example.invalid/v1"
    assert captured["api_key"] == "search-key"


@pytest.mark.unit
def test_get_search_client_requires_the_switch(monkeypatch):
    """默认关闭时不得构造搜索客户端 —— 也就不会产生无效的 400 请求。"""
    monkeypatch.setattr(settings, "LLM_SEARCH_ENABLED", False)
    with pytest.raises(RuntimeError, match="联网搜索未启用"):
        llm_provider.get_search_client()


@pytest.mark.unit
def test_build_web_search_tool_matches_plugin_format():
    """工具定义必须是端点插件的那套格式（不是智谱的 enable/search_result）。"""
    tool = llm_provider.build_web_search_tool()

    assert tool["type"] == "web_search"
    assert tool["force_search"] is True
    assert tool["max_keyword"] == settings.LLM_SEARCH_MAX_KEYWORD
    assert "web_search" not in tool  # 智谱的嵌套写法不应出现
    assert tool["user_location"]["country"] == "China"


@pytest.mark.unit
def test_describe_exposes_no_secret():
    info = llm_provider.describe()

    assert info["provider"] == settings.LLM_PROVIDER
    assert info["model"] == settings.LLM_MODEL
    assert set(info) == {
        "provider",
        "model",
        "search_model",
        "base_url",
        "configured",
        "token_plan_backend",
    }
    # 任何字段都不得包含密钥
    secret = settings.LLM_API_KEY.get_secret_value()
    assert all(secret not in str(v) for v in info.values())


@pytest.mark.unit
def test_is_configured_requires_key_url_and_model(monkeypatch):
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr(""))
    assert llm_provider.is_configured() is False

    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("test-key"))
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    assert llm_provider.is_configured() is False

    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "")
    assert llm_provider.is_configured() is False

    monkeypatch.setattr(settings, "LLM_MODEL", "test-model")
    assert llm_provider.is_configured() is True


@pytest.mark.unit
def test_no_legacy_provider_fields_remain():
    """守卫：配置面不得再出现写死的供应商变量名。

    变异验证：把任一 MIMO_* 字段加回 Settings —— 本用例立刻变红。
    """
    fields = set(type(settings).model_fields)
    for legacy in (
        "MIMO_API_KEY",
        "MIMO_BASE_URL",
        "MIMO_MODEL",
        "MIMO_SEARCH_MODEL",
        "MIMO_SEARCH_MAX_KEYWORD",
        "MIMO_TRUST_ENV",
    ):
        assert legacy not in fields, f"{legacy} 应已删除，不再有旧供应商配置"


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
    monkeypatch.setattr(settings, "LLM_SEARCH_ENABLED", True)
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

    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("sk-CANARY-abcdef"))
    monkeypatch.setattr(
        settings, "DATABASE_URL", SecretStr("mysql+pymysql://root:canarypw@h/db")
    )

    for label, rendered in (
        ("repr", repr(settings)),
        ("str", str(settings)),
        ("model_dump", str(settings.model_dump())),
        ("model_dump_json", settings.model_dump_json()),
    ):
        assert "sk-CANARY-abcdef" not in rendered, f"{label} 泄露了 API key"
        assert "canarypw" not in rendered, f"{label} 泄露了数据库密码"


@pytest.mark.unit
def test_secrets_are_still_readable_when_needed(monkeypatch):
    """遮蔽不能妨碍正常取用。"""
    from pydantic import SecretStr

    from app.config import settings

    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("sk-real-value"))

    assert settings.LLM_API_KEY.get_secret_value() == "sk-real-value"


@pytest.mark.unit
def test_is_configured_reads_the_value_not_the_object(monkeypatch):
    """`SecretStr("")` 这个**对象**是真值 —— 判断有没有配置必须看里面的值。

    这是个很容易写错的地方：`bool(SecretStr(""))` 是 True。
    """
    from pydantic import SecretStr

    from app.config import settings
    from app.services.llm_provider import is_configured

    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr(""))
    assert is_configured() is False, "空密钥被判成「已配置」"

    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("sk-x"))
    assert is_configured() is True


@pytest.mark.unit
def test_describe_completion_reports_truncation_and_usage():
    """解析失败时日志里要能看到 finish_reason —— 截断与格式错误是两类故障。"""

    class _Message:
        content = "abc"
        response_metadata = {
            "finish_reason": "length",
            "token_usage": {"completion_tokens": 8192, "total_tokens": 9000},
        }

    text = llm_provider.describe_completion(_Message())

    assert "finish_reason=length" in text
    assert "output_tokens=8192" in text
    assert "content_chars=3" in text


@pytest.mark.unit
def test_describe_completion_tolerates_missing_metadata():
    assert llm_provider.describe_completion(None) == "无响应元数据"

    class _Bare:
        content = ""

    assert "finish_reason" not in llm_provider.describe_completion(_Bare())


# --------------------------------------------------------------------------- #
# 端点内容风控
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, finish_reason: str) -> None:
        self.content = "{}"
        self.response_metadata = {"finish_reason": finish_reason}


class _ScriptedLLM:
    """按预设的 finish_reason 序列返回响应，并记录调用次数。"""

    def __init__(self, *finish_reasons: str) -> None:
        self._reasons = list(finish_reasons)
        self.calls = 0

    def invoke(self, prompt: str):
        self.calls += 1
        reason = self._reasons.pop(0) if self._reasons else "stop"
        return _FakeResponse(reason)


@pytest.mark.unit
def test_retry_on_content_filter_retries_once():
    """MiMo 端点会把部分市场分析请求判成高风险；重试一次再决定。"""
    llm = _ScriptedLLM("content_filter", "stop")

    response = llm_provider.retry_on_content_filter(llm, "prompt")

    assert llm.calls == 2, "被内容风控拒绝后必须重试一次"
    assert response.response_metadata["finish_reason"] == "stop"


@pytest.mark.unit
def test_retry_on_content_filter_keeps_a_good_answer():
    llm = _ScriptedLLM("stop")

    llm_provider.retry_on_content_filter(llm, "prompt")

    assert llm.calls == 1, "正常返回不该多花一次调用"


@pytest.mark.unit
def test_retry_on_content_filter_gives_up_after_one_retry():
    """仍被拒就如实返回 —— 上层据此显示「暂不可用」，不编内容。"""
    llm = _ScriptedLLM("content_filter", "content_filter", "stop")

    response = llm_provider.retry_on_content_filter(llm, "prompt")

    assert llm.calls == 2
    assert response.response_metadata["finish_reason"] == "content_filter"


# --------------------------------------------------------------------------- #
# Token Plan 端点合规（R4-18）
# --------------------------------------------------------------------------- #
# 背景：小米 Token Plan 条款限定「仅可在编程工具中使用」，以 `tp-` key +
# token-plan 端点做后端调用属条款外用法。代码不替持有人换 key，但必须警告
# 出来并在 /health 里如实标记。检测是纯函数，先写真值表。
_TOKEN_PLAN_URL = "https://token-plan-cn.xiaomimimo.com/v1"
_COMPLIANT_URL = "https://api.xiaomimimo.com/v1"


@pytest.mark.unit
def test_token_plan_combo_needs_both_conditions():
    assert llm_provider.is_token_plan_combo(_TOKEN_PLAN_URL, "tp-abc123")
    # 单条件都不算：换掉密钥、或换掉端点，就不再是 Token Plan 组合
    assert not llm_provider.is_token_plan_combo(_COMPLIANT_URL, "tp-abc123")
    assert not llm_provider.is_token_plan_combo(_TOKEN_PLAN_URL, "sk-abc123")
    assert not llm_provider.is_token_plan_combo(_COMPLIANT_URL, "sk-abc123")


@pytest.mark.unit
def test_get_chat_llm_warns_on_token_plan_backend(monkeypatch, caplog):
    """命中组合必须警告：给切换指引、不打印密钥、只记一条。"""

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(llm_provider, "_chat_openai_class", lambda: _FakeChatOpenAI)
    monkeypatch.setattr(llm_provider, "_token_plan_warned", False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", _TOKEN_PLAN_URL)
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("tp-CANARY-portal-0001"))

    with caplog.at_level(logging.WARNING, logger="app.services.llm_provider"):
        llm_provider.get_chat_llm()

    hits = [r.getMessage() for r in caplog.records if "Token Plan" in r.getMessage()]
    assert len(hits) == 1, "命中组合必须记且只记一条警告"
    assert llm_provider.COMPLIANT_MIMO_BASE_URL in hits[0], "警告里要给出切换指引"
    assert "tp-CANARY-portal-0001" not in hits[0], "警告不得带出密钥本身"


@pytest.mark.unit
def test_token_plan_warning_is_once_per_process(monkeypatch, caplog):
    """进程内去重：构造多次只警告一次，日志不刷屏。"""

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(llm_provider, "_chat_openai_class", lambda: _FakeChatOpenAI)
    monkeypatch.setattr(llm_provider, "_token_plan_warned", False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", _TOKEN_PLAN_URL)
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("tp-abc123"))

    with caplog.at_level(logging.WARNING, logger="app.services.llm_provider"):
        for _ in range(3):
            llm_provider.get_chat_llm()

    hits = [r for r in caplog.records if "Token Plan" in r.getMessage()]
    assert len(hits) == 1


@pytest.mark.unit
def test_compliant_endpoint_does_not_warn(monkeypatch, caplog):

    class _FakeChatOpenAI:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(llm_provider, "_chat_openai_class", lambda: _FakeChatOpenAI)
    monkeypatch.setattr(llm_provider, "_token_plan_warned", False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", _COMPLIANT_URL)
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("sk-abc123"))

    with caplog.at_level(logging.WARNING, logger="app.services.llm_provider"):
        llm_provider.get_chat_llm()

    assert not [r for r in caplog.records if "Token Plan" in r.getMessage()]


@pytest.mark.unit
def test_search_client_override_is_checked_too(monkeypatch, caplog):
    """搜索覆盖配置是第二个构造点，同样要检测 —— 别只守推理那一条路径。"""

    class _FakeOpenAI:
        def __init__(self, **kwargs):
            pass

    monkeypatch.setattr(llm_provider, "_openai_class", lambda: _FakeOpenAI)
    monkeypatch.setattr(llm_provider, "_token_plan_warned", False)
    monkeypatch.setattr(settings, "LLM_SEARCH_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_SEARCH_BASE_URL", _TOKEN_PLAN_URL)
    monkeypatch.setattr(settings, "LLM_SEARCH_API_KEY", SecretStr("tp-abc123"))

    with caplog.at_level(logging.WARNING, logger="app.services.llm_provider"):
        llm_provider.get_search_client()

    assert [r for r in caplog.records if "Token Plan" in r.getMessage()]


@pytest.mark.unit
def test_describe_reports_token_plan_backend(monkeypatch):
    """/health 的 ai_config 段要能看出这个标记（且不含密钥）。"""
    monkeypatch.setattr(settings, "LLM_BASE_URL", _TOKEN_PLAN_URL)
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("tp-abc123"))
    assert llm_provider.describe()["token_plan_backend"] is True

    monkeypatch.setattr(settings, "LLM_BASE_URL", _COMPLIANT_URL)
    assert llm_provider.describe()["token_plan_backend"] is False
