"""市场总结的机构数据诚实性。

回归背景：`institution_predictions` 里「暂无最新预测」的占位行
（target_price 为空、rating 缺省为 neutral、reasoning 是固定文案）被直接喂给
LLM 后，总结输出「四大投行集体中性评级」这类**不存在的机构判断**：

- 占位行只表示「窗口期内没有可核实预测」，不代表机构给出中性评级；
- 缓存里确实出现过这种内容，与结构化机构数据互相矛盾。

修复分三层：占位行不进提示词；输出用确定性规则清洗；缓存读取时同样清洗。
"""
from __future__ import annotations

import copy
import json

import pytest


def _placeholder(name: str = "高盛 (Goldman Sachs)") -> dict:
    """`institution_prediction_service` 写的跟踪占位行。"""
    return {
        "name": name,
        "rating": "neutral",
        "target_price": None,
        "timeframe": "",
        "reasoning": "暂无最新预测",
        "as_of_date": None,
    }


def _real(name: str = "摩根士丹利 (Morgan Stanley)", target: float = 4000.0) -> dict:
    return {
        "name": name,
        "rating": "bullish",
        "target_price": target,
        "timeframe": "短期",
        "reasoning": "回调接近底部，$4000 构成关键支撑",
        "as_of_date": "2026-10-01",
    }


def _fabricated_summary() -> dict:
    """复刻缓存里真实出现过的幻觉输出（含不存在的机构目标价）。"""
    return {
        "core_bullish_logic": ["美元走强压制金价", "四家顶级机构均维持中性评级，无看空信号"],
        "main_risks": ["114%振幅蕴含回调风险", "四大投行暂无统一目标价"],
        "market_consensus": ["高盛、瑞银、摩根士丹利、花旗均维持中性评级", "市场波动加大"],
        "institution_targets": [
            {"institution": "高盛 (Goldman Sachs)", "target": 5400, "probability": "中"},
            {"institution": "摩根士丹利 (Morgan Stanley)", "target": 4000, "probability": "高"},
        ],
        "current_price": 4245.14,
    }


@pytest.mark.unit
def test_placeholder_rows_are_not_usable_institution_data():
    from app.services.market_summary_service import usable_institution_predictions

    assert usable_institution_predictions(None) == []
    assert usable_institution_predictions([_placeholder()]) == []
    assert usable_institution_predictions([_real()]) == [_real()]


@pytest.mark.unit
def test_row_with_a_date_but_no_target_is_still_data():
    from app.services.market_summary_service import usable_institution_predictions

    rows = [
        {"name": "瑞银 (UBS)", "target_price": None, "reasoning": "暂无最新预测", "as_of_date": None},
        {"name": "瑞银 (UBS)", "target_price": None, "reasoning": "暂无最新预测", "as_of_date": "2026-09-30"},
    ]

    assert usable_institution_predictions(rows) == [rows[1]]


@pytest.mark.unit
def test_sanitize_clears_institution_claims_when_only_placeholders_exist():
    from app.services.market_summary_service import sanitize_institution_claims

    cleaned = sanitize_institution_claims(_fabricated_summary(), [_placeholder()])

    assert cleaned["institution_targets"] == []
    assert cleaned["core_bullish_logic"] == ["美元走强压制金价"]
    assert cleaned["main_risks"] == ["114%振幅蕴含回调风险"]
    assert cleaned["market_consensus"] == ["市场波动加大"]
    assert cleaned["current_price"] == 4245.14, "价格不是机构判断，应保留"


@pytest.mark.unit
def test_macro_factors_survive_even_without_institution_data():
    """央行动向是宏观事实，不是机构判断；清洗不得误伤。"""
    from app.services.market_summary_service import sanitize_institution_claims

    result = {
        "core_bullish_logic": ["全球央行持续购金"],
        "market_consensus": ["美联储降息预期升温"],
    }

    cleaned = sanitize_institution_claims(result, [_placeholder()])

    assert cleaned["core_bullish_logic"] == ["全球央行持续购金"]
    assert cleaned["market_consensus"] == ["美联储降息预期升温"]


@pytest.mark.unit
def test_sanitize_keeps_only_institutions_with_real_predictions():
    from app.services.market_summary_service import sanitize_institution_claims

    cleaned = sanitize_institution_claims(_fabricated_summary(), [_real()])

    assert [t["institution"] for t in cleaned["institution_targets"]] == [
        "摩根士丹利 (Morgan Stanley)"
    ], "高盛没有可核实预测，它的目标价条目不得保留"
    assert cleaned["market_consensus"] == ["市场波动加大"], (
        "提到了没有可核实数据的机构 → 整条删除"
    )


@pytest.mark.unit
def test_sanitize_keeps_entries_matching_the_real_predictions():
    from app.services.market_summary_service import sanitize_institution_claims

    result = {
        "core_bullish_logic": ["摩根士丹利认为 $4000 构成关键底部支撑"],
        "main_risks": [],
        "market_consensus": ["摩根士丹利长期看至 2027 下半年 $5000"],
        "institution_targets": [{"institution": "摩根士丹利 (Morgan Stanley)", "target": 4000}],
        "current_price": 4200.0,
    }

    assert sanitize_institution_claims(copy.deepcopy(result), [_real()]) == result


@pytest.mark.unit
def test_sanitize_drops_english_and_generic_institution_claims():
    from app.services.market_summary_service import sanitize_institution_claims

    result = {
        "core_bullish_logic": ["Goldman Sachs expects a pullback", "Wall Street is split"],
        "main_risks": [],
        "market_consensus": [],
    }

    cleaned = sanitize_institution_claims(result, [_real()])

    assert cleaned["core_bullish_logic"] == []


@pytest.mark.unit
def test_prompt_hides_placeholder_rows_and_states_the_rule():
    from app.services.market_summary_service import MarketSummaryAnalyzer

    prompt = MarketSummaryAnalyzer()._build_analysis_prompt(
        "金价在 $4200 附近", [], [], [_placeholder()], []
    )

    assert "高盛" not in prompt, "占位行不得以机构评级形式进入提示词"
    assert "暂无数据" in prompt
    assert "institution_targets 必须为空数组" in prompt


@pytest.mark.unit
def test_prompt_feeds_real_rows_and_hides_placeholders():
    from app.services.market_summary_service import MarketSummaryAnalyzer

    prompt = MarketSummaryAnalyzer()._build_analysis_prompt(
        "金价在 $4200 附近", [], [], [_placeholder(), _real()], []
    )

    assert "- 摩根士丹利 (Morgan Stanley): 目标价$4000.0" in prompt
    assert "高盛" not in prompt


@pytest.mark.unit
def test_analyze_sanitizes_fabricated_institution_output(fake_llm):
    from app.services.market_summary_service import MarketSummaryAnalyzer

    fake_llm.responses.append(
        json.dumps(
            {
                "core_bullish_logic": ["四家顶级机构均维持中性评级"],
                "main_risks": [],
                "market_consensus": ["高盛、瑞银、摩根士丹利、花旗均维持中性评级"],
                "institution_targets": [{"institution": "高盛 (Goldman Sachs)", "target": 5400}],
                "current_price": 4245.14,
            },
            ensure_ascii=False,
        )
    )

    result = MarketSummaryAnalyzer().analyze(
        None, "金价在 $4200 附近", [], [], [_placeholder()], []
    )

    assert result["institution_targets"] == []
    assert result["core_bullish_logic"] == []
    assert result["market_consensus"] == []


@pytest.mark.unit
def test_cached_summary_is_sanitized_with_current_institution_data(monkeypatch):
    from app.services.market_summary_service import MarketSummaryService

    service = MarketSummaryService(db=None)
    monkeypatch.setattr(service, "_get_realtime_price", lambda: 4200.0)
    monkeypatch.setattr(service.cache, "get", lambda: _fabricated_summary())

    result = service.get_market_summary(institution_predictions=[_placeholder()])

    assert result["institution_targets"] == []
    assert result["market_consensus"] == ["市场波动加大"]
    assert result["current_price"] == 4200.0, "实时价格仍应覆盖缓存价格"


@pytest.mark.unit
def test_cached_summary_keeps_targets_with_real_predictions(monkeypatch):
    from app.services.market_summary_service import MarketSummaryService

    service = MarketSummaryService(db=None)
    monkeypatch.setattr(service, "_get_realtime_price", lambda: 4200.0)
    monkeypatch.setattr(service.cache, "get", lambda: _fabricated_summary())

    result = service.get_market_summary(institution_predictions=[_real()])

    assert [t["institution"] for t in result["institution_targets"]] == [
        "摩根士丹利 (Morgan Stanley)"
    ]
