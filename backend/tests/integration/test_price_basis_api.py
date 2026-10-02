"""价格口径（basis）接口守卫：每个价格都要带口径、来源与 as-of（A9）。

红线：口径不许靠 is_realtime 反推 —— 兜底价必须标成日收盘，
量化基准必须标明它派生自 gold_close 日收盘序列。
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _quote(**overrides):
    quote = {
        "price": 4210.5,
        "previous_close": 4200.0,
        "change": 10.5,
        "change_percent": 0.25,
        "updated_at": "2026-10-03T10:00:00+08:00",
        "date": "2026-10-03",
        "source": "sina",
        "source_name": "新浪财经-伦敦金",
    }
    quote.update(overrides)
    return quote


def _stub_realtime(monkeypatch, quote):
    import app.services.realtime_price as realtime_price

    monkeypatch.setattr(realtime_price, "get_realtime_gold_price", lambda **kwargs: quote)


def test_daily_prices_label_the_realtime_point_and_keep_close_for_history(
    client, seed_gold_prices, monkeypatch
):
    seed_gold_prices(days=5)
    _stub_realtime(monkeypatch, _quote())

    body = client.get("/api/gold/prices/daily?limit=50").json()

    assert len(body) == 5
    last = body[-1]
    assert last["basis"] == "realtime"
    assert last["basis_label"] == "实时报价"
    assert last["source"] == "新浪财经-伦敦金"
    assert last["as_of"] == "2026-10-03"
    # 历史行全部是日收盘，且 as-of 与日期一致。
    for row in body[:-1]:
        assert row["basis"] == "close"
        assert row["basis_label"] == "日收盘"
        assert row["as_of"] == row["date"]


def test_daily_prices_keep_close_basis_when_realtime_falls_back_to_the_database(
    client, seed_gold_prices, monkeypatch
):
    seed_gold_prices(days=5)
    _stub_realtime(
        monkeypatch,
        _quote(source="database", source_name="数据库历史数据", price=4180.0),
    )

    body = client.get("/api/gold/prices/daily?limit=50").json()

    last = body[-1]
    # 兜底价来自 gold_prices 表，它就是日收盘 —— 不许标成实时。
    assert last["basis"] == "close"
    assert last["basis_label"] == "日收盘"
    assert last["source"] == "数据库历史数据"


def test_correlation_points_carry_basis_for_both_series(
    client, seed_gold_prices, monkeypatch
):
    seed_gold_prices(days=5)
    _stub_realtime(monkeypatch, _quote())

    body = client.get("/api/gold/prices/correlation?days=5").json()

    assert body
    last = body[-1]
    assert last["gold_basis"] == "realtime"
    assert last["gold_source"] == "新浪财经-伦敦金"
    assert last["dollar_basis"] == "close"
    assert last["dollar_basis_label"] == "日收盘"
    assert last["as_of"] == last["date"]
    for row in body[:-1]:
        assert row["gold_basis"] == "close"
        assert row["dollar_basis"] == "close"


def test_latest_price_is_always_labeled_as_a_daily_close(client, seed_gold_prices):
    seed_gold_prices(days=3)

    body = client.get("/api/gold/latest").json()

    assert body["basis"] == "close"
    assert body["basis_label"] == "日收盘"
    assert body["as_of"] == body["date"]


def test_quant_predictions_declare_the_quant_basis(client, seed_quant_panel):
    seed_quant_panel()

    body = client.get("/api/gold/quant/predictions").json()

    assert body["price_basis"]["basis"] == "quant_basis"
    assert body["price_basis"]["label"] == "量化基准"
    assert "gold_close" in body["price_basis"]["source"]
    assert body["predictions"], "面板充足时应给出尺度"
    for item in body["predictions"]:
        assert item["base_basis"] == "quant_basis"
        assert item["base_basis_label"] == "量化基准"
    assert body["fair_value"]["basis"] == "quant_basis"
