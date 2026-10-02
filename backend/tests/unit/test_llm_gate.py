"""LLM 调用门控（2.0.2 第 19 条）：输入指纹去重 + 每日调用预算。

两条底线各配守卫：

- **输入没变不重算**：调度器 / 后台任务重复触发的同一份分析，不得再花一次
  付费调用；用户显式刷新（``force=True``）不受限。
- **预算耗尽不发车**：``LLMBudgetExceeded`` 必须在真正发起调用**之前**抛出，
  分析服务随后照常走「暂不可用」，不会为了填满页面而编内容。

本文件里的测试只驱动假 LLM（仓库红线 4），并做变异验证：
把被测行为改坏后必须变红，否则等于没守。
"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.price_window import PriceWindow

WINDOW = PriceWindow(
    window_start=date(2025, 10, 1),
    window_end=date(2026, 10, 1),
    start_price=3800.0,
    end_price=4245.14,
    change_pct=11.71,
    high=4400.0,
    low=3100.0,
    high_date=date(2026, 9, 25),
    low_date=date(2025, 10, 6),
    amplitude_pct=41.94,
    full_window=True,
    label="近12个月",
)


# --------------------------------------------------------------------------- #
# 指纹本身
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_prompt_fingerprint_ignores_declared_volatile_values():
    """声明为 volatile 的时间戳先被替换：两次调用的指纹必须相等。"""
    from app.services.llm_gate import prompt_fingerprint

    stamp_a = "2026-10-03 09:00:00"
    stamp_b = "2026-10-03 09:00:07"
    prompt_a = f"新闻内容：金价上涨。\n当前时间：{stamp_a}\n请分析。"
    prompt_b = f"新闻内容：金价上涨。\n当前时间：{stamp_b}\n请分析。"

    assert prompt_fingerprint(prompt_a, volatile=(stamp_a,)) == prompt_fingerprint(
        prompt_b, volatile=(stamp_b,)
    )


@pytest.mark.unit
def test_prompt_fingerprint_changes_when_content_changes():
    """指纹不能把真内容也「洗掉」：输入数据一变，指纹必须变。"""
    from app.services.llm_gate import prompt_fingerprint

    stamp = "2026-10-03 09:00:00"
    base = f"新闻内容：金价上涨。\n当前时间：{stamp}"
    changed = f"新闻内容：金价下跌。\n当前时间：{stamp}"

    assert prompt_fingerprint(base, volatile=(stamp,)) != prompt_fingerprint(
        changed, volatile=(stamp,)
    )


@pytest.mark.unit
def test_skip_if_unchanged_requires_both_fingerprint_and_cache():
    """跳过条件 = 指纹相同 **且** 结果还在；缺任一条都必须重算。"""
    from app.services.cache_manager import CacheManager
    from app.services.llm_gate import CallGate

    gate = CallGate()
    cache = CacheManager("gate_unit_test", ttl=600)
    cache.set({"bullish_factors": [{"id": "x"}]})

    assert gate.skip_if_unchanged("k", "fp-1", cache) is None, "从未记录过指纹"
    gate.record("k", "fp-1")
    assert gate.skip_if_unchanged("k", "fp-2", cache) is None, "输入变了必须重算"
    assert gate.skip_if_unchanged("k", "fp-1", cache) == {
        "bullish_factors": [{"id": "x"}]
    }

    empty = CallGate()
    assert empty.skip_if_unchanged("k", "fp-1", CacheManager("empty_gate_cache")) is None


# --------------------------------------------------------------------------- #
# 每日预算：在 llm_provider 的真实调用入口上验证
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_daily_budget_blocks_the_next_call_before_it_happens(fake_llm, monkeypatch):
    from app.config import settings
    from app.services import llm_gate
    from app.services.llm_provider import retry_on_content_filter

    monkeypatch.setattr(settings, "LLM_DAILY_CALL_BUDGET", 1)

    retry_on_content_filter(fake_llm, "第一条")
    with pytest.raises(llm_gate.LLMBudgetExceeded):
        retry_on_content_filter(fake_llm, "第二条")

    assert len(fake_llm.calls) == 1, "预算耗尽后仍发起了真实调用"


@pytest.mark.unit
def test_budget_zero_means_no_cap(fake_llm, monkeypatch):
    """budget<=0 是「不设上限」：不能把默认配置误读成封锁。"""
    from app.config import settings
    from app.services.llm_provider import retry_on_content_filter

    monkeypatch.setattr(settings, "LLM_DAILY_CALL_BUDGET", 0)

    for i in range(3):
        retry_on_content_filter(fake_llm, f"第{i}条")

    assert len(fake_llm.calls) == 3


# --------------------------------------------------------------------------- #
# 五个服务的门控键必须与单飞键一致：错一个，跳过就会读到别的服务的缓存
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_gate_keys_match_service_analysis_keys():
    import importlib

    pairs = [
        ("app.services.bullish_factor_service", "BullishFactorService"),
        ("app.services.bearish_factor_service", "BearishFactorService"),
        ("app.services.institution_prediction_service", "InstitutionPredictionService"),
        ("app.services.investment_advice_service", "InvestmentAdviceService"),
        ("app.services.market_summary_service", "MarketSummaryService"),
    ]

    for module_name, class_name in pairs:
        module = importlib.import_module(module_name)
        service_cls = getattr(module, class_name)
        assert module.GATE_KEY == service_cls._ANALYSIS_KEY, module_name


# --------------------------------------------------------------------------- #
# 端到端：输入没变 → 第二次不再调用；输入变了 / force → 必须调用
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_unchanged_input_skips_the_second_call_and_force_bypasses(
    db_session, fake_llm, seed_news, seed_gold_prices
):
    from app.services.bullish_factor_service import BullishFactorService

    seed_news(count=1, hours_ago=1)
    seed_gold_prices(days=5)

    service = BullishFactorService(db_session)
    service.refresh_analysis_sync()
    assert len(fake_llm.calls) == 1

    service.refresh_analysis_sync()
    assert len(fake_llm.calls) == 1, "输入没变却重复调用了 LLM（白花一次付费调用）"

    service.refresh_analysis_sync(force=True)
    assert len(fake_llm.calls) == 2, "force=True 必须绕过指纹门控"


@pytest.mark.integration
def test_new_news_invalidates_the_fingerprint(db_session, fake_llm, seed_news, seed_gold_prices):
    from app.models.news import GoldNews, SentimentType
    from app.services.bullish_factor_service import BullishFactorService
    from app.utils import timeutil

    seed_news(count=1, hours_ago=1)
    seed_gold_prices(days=5)

    service = BullishFactorService(db_session)
    service.refresh_analysis_sync()
    assert len(fake_llm.calls) == 1

    db_session.add(
        GoldNews(
            title="新增：央行宣布增持黄金",
            content="央行购金",
            source="单元测试",
            url="https://example.invalid/news/extra",
            published_at=timeutil.now_naive(),
            sentiment=SentimentType.POSITIVE,
        )
    )
    db_session.commit()

    service.refresh_analysis_sync()
    assert len(fake_llm.calls) == 2, "新闻变了却沿用了旧指纹，跳过了必要的重算"


@pytest.mark.integration
def test_each_analyzer_gate_skips_before_calling_the_model(
    db_session, fake_llm, seed_news, monkeypatch
):
    """四个 Analyzer 的传统 LLM 路径都要在调用前过门控。

    `force` 只在 Service 层暴露，Analyzer 第一次跑完后把结果写进各自的缓存
    （真实运行由 Service 写入同一 key），第二次必须直接复用、不再调用。
    """
    import json

    from app.services.bearish_factor_service import BearishFactorAnalyzer as Bearish
    from app.services.institution_prediction_service import (
        InstitutionPredictionAnalyzer as Institution,
    )
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer as Advice
    from app.services.market_summary_service import MarketSummaryAnalyzer as Summary

    seed_news(count=1, hours_ago=1)
    calls = 0

    for analyzer_cls in (Bearish, Institution):
        analyzer = analyzer_cls()
        fake_llm.responses.append("{}")
        analyzer._analyze_with_traditional_llm(db_session)
        calls += 1
        assert len(fake_llm.calls) == calls, f"{analyzer_cls.__name__} 第一次没有调用 LLM"
        analyzer.cache.set({"cached": True})
        analyzer._analyze_with_traditional_llm(db_session)
        assert len(fake_llm.calls) == calls, f"{analyzer_cls.__name__} 第二次仍调用了 LLM"

    advice = Advice()
    monkeypatch.setattr(advice, "_fetch_recent_news", lambda db, hours=24: [])
    monkeypatch.setattr(advice, "_fetch_recent_prices", lambda db, days=10: [])
    monkeypatch.setattr(advice, "_fetch_window_data", lambda db: WINDOW)
    fake_llm.responses.append(
        json.dumps(
            {
                "market_assessment": {"current_position": "高位"},
                "strategies": [{"type": "conservative"}],
                "core_principles": [],
                "risk_warning": "w",
                "disclaimer": "d",
            }
        )
    )
    advice.analyze(None, "状态", [{"title": "降息预期"}], [], [])
    calls += 1
    assert len(fake_llm.calls) == calls, "投资建议第一次没有调用 LLM"
    advice.cache.set({"cached": True})
    advice.analyze(None, "状态", [{"title": "降息预期"}], [], [])
    assert len(fake_llm.calls) == calls, "投资建议第二次仍调用了 LLM"

    summary = Summary()
    fake_llm.responses.append(
        json.dumps(
            {
                "core_bullish_logic": [],
                "main_risks": [],
                "market_consensus": [],
                "institution_targets": [],
                "current_price": 4200.0,
            }
        )
    )
    summary.analyze(None, "金价在 $4200 附近", [], [], [], [])
    calls += 1
    assert len(fake_llm.calls) == calls, "市场总结第一次没有调用 LLM"
    summary.cache.set({"cached": True})
    summary.analyze(None, "金价在 $4200 附近", [], [], [], [])
    assert len(fake_llm.calls) == calls, "市场总结第二次仍调用了 LLM"