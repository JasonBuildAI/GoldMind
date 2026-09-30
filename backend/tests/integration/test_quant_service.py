"""量化服务：落库、幂等、回测节流与降级。"""
from __future__ import annotations

import pytest

from app.models.analysis import ModelEvaluation, Prediction
from app.services.quant import service
from app.services.quant.definitions import HORIZONS, MODEL_VERSION


@pytest.mark.integration
def test_refresh_persists_one_prediction_per_horizon(db_session, seed_quant_panel):
    seed_quant_panel()

    result = service.refresh_predictions(db_session)

    assert result["status"] == "ok"
    rows = db_session.query(Prediction).filter(Prediction.model_version == MODEL_VERSION).all()
    assert {row.horizon_days for row in rows} == set(HORIZONS)
    assert all(row.target_price > 0 for row in rows)
    assert all(row.direction in ("up", "down") for row in rows)
    # 落库的推理必须能对回具体的因子，别是一句空话
    assert all(row.reasoning and "合成得分" in row.reasoning for row in rows)


@pytest.mark.integration
def test_refresh_is_idempotent_for_the_same_day(db_session, seed_quant_panel):
    seed_quant_panel()

    service.refresh_predictions(db_session)
    first = db_session.query(Prediction).filter(Prediction.model_version == MODEL_VERSION).count()
    service.refresh_predictions(db_session)
    second = db_session.query(Prediction).filter(Prediction.model_version == MODEL_VERSION).count()

    assert first == len(HORIZONS)
    assert second == first


@pytest.mark.integration
def test_backtest_runs_once_a_day_unless_forced(db_session, seed_quant_panel):
    seed_quant_panel()

    service.refresh_predictions(db_session)
    after_first = db_session.query(ModelEvaluation).filter(
        ModelEvaluation.model_version == MODEL_VERSION
    ).count()
    service.refresh_predictions(db_session)
    after_second = db_session.query(ModelEvaluation).filter(
        ModelEvaluation.model_version == MODEL_VERSION
    ).count()
    service.refresh_predictions(db_session, force_backtest=True)
    after_forced = db_session.query(ModelEvaluation).filter(
        ModelEvaluation.model_version == MODEL_VERSION
    ).count()

    assert after_first == len(HORIZONS)
    assert after_second == after_first
    assert after_forced == after_first + len(HORIZONS)


@pytest.mark.integration
def test_refresh_without_prices_reports_unavailable(db_session):
    result = service.refresh_predictions(db_session)

    assert result["status"] == "unavailable"
    assert result["predictions"] == []
    assert db_session.query(Prediction).count() == 0


@pytest.mark.integration
def test_accuracy_report_marks_horizons_that_never_ran(db_session):
    report = service.accuracy_report(db_session)

    assert [row["horizon_days"] for row in report["latest"]] == list(HORIZONS)
    assert all(row["sample_size"] == 0 for row in report["latest"])
    assert all(row["reason"] for row in report["latest"])


@pytest.mark.integration
def test_accuracy_report_includes_baselines_and_factor_detail(db_session, seed_quant_panel):
    seed_quant_panel()
    service.refresh_predictions(db_session, force_backtest=True)

    report = service.accuracy_report(db_session)

    latest = {row["horizon_days"]: row for row in report["latest"]}
    for horizon in HORIZONS:
        row = latest[horizon]
        assert row["accuracy"] is not None
        assert row["baseline_up_accuracy"] is not None
        assert row["baseline_momentum_accuracy"] is not None
        assert row["brier_score"] is not None
        assert row["factors"], "逐因子指标是「权重是否失效」的唯一证据，不能为空"
    assert latest[20]["sample_size"] >= 500
    assert report["history"]


@pytest.mark.integration
def test_live_predictions_reflect_the_stored_panel(db_session, seed_quant_panel):
    written, close = seed_quant_panel()

    payload = service.live_predictions(db_session)

    assert payload["as_of"] == close.index[-1].date()
    assert len(payload["predictions"]) == len(HORIZONS)
    assert all(item["status"] == "ok" for item in payload["predictions"])
    fair = payload["fair_value"]
    assert fair["status"] == "ok"
    assert fair["samples"] >= 120
    blocks = {block["key"]: block for block in fair["blocks"]}
    assert set(blocks) == {"anchor", "demand", "risk", "residual"}
    assert sum(block["usd"] for block in blocks.values()) == pytest.approx(
        fair["market_price"], rel=1e-9
    )
    assert fair["deviation_pct"] == pytest.approx(
        fair["market_price"] / fair["fair_value"] - 1.0, rel=1e-9
    )
    for item in payload["predictions"]:
        assert item["scenario_reason"] is None
        assert len(item["scenarios"]) == 3
        by_key = {scenario["key"]: scenario for scenario in item["scenarios"]}
        assert by_key["base"]["price_low"] == pytest.approx(item["range_low"], rel=1e-9)
        assert by_key["base"]["price_high"] == pytest.approx(item["range_high"], rel=1e-9)
        assert item["range_low"] < item["range_high"]
        assert by_key["bull"]["price_high"] is None
        assert by_key["bear"]["price_low"] is None
        assert by_key["bull"]["trigger"] and by_key["bear"]["invalidation"]
    etf = next(f for f in payload["predictions"][0]["factors"] if f["key"] == "etf_shares")
    # 只有一天快照的因子不可能算出 z：它必须被标出来，而不是当成 0 参与
    assert etf["contribution"] is None
    assert etf["status"] in ("warming", "ok")
    assert payload["predictions"][0]["available_factors"] < payload["predictions"][0]["total_factors"]


@pytest.mark.integration
def test_factor_dashboard_reports_staleness(db_session, seed_quant_panel):
    written, _ = seed_quant_panel()
    # 把地缘语料砍到只剩最后一次观测：超过 3 天的更新周期 → 陈旧
    from app.services.quant import storage
    from app.models.analysis import FactorObservation

    db_session.query(FactorObservation).filter(
        FactorObservation.factor_key == "geopolitical"
    ).delete()
    storage.upsert_series(
        db_session,
        "geopolitical",
        written["geopolitical"].iloc[:1],
        source="测试夹具",
    )

    dashboard = service.factor_dashboard(db_session)

    state = next(f for f in dashboard["factors"] if f["key"] == "geopolitical")
    assert state["status"] == "stale"
    assert state["contribution"] is None
    assert dashboard["available_factors"] < dashboard["total_factors"]
