"""量化预测的高层入口：同步 → 计算 → 落库 → 读取。

调度器与 ``POST /api/gold/quant/refresh`` 都走 ``full_refresh``；读接口走下面
几个只读函数。这一层不自己算任何统计量 —— 统计量全部来自 ``engine`` /
``backtest``，不然口径就会分成两份。
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from app.models.analysis import ModelEvaluation, Prediction
from app.services.quant import backtest, engine, storage, sync
from app.services.quant.definitions import (
    BENCHMARK_KEY,
    CATEGORY_NAMES,
    HORIZONS,
    MODEL_VERSION,
    factor_by_key,
)
from app.utils import timeutil

# 完整回测的最小间隔：预测每 2 小时重算，回测每天只跑一次（它要扫全历史）
BACKTEST_INTERVAL = timedelta(hours=24)


def load_panel(db: Session) -> tuple[dict[str, pd.Series], pd.Series]:
    """把因子面板与基准价格从库里读出来（不访问网络）。"""
    series = storage.load_all(db)
    close = series.pop(BENCHMARK_KEY, None)
    if close is None:
        close = pd.Series(dtype="float64", name=BENCHMARK_KEY)
    return series, close


def build_snapshots(
    db: Session, *, horizons: tuple[int, ...] = HORIZONS
) -> list[engine.SignalSnapshot]:
    factors, close = load_panel(db)
    return [engine.build_snapshot(factors, close, horizon=horizon) for horizon in horizons]


# --------------------------------------------------------------------------- #
# 读：预测
# --------------------------------------------------------------------------- #
def live_predictions(
    db: Session,
    *,
    horizon: Optional[int] = None,
    horizons: tuple[int, ...] = HORIZONS,
) -> dict:
    """当前时点重新计算的预测（不读 predictions 表）。

    为什么读接口也现算：预测的价值取决于「数据刚更新过」。落库的那一行是
    **历史记录**（用于回看「当时说过什么」），页面上的数字必须与因子面板
    同一时刻，否则两个区块会互相矛盾。
    """
    if horizon is not None:
        horizons = (horizon,)
    snapshots = build_snapshots(db, horizons=horizons)
    return {
        "model_version": MODEL_VERSION,
        "as_of": snapshots[0].as_of if snapshots else None,
        "predictions": [_prediction_payload(snapshot) for snapshot in snapshots],
    }


def _prediction_payload(snapshot: engine.SignalSnapshot) -> dict:
    return {
        "horizon_days": snapshot.horizon_days,
        "status": snapshot.status,
        "reason": snapshot.reason,
        "direction": snapshot.direction,
        "direction_label": _direction_label(snapshot.direction, snapshot.status),
        "as_of": snapshot.as_of,
        "base_price": snapshot.base_price,
        "target_price": snapshot.target_price,
        "expected_return": snapshot.expected_return,
        "uncertainty": snapshot.uncertainty,
        "probability_up": snapshot.probability_up,
        "score": snapshot.score,
        "model_version": MODEL_VERSION,
        "available_factors": snapshot.available_factors,
        "total_factors": len(snapshot.states),
        "factors": [_contribution_payload(state) for state in snapshot.states],
    }


def _direction_label(direction: Optional[str], status: str) -> Optional[str]:
    if status != engine.STATUS_OK or direction is None:
        return None
    return "看涨" if direction == "up" else "看跌"


def _contribution_payload(state: engine.FactorState) -> dict:
    return {
        "key": state.key,
        "name": state.name,
        "category": state.category,
        "category_name": CATEGORY_NAMES.get(state.category, state.category),
        "weight": state.weight,
        "sign": state.sign,
        "value": state.value,
        "obs_date": state.obs_date,
        "z": state.z,
        "signed_z": state.signed_z,
        "contribution": state.contribution,
        "status": state.status,
        "reason": state.reason,
    }


# --------------------------------------------------------------------------- #
# 读：因子面板与数据源状态
# --------------------------------------------------------------------------- #
def factor_dashboard(db: Session, *, category: Optional[str] = None) -> dict:
    factors, close = load_panel(db)
    today = timeutil.today()
    if close.empty:
        states = engine.factor_states(factors, pd.DataFrame(), as_of=pd.Timestamp(today))
        as_of: Optional[object] = None
        reason = "尚无黄金价格序列（行情源未同步），无法计算信号"
    else:
        snapshot = engine.build_snapshot(factors, close, horizon=HORIZONS[0])
        states = snapshot.states
        as_of = snapshot.as_of
        reason = None if snapshot.status == engine.STATUS_OK else snapshot.reason

    visible = states if category is None else tuple(s for s in states if s.category == category)

    categories = [
        {
            "key": key,
            "name": name,
            "total": sum(1 for state in states if state.category == key),
            "available": sum(1 for state in states if state.category == key and state.available),
        }
        for key, name in CATEGORY_NAMES.items()
    ]

    report = sync.load_report() or {}
    sources = [
        {
            "name": name,
            "label": item.get("label"),
            "status": item.get("status", "unknown"),
            "error": item.get("error"),
            "reason": item.get("reason"),
        }
        for name, item in (report.get("sources") or {}).items()
    ]

    return {
        "model_version": MODEL_VERSION,
        "as_of": as_of,
        "available_factors": sum(1 for state in states if state.available),
        "total_factors": len(states),
        "categories": categories,
        "factors": [_factor_payload(state) for state in visible],
        "sources": sources,
        "sync": {
            "started_at": report.get("started_at"),
            "finished_at": report.get("finished_at"),
            "sources_ok": report.get("sources_ok"),
            "sources_total": report.get("sources_total"),
        },
        "unavailable_reason": reason,
    }


def _factor_payload(state: engine.FactorState) -> dict:
    payload = _contribution_payload(state)
    payload.update(
        {
            "weight": state.weight,
            "unit": state.unit,
            "source": state.source,
            "description": state.description,
            "age_days": state.age_days,
            "max_age_days": state.max_age_days,
        }
    )
    return payload


# --------------------------------------------------------------------------- #
# 读：准确率
# --------------------------------------------------------------------------- #
def accuracy_report(db: Session, *, history_limit: int = 40) -> dict:
    rows = (
        db.query(ModelEvaluation)
        .filter(ModelEvaluation.model_version == MODEL_VERSION)
        .order_by(ModelEvaluation.evaluated_at.desc(), ModelEvaluation.id.desc())
        .limit(history_limit * max(len(HORIZONS), 1))
        .all()
    )
    latest_by_horizon = {}
    for row in rows:
        latest_by_horizon.setdefault(row.horizon_days, row)
    latest = [latest_by_horizon.get(horizon) for horizon in HORIZONS]

    return {
        "model_version": MODEL_VERSION,
        "latest": [
            _evaluation_payload(row, horizon) for horizon, row in zip(HORIZONS, latest)
        ],
        "history": [_evaluation_payload(row) for row in rows],
    }


def _evaluation_payload(row: Optional[ModelEvaluation], horizon: Optional[int] = None) -> dict:
    if row is None:
        return {
            "horizon_days": horizon,
            "evaluated_at": None,
            "window_start": None,
            "window_end": None,
            "sample_size": 0,
            "accuracy": None,
            "baseline_up_accuracy": None,
            "baseline_momentum_accuracy": None,
            "brier_score": None,
            "metrics": {},
            "factors": [],
            "reason": "尚未回测（同步数据后会自动追加一条评估）",
        }

    metrics = row.metrics or {}
    per_factor = metrics.get("per_factor") or {}
    factors = []
    for key, item in per_factor.items():
        definition = factor_by_key.get(key)
        factors.append(
            {
                "key": key,
                "name": item.get("name") or (definition.name if definition else key),
                "category": item.get("category") or (definition.category if definition else ""),
                "category_name": CATEGORY_NAMES.get(
                    item.get("category") or (definition.category if definition else ""), ""
                ),
                "weight": item.get("weight") or 0.0,
                "sign": item.get("sign") or 0,
                "samples": item.get("samples") or 0,
                "hit_rate": item.get("hit_rate"),
                "ic": item.get("ic"),
                "rank_ic": item.get("rank_ic"),
            }
        )
    factors.sort(key=lambda factor: factor["weight"], reverse=True)

    return {
        "horizon_days": row.horizon_days,
        "evaluated_at": row.evaluated_at,
        "window_start": row.window_start,
        "window_end": row.window_end,
        "sample_size": row.sample_size or 0,
        "accuracy": row.accuracy,
        "baseline_up_accuracy": row.baseline_up_accuracy,
        "baseline_momentum_accuracy": row.baseline_momentum_accuracy,
        "brier_score": row.brier_score,
        "metrics": metrics,
        "factors": factors,
        "reason": metrics.get("reason"),
    }


# --------------------------------------------------------------------------- #
# 写：预测与回测
# --------------------------------------------------------------------------- #
def refresh_predictions(
    db: Session,
    *,
    horizons: tuple[int, ...] = HORIZONS,
    force_backtest: bool = False,
) -> dict:
    """重算预测并（按需）追加回测。返回本次做了什么。"""
    factors, close = load_panel(db)
    if close.empty:
        return {
            "status": engine.PREDICTION_UNAVAILABLE,
            "reason": "尚无黄金价格序列，未生成预测",
            "predictions": [],
            "evaluations": [],
        }

    predictions = []
    for horizon in horizons:
        snapshot = engine.build_snapshot(factors, close, horizon=horizon)
        payload = _prediction_payload(snapshot)
        if snapshot.status == engine.STATUS_OK:
            _store_prediction(db, snapshot)
        predictions.append(payload)
    db.commit()

    evaluations = []
    for horizon in horizons:
        if not force_backtest and not _backtest_due(db, horizon):
            continue
        evaluation = backtest.evaluate_horizon(factors, close, horizon=horizon)
        if evaluation.accuracy is None:
            logger.info(f"[量化] 周期 {horizon} 暂不写回测：{evaluation.metrics.get('reason')}")
            continue
        _store_evaluation(db, evaluation)
        evaluations.append(evaluation.to_dict())
    db.commit()

    logger.info(
        f"[量化] 预测刷新完成：{sum(1 for item in predictions if item['status'] == engine.STATUS_OK)}"
        f"/{len(predictions)} 个周期可用，追加 {len(evaluations)} 条回测"
    )
    return {
        "status": engine.STATUS_OK,
        "reason": None,
        "predictions": predictions,
        "evaluations": evaluations,
    }


def _backtest_due(db: Session, horizon: int) -> bool:
    latest = (
        db.query(ModelEvaluation.evaluated_at)
        .filter(
            ModelEvaluation.model_version == MODEL_VERSION,
            ModelEvaluation.horizon_days == horizon,
        )
        .order_by(ModelEvaluation.evaluated_at.desc())
        .first()
    )
    if latest is None or latest[0] is None:
        return True
    return timeutil.now_naive() - latest[0] >= BACKTEST_INTERVAL


def _store_prediction(db: Session, snapshot: engine.SignalSnapshot) -> None:
    """同一 (版本, 周期, 截止日, 方向, 目标价) 只存一行 —— 两小时一次的刷新
    不应该把表撑成流水账。"""
    latest = (
        db.query(Prediction)
        .filter(
            Prediction.model_version == MODEL_VERSION,
            Prediction.horizon_days == snapshot.horizon_days,
        )
        .order_by(Prediction.as_of.desc(), Prediction.id.desc())
        .first()
    )
    if (
        latest is not None
        and latest.as_of == snapshot.as_of
        and latest.direction == snapshot.direction
        and latest.target_price is not None
        and abs(latest.target_price - snapshot.target_price) < 1e-9
    ):
        return

    db.add(
        Prediction(
            prediction_type=snapshot.direction,
            target_price=snapshot.target_price,
            confidence=snapshot.probability_up,
            timeframe=f"{snapshot.horizon_days}D",
            reasoning=_reasoning(snapshot),
            factors=[
                {
                    "key": state.key,
                    "name": state.name,
                    "contribution": state.contribution,
                    "signed_z": state.signed_z,
                }
                for state in snapshot.states
                if state.available
            ],
            direction=snapshot.direction,
            horizon_days=snapshot.horizon_days,
            as_of=snapshot.as_of,
            base_price=snapshot.base_price,
            score=snapshot.score,
            expected_return=snapshot.expected_return,
            uncertainty=snapshot.uncertainty,
            model_version=MODEL_VERSION,
        )
    )


def _reasoning(snapshot: engine.SignalSnapshot) -> str:
    parts = [
        f"合成得分 {snapshot.score:+.2f}",
        f"可用因子 {snapshot.available_factors}/{len(snapshot.states)}",
    ]
    top = sorted(
        (state for state in snapshot.states if state.available and state.contribution is not None),
        key=lambda state: abs(state.contribution),
        reverse=True,
    )[:3]
    if top:
        parts.append("主要贡献：" + "、".join(f"{state.name} {state.contribution:+.2f}" for state in top))
    if snapshot.expected_return is not None:
        parts.append(f"{snapshot.horizon_days} 个交易日期望收益 {snapshot.expected_return * 100:+.2f}%")
    if snapshot.probability_up is not None:
        parts.append(f"上行概率 {snapshot.probability_up * 100:.0f}%")
    return "；".join(parts) + "。"


def _store_evaluation(db: Session, evaluation: backtest.HorizonEvaluation) -> None:
    db.add(
        ModelEvaluation(
            model_version=MODEL_VERSION,
            horizon_days=evaluation.horizon_days,
            evaluated_at=timeutil.now_naive(),
            window_start=evaluation.window_start,
            window_end=evaluation.window_end,
            sample_size=evaluation.sample_size,
            accuracy=evaluation.accuracy,
            baseline_up_accuracy=evaluation.baseline_up_accuracy,
            baseline_momentum_accuracy=evaluation.baseline_momentum_accuracy,
            brier_score=evaluation.brier_score,
            metrics=evaluation.metrics,
        )
    )


def full_refresh(db: Session, *, force: bool = True) -> dict:
    """抓取 → 派生 → 落库 → 重算预测 → 回测。限流与耗时见 POST /refresh。"""
    report = sync.run_sync(db, force=force)
    result = refresh_predictions(db, force_backtest=True)
    available = sum(1 for item in result["predictions"] if item["status"] == engine.STATUS_OK)
    return {
        "success": True,
        "message": (
            f"数据源 {report.to_dict()['sources_ok']}/{len(report.source_status)} 可用；"
            f"{available}/{len(result['predictions'])} 个周期已生成预测"
        ),
        "sources": [
            {
                "name": name,
                "label": item.get("label"),
                "status": item.get("status", "unknown"),
                "error": item.get("error"),
                "reason": item.get("reason"),
            }
            for name, item in report.source_status.items()
        ],
        "factor_status": report.factor_status,
        "predictions": result["predictions"],
        "evaluations": [
            _evaluation_payload_from_dict(item) for item in result["evaluations"]
        ],
    }


def _evaluation_payload_from_dict(item: dict) -> dict:
    metrics = item.get("metrics") or {}
    per_factor = metrics.get("per_factor") or {}
    factors = []
    for key, entry in per_factor.items():
        definition = factor_by_key.get(key)
        category = entry.get("category") or (definition.category if definition else "")
        factors.append(
            {
                "key": key,
                "name": entry.get("name") or (definition.name if definition else key),
                "category": category,
                "category_name": CATEGORY_NAMES.get(category, ""),
                "weight": entry.get("weight") or 0.0,
                "sign": entry.get("sign") or 0,
                "samples": entry.get("samples") or 0,
                "hit_rate": entry.get("hit_rate"),
                "ic": entry.get("ic"),
                "rank_ic": entry.get("rank_ic"),
            }
        )
    factors.sort(key=lambda factor: factor["weight"], reverse=True)
    return {
        "horizon_days": item["horizon_days"],
        "evaluated_at": timeutil.now_naive(),
        "window_start": item.get("window_start"),
        "window_end": item.get("window_end"),
        "sample_size": item.get("sample_size") or 0,
        "accuracy": item.get("accuracy"),
        "baseline_up_accuracy": item.get("baseline_up_accuracy"),
        "baseline_momentum_accuracy": item.get("baseline_momentum_accuracy"),
        "brier_score": item.get("brier_score"),
        "metrics": metrics,
        "factors": factors,
        "reason": metrics.get("reason"),
    }
