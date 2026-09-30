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
