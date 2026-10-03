"""金价出现在哪儿，它的「最后一次刷新时间」就必须跟到哪儿。

回归背景：金价在页面上出现在五处（侧边栏今日速览 / 行情 / 今日结论「当前价格」/
投资策略降级快照 / 量化基准价），其中三处只给数字不给时间 —— 读者无法判断
「$4,170 是刚才的报价，还是昨天的收盘」。用户明确要求补上。

本文件钉住后端一侧的口径：

1. 价格与它的时间 / 口径 / 来源**同源同刻**取出，不允许只换数字留下旧时间；
2. 取不到金价时四个字段一起为 `null` —— 不编价格，也**不编时间**
   （编一个「刚刚」比不给时间更糟）；
3. 口径名与中文标签只从 `services/price_basis.py` 取，不在各服务里各写一套。
"""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services import price_basis

STATS = {
    "current_price": 4170.09,
    "price_as_of": "2026-10-03T12:40:00",
    "updated_at": "2026-10-03T12:41:00",
    "data_source": "腾讯财经-纽约黄金",
    "is_realtime": True,
}


def _stub_stats(monkeypatch, stats):
    def _get_statistics(self):  # noqa: ANN001
        return stats

    monkeypatch.setattr(
        "app.services.gold_service.GoldService.get_statistics", _get_statistics
    )


# --------------------------------------------------------------------------- #
# 市场总结
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_price_meta_carries_price_time_basis_and_source(monkeypatch):
    from app.services.market_summary_service import MarketSummaryService

    _stub_stats(monkeypatch, STATS)

    meta = MarketSummaryService(db=None)._realtime_price_meta()

    assert meta["price"] == 4170.09
    # 报价自带的时间优先，而不是响应生成的时间（updated_at 是第二顺位）
    assert meta["as_of"] == "2026-10-03T12:40:00"
    assert meta["basis"] == price_basis.REALTIME
    assert meta["basis_label"] == price_basis.LABELS[price_basis.REALTIME]
    assert meta["source"] == "腾讯财经-纽约黄金"


@pytest.mark.unit
def test_price_meta_falls_back_to_close_basis_when_the_realtime_source_failed(monkeypatch):
    """实时源全挂时退回库里的收盘 —— 不许把兜底价说成实时。"""
    from app.services.market_summary_service import MarketSummaryService

    _stub_stats(monkeypatch, {**STATS, "is_realtime": False, "data_source": "数据库历史数据"})

    meta = MarketSummaryService(db=None)._realtime_price_meta()

    assert meta["basis"] == price_basis.CLOSE
    assert meta["basis_label"] == price_basis.LABELS[price_basis.CLOSE]


@pytest.mark.unit
def test_price_meta_is_none_when_the_price_is_unavailable(monkeypatch):
    """取不到金价：整块 None。**不编时间**，也不给一个 0。"""
    from app.services.market_summary_service import MarketSummaryService

    _stub_stats(monkeypatch, {"current_price": None, "data_source": "数据库历史数据"})

    assert MarketSummaryService(db=None)._realtime_price_meta() is None


@pytest.mark.unit
def test_price_meta_is_none_when_the_data_source_blows_up(monkeypatch):
    from app.services.market_summary_service import MarketSummaryService

    def _boom(self):  # noqa: ANN001
        raise RuntimeError("数据源不可达")

    monkeypatch.setattr("app.services.gold_service.GoldService.get_statistics", _boom)

    assert MarketSummaryService(db=None)._realtime_price_meta() is None


@pytest.mark.unit
@pytest.mark.parametrize("price", [None, 4170.09])
def test_all_three_summary_branches_write_the_same_price_fields(monkeypatch, price):
    """新算 / 命中缓存 / 默认三处响应用同一组字段，缺一处就是「有的页面有时间，有的没有」。"""
    from app.services.market_summary_service import MarketSummaryService

    meta = None if price is None else {
        "price": price,
        "as_of": "2026-10-03T12:40:00",
        "basis": price_basis.REALTIME,
        "basis_label": price_basis.LABELS[price_basis.REALTIME],
        "source": "腾讯财经-纽约黄金",
    }
    target: dict = {}

    MarketSummaryService._apply_price_meta(target, meta)

    assert target["current_price"] == price
    assert set(target) == {
        "current_price",
        "price_as_of",
        "price_basis",
        "price_basis_label",
        "price_source",
    }
    if price is None:
        assert target["price_as_of"] is None, "价格都没有，就不许有「金价时间」"
        assert target["price_source"] is None


@pytest.mark.unit
def test_cached_branch_refreshes_the_timestamp_with_the_price(monkeypatch):
    """只换价格不换时间 = 「新价格 + 旧时间」，比不给时间更容易误导。"""
    from app.services.market_summary_service import MarketSummaryService

    service = MarketSummaryService(db=None)
    monkeypatch.setattr(
        service,
        "_realtime_price_meta",
        lambda: {
            "price": 4200.0,
            "as_of": "2026-10-03T12:40:00",
            "basis": price_basis.REALTIME,
            "basis_label": price_basis.LABELS[price_basis.REALTIME],
            "source": "腾讯财经-纽约黄金",
        },
    )
    stale = {
        "core_bullish_logic": [],
        "main_risks": [],
        "market_consensus": [],
        "institution_targets": [],
        "current_price": 1111.0,
        "price_as_of": "2020-01-01T00:00:00",
        "price_basis": price_basis.CLOSE,
        "price_basis_label": price_basis.LABELS[price_basis.CLOSE],
        "price_source": "上一轮的来源",
    }
    monkeypatch.setattr(service.cache, "get", lambda: dict(stale))

    result = service.get_market_summary(institution_predictions=[])

    assert result["current_price"] == 4200.0
    assert result["price_as_of"] == "2026-10-03T12:40:00"
    assert result["price_source"] == "腾讯财经-纽约黄金"


@pytest.mark.unit
def test_summary_response_model_exposes_the_price_fields():
    """接口模型少了字段，前端就拿不到 —— 后端算得再对也白搭。"""
    from app.schemas.analysis_ai import MarketSummaryAIResponse

    fields = MarketSummaryAIResponse.model_fields
    for name in ("price_as_of", "price_basis", "price_basis_label", "price_source"):
        assert name in fields, f"MarketSummaryAIResponse 缺少 {name}"
        assert fields[name].default is None, f"{name} 必须可空（金价取不到时是 null）"


# --------------------------------------------------------------------------- #
# 投资策略的降级快照
# --------------------------------------------------------------------------- #
def _window() -> SimpleNamespace:
    return SimpleNamespace(
        label="近 12 个月",
        window_start=date(2025, 10, 3),
        window_end=date(2026, 10, 2),
        end_price=4100.5,
        change_pct=7.45,
        high=4300.0,
        low=2600.0,
        amplitude_pct=65.4,
        full_window=True,
    )


@pytest.mark.unit
def test_insufficient_data_snapshot_stamps_the_close_price():
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer

    snapshot = InvestmentAdviceAnalyzer().insufficient_data_advice(_window())["price_snapshot"]

    assert snapshot["latest_price"] == 4100.5
    # 快照价就是窗口末的日收盘：时间取它自己的交易日
    assert snapshot["as_of"] == "2026-10-02"
    assert snapshot["basis"] == price_basis.CLOSE
    assert snapshot["basis_label"] == price_basis.LABELS[price_basis.CLOSE]
    assert snapshot["source"]


@pytest.mark.unit
def test_insufficient_data_snapshot_is_absent_when_the_window_is_missing():
    from app.services.investment_advice_service import InvestmentAdviceAnalyzer

    advice = InvestmentAdviceAnalyzer().insufficient_data_advice(None)

    assert advice["price_snapshot"] is None
