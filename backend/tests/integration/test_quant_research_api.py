"""研究端点：结构、三个样本期、裁决与缓存；空库必须诚实降级。"""
from __future__ import annotations

from datetime import date

import pytest

from app.services.quant import backtest, engine, preregistered
from app.services.quant.definitions import (
    ACTIVE_HOLDOUT_START,
    HOLDOUT_START,
    HORIZONS,
    MODEL_VERSION,
)


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
    assert body["active_holdout_start"] == ACTIVE_HOLDOUT_START.isoformat()
    assert body["as_of"]
    assert body["generated_at"]
    # 数据窗口显著标注：起止 + 交易日数 + 年数，页面据此说明数字来自哪一段；
    # 年数由日历跨度折算——拿交易日数除以 365 是另一种口径，会在这里红
    window = body["data_window"]
    assert window["start"] < window["end"] == body["as_of"]
    assert window["trading_days"] > 0
    span = (
        date.fromisoformat(window["end"]) - date.fromisoformat(window["start"])
    ).days
    assert window["years"] == pytest.approx(span / 365.25, abs=0.05)
    assert body["reason"] is None
    assert [item["horizon_days"] for item in body["horizons"]] == list(HORIZONS)

    for item in body["horizons"]:
        assert item["label"] and item["headline"]
        assert set(item["periods"]) == {"development", "holdout", "forward", "full"}
        # 历史那一段必须在标签里说清楚它是记录、不是干净的样本外证据
        assert "历史" in item["periods"]["holdout"]["label"]
        assert "前向" in item["periods"]["forward"]["label"]
        # 裁决窗口的进度：口径与 horizon 一致，且缺口非负
        readiness = item["forward_readiness"]
        assert readiness["window_start"] == ACTIVE_HOLDOUT_START.isoformat()
        assert readiness["required_bets"] == preregistered.MIN_EFFECTIVE_SAMPLES
        # 下注次数以回测实际数出来的为准：日历折算会把还没实现收益的最后 h 行也算上，
        # 于是同一页面上 readiness 报「可判」而样本量闸门报「不足」——差一注就翻脸。
        assert (
            readiness["independent_bets"]
            == (item["periods"]["forward"]["independent_bets"] or 0)
        )
        assert readiness["shortfall_bets"] >= 0
        assert readiness["decidable"] == (readiness["shortfall_bets"] == 0)
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
        # 评估窗口必须落在披露的数据窗口内（不能拿窗口外的样本说事）
        full = item["periods"]["full"]
        assert window["start"] <= full["window_start"]
        assert full["window_end"] <= window["end"]
        assert item["factors"], "全样本必须给出逐因子拆解"
        weights = [row["weight"] for row in item["factors"]]
        assert weights == sorted(weights, reverse=True)
        for row in item["factors"]:
            assert row["key"] and row["name"] and row["category_name"]

    verdict = body["verdict"]
    # 裁决窗口够不够判，决定了结论是「尚不可判」还是「有 / 无优势」——
    # 两者必须自洽：所有尺度都判不了时，不许出现「无统计优势」这种盖棺论定。
    decidable = [item for item in body["horizons"] if item["forward_readiness"]["decidable"]]
    if decidable:
        assert verdict["status"] in ("candidate", "no_edge")
    else:
        assert verdict["status"] == preregistered.STATUS_PENDING
        assert "交易日" in verdict["detail"], "pending 必须摊开还差多少个交易日"
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
    assert body["data_window"] is None, "没有窗口就不许编一个"
    assert body["horizons"] == []
    assert body["verdict"]["status"] == "unavailable"
    assert "数据不可用" in body["verdict"]["label"]

    # 不可用的结果不进缓存：数据补上后第一次请求必须现算
    again = client.get("/api/gold/quant/research").json()
    assert again["cached"] is False
