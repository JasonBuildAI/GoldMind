"""健康检查端点集成测试。

这个文件同时充当「测试基建是否可用」的冒烟测试：它验证内存 SQLite、
TestClient lifespan、以及出网拦截都没问题。
"""
import pytest


@pytest.mark.integration
def test_health_returns_expected_shape(client):
    resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("healthy", "degraded")
    assert body["version"] == "1.0.0"
    for service in ("database", "tencent_api", "cache", "scheduler", "ai_config"):
        assert service in body["services"], f"健康检查缺少 {service}"


@pytest.mark.integration
def test_health_reports_mimo_as_provider(client):
    """AI 配置段必须上报 MiMo，而不是迁移前的 deepseek/zhipu。"""
    ai = client.get("/health").json()["services"]["ai_config"]

    assert ai["status"] in ("ok", "unconfigured")
    assert ai["provider"] == "mimo"
    assert ai["model"]
    assert "configured" in ai
    assert "deepseek_configured" not in ai
    assert "zhipu_configured" not in ai


@pytest.mark.integration
def test_health_database_is_connected(client):
    """测试期数据库是内存 SQLite，必须连通。"""
    db = client.get("/health").json()["services"]["database"]

    assert db["status"] == "connected"


@pytest.mark.integration
def test_root_endpoint(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert resp.json()["version"] == "1.0.0"


# --------------------------------------------------------------------------- #
# 信息泄露
# --------------------------------------------------------------------------- #
# /health 是**公开**接口（本项目无鉴权，docs/00-产品方向.md 第四节第 4 条）。
# 各服务的错误分支原本把 `str(e)` 直接回给客户端 —— 数据库异常的文本里会带
# 主机、用户名与驱动细节，例如
#   (1045, "Access denied for user 'root'@'localhost' (using password: YES)")
# 完整信息应当只进服务端日志。

_SECRET_TEXT = "Access denied for user 'root'@'db.internal' password=hunter2"


@pytest.mark.integration
def test_health_does_not_leak_exception_text(client, monkeypatch):
    """回归：错误分支只能回异常类型，不能回异常文本。"""
    from app import main

    def boom():
        raise RuntimeError(_SECRET_TEXT)

    monkeypatch.setattr(main.engine, "connect", boom)

    body = client.get("/health").json()
    raw = str(body)

    assert _SECRET_TEXT not in raw, "/health 把异常原文回给客户端了"
    for fragment in ("hunter2", "Access denied", "db.internal", "Traceback"):
        assert fragment not in raw, f"/health 泄露了 {fragment!r}"

    db = body["services"]["database"]
    assert db["status"] == "disconnected"
    # 异常**类型**是有用的排查线索，保留
    assert db["error_type"] == "RuntimeError"


@pytest.mark.integration
def test_health_does_not_expose_server_paths(client):
    """回归：缓存段原本回完整的服务器绝对路径。"""
    import json
    import re

    raw = json.dumps(client.get("/health").json(), ensure_ascii=False)
    cache = client.get("/health").json()["services"]["cache"]

    # 只给目录名，不给完整路径
    assert "cache_dir" not in cache, "不该再回完整路径"
    assert "/" not in cache.get("cache_dir_name", "")
    assert "\\" not in cache.get("cache_dir_name", "")

    # 盘符形式的绝对路径（前面的负向断言排除 https:// 这类协议前缀）
    assert not re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", raw), "响应里出现了盘符绝对路径"
    # POSIX 形式
    assert not re.search(r"(?:^|[\"' ])/(?:home|Users|var|opt|srv|root)/", raw), "响应里出现了 POSIX 绝对路径"


# --------------------------------------------------------------------------- #
# 上游探测的放大
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_health_does_not_amplify_upstream_requests(client, monkeypatch):
    """回归：/health 是**公开且不限流**的接口，却每次调用都同步请求一次上游。

    也就是说任何人都能让服务器按请求量去打腾讯行情接口，同时把自己的
    /health 拖慢到 3 秒超时。实测 20 次调用 = 20 次出网（1:1 放大）。
    现在探测结果缓存 60 秒。
    """
    import requests

    from app import main

    calls: list[str] = []

    class _Response:
        status_code = 200

    def counting_get(url, *args, **kwargs):
        calls.append(url)
        return _Response()

    monkeypatch.setattr(requests, "get", counting_get)
    # 清掉缓存，保证第一次是真实探测
    monkeypatch.setattr(main, "_upstream_probe", {"at": 0.0, "payload": None})

    for _ in range(20):
        assert client.get("/health").status_code == 200

    assert len(calls) == 1, f"20 次 /health 触发了 {len(calls)} 次出网"


@pytest.mark.integration
def test_health_caches_a_failed_probe_too(client, monkeypatch):
    """上游挂掉时也要缓存结果。

    否则上游不可用期间，每次 /health 都要等满 3 秒超时 —— 探测越慢，
    被刷的代价越高。
    """
    import requests

    from app import main

    calls: list[str] = []

    def failing_get(url, *args, **kwargs):
        calls.append(url)
        raise requests.ConnectionError("upstream down")

    monkeypatch.setattr(requests, "get", failing_get)
    monkeypatch.setattr(main, "_upstream_probe", {"at": 0.0, "payload": None})

    for _ in range(10):
        body = client.get("/health").json()

    assert len(calls) == 1, f"10 次 /health 触发了 {len(calls)} 次出网"
    assert body["services"]["tencent_api"]["status"] == "unavailable"
