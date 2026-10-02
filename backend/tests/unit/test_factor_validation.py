"""因子输出的结构校验 —— 数量 / 去重 / 枚举 / best-effort 数字引用。

由来：prompt 早已写清「最多 5 个因子、id 必须在允许集合内、必须有新闻支撑」，
但代码 `json.loads` 后直接 return —— 模型给出重复因子、拼错 id、或凭空引用
新闻里不存在的数字时，页面、缓存与数据库照单全收。
"""
from __future__ import annotations

import json

import pytest

from app.services.factor_validation import validate_factor_response


def _factor(**overrides):
    base = {
        "id": "fed-policy",
        "title": "美联储降息预期",
        "subtitle": "政策转向",
        "description": "非农数据走弱强化降息预期，支撑金价",
        "details": ["要点一", "要点二"],
        "impact": "high",
    }
    base.update(overrides)
    return base


def _payload(*factors, side: str = "bullish"):
    return {f"{side}_factors": list(factors), "analysis_summary": "总结"}


@pytest.mark.unit
def test_clean_payload_passes_through_unchanged():
    result = _payload(_factor())

    cleaned, dropped = validate_factor_response(result, side="bullish")

    assert dropped == []
    assert cleaned["bullish_factors"] == result["bullish_factors"]
    assert cleaned["analysis_summary"] == "总结"


@pytest.mark.unit
def test_unknown_id_is_dropped():
    cleaned, dropped = validate_factor_response(
        _payload(_factor(id="invented-id")), side="bullish"
    )

    assert cleaned["bullish_factors"] == []
    assert dropped and "invented-id" in dropped[0]


@pytest.mark.unit
def test_duplicate_id_and_duplicate_title_keep_the_first():
    first = _factor()
    same_id = _factor(title="另一个标题")
    same_title = _factor(id="central-bank")

    cleaned, dropped = validate_factor_response(
        _payload(first, same_id, same_title), side="bullish"
    )

    assert [item["id"] for item in cleaned["bullish_factors"]] == ["fed-policy"]
    assert len(dropped) == 2


@pytest.mark.unit
def test_caps_the_factor_count():
    factors = [
        _factor(id="fed-policy", title="因子一"),
        _factor(id="central-bank", title="因子二"),
        _factor(id="dollar-credit", title="因子三"),
    ]

    cleaned, dropped = validate_factor_response(
        _payload(*factors), side="bullish", max_factors=2
    )

    assert len(cleaned["bullish_factors"]) == 2
    assert any("上限" in reason for reason in dropped)


@pytest.mark.unit
def test_missing_fields_and_empty_details_are_dropped():
    empty_title = _factor(title="")
    no_description = _factor(id="central-bank", description="  ")
    empty_details = _factor(id="dollar-credit", details=[])

    cleaned, dropped = validate_factor_response(
        _payload(empty_title, no_description, empty_details), side="bullish"
    )

    assert cleaned["bullish_factors"] == []
    assert len(dropped) == 3


@pytest.mark.unit
def test_invalid_impact_is_normalized_to_medium():
    cleaned, _ = validate_factor_response(
        _payload(_factor(impact="extreme")), side="bullish"
    )

    assert cleaned["bullish_factors"][0]["impact"] == "medium"


@pytest.mark.unit
def test_factor_numbers_must_appear_in_the_reference_news():
    invented = _factor(description="机构给出 8888 美元目标价")
    supported = _factor(id="central-bank", description="机构给出 5400 美元目标价")
    reference = "- [2026-10-02 21:00] [路透社] 某机构预测 5400 美元"

    cleaned, dropped = validate_factor_response(
        _payload(invented, supported), side="bullish", reference_text=reference
    )

    assert [item["id"] for item in cleaned["bullish_factors"]] == ["central-bank"]
    assert dropped and "8888" not in dropped[0] and "依据" in dropped[0]


@pytest.mark.unit
def test_number_check_is_skipped_without_a_reference_text():
    cleaned, dropped = validate_factor_response(
        _payload(_factor(description="机构给出 8888 美元目标价")), side="bullish"
    )

    assert len(cleaned["bullish_factors"]) == 1
    assert dropped == []


@pytest.mark.unit
def test_side_specific_ids_do_not_leak_across_sides():
    cleaned, dropped = validate_factor_response(
        _payload(_factor(id="fed-policy", title="美联储降息预期"), side="bearish"),
        side="bearish",
    )

    assert cleaned["bearish_factors"] == []
    assert dropped


@pytest.mark.unit
def test_non_list_factors_degrade_to_empty():
    cleaned, dropped = validate_factor_response(
        {"bullish_factors": {"not": "a list"}}, side="bullish"
    )

    assert cleaned["bullish_factors"] == []
    assert dropped


# --------------------------------------------------------------------------- #
# 服务路径：脏输出在返回 / 缓存前被清洗
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_dirty_llm_output_is_cleaned_before_return(db_session, fake_llm):
    from app.models.news_digest import NewsDigestItem
    from app.services.bullish_factor_service import BullishFactorAnalyzer
    from app.utils import timeutil

    db_session.add(
        NewsDigestItem(
            title="央行连续第三个月增持黄金",
            summary="",
            source="路透社",
            source_key="reuters",
            authority_tier=1,
            url="https://digest.invalid/a",
            published_at=timeutil.now_naive(),
            fetched_at=timeutil.now_naive(),
        )
    )
    db_session.commit()

    dirty = {
        "bullish_factors": [
            _factor(),
            _factor(title="重复的另一个标题"),
            _factor(id="invented-id", title="拼错的 id"),
        ],
        "analysis_summary": "总结",
    }
    fake_llm.responses.append(json.dumps(dirty, ensure_ascii=False))

    result = BullishFactorAnalyzer()._analyze_with_traditional_llm(db_session)

    assert fake_llm.calls, "应走 LLM 路径"
    assert [item["id"] for item in result["bullish_factors"]] == ["fed-policy"]


@pytest.mark.integration
def test_invalid_search_result_falls_back_to_the_llm_path(db_session, fake_llm, monkeypatch):
    from app.models.news_digest import NewsDigestItem
    from app.services.bullish_factor_service import BullishFactorAnalyzer
    from app.utils import timeutil

    db_session.add(
        NewsDigestItem(
            title="央行连续第三个月增持黄金",
            summary="",
            source="路透社",
            source_key="reuters",
            authority_tier=1,
            url="https://digest.invalid/b",
            published_at=timeutil.now_naive(),
            fetched_at=timeutil.now_naive(),
        )
    )
    db_session.commit()

    analyzer = BullishFactorAnalyzer()
    monkeypatch.setattr(
        analyzer,
        "_search_bullish_factors",
        lambda: {"bullish_factors": [_factor(id="invented-id")], "analysis_summary": "脏"},
    )

    result = analyzer.analyze(db_session)

    assert fake_llm.calls, "搜索输出全部不合格时必须回退到有依据的分析路径"
    assert result.get("bullish_factors", []) == []


@pytest.mark.integration
def test_valid_search_result_is_returned_without_the_fallback(db_session, fake_llm, monkeypatch):
    from app.services.bullish_factor_service import BullishFactorAnalyzer

    analyzer = BullishFactorAnalyzer()
    monkeypatch.setattr(
        analyzer,
        "_search_bullish_factors",
        lambda: {"bullish_factors": [_factor()], "analysis_summary": "干净"},
    )

    result = analyzer.analyze(db_session)

    assert result["data_source"] == "联网搜索"
    assert [item["id"] for item in result["bullish_factors"]] == ["fed-policy"]
    assert fake_llm.calls == [], "搜索结果合格时不应再走备用 LLM"
