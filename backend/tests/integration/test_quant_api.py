"""量化端点：形状、契约、降级与手动刷新。"""
from __future__ import annotations

import pytest

from app.services.quant import service
from app.services.quant.definitions import HORIZONS


@pytest.mark.integration
def test_predictions_endpoint_returns_every_horizon_with_numbers(client, db_session, seed_quant_panel):
    seed_quant_panel()

    body = client.get("/api/gold/quant/predictions").json()

    assert [item["horizon_days"] for item in body["predictions"]] == list(HORIZONS)
    for item in body["predictions"]:
        assert item["status"] == "ok"
        assert item["direction"] in ("up", "down")
        assert item["direction_label"] in ("看涨", "看跌")
        assert item["target_price"] > 0
        assert 0.0 <= item["probability_up"] <= 1.0
        assert item["uncertainty"] >= 0.0
        assert item["headline"]
        contributions = [f["contribution"] for f in item["factors"] if f["contribution"] is not None]
        assert sum(contributions) == pytest.approx(item["score"], abs=1e-9)

    long_run = next(item for item in body["predictions"] if item["horizon_days"] == 250)
    assert "公允价值" in long_run["headline"]
    assert "区间" in long_run["headline"]


@pytest.mark.integration
def test_predictions_endpoint_filters_by_horizon(client, db_session, seed_quant_panel):
    seed_quant_panel()

    body = client.get("/api/gold/quant/predictions?horizon_days=5").json()

    assert [item["horizon_days"] for item in body["predictions"]] == [5]


@pytest.mark.integration
def test_predictions_endpoint_rejects_an_out_of_range_horizon(client, db_session, seed_quant_panel):
    seed_quant_panel()

    assert client.get("/api/gold/quant/predictions?horizon_days=999").status_code == 422


@pytest.mark.integration
def test_factors_endpoint_reports_source_and_freshness(client, db_session, seed_quant_panel):
    seed_quant_panel()

    body = client.get("/api/gold/quant/factors").json()

    assert body["total_factors"] == 14
    assert body["available_factors"] >= 12
    assert {item["key"] for item in body["categories"]} == {
        "monetary", "risk", "supply", "technical"
    }
    for factor in body["factors"]:
        assert factor["source"], f"{factor['key']} 没有来源说明"
        assert factor["obs_date"] is not None
        assert factor["age_days"] is not None
        assert factor["status"] in ("ok", "stale", "missing", "warming")
        if factor["status"] != "ok":
            assert factor["reason"], f"{factor['key']} 不可用却没有原因"


@pytest.mark.integration
def test_factors_endpoint_filters_by_category(client, db_session, seed_quant_panel):
    seed_quant_panel()

    body = client.get("/api/gold/quant/factors?category=monetary").json()

    assert body["factors"], "货币政策类不可能一个因子都没有"
    assert {factor["category"] for factor in body["factors"]} == {"monetary"}
    assert len(body["factors"]) < body["total_factors"]
    assert all(item["key"] == "monetary" for item in body["categories"] if item["total"] and item["key"] == "monetary")


@pytest.mark.integration
def test_factors_endpoint_returns_an_empty_list_for_an_unknown_category(client, db_session, seed_quant_panel):
    seed_quant_panel()

    body = client.get("/api/gold/quant/factors?category=astrology").json()

    assert body["factors"] == []


@pytest.mark.integration
def test_accuracy_endpoint_reports_baselines(client, db_session, seed_quant_panel):
    seed_quant_panel()
    service.refresh_predictions(db_session, force_backtest=True)

    body = client.get("/api/gold/quant/accuracy").json()

    assert len(body["latest"]) == len(HORIZONS)
    for row in body["latest"]:
        # 可评估样本 = 日历长度 − 2h − 119（60 天 z 预热、h 天配对、
        # 补到 60 组校准样本的 59 天、末尾 h 天等待实现）。850 个交易日的
        # 夹具里长尺度天生短一截（250 日：850 − 500 − 119 = 231），不是漏算
        floor = 200 if row["horizon_days"] >= 250 else 500
        assert row["sample_size"] >= floor
        assert row["accuracy"] is not None
        assert row["baseline_up_accuracy"] is not None
        assert row["factors"]
    assert body["history"]


def test_monitor_endpoint_lists_rows_with_value_or_reason(client, db_session, seed_quant_panel):
    seed_quant_panel()

    body = client.get("/api/gold/quant/monitor").json()

    assert len(body["rows"]) >= 10
    for row in body["rows"]:
        assert row["name"] and row["frequency"] and row["source"] and row["unit"] and row["note"]
        assert row["status"] in ("ok", "unavailable")
        if row["status"] == "ok":
            assert row["value"] is not None
            assert row["obs_date"]
        else:
            assert row["reason"]
            assert row["value"] is None
            assert row["signal"] is None
    rows = {row["key"]: row for row in body["rows"]}
    assert rows["ma200"]["status"] == "ok"
    assert rows["shanghai_premium"]["status"] == "unavailable"
    assert "不编数" in rows["shanghai_premium"]["reason"]


@pytest.mark.integration
def test_every_quant_endpoint_degrades_honestly_on_an_empty_database(client):
    predictions = client.get("/api/gold/quant/predictions").json()
    assert all(item["status"] == "unavailable" for item in predictions["predictions"])
    assert all(item["reason"] for item in predictions["predictions"])
    assert all(item["target_price"] is None for item in predictions["predictions"])
    assert all(item["direction"] is None for item in predictions["predictions"])
    assert predictions["fair_value"]["status"] == "unavailable"
    assert predictions["fair_value"]["reason"]
    assert predictions["fair_value"]["blocks"] == []
    assert all(item["scenario_reason"] for item in predictions["predictions"])
    assert all(item["scenarios"] == [] for item in predictions["predictions"])

    factors = client.get("/api/gold/quant/factors").json()
    assert factors["available_factors"] == 0
    assert factors["unavailable_reason"]
    assert all(factor["status"] == "missing" for factor in factors["factors"])

    accuracy = client.get("/api/gold/quant/accuracy").json()
    assert all(row["sample_size"] == 0 for row in accuracy["latest"])
    assert all(row["accuracy"] is None for row in accuracy["latest"])
    assert all(row["reason"] for row in accuracy["latest"])

    monitor = client.get("/api/gold/quant/monitor").json()
    assert len(monitor["rows"]) >= 10
    assert all(row["status"] == "unavailable" for row in monitor["rows"])
    assert all(row["reason"] for row in monitor["rows"])


@pytest.mark.integration
def test_refresh_endpoint_syncs_then_recomputes(client, db_session, seed_quant_panel, monkeypatch):
    seed_quant_panel()

    from app.services.quant import sync as quant_sync

    calls = []

    def fake_run_sync(db, *, force=False, **kwargs):
        calls.append(force)
        report = quant_sync.SyncReport()
        report.source_status = {"yahoo": {"status": "ok", "label": "Yahoo Finance 行情"}}
        report.finished_at = "2026-01-01T00:00:00"
        return report

    monkeypatch.setattr(quant_sync, "run_sync", fake_run_sync)

    body = client.post("/api/gold/quant/refresh").json()

    assert calls == [True]
    assert body["success"] is True
    assert len(body["predictions"]) == len(HORIZONS)
    assert len(body["evaluations"]) == len(HORIZONS)
    assert body["sources"][0]["name"] == "yahoo"


@pytest.mark.integration
def test_legacy_predictions_endpoint_returns_the_quant_rows(client, db_session, seed_quant_panel):
    seed_quant_panel()
    service.refresh_predictions(db_session)

    body = client.get("/api/gold/predictions").json()

    assert body, "predictions 表不再恒为空"
    assert all(row["model_version"] for row in body)
    assert all(row["horizon_days"] in HORIZONS for row in body)
