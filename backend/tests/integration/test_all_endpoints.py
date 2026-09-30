"""全接口冒烟：任何 GET 接口都不允许出现未处理的 500。

这是用来**系统性地发现**问题，而不是逐个验证已知问题：新增接口只要会在空库或
上游不可用时崩掉，就会在这里变红。

约定：
  - 空数据库是最苛刻的输入，因此默认就用空库跑
  - 503 是 `dollar-realtime` 有意返回的「上游不可用」，可以接受
  - 除 500 与 503 之外的 5xx 同样视为缺陷
"""
from __future__ import annotations

import pytest

from app.main import app


def _get_paths() -> list[str]:
    """收集所有无路径参数的 GET 接口。

    带 `{param}` 的接口无法直接拼出合法 URL，单独在下面显式测。
    """
    paths: list[str] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods or "GET" not in methods:
            continue
        if "{" in path:
            continue
        if path.startswith("/api/") or path in ("/", "/health"):
            paths.append(path)
    return sorted(set(paths))


GET_PATHS = _get_paths()

# 有意返回 503（上游行情不可用）的接口
ALLOWED_5XX = {"/api/gold/dollar-realtime": {503}}


@pytest.mark.integration
def test_sweep_discovered_endpoints():
    """确保枚举逻辑有效，否则下面的参数化会静默变成空集合。"""
    assert len(GET_PATHS) >= 15, f"只发现 {len(GET_PATHS)} 个 GET 接口"
    assert "/api/gold/stats" in GET_PATHS


@pytest.mark.integration
@pytest.mark.parametrize("path", GET_PATHS)
def test_get_endpoint_does_not_500_on_empty_database(client, path):
    resp = client.get(path)

    allowed = ALLOWED_5XX.get(path, set())
    assert resp.status_code not in allowed or resp.status_code in allowed
    assert resp.status_code < 500 or resp.status_code in allowed, (
        f"{path} 在空库下返回 {resp.status_code}：{resp.text[:300]}"
    )


@pytest.mark.integration
def test_get_endpoint_does_not_500_with_data(client, seed_gold_prices, seed_news):
    """有数据时再扫一遍：某些分支只在有数据时才会走到。"""
    seed_gold_prices(days=5)
    seed_news(count=2)

    failures = []
    for path in GET_PATHS:
        resp = client.get(path)
        allowed = ALLOWED_5XX.get(path, set())
        if resp.status_code >= 500 and resp.status_code not in allowed:
            failures.append(f"{path} -> {resp.status_code}: {resp.text[:200]}")

    assert not failures, "有数据时出现未处理的 5xx：\n" + "\n".join(failures)


# --------------------------------------------------------------------------- #
# 带路径参数的接口
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_news_detail_for_missing_id_returns_404(client):
    """不存在的新闻必须用状态码表达，而不是 200 + error 字段。

    原实现返回 200 + {"error": ...}，调用方无法用状态码判断成败。
    """
    resp = client.get("/api/gold/news/999999")

    assert resp.status_code == 404
    assert "不存在" in resp.json()["detail"]


@pytest.mark.integration
def test_predictions_endpoints_are_consistently_empty(client):
    """predictions 表没有任何代码写入，两个接口都必须是「空」而不是报错。"""
    listing = client.get("/api/gold/predictions")
    assert listing.status_code == 200
    assert listing.json() == []

    latest = client.get("/api/gold/predictions/latest")
    assert latest.status_code == 200
    assert "message" in latest.json()


@pytest.mark.integration
def test_stats_data_source_is_human_readable(client, seed_gold_prices, monkeypatch):
    """回归：`data_source` 是给人看的字段，不能退化成 "tencent" 这类短 id。

    实时价统一入口同时提供 source（短 id）与 source_name（中文名）。
    合并时如果这里取错字段，前端/接口文档上看到的来源就会变成英文标识。
    """
    import app.services.realtime_price as realtime_price

    monkeypatch.setattr(
        realtime_price,
        "get_realtime_gold_price",
        lambda **kwargs: {
            "price": 2700.0,
            "previous_close": 2690.0,
            "change": 10.0,
            "change_percent": 0.37,
            "open": 2695.0,
            "high": 2705.0,
            "low": 2690.0,
            "updated_at": "2026-02-03T10:00:00",
            "date": "2026-02-03",
            "update_time": "2026-02-03 10:00:00",
            "source": "tencent",
            "source_name": "腾讯财经-纽约黄金",
            "symbol": "XAU/USD",
            "unit": "美元/盎司",
        },
    )
    seed_gold_prices(days=5)

    body = client.get("/api/gold/stats").json()

    assert body["data_source"] == "腾讯财经-纽约黄金"
    assert body["is_realtime"] is True
    assert body["current_price"] == 2700.0


@pytest.mark.integration
def test_stats_marks_database_fallback_as_not_realtime(client, seed_gold_prices, monkeypatch):
    """实时源全挂时必须如实标注 is_realtime=False。

    前端据此决定显示「实时」还是「历史数据」——原先那个绿色「实时」徽标是
    无条件渲染的，价格来自数据库历史记录时也照闪。
    """
    import app.services.realtime_price as realtime_price

    monkeypatch.setattr(realtime_price, "get_realtime_gold_price", lambda **kwargs: None)
    seed_gold_prices(days=5)

    body = client.get("/api/gold/stats").json()

    assert body["is_realtime"] is False
    assert body["data_source"] == "数据库历史数据"
