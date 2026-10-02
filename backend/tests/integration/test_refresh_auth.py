"""POST .../refresh 的可选令牌门（2.0.2 第 20 条）。

七条刷新路由会真实调用付费 LLM / 抓外网 / 重算回测；公开部署时任何人都能
反复触发。设了 `REFRESH_TOKEN` 之后，缺头或错令牌必须在**执行任何副作用之前**
被 401 拒绝；没设（默认）则保持旧行为，本机开发不受影响。
"""
from __future__ import annotations

import pytest
from pydantic import SecretStr

REFRESH_ROUTES = [
    "/api/gold/bullish-factors-ai/refresh",
    "/api/gold/bearish-factors-ai/refresh",
    "/api/gold/institution-predictions-ai/refresh",
    "/api/gold/investment-advice-ai/refresh",
    "/api/gold/market-summary-ai/refresh",
    "/api/gold/news/digest/refresh",
    "/api/gold/quant/refresh",
]


def _configure(monkeypatch, token: str) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "REFRESH_TOKEN", SecretStr(token))


def _lift_paid_tier(monkeypatch) -> None:
    """把付费档限流抬到能覆盖全部刷新路由。

    本用例要连打 7 条刷新路由，而默认付费档是 6 次/分钟：第 7 条会先收到
    429，测不到令牌门。本地 `backend/.env` 抬高过上限时看不出来，CI 没有
    `.env`（用默认值）必现 —— 抬的是测试进程内的限流器，生产默认值不动。
    """
    import app.main as main
    from app.utils.rate_limit import SlidingWindowRateLimiter

    monkeypatch.setattr(
        main, "_ai_limiter", SlidingWindowRateLimiter(len(REFRESH_ROUTES) + 1)
    )


@pytest.mark.unit
def test_dependency_semantics(monkeypatch):
    from fastapi import HTTPException

    from app.config import settings
    from app.utils.refresh_auth import require_refresh_token

    monkeypatch.setattr(settings, "REFRESH_TOKEN", SecretStr(""))
    assert require_refresh_token(None) is None, "未配置令牌时必须放行（旧行为）"

    monkeypatch.setattr(settings, "REFRESH_TOKEN", SecretStr("abc"))
    assert require_refresh_token("abc") is None
    assert require_refresh_token(" abc ") is None, "两端空白不应误伤"

    for bad in (None, "", "ab", "abcd"):
        with pytest.raises(HTTPException) as exc:
            require_refresh_token(bad)
        assert exc.value.status_code == 401


@pytest.mark.integration
def test_every_refresh_route_is_behind_the_gate(client, monkeypatch):
    """漏接一条 = 留下一个可被外人刷的付费入口。"""
    _configure(monkeypatch, "s3cret-token")
    _lift_paid_tier(monkeypatch)

    for route in REFRESH_ROUTES:
        resp = client.post(route)
        assert resp.status_code == 401, f"{route} 没被令牌门保护"


@pytest.mark.integration
def test_wrong_token_is_rejected_without_running_anything(
    client, monkeypatch, fake_llm
):
    _configure(monkeypatch, "s3cret-token")

    resp = client.post(
        "/api/gold/bullish-factors-ai/refresh",
        headers={"X-Refresh-Token": "wrong-token"},
    )

    assert resp.status_code == 401
    assert fake_llm.calls == [], "被拒的请求仍然执行了付费分析"


@pytest.mark.integration
def test_correct_token_passes_and_runs_the_refresh(
    client, monkeypatch, fake_llm, seed_news, seed_gold_prices
):
    _configure(monkeypatch, "s3cret-token")
    seed_news(count=1, hours_ago=1)
    seed_gold_prices(days=5)

    resp = client.post(
        "/api/gold/bullish-factors-ai/refresh",
        headers={"X-Refresh-Token": "s3cret-token"},
    )

    assert resp.status_code == 200, resp.text
    assert fake_llm.calls, "令牌正确却没跑分析"


@pytest.mark.integration
def test_open_mode_keeps_working_when_no_token_is_configured(
    client, monkeypatch, fake_llm, seed_news, seed_gold_prices
):
    _configure(monkeypatch, "")
    seed_news(count=1, hours_ago=1)
    seed_gold_prices(days=5)

    resp = client.post("/api/gold/bullish-factors-ai/refresh")

    assert resp.status_code == 200, resp.text
    assert fake_llm.calls