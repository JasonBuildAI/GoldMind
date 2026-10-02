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
        assert item["target_price"] > 0
        assert 0.0 <= item["probability_up"] <= 1.0
        assert item["uncertainty"] >= 0.0
        assert item["headline"]
        contributions = [f["contribution"] for f in item["factors"] if f["contribution"] is not None]
        assert sum(contributions) == pytest.approx(item["score"], abs=1e-9)
        if item["horizon_days"] == 250:
            # 1 年尺度停发方向：只发布公允价值偏离与校准区间，且必须给出原因
            assert item["direction"] is None
            assert item["direction_label"] is None
            assert item["direction_status"] == "not_published"
            assert item["direction_reason"]
        else:
            assert item["direction"] in ("up", "down")
            assert item["direction_label"] in ("看涨", "看跌")
            assert item["direction_status"] == "published"
            assert item["direction_reason"] is None

    long_run = next(item for item in body["predictions"] if item["horizon_days"] == 250)
    assert "公允价值" in long_run["headline"]
    assert "区间" in long_run["headline"]
    # 停发方向不等于停发区间：1 年尺度照样给公允价值与区间
    assert long_run["range_low"] < long_run["range_high"]


@pytest.mark.integration
def test_prediction_payload_reports_the_nominal_level_and_the_cap_flag(
    client, db_session, seed_quant_panel
):
    """名义水平与 σ 来源必须对用户可见，封顶也必须可见。

    区间端点取分位 ``α/2`` 与 ``1−α/2``，而 α 是**自适应**的：真实 26 年面板
    h=250 有 1602 行贴在下界（名义水平 99.5%）、919 行贴上界（名义水平 50%）。
    只给一个「80% 区间」而不给实际的 α，等于让用户按名义值读一个名义值已经不
    成立的区间。``distribution_mode`` 记录这一行用的是经验分布还是正态兜底；
    ``expected_capped`` 记录期望收益是否被护栏夹过（h=250 触发率 4.48%）。

    变异验证：把这三个字段从 payload 里删掉本测试必红。
    """
    seed_quant_panel()

    body = client.get("/api/gold/quant/predictions").json()

    for item in body["predictions"]:
        assert item["status"] == "ok"
        assert item["distribution_mode"] in ("aci", "normal")
        assert item["interval_alpha"] is not None
        assert 0.0 < item["interval_alpha"] <= 0.5
        assert isinstance(item["expected_capped"], bool)


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
    # 空库时上海金溢价没有两条源序列，必须如实标不可用并给原因。
    assert rows["shanghai_premium"]["status"] == "unavailable"
    assert rows["shanghai_premium"]["reason"]


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
