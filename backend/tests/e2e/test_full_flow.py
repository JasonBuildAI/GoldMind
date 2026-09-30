"""端到端测试：把整个用户旅程走一遍。

与 `tests/integration/` 的区别：
    - integration 逐个端点验证契约；
    - e2e 按**真实使用顺序**串起整条链路，并检查跨层的数据一致性
      （种进数据库的数字，最终必须出现在给 LLM 的 prompt 和给前端的响应里）。

所有外部依赖都被替换：LLM 用按 prompt 内容分发的假实现，行情与 RSS 由
conftest 的出网拦截兜底，数据库是内存 SQLite。
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from app.services import llm_provider

# --------------------------------------------------------------------------- #
# 各分析服务的期望输出结构（与 prompt 里要求的 schema 一致）
# --------------------------------------------------------------------------- #
BULLISH = {
    "bullish_factors": [
        {
            "id": "fed-policy",
            "title": "端到端看涨因子",
            "subtitle": "副标题",
            "description": "描述",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "high",
        }
    ],
    "analysis_summary": "看涨总结",
    "last_updated": "2026-02-03 10:00:00",
}

BEARISH = {
    "bearish_factors": [
        {
            "id": "dollar-strength",
            "title": "端到端看跌因子",
            "subtitle": "副标题",
            "description": "描述",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "medium",
        }
    ],
    "analysis_summary": "看跌总结",
    "last_updated": "2026-02-03 10:00:00",
}

INSTITUTIONS = {
    "institutions": [
        {
            "name": "高盛 (Goldman Sachs)",
            "logo": "GS",
            "rating": "bullish",
            "target_price": 5400,
            "timeframe": "2026年底",
            "reasoning": "端到端机构理由",
            "key_points": ["a", "b", "c", "d"],
        }
    ],
    "analysis_summary": "机构汇总",
    "last_updated": "2026-02-03 10:00:00",
}

ADVICE = {
    "market_assessment": {
        "current_position": "中位",
        "risk_level": "medium",
        "recommended_approach": "分批建仓",
        "key_considerations": ["考虑1", "考虑2", "考虑3"],
    },
    "strategies": [
        {
            "type": "conservative",
            "title": "保守策略",
            "description": "描述",
            "allocation": "5%",
            "timeframe": "长期",
            "risk_level": "low",
            "entry_strategy": {
                "current_price_assessment": "偏高",
                "recommended_entry_range": "$2500-2600",
                "entry_timing": "等待回调",
                "position_building": "分三批",
            },
            "exit_strategy": {
                "profit_target": "$2900",
                "stop_loss": "-10%",
                "rebalancing_trigger": "年末",
            },
            "pros": ["稳"],
            "cons": ["收益低"],
            "suitable_for": ["新手"],
            "execution_steps": ["步骤1", "步骤2"],
        }
    ],
    "core_principles": [{"title": "风险管理", "description": "描述"}],
    "risk_warning": "端到端风险提示",
    "disclaimer": "端到端免责声明",
}

SUMMARY = {
    "core_bullish_logic": ["端到端核心看涨逻辑"],
    "main_risks": ["端到端主要风险"],
    "market_consensus": ["端到端市场共识"],
    "institution_targets": [
        {"institution": "高盛", "target": 5400, "probability": "高", "timeframe": "2026年底"}
    ],
    "current_price": 2690.0,
    "comprehensive_judgment": {
        "bullish_summary": "偏多",
        "bearish_summary": "偏空",
        "neutral_summary": "中性",
    },
    "core_view": "端到端核心观点",
    "investment_recommendation": "端到端投资建议",
    "confidence_level": "中",
    "time_horizon": "中期",
}

# 按 prompt 内容分发。注意顺序：先匹配最独特的键，
# 因为「投资建议」和「市场总结」的 prompt 里会嵌入因子数据。
DISPATCH = [
    ("market_assessment", ADVICE),
    ("core_bullish_logic", SUMMARY),
    ("institutions", INSTITUTIONS),
    ("bearish_factors", BEARISH),
    ("bullish_factors", BULLISH),
]


class SmartFakeLLM:
    """按 prompt 里要求的 JSON 结构返回对应样例。"""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.unmatched: list[str] = []
        self.last_kwargs: dict[str, Any] = {}

    def invoke(self, prompt: str):
        self.calls.append(prompt)
        for needle, payload in DISPATCH:
            if needle in prompt:
                return _Message(json.dumps(payload, ensure_ascii=False))
        self.unmatched.append(prompt[:200])
        return _Message("{}")

    def prompts_for(self, needle: str) -> list[str]:
        return [p for p in self.calls if needle in p]


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


@pytest.fixture
def smart_llm(monkeypatch: pytest.MonkeyPatch) -> SmartFakeLLM:
    llm = SmartFakeLLM()

    class _Factory:
        def __call__(self, **kwargs):
            llm.last_kwargs = kwargs
            return llm

    monkeypatch.setattr(llm_provider, "_chat_openai_class", lambda: _Factory())
    return llm


# --------------------------------------------------------------------------- #
# 旅程
# --------------------------------------------------------------------------- #
@pytest.mark.e2e
def test_journey_from_empty_database_degrades_gracefully(client, smart_llm):
    """空库启动：行情类接口给出明确错误，AI 类接口仍可用（走默认/兜底）。"""
    assert client.get("/api/gold/stats").status_code == 404
    assert client.get("/api/gold/prices/latest").status_code == 404
    assert client.get("/api/gold/prices/daily").json() == []

    for path in (
        "/api/gold/bullish-factors-ai",
        "/api/gold/bearish-factors-ai",
        "/api/gold/institution-predictions-ai",
        "/api/gold/market-summary-ai",
    ):
        assert client.get(path).status_code == 200, path


@pytest.mark.e2e
def test_full_user_journey(client, seed_gold_prices, seed_news, smart_llm):
    """种数据 → 看行情 → 看新闻 → 看分析，并校验跨层数据一致性。"""
    seed_gold_prices(days=10, start=2600.0, step=10.0)
    seed_news(count=3)

    # --- 1. 健康检查 ---
    health = client.get("/health").json()
    assert health["services"]["database"]["status"] == "connected"
    assert health["services"]["ai_config"]["provider"] == "mimo"

    # --- 2. 行情：日线 + 统计 + 相关性 ---
    daily = client.get("/api/gold/prices/daily").json()
    assert len(daily) >= 10
    assert daily[0]["date"] == "2025-01-02"
    assert daily[0]["price"] == 2600.0

    stats = client.get("/api/gold/stats")
    assert stats.status_code == 200
    stats = stats.json()
    # 最新收盘 2690（2600 + 10*9），起始 2600
    assert stats["current_price"] == 2690.0
    assert stats["start_price"] == 2600.0
    assert stats["ytd_return"] == pytest.approx(3.46, abs=0.01)
    # 最高 = max(high) = 2695；最低 = min(low) = 2595
    assert stats["max_price"] == 2695.0
    assert stats["min_price"] == 2595.0
    assert stats["market_status"]

    correlation = client.get("/api/gold/prices/correlation").json()
    assert len(correlation) >= 10
    assert set(correlation[0]) == {"date", "gold_price", "dollar_index"}

    # --- 3. 新闻 ---
    news = client.get("/api/gold/news").json()
    assert len(news) == 3
    assert news[0]["title"].startswith("测试新闻")

    sentiment = client.get("/api/gold/news/sentiment/summary").json()
    assert sentiment["neutral"] == 3

    # --- 4. 分析接口：先看「无缓存」行为，再触发真实分析 ---
    # 4a. 缓存为空时 GET 返回内置默认因子，且不调用 LLM
    first_view = client.get("/api/gold/bullish-factors-ai").json()
    assert first_view["metadata"]["status"] == "analyzing"
    # 缓存为空时**不返回任何内容** —— 编造的因子与真实分析结构一样，用户分不出来。
    # 项目红线：「不为了好看而展示编造的数据 —— 宁可显示「数据不可用」」。
    assert first_view["bullish_factors"] == []
    assert first_view["analysis_summary"] == ""
    assert smart_llm.calls == []

    # 4b. 用户点「刷新」→ 真正跑一次分析
    refreshed = client.post("/api/gold/bullish-factors-ai/refresh")
    assert refreshed.status_code == 200
    assert refreshed.json()["data"]["bullish_factors"][0]["title"] == "端到端看涨因子"

    # 4c. 再读一次 → 命中缓存，拿到刚才那份真实分析
    cached = client.get("/api/gold/bullish-factors-ai").json()
    assert cached["bullish_factors"][0]["title"] == "端到端看涨因子"
    assert cached["metadata"]["cached"] is True

    assert client.post("/api/gold/bearish-factors-ai/refresh").status_code == 200
    assert client.get("/api/gold/institution-predictions-ai").status_code == 200
    assert client.get("/api/gold/market-summary-ai").status_code == 200

    # --- 5. 投资建议：整条链路的汇聚点 ---
    # 这个端点内部会依次跑 看涨 → 看跌 → 机构 → 建议，是最完整的一条链
    advice = client.post("/api/gold/investment-advice-ai/refresh")
    assert advice.status_code == 200
    assert advice.json()["data"]["risk_warning"] == "端到端风险提示"

    # --- 6. 跨层一致性：数据库里的真实数字必须一路传到 prompt ---
    assert smart_llm.calls, "整个旅程中一次 LLM 都没被调用"
    assert not smart_llm.unmatched, f"有 prompt 没被识别: {smart_llm.unmatched}"

    advice_prompts = smart_llm.prompts_for("market_assessment")
    assert advice_prompts, "投资建议的 prompt 没有生成"
    advice_prompt = advice_prompts[0]
    # 统计值来自数据库（而不是恒为 0 的旧 bug）
    assert "3.46%" in advice_prompt
    assert "0.00%" not in advice_prompt
    # 同一请求链里上游产出的因子内容，被带进了最终建议
    assert "端到端看涨因子" in advice_prompt
    assert "端到端看跌因子" in advice_prompt


@pytest.mark.e2e
def test_refresh_cycle_produces_data_for_every_analysis(client, seed_gold_prices, smart_llm):
    """POST /refresh 全轮跑一遍：每个服务都必须产出内容，且写回缓存。"""
    seed_gold_prices(days=5)

    endpoints = {
        "bullish": ("/api/gold/bullish-factors-ai/refresh", "bullish_factors"),
        "bearish": ("/api/gold/bearish-factors-ai/refresh", "bearish_factors"),
        "institution": ("/api/gold/institution-predictions-ai/refresh", "institutions"),
        "advice": ("/api/gold/investment-advice-ai/refresh", "strategies"),
        "summary": ("/api/gold/market-summary-ai/refresh", "core_bullish_logic"),
    }

    for name, (path, key) in endpoints.items():
        resp = client.post(path)
        assert resp.status_code == 200, f"{name}: {resp.text[:200]}"
        assert resp.json()["success"] is True, name
        assert resp.json()["data"].get(key), f"{name} 的 data.{key} 为空"


@pytest.mark.e2e
def test_cached_read_after_refresh_is_consistent(client, seed_gold_prices, smart_llm):
    """刷新后立刻读缓存：两次响应应描述同一份分析（不是又回退到默认值）。"""
    seed_gold_prices(days=5)

    refreshed = client.post("/api/gold/bullish-factors-ai/refresh").json()["data"]
    cached = client.get("/api/gold/bullish-factors-ai").json()

    assert refreshed["bullish_factors"][0]["title"] == "端到端看涨因子"
    assert cached["bullish_factors"][0]["title"] == "端到端看涨因子"
    assert cached.get("metadata", {}).get("cached") is True


@pytest.mark.e2e
def test_get_without_cache_returns_no_content_and_a_status(client, seed_gold_prices, smart_llm):
    """诚实记录一个产品行为：缓存为空时，GET 返回的是**硬编码默认因子**，
    而不是真实分析结果 —— 真实分析只在 /refresh 或后台任务里发生。

    这就是为什么服务重启后（或首次加载时）页面上的「分析」可能并非当天生成，
    却依然显示得像一份分析结论。前端会用一行提示区分，但数据本身是内置常量。
    """
    seed_gold_prices(days=5)

    body = client.get("/api/gold/bullish-factors-ai").json()

    assert smart_llm.calls == [], "缓存为空时 GET 不应触发 LLM 调用"
    assert body["metadata"]["status"] == "analyzing"
    # 不返回内置因子，也不返回写死的总结文案
    assert body["bullish_factors"] == []
    assert body["analysis_summary"] == ""
    # 前端靠 metadata.status 显示「正在分析中」
    assert "进行中" in body["metadata"]["message"]


@pytest.mark.e2e
def test_llm_client_is_constructed_from_config_not_hardcoded(
    client, seed_gold_prices, smart_llm
):
    """LLM 必须以「配置里的 MiMo 端点」构造，而不是任何遗留供应商的硬编码地址。

    测试环境把 MIMO_BASE_URL 指向 example.invalid，所以这里断言的是
    「取值来自 settings」——即工厂确实读配置；再显式排除旧供应商域名。
    """
    from app.config import settings

    seed_gold_prices(days=5)
    assert client.post("/api/gold/bullish-factors-ai/refresh").status_code == 200

    assert smart_llm.last_kwargs, "没有捕获到 LLM 构造参数"
    assert smart_llm.last_kwargs["base_url"] == settings.MIMO_BASE_URL
    assert smart_llm.last_kwargs["model"] == settings.MIMO_MODEL
    assert smart_llm.last_kwargs["api_key"] == settings.MIMO_API_KEY
    assert smart_llm.last_kwargs["max_tokens"] == 4096
    for stale in ("deepseek.com", "bigmodel.cn"):
        assert stale not in smart_llm.last_kwargs["base_url"]
