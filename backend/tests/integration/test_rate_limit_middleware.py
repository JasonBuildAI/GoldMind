"""限流中间件与 CORS 的集成测试。

覆盖原实现的两个缺陷：
  - 健康检查被一起限流（探针会被误判成服务不可用）
  - 会触发付费 LLM 调用的接口与普通接口共用一个上限
以及一个安全配置问题：通配来源 + 允许凭证。
"""
import pytest

from app.utils.rate_limit import SlidingWindowRateLimiter

ALLOWED_ORIGIN = "http://localhost:5173"


def _install_limiters(monkeypatch, general: int, ai: int) -> None:
    import app.main as main

    monkeypatch.setattr(main, "_general_limiter", SlidingWindowRateLimiter(general))
    monkeypatch.setattr(main, "_ai_limiter", SlidingWindowRateLimiter(ai))


# --------------------------------------------------------------------------- #
# 限流
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_general_endpoints_return_429_with_retry_after(client, monkeypatch):
    _install_limiters(monkeypatch, general=2, ai=100)

    assert client.get("/api/gold/news").status_code == 200
    assert client.get("/api/gold/news").status_code == 200

    resp = client.get("/api/gold/news")
    assert resp.status_code == 429
    body = resp.json()
    assert body["error"]
    assert body["retry_after"] > 0


@pytest.mark.integration
def test_health_is_exempt_from_rate_limiting(client, monkeypatch):
    """回归：健康检查被限流会让编排/探针误判服务不可用。"""
    _install_limiters(monkeypatch, general=1, ai=1)

    for _ in range(5):
        assert client.get("/health").status_code == 200


@pytest.mark.integration
def test_ai_refresh_endpoints_use_a_stricter_limit(client, monkeypatch):
    """会花钱的接口必须比普通接口更容易被挡住。"""
    _install_limiters(monkeypatch, general=100, ai=2)

    # 普通读接口不受 AI 上限影响
    assert client.get("/api/gold/bullish-factors-ai").status_code == 200

    assert client.post("/api/gold/bullish-factors-ai/refresh").status_code != 429
    assert client.post("/api/gold/bullish-factors-ai/refresh").status_code != 429

    assert client.post("/api/gold/bullish-factors-ai/refresh").status_code == 429


@pytest.mark.integration
def test_limiters_are_independent_between_reads_and_refreshes(client, monkeypatch):
    """读接口刷满普通上限，不应连带把刷新接口也挡掉。"""
    _install_limiters(monkeypatch, general=2, ai=10)

    client.get("/api/gold/news")
    client.get("/api/gold/news")
    assert client.get("/api/gold/news").status_code == 429

    assert client.post("/api/gold/bullish-factors-ai/refresh").status_code != 429


@pytest.mark.integration
@pytest.mark.parametrize(
    "path,query,expected",
    [
        # POST 强制刷新
        ("/api/gold/bullish-factors-ai/refresh", "", True),
        # GET 带 refresh=true 同样会走 use_cache=False → 真实调 LLM
        ("/api/gold/bullish-factors-ai", "refresh=true", True),
        ("/api/gold/bullish-factors-ai", "refresh=1", True),
        ("/api/gold/market-summary-ai", "refresh=True", True),
        # 不刷新的读请求不该被算进付费额度
        ("/api/gold/bullish-factors-ai", "refresh=false", False),
        ("/api/gold/bullish-factors-ai", "", False),
        # 普通接口带个同名参数不该被误伤
        ("/api/gold/stats", "refresh=true", False),
        ("/api/gold/prices/daily", "limit=5", False),
    ],
)
def test_ai_path_detection_covers_the_query_flag(path, query, expected):
    """回归：判定只看路径后缀，漏掉了 `?refresh=true`。

    `GET .../bullish-factors-ai?refresh=true` 与 POST /refresh 一样会真实调用
    LLM，却因为路径不以 /refresh 结尾而只受**通用**上限约束 ——
    等于把 6 次/分 的额度放大成 60 次/分。
    """
    from app.main import _is_ai_path

    assert _is_ai_path(path, query) is expected


@pytest.mark.integration
def test_get_with_refresh_flag_hits_the_stricter_limit(client, monkeypatch):
    """端到端确认：带 ?refresh=true 的 GET 也受 AI 上限约束。"""
    _install_limiters(monkeypatch, general=100, ai=2)

    assert client.get("/api/gold/bullish-factors-ai?refresh=true").status_code != 429
    assert client.get("/api/gold/bullish-factors-ai?refresh=true").status_code != 429

    assert client.get("/api/gold/bullish-factors-ai?refresh=true").status_code == 429


# --------------------------------------------------------------------------- #
# CORS
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_cors_config_never_combines_wildcard_with_credentials():
    """回归：`allow_origins=["*"]` + `allow_credentials=True` 时，
    任何站点都能带着用户凭证调用本 API。配置层先禁止这种写法。"""
    from app.config import settings

    origins = [o.strip() for o in settings.CORS_ALLOW_ORIGINS.split(",") if o.strip()]
    assert origins, "必须显式列出允许的来源"
    assert "*" not in origins


@pytest.mark.integration
def test_allowed_origin_is_echoed(client):
    resp = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})

    assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.integration
def test_unknown_origin_is_not_allowed(client):
    resp = client.get("/health", headers={"Origin": "https://evil.example"})

    assert resp.headers.get("access-control-allow-origin") is None

@pytest.mark.integration
def test_429_carries_the_standard_retry_after_header(client, monkeypatch):
    """429 必须带标准的 `Retry-After` 头。

    只把等待时间放在 body 里的话，通用客户端（浏览器、curl、反向代理、
    axios 的重试逻辑）看不到「还要等多久」—— 它们认的是这个头。
    前端的 `describeApiError` 两种都会读，但头是给通用工具用的。
    """
    _install_limiters(monkeypatch, general=1, ai=10)

    # 用 /factors：它在空库上也返回 200（/stats 没有数据时会 404）
    assert client.get("/api/gold/factors").status_code == 200
    blocked = client.get("/api/gold/factors")

    assert blocked.status_code == 429
    assert "retry-after" in {k.lower() for k in blocked.headers}
    assert int(blocked.headers["retry-after"]) >= 1
    # body 里也保留一份（前端与脚本都可能读它）
    assert blocked.json()["retry_after"] >= 1
