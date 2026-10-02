# -*- coding: utf-8 -*-
"""指纹只在真正解析出内容后记录（2.0.2 冷启动验收逼出来的守卫）。

真实故障（2026-10-03 第二次零人工冷启动验收，build 34c0de8 之前）：
空头因子那次 LLM 输出解析失败，服务返回**空**默认结构，却照样把输入
指纹记进门控；此后只要输入不变，`skip_if_unchanged` 就一直把这份空结构
当「成功结果」复用 —— 页面上空头因子永久为空（探针实测 bearish count: 0）。
多头上限截断（finish_reason=length）与机构解析失败命中同一路径。

约定：解析失败、或解析结果里没有任何可展示内容，都按「本次没产出」处理：
不记指纹、不复用，下一轮重试。四个 LLM 解析入口各配一对守卫：
**失败要重试、成功才跳过**。

变异验证：把任一服务里的 `parsed_ok` / `has_analysis_content` 条件删掉，
对应的「失败要重试」用例必须变红。
"""
from __future__ import annotations

import json

import pytest


def _valid_bullish_payload() -> str:
    return json.dumps(
        {
            "bullish_factors": [
                {
                    "id": "fed-policy",
                    "title": "降息预期升温",
                    "description": "实际利率下行支撑金价",
                    "details": ["市场押注宽松周期"],
                    "impact": "high",
                }
            ]
        }
    )


def _valid_bearish_payload() -> str:
    return json.dumps(
        {
            "bearish_factors": [
                {
                    "id": "profit-taking",
                    "title": "获利了结压力",
                    "description": "高位出现抛压",
                    "details": ["短线资金撤离"],
                    "impact": "medium",
                }
            ]
        }
    )


def _valid_institution_payload() -> str:
    return json.dumps({"institutions": [{"name": "高盛", "rating": "bullish"}]})


def _valid_summary_payload() -> str:
    return json.dumps(
        {
            "core_bullish_logic": [{"point": "降息预期升温"}],
            "core_view": "金价震荡偏多",
        }
    )


# --------------------------------------------------------------------------- #
# 解析失败 / 空输出 → 不得记指纹：第二轮必须重新调用
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_bullish_empty_output_is_retried(db_session, fake_llm, seed_news, seed_gold_prices):
    from app.services.bullish_factor_service import BullishFactorAnalyzer

    seed_news(count=1, hours_ago=1)
    seed_gold_prices(days=5)

    analyzer = BullishFactorAnalyzer()
    fake_llm.responses.append("{}")
    first = analyzer._analyze_with_traditional_llm(db_session)
    assert first.get("bullish_factors") == []
    # Service 层会把这次「空结果」照样写进缓存；门控的错误记录因此会被
    # 一直复用 —— 这正是要防的路径，夹具必须还原它，否则守卫测不到 bug。
    analyzer.cache.set(first)

    analyzer._analyze_with_traditional_llm(db_session)
    assert len(fake_llm.calls) == 2, (
        "空输出被当成成功记了指纹：输入不变时第二轮会永远跳过重试"
    )


@pytest.mark.integration
def test_bearish_parse_failure_is_retried(db_session, fake_llm, seed_news, seed_gold_prices):
    from app.services.bearish_factor_service import BearishFactorAnalyzer

    seed_news(count=1, hours_ago=1)
    seed_gold_prices(days=5)

    analyzer = BearishFactorAnalyzer()
    fake_llm.responses.append("本次分析：无有效 JSON 输出。")
    first = analyzer._analyze_with_traditional_llm(db_session)
    assert first.get("bearish_factors") == []
    analyzer.cache.set(first)

    analyzer._analyze_with_traditional_llm(db_session)
    assert len(fake_llm.calls) == 2, (
        "解析失败被当成成功记了指纹：输入不变时第二轮会永远跳过重试"
    )


@pytest.mark.integration
def test_institution_parse_failure_is_retried(db_session, fake_llm, seed_news):
    from app.services.institution_prediction_service import InstitutionPredictionAnalyzer

    seed_news(count=1, hours_ago=1)

    analyzer = InstitutionPredictionAnalyzer()
    fake_llm.responses.append("{}")
    first = analyzer._analyze_with_traditional_llm(db_session)
    assert not first.get("institutions"), "空输出必须落到空机构结构"
    analyzer.cache.set(first)

    analyzer._analyze_with_traditional_llm(db_session)
    assert len(fake_llm.calls) == 2, (
        "空机构输出被当成成功记了指纹：输入不变时第二轮会永远跳过重试"
    )


@pytest.mark.unit
def test_market_summary_parse_failure_is_retried(fake_llm):
    from app.services.market_summary_service import MarketSummaryAnalyzer

    analyzer = MarketSummaryAnalyzer()
    fake_llm.responses.append("分析如下：市场暂无明显方向。")
    first = analyzer.analyze(None, "震荡", [], [], [], [])
    assert first.get("core_view") == ""
    analyzer.cache.set(first)

    analyzer.analyze(None, "震荡", [], [], [], [])
    assert len(fake_llm.calls) == 2, (
        "解析失败返回的空壳被当成成功记了指纹：输入不变时永远跳过重试"
    )


# --------------------------------------------------------------------------- #
# 解析出真内容 → 记指纹：第二轮必须跳过（不花第二次付费调用）
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_bullish_parsed_content_is_recorded(db_session, fake_llm, seed_news, seed_gold_prices):
    from app.services.bullish_factor_service import BullishFactorAnalyzer

    seed_news(count=1, hours_ago=1)
    seed_gold_prices(days=5)

    analyzer = BullishFactorAnalyzer()
    fake_llm.responses.append(_valid_bullish_payload())
    first = analyzer._analyze_with_traditional_llm(db_session)
    assert first["bullish_factors"], "夹具输出没通过因子校验，用例前提不成立"

    analyzer.cache.set(first)
    analyzer._analyze_with_traditional_llm(db_session)
    assert len(fake_llm.calls) == 1, "真内容记录后第二轮仍然重复调用了 LLM"


@pytest.mark.integration
def test_bearish_parsed_content_is_recorded(db_session, fake_llm, seed_news, seed_gold_prices):
    from app.services.bearish_factor_service import BearishFactorAnalyzer

    seed_news(count=1, hours_ago=1)
    seed_gold_prices(days=5)

    analyzer = BearishFactorAnalyzer()
    fake_llm.responses.append(_valid_bearish_payload())
    first = analyzer._analyze_with_traditional_llm(db_session)
    assert first["bearish_factors"], "夹具输出没通过因子校验，用例前提不成立"

    analyzer.cache.set(first)
    analyzer._analyze_with_traditional_llm(db_session)
    assert len(fake_llm.calls) == 1, "真内容记录后第二轮仍然重复调用了 LLM"


@pytest.mark.integration
def test_institution_parsed_content_is_recorded(db_session, fake_llm, seed_news):
    from app.services.institution_prediction_service import InstitutionPredictionAnalyzer

    seed_news(count=1, hours_ago=1)

    analyzer = InstitutionPredictionAnalyzer()
    fake_llm.responses.append(_valid_institution_payload())
    first = analyzer._analyze_with_traditional_llm(db_session)
    assert first["institutions"], "夹具输出没有机构内容，用例前提不成立"

    analyzer.cache.set(first)
    analyzer._analyze_with_traditional_llm(db_session)
    assert len(fake_llm.calls) == 1, "真内容记录后第二轮仍然重复调用了 LLM"


@pytest.mark.unit
def test_market_summary_parsed_content_is_recorded(fake_llm):
    from app.services.market_summary_service import MarketSummaryAnalyzer

    analyzer = MarketSummaryAnalyzer()
    fake_llm.responses.append(_valid_summary_payload())
    first = analyzer.analyze(None, "震荡", [], [], [], [])
    assert first["core_view"] == "金价震荡偏多"

    analyzer.cache.set(first)
    analyzer.analyze(None, "震荡", [], [], [], [])
    assert len(fake_llm.calls) == 1, "真内容记录后第二轮仍然重复调用了 LLM"
