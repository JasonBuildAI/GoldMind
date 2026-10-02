"""投资建议的诚实降级：没有可分析输入时，不调 LLM、不给点位。

回归背景：四类输入（多空因子 / 可核实机构预测 / 近期新闻）全空时，原实现
照样调用 LLM，而提示词要求「必须给出具体的入场价位区间」「必须明确止损和
止盈设置」—— 模型只能编。现在输入全空时整条链路确定性降级：只给行情统计与
「数据不足」说明；提示词也允许如实写「数据不足」。
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


def _placeholder_institution() -> dict:
    return {
        "name": "高盛 (Goldman Sachs)",
        "rating": "neutral",
        "target_price": None,
        "reasoning": "暂无最新预测",
        "as_of_date": None,
    }


def _prepare(analyzer, monkeypatch, *, news=None):
    monkeypatch.setattr(analyzer, "_fetch_recent_news", lambda db, hours=24: list(news or []))
    monkeypatch.setattr(analyzer, "_fetch_recent_prices", lambda db, days=10: [])
    monkeypatch.setattr(analyzer, "_fetch_window_data", lambda db: WINDOW)


@pytest.mark.unit
def test_no_llm_call_when_every_input_is_empty(fake_llm, monkeypatch):
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer

    analyzer = InvestmentAdviceAnalyzer()
    _prepare(analyzer, monkeypatch)

    result = analyzer.analyze(None, "金价 $4245.14", [], [], [])

    assert fake_llm.calls == [], "输入全空时不得调用 LLM"
    assert result["analysis_status"] == "insufficient_data"
    assert result["strategies"] == []
    assert result["core_principles"] == []
    assert result["market_assessment"] == {}
    assert result["price_snapshot"]["latest_price"] == 4245.14
    assert result["price_snapshot"]["label"] == "近12个月"


@pytest.mark.unit
def test_placeholder_institutions_count_as_no_input(fake_llm, monkeypatch):
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer

    analyzer = InvestmentAdviceAnalyzer()
    _prepare(analyzer, monkeypatch)

    result = analyzer.analyze(None, "金价 $4245.14", [], [], [_placeholder_institution()])

    assert fake_llm.calls == []
    assert result["analysis_status"] == "insufficient_data"


@pytest.mark.unit
def test_real_input_still_calls_the_llm(fake_llm, monkeypatch):
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer

    fake_llm.responses.append(
        '{"market_assessment": {"current_position": "高位"}, '
        '"strategies": [{"type": "conservative"}], "core_principles": [], '
        '"risk_warning": "w", "disclaimer": "d"}'
    )
    analyzer = InvestmentAdviceAnalyzer()
    _prepare(analyzer, monkeypatch)

    result = analyzer.analyze(None, "金价 $4245.14", [{"title": "降息预期"}], [], [])

    assert len(fake_llm.calls) == 1
    assert result["strategies"] == [{"type": "conservative"}]
    assert result.get("analysis_status") is None


@pytest.mark.unit
def test_news_alone_is_enough_input(fake_llm, monkeypatch):
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer

    fake_llm.responses.append(
        '{"market_assessment": {}, "strategies": [], "core_principles": [], '
        '"risk_warning": "w", "disclaimer": "d"}'
    )
    analyzer = InvestmentAdviceAnalyzer()
    _prepare(analyzer, monkeypatch, news=[{"title": "新闻"}])

    analyzer.analyze(None, "状态", [], [], [])

    assert len(fake_llm.calls) == 1


@pytest.mark.unit
def test_prompt_never_shoulders_the_model_into_invented_price_levels(fake_llm, monkeypatch):
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer

    fake_llm.responses.append(
        '{"market_assessment": {}, "strategies": [], "core_principles": [], '
        '"risk_warning": "w", "disclaimer": "d"}'
    )
    analyzer = InvestmentAdviceAnalyzer()
    _prepare(analyzer, monkeypatch)

    analyzer.analyze(None, "状态", [{"title": "降息预期"}], [], [_placeholder_institution()])

    prompt = fake_llm.calls[0]
    assert "不得为了满足格式编造精确数字" in prompt
    # 占位机构行不得进入提示词 ——「暂无最新预测」不是观点
    assert "暂无最新预测" not in prompt


@pytest.mark.unit
def test_service_degrades_without_reading_stale_cache(fake_llm, monkeypatch):
    from app.services.investment_advice_service import InvestmentAdviceService

    service = InvestmentAdviceService(db=None)
    _prepare(service.analyzer, monkeypatch)
    cache_reads = []
    monkeypatch.setattr(
        service.cache, "get", lambda: cache_reads.append(True) or {"stale": "advice"}
    )

    result = service.get_investment_advice(
        bullish_factors=[], bearish_factors=[], institution_predictions=[]
    )

    assert fake_llm.calls == []
    assert cache_reads == [], "降级路径不得读取旧缓存（旧建议同样没有依据）"
    assert result["metadata"]["status"] == "insufficient_data"
    assert result["metadata"]["cache_source"] == "insufficient_data"
    assert result["price_snapshot"]["latest_price"] == 4245.14


@pytest.mark.unit
def test_cached_degraded_result_keeps_its_status(fake_llm, monkeypatch):
    from app.services.investment_advice_service import InvestmentAdviceService

    service = InvestmentAdviceService(db=None)
    degraded = {
        "analysis_status": "insufficient_data",
        "market_assessment": {},
        "strategies": [],
        "core_principles": [],
        "risk_warning": "数据不足",
        "disclaimer": "",
        "price_snapshot": None,
    }
    monkeypatch.setattr(service.cache, "get", lambda: dict(degraded))

    result = service.get_investment_advice(
        bullish_factors=[{"title": "降息预期"}], bearish_factors=[], institution_predictions=[]
    )

    assert fake_llm.calls == [], "命中降级缓存时同样不得补一次 LLM 调用"
    assert result["metadata"]["status"] == "insufficient_data"
    assert result["metadata"]["cached"] is True
