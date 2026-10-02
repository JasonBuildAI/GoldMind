"""五个 AI 接口的响应契约。

这些接口此前声明的是 `response_model=Dict[str, Any]` —— 等于没有契约。加上模型
之后立刻暴露了两个长期存在的结构错误：

1. `investment-advice-ai` 缓存未命中时返回的是另一份结构完全不同的历史遗留 dict：
   `market_assessment` / `strategies` / `core_principles` / `disclaimer` 全部缺失。
   前端于是显示内置兜底策略、市场评估一片空白、免责声明消失。
2. `institution-predictions-ai` 的 `target_price` 是字符串（`"2,900美元"`），
   而前端按数字用 `Math.min(...)`，页面显示「目标价集中在 NaN-NaN 美元区间」。

两条都源于同一件事：**占位响应的结构/类型与真实响应不一致**。
"""
from __future__ import annotations

import pytest

# 路径 -> 契约要求的顶层键
AI_ENDPOINTS: dict[str, set[str]] = {
    "/api/gold/bullish-factors-ai": {
        "bullish_factors",
        "analysis_summary",
        "last_updated",
    },
    "/api/gold/bearish-factors-ai": {
        "bearish_factors",
        "analysis_summary",
        "last_updated",
    },
    "/api/gold/institution-predictions-ai": {
        "institutions",
        "analysis_summary",
        "last_updated",
    },
    "/api/gold/investment-advice-ai": {
        "market_assessment",
        "strategies",
        "core_principles",
        "risk_warning",
        "disclaimer",
    },
    "/api/gold/market-summary-ai": {
        "core_bullish_logic",
        "main_risks",
        "market_consensus",
        "institution_targets",
        "comprehensive_judgment",
        "core_view",
        "investment_recommendation",
        "confidence_level",
        "time_horizon",
    },
}


@pytest.mark.integration
@pytest.mark.parametrize("path,required", sorted(AI_ENDPOINTS.items()))
def test_ai_endpoint_returns_its_declared_contract(client, path, required):
    """每个 AI 接口都必须返回契约里声明的顶层键。

    响应模型现在会挡住结构漂移（缺键直接 500），这条测试把「挡住」这件事本身
    也钉住 —— 否则有人把 response_model 改回 Dict[str, Any]，问题会重新变安静。
    """
    response = client.get(f"{path}?refresh=false")

    assert response.status_code == 200, (
        f"{path} 返回 {response.status_code}；响应模型校验失败通常意味着结构漂移"
    )
    missing = required - set(response.json().keys())
    assert not missing, f"{path} 缺少契约字段：{sorted(missing)}"


@pytest.mark.integration
@pytest.mark.parametrize("path", sorted(AI_ENDPOINTS))
def test_ai_endpoints_declare_a_real_response_model(path):
    """回归：不能退回 `Dict[str, Any]` —— 那等于放弃契约。"""
    from fastapi.routing import APIRoute

    from app.main import app

    route = next(
        (r for r in app.routes if isinstance(r, APIRoute) and r.path == path), None
    )
    assert route is not None, f"找不到路由 {path}"
    assert route.response_model is not None, f"{path} 没有声明响应模型"

    # 契约必须能说清有哪些字段
    fields = getattr(route.response_model, "model_fields", None)
    assert fields, f"{path} 的响应模型没有字段（大概又变回 Dict[str, Any] 了）"
    assert required_fields_of(route) >= AI_ENDPOINTS[path]


def required_fields_of(route) -> set[str]:
    return set(route.response_model.model_fields)


@pytest.mark.integration
def test_institution_target_price_is_numeric(client):
    """回归：target_price 曾经是字符串，前端算 Math.min 得到 NaN。

    页面因此显示「目标价集中在 NaN-NaN 美元区间」。
    """
    body = client.get("/api/gold/institution-predictions-ai?refresh=false").json()

    institutions = body["institutions"]

    # 缓存为空时后端返回**空列表** + status=analyzing：产品方向第四节明确禁止
    # 编造机构目标价，所以这里没有「默认内容」可断言，只校验契约本身。
    if not institutions:
        assert body["metadata"]["status"] == "analyzing"
        return

    for item in institutions:
        price = item.get("target_price")
        assert isinstance(price, (int, float)) and not isinstance(price, bool), (
            f"target_price 必须是数字，实际是 {type(price).__name__}: {price!r}"
        )
        assert price > 0, f"target_price 应为正数，实际 {price}"

    # 前端就是这么做区间展示的 —— 不能出 NaN
    prices = [i["target_price"] for i in institutions]
    assert min(prices) == min(prices), "Math.min 得到了 NaN"
    assert max(prices) > 0


@pytest.mark.integration
def test_institution_items_match_the_frontend_contract(client):
    """机构条目必须带上前端渲染需要的字段。"""
    body = client.get("/api/gold/institution-predictions-ai?refresh=false").json()

    for item in body["institutions"]:
        for key in ("name", "rating", "timeframe", "reasoning", "key_points"):
            assert key in item, f"机构条目缺少 {key}"


@pytest.mark.integration
def test_placeholder_responses_are_marked_as_such(client):
    """占位响应必须带上可供前端识别的标记。

    否则前端会把内置常量当成分析结论展示（这是另一条已经修过的 bug）。
    """
    for path in sorted(AI_ENDPOINTS):
        body = client.get(f"{path}?refresh=false").json()
        metadata = body.get("metadata")

        assert metadata is not None, f"{path} 的响应没有 metadata"
        assert metadata.get("status") == "analyzing" or metadata.get("cache_source") == "default", (
            f"{path} 的占位标记无法被 isPlaceholder 识别：{metadata}"
        )


# 端点 -> (缓存键, 一份「模型漏吐 last_updated」的载荷)
_CACHE_PAYLOADS_WITHOUT_LAST_UPDATED = {
    "/api/gold/bullish-factors-ai": (
        "bullish_factors",
        {"bullish_factors": [], "analysis_summary": ""},
    ),
    "/api/gold/bearish-factors-ai": (
        "bearish_factors",
        {"bearish_factors": [], "analysis_summary": ""},
    ),
    "/api/gold/institution-predictions-ai": (
        "institution_predictions",
        {"institutions": [], "analysis_summary": ""},
    ),
}


@pytest.mark.integration
@pytest.mark.parametrize(
    "path,cache_key,payload",
    [
        (path, cache_key, payload)
        for path, (cache_key, payload) in sorted(_CACHE_PAYLOADS_WITHOUT_LAST_UPDATED.items())
    ],
)
def test_cache_hit_without_last_updated_is_backfilled(client, path, cache_key, payload):
    """回归（2026-10-02 实测 500）：模型漏吐 `last_updated` → 缓存命中 → 整个接口崩。

    缓存里存的是分析器原样交给 CacheManager 的 JSON；模型不写这个键时，
    它就一直缺。服务出口的兜底必须把它补成服务端产生的时间，且响应为 200。
    """
    from app.services.cache_manager import CacheManager

    CacheManager(cache_key).set(dict(payload))

    response = client.get(f"{path}?refresh=false")

    assert response.status_code == 200, (
        f"{path} 在缺少 last_updated 的缓存命中路径返回 {response.status_code}"
    )
    body = response.json()
    assert isinstance(body.get("last_updated"), str) and body["last_updated"], (
        f"{path} 没有把 last_updated 兜底成非空字符串：{body.get('last_updated')!r}"
    )
