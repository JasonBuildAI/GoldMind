"""研究端点：结构、三个样本期、裁决与缓存；空库必须诚实降级。"""
from __future__ import annotations

import pytest

from app.services.quant import backtest, engine
from app.services.quant.definitions import HOLDOUT_START, HORIZONS, MODEL_VERSION


@pytest.mark.integration
def test_research_endpoint_reports_periods_factors_and_verdict(
    client, db_session, seed_quant_panel
):
    seed_quant_panel()

    response = client.get("/api/gold/quant/research")

    assert response.status_code == 200
    body = response.json()
    assert body["model_version"] == MODEL_VERSION
    assert body["status"] == engine.STATUS_OK
    assert body["holdout_start"] == HOLDOUT_START.isoformat()
    assert body["as_of"]
    assert body["generated_at"]
    assert body["reason"] is None
    assert [item["horizon_days"] for item in body["horizons"]] == list(HORIZONS)

    for item in body["horizons"]:
        assert item["label"] and item["headline"]
        assert set(item["periods"]) == {"development", "holdout", "full"}
        for period in item["periods"].values():
            assert period["label"]
            assert period["sample_size"] >= 0
            # 独立下注口径：次数与 stride 必须一起给出，且次数不超过样本数
            assert period["independent_bet_stride"] == item["horizon_days"]
            assert 0 <= (period["independent_bets"] or 0) <= period["sample_size"]
            if (
                period["independent_bets"]
                and period["independent_bets"] >= backtest.MIN_NONOVERLAPPING_SAMPLES
            ):
                assert period["accuracy_independent_bets"] is not None
            if period["accuracy"] is None:
                assert period["reason"], "没有数字就必须给出原因"
                continue
            assert 0.0 <= period["accuracy"] <= 1.0
            assert period["baseline_up_accuracy"] is not None
            # 差值口径必须与两个命中率自洽（防止接口搬错列）
            assert period["accuracy_diff_vs_up"] == pytest.approx(
                period["accuracy"] - period["baseline_up_accuracy"], abs=1e-9
            )
        assert item["factors"], "全样本必须给出逐因子拆解"
        weights = [row["weight"] for row in item["factors"]]
        assert weights == sorted(weights, reverse=True)
        for row in item["factors"]:
            assert row["key"] and row["name"] and row["category_name"]

    verdict = body["verdict"]
    assert verdict["status"] in ("candidate", "no_edge")
    assert verdict["label"] and verdict["detail"]
    assert body["cached"] is False


@pytest.mark.integration
def test_research_endpoint_serves_the_second_call_from_cache(
    client, db_session, seed_quant_panel
):
    seed_quant_panel()

    first = client.get("/api/gold/quant/research").json()
    second = client.get("/api/gold/quant/research").json()

    assert first["cached"] is False
    assert second["cached"] is True
    assert second["verdict"] == first["verdict"]
    assert second["as_of"] == first["as_of"]


@pytest.mark.integration
def test_research_endpoint_is_honest_on_an_empty_database(client, db_session):
    body = client.get("/api/gold/quant/research").json()

    assert body["status"] == engine.PREDICTION_UNAVAILABLE
    assert body["reason"], "没有数据就必须说明原因"
    assert body["horizons"] == []
    assert body["verdict"]["status"] == "unavailable"
    assert "数据不可用" in body["verdict"]["label"]

    # 不可用的结果不进缓存：数据补上后第一次请求必须现算
    again = client.get("/api/gold/quant/research").json()
    assert again["cached"] is False
