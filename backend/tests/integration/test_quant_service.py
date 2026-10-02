"""量化服务：落库、幂等、回测节流与降级。"""
from __future__ import annotations

import pytest

from app.models.analysis import ModelEvaluation, Prediction
from app.services.quant import preregistered, service
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

def test_research_verdict_separates_undecidable_scales_from_failures():
    """结论句子必须说清哪个尺度「没被判定」（还差多少），哪个尺度真的不及格。"""

    def payload(
        horizon: int,
        accuracy: float,
        up: float,
        coverage: float,
        n_eff: float,
        *,
        decidable: bool = True,
        days_needed: int = 0,
    ) -> dict:
        return {
            "horizon_days": horizon,
            "forward_readiness": {
                "window_start": "2026-10-02",
                "observations": int(n_eff * horizon),
                "independent_bets": int(n_eff),
                "required_bets": preregistered.MIN_EFFECTIVE_SAMPLES,
                "decidable": decidable,
                "shortfall_bets": 0 if decidable else preregistered.MIN_EFFECTIVE_SAMPLES,
                "approx_trading_days_needed": days_needed,
            },
            "periods": {
                "forward": {
                    "accuracy": accuracy,
                    "baseline_up_accuracy": up,
                    "accuracy_diff_vs_up": accuracy - up,
                    "interval_coverage_80": coverage,
                    "effective_sample_size": n_eff,
                }
            },
        }

    verdict = service._research_verdict(
        [],
        [
            payload(1, 0.563, 0.563, 0.789, 753.0),
            payload(250, 1.0, 1.0, 0.241, 2.0, decidable=False, days_needed=4971),
        ],
    )

    assert verdict["status"] == "no_edge"
    assert "不可判定" in verdict["detail"]
    assert "250 日" in verdict["detail"]
    # 版本号不写死在断言里：它是 MODEL_VERSION 的镜像，升版时这里应当自动跟着走
    assert f"保留 {MODEL_VERSION}" in verdict["detail"]
    # 判不了的尺度必须顺带说清还要等多久，而不是只丢一句「样本不足」
    assert "还需约 4971 个交易日" in verdict["detail"]
    # 可判定的尺度不许被顺带标成不可判定
    assert "1 日命中" in verdict["detail"]
    assert "仅约 753" not in verdict["detail"]

def test_stored_prediction_carries_its_own_skill_verdict(db_session, seed_quant_panel):
    """落库的 reasoning 必须自带「有没有可核实技能」的结论，而不是只把胜率留给研究页。

    变异验证：把 `_reasoning` 里追加 `skill_note` 的那一行删掉，第二条断言必红；
    把 `_skill_note` 在缺评估时改成返回空串，第一条断言必红。
    """
    empty_note = service._skill_note(db_session, 20)
    assert "尚无该尺度的回测记录" in empty_note, "没有回测时必须明说没有背书，而不是沉默"

    seed_quant_panel()
    service.refresh_predictions(db_session, force_backtest=True)
    rows = (
        db_session.query(Prediction)
        .filter(Prediction.model_version == MODEL_VERSION)
        .order_by(Prediction.horizon_days)
        .all()
    )
    assert rows, "刷新后没有任何预测落库"
    for row in rows:
        assert "技能状态" in (row.reasoning or ""), f"h={row.horizon_days} 的 reasoning 没有技能结论"
        assert ("无法判定" in row.reasoning) or ("未跑赢朴素基准" in row.reasoning) or (
            "有可核实优势" in row.reasoning
        ), row.reasoning
    # 合成面板只有几百个交易日：长尺度必然落在「独立下注不足」这一支
    long_row = next(row for row in rows if row.horizon_days == max(HORIZONS))
    assert "无法判定" in long_row.reasoning or "独立下注" in long_row.reasoning

