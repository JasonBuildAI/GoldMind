"""量化预测的高层入口：同步 → 计算 → 落库 → 读取。

调度器与 ``POST /api/gold/quant/refresh`` 都走 ``full_refresh``；读接口走下面
几个只读函数。这一层不自己算任何统计量 —— 统计量全部来自 ``engine`` /
``backtest`` / ``decompose``，不然口径就会分成两份。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from app.models.analysis import ModelEvaluation, Prediction
from app.services.cache_manager import CacheManager
from app.services.quant import (
    backtest,
    decompose,
    engine,
    preregistered,
    scenarios,
    stats,
    storage,
    sync,
)
from app.services.quant.definitions import (
    ACTIVE_HOLDOUT_START,
    BENCHMARK_KEY,
    CATEGORY_NAMES,
    DIRECTION_NOT_PUBLISHED,
    HOLDOUT_START,
    HORIZONS,
    MODEL_VERSION,
    direction_publication,
    factor_by_key,
    horizon_spec,
)
from app.utils import timeutil

# 完整回测的最小间隔：预测每 2 小时重算，回测每天只跑一次（它要扫全历史）
BACKTEST_INTERVAL = timedelta(hours=24)
# 研究页报告：走查式重算约数秒，缓存 1 小时；刷新数据后主动失效
RESEARCH_CACHE_TTL = 3600
RESEARCH_CACHE_KEY = "quant_research"
# 「历史留出期」这一段第一/二轮裁决已经看过，标签就必须写清楚它是记录而不是证据 ——
# 把两段留出期都叫「留出期」，读者会以为页面上的样本外成绩还是干净的。
RESEARCH_PERIOD_LABELS = {
    "development": "开发期",
    "holdout": "历史留出期（已看过）",
    "forward": "前向留出期（裁决窗口）",
    "full": "全样本",
}


def load_panel(
    db: Session, *, as_of: Optional[date] = None
) -> tuple[dict[str, pd.Series], pd.Series]:
    """把因子面板与基准价格从库里读出来（不访问网络）。

    ``as_of`` 给定时读的是**修订流水**，即「那一天看到的值」：回填与数据源回修都会
    改掉 `factor_observations` 里的当前值，所以不带这个入口的话，
    「按上次的输入重跑一遍预注册」在物理上做不到（回填一轮就修订过 26,445 行）。
    """
    series = storage.load_all(db) if as_of is None else storage.load_series_as_of(db, as_of)
    close = series.pop(BENCHMARK_KEY, None)
    if close is None:
        close = pd.Series(dtype="float64", name=BENCHMARK_KEY)
    return series, close


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
    factors, close = load_panel(db)
    snapshots = [
        engine.build_snapshot(factors, close, horizon=horizon) for horizon in horizons
    ]
    decomposition = decompose.decompose_latest(factors, close)
    return {
        "model_version": MODEL_VERSION,
        "as_of": snapshots[0].as_of if snapshots else None,
        "fair_value": decomposition.to_dict(),
        "predictions": [
            _prediction_payload(snapshot, close) for snapshot in snapshots
        ],
    }


def _prediction_payload(snapshot: engine.SignalSnapshot, close: pd.Series) -> dict:
    spec = horizon_spec.get(snapshot.horizon_days)
    scenario_set = scenarios.build_scenarios(snapshot, close)
    # 方向发布策略：算得出方向 ≠ 该发布方向（长尺度没有可核实的信息优势）。
    direction_status, direction_reason = direction_publication(snapshot.horizon_days)
    published_direction = (
        None if direction_status == DIRECTION_NOT_PUBLISHED else snapshot.direction
    )
    return {
        "horizon_days": snapshot.horizon_days,
        "scale_label": spec.label if spec else None,
        "scale": spec.scale if spec else None,
        "scale_description": spec.description if spec else None,
        "headline": spec.headline if spec else None,
        "status": snapshot.status,
        "reason": snapshot.reason,
        "direction": published_direction,
        "direction_label": _direction_label(published_direction, snapshot.status),
        "direction_status": direction_status,
        "direction_reason": direction_reason,
        "as_of": snapshot.as_of,
        "base_price": snapshot.base_price,
        "target_price": snapshot.target_price,
        "expected_return": snapshot.expected_return,
        "uncertainty": snapshot.uncertainty,
        "probability_up": snapshot.probability_up,
        # 区间的实际名义水平与 σ 来源：区间是自适应的，名义 80% 只是起点
        "distribution_mode": snapshot.distribution_mode,
        "interval_alpha": snapshot.interval_alpha,
        "interval_nominal": (
            None if snapshot.interval_alpha is None else 1.0 - snapshot.interval_alpha
        ),
        "expected_capped": snapshot.expected_capped,
        "range_low": scenario_set.range_low,
        "range_high": scenario_set.range_high,
        "scenarios": [scenario.to_dict() for scenario in scenario_set.scenarios],
        "scenario_reason": scenario_set.reason,
        "score": snapshot.score,
        "model_version": MODEL_VERSION,
        "available_factors": snapshot.available_factors,
        "total_factors": len(snapshot.states),
        "factors": [_contribution_payload(state) for state in snapshot.states],
    }


def _direction_label(direction: Optional[str], status: str) -> Optional[str]:
    if status != engine.STATUS_OK or direction is None:
        return None
    return {"up": "看涨", "down": "看跌", "flat": "持平"}.get(direction)


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
            "publication_lag_days": state.publication_lag_days,
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
        # 历史行写库时已清洗过；这里再洗一次是给「旧版本写下的行」兜底 ——
        # 读接口同样不该把 NaN 交给 JSON 序列化器。
        "metrics": stats.json_safe(metrics),
        "factors": factors,
        "reason": metrics.get("reason"),
    }


# --------------------------------------------------------------------------- #
# 读：研究页（技能评估 / 可靠性 / 因子拆解 / 预注册裁决）
# --------------------------------------------------------------------------- #
def research_report(db: Session, *, use_cache: bool = True) -> dict:
    """研究页的数据：三个样本期的技能指标 + 可靠性分桶 + 因子拆解 + 裁决。

    技能指标是走查式现算（数据一变、页面跟着变），单次约数秒，用 1 小时缓存
    挡住页面刷新；``full_refresh`` 成功后会让缓存失效。数字全部来自
    ``backtest`` / ``stats``，这一层只做搬运与裁定，不自己造口径。
    """
    cache = CacheManager(RESEARCH_CACHE_KEY, ttl=RESEARCH_CACHE_TTL)
    if use_cache:
        cached = cache.get()
        if cached is not None:
            return {**cached, "cached": True}
    payload = _build_research_payload(db)
    if payload["status"] == engine.STATUS_OK:
        cache.set(payload)
    return {**payload, "cached": False}


def _data_window(close) -> dict:
    """本页数字实际来自的库内窗口：起止、交易日数与年数（研究页显著标注）。"""
    start = close.index[0].date()
    end = close.index[-1].date()
    span_days = max((end - start).days, 0)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "trading_days": int(len(close)),
        "years": round(span_days / 365.25, 1),
    }


def _build_research_payload(db: Session) -> dict:
    factors, close = load_panel(db)
    generated_at = timeutil.now_iso()
    if close is None or close.empty or not factors:
        return {
            "model_version": MODEL_VERSION,
            "status": engine.PREDICTION_UNAVAILABLE,
            "reason": "库里还没有因子面板或黄金价格序列（先同步数据，再看研究页）",
            "as_of": None,
            "data_window": None,
            "holdout_start": HOLDOUT_START.isoformat(),
            "active_holdout_start": ACTIVE_HOLDOUT_START.isoformat(),
            "generated_at": generated_at,
            "verdict": {
                "status": "unavailable",
                "label": "数据不可用",
                "detail": "没有可评估的数据，研究页不给出任何技能结论。",
            },
            "horizons": [],
        }

    horizons_payload = []
    flags = {}
    for horizon in HORIZONS:
        periods = backtest.evaluate_periods(factors, close, horizon=horizon)
        spec = horizon_spec.get(horizon)
        # 裁决窗口够不够判、还差多少 —— 页面必须能回答「为什么没有结论」。
        # 下注次数以回测**实际**数出来的为准（日历折算会把还没实现收益的最后 h 行
        # 也算上，于是与 rule_flags 的样本量闸门差一注）。评估压根没跑时
        # （`_empty`：样本不足 30）那个指标是缺失的 —— 一次可用下注都没有，记 0。
        forward_metrics = periods["forward"].metrics or {}
        forward_bets = forward_metrics.get("nonoverlapping_samples")
        forward_rule_input = preregistered.rule_input(periods["forward"], periods["forward"])
        flags[horizon] = preregistered.rule_flags(forward_rule_input)
        # 前向裁决的 Beta 后验（先验写死 Beta(1,1)）与 CRPS 并排：入选规则不变，
        # 但结论旁边必须能看见「这个命中率有多少独立证据、整张分布评分如何」。
        forward_posterior = preregistered.forward_posterior(forward_rule_input)
        horizons_payload.append(
            {
                "horizon_days": horizon,
                "label": spec.label if spec else f"{horizon} 日",
                "headline": spec.headline if spec else "方向 / 校准区间",
                "forward_readiness": preregistered.forward_window_readiness(
                    close.index,
                    horizon,
                    realized_bets=0 if forward_bets is None else forward_bets,
                ),
                "forward_posterior": forward_posterior,
                "periods": {
                    name: _research_period(name, evaluation)
                    for name, evaluation in periods.items()
                },
                "reliability_bins": _research_bins(                    (periods["full"].metrics or {}).get("reliability_bins")
                ),
                "factors": _research_factors(periods["full"]),
            }
        )
    passed_scales = [horizon for horizon, flag in flags.items() if flag["pass"]]
    return {
        "model_version": MODEL_VERSION,
        "status": engine.STATUS_OK,
        "reason": None,
        "as_of": close.index[-1].date().isoformat(),
        "data_window": _data_window(close),
        "holdout_start": HOLDOUT_START.isoformat(),
        "active_holdout_start": ACTIVE_HOLDOUT_START.isoformat(),
        "generated_at": generated_at,
        "verdict": _research_verdict(passed_scales, horizons_payload),
        "horizons": horizons_payload,
    }


def _finite_pair(pair):
    if pair is None:
        return None
    values = [preregistered.finite(value) for value in pair]
    return None if any(value is None for value in values) else values


def _research_period(name: str, evaluation: backtest.HorizonEvaluation) -> dict:
    """一个样本期的指标（None = 算不出来；页面照实显示，不补数字）。"""
    metrics = evaluation.metrics or {}
    return {
        "label": RESEARCH_PERIOD_LABELS.get(name, name),
        "window_start": (
            evaluation.window_start.isoformat() if evaluation.window_start else None
        ),
        "window_end": (
            evaluation.window_end.isoformat() if evaluation.window_end else None
        ),
        "sample_size": evaluation.sample_size,
        "accuracy": preregistered.finite(evaluation.accuracy),
        "baseline_up_accuracy": preregistered.finite(evaluation.baseline_up_accuracy),
        "baseline_momentum_accuracy": preregistered.finite(
            evaluation.baseline_momentum_accuracy
        ),
        "brier_score": preregistered.finite(evaluation.brier_score),
        "brier_skill_score": preregistered.finite(metrics.get("brier_skill_score")),
        "brier_skill_p_value": preregistered.finite(metrics.get("brier_skill_p_value")),
        "mean_crps": preregistered.finite(metrics.get("mean_crps")),
        "crps_skill_vs_flat": preregistered.finite(metrics.get("crps_skill_vs_flat")),
        "accuracy_diff_vs_up": preregistered.finite(metrics.get("accuracy_diff_vs_up")),
        # 一级 KPI：相对「永远看多」的增量 + 置信区间；点估计在牛市里几乎总是负的，
        # 区间跨不跨 0 才决定它能不能当结论。
        "direction_edge_vs_up_ci95": _finite_pair(metrics.get("direction_edge_vs_up_ci95")),
        # 「敢喊跌质量」：喊跌日上模型命中率 − 同一天「永远看多」的命中率。
        "down_calls": metrics.get("down_calls"),
        "down_call_accuracy": preregistered.finite(metrics.get("down_call_accuracy")),
        "down_call_edge_vs_up": preregistered.finite(metrics.get("down_call_edge_vs_up")),
        "accuracy_ci95": _finite_pair(metrics.get("accuracy_ci95")),
        "p_value_vs_up": preregistered.finite(metrics.get("p_value_vs_up")),
        "interval_coverage_80": preregistered.finite(metrics.get("interval_coverage_80")),
        "interval_coverage_ci95": _finite_pair(metrics.get("interval_coverage_ci95")),
        "effective_sample_size": preregistered.finite(metrics.get("effective_sample_size")),
        # 独立下注口径：把重叠的逐日样本按 stride = 尺度抽成 k 次互不相干的下注后，
        # 成绩还剩多少。样本不足时命中率/覆盖率给 None，次数照实报出 —— 页面因此
        # 能显示「506 个样本 = 2 次下注」而不是把 2 个观测的比例当结论。
        "independent_bets": metrics.get("nonoverlapping_samples"),
        # 算不出成绩的样本期（空窗口 / 样本不足）也要给出 stride ——
        # 它是尺度的属性，不是这次算出来的结果。
        "independent_bet_stride": metrics.get("nonoverlapping_stride")
        or evaluation.horizon_days,
        "accuracy_independent_bets": preregistered.finite(
            metrics.get("accuracy_nonoverlapping")
        ),
        "interval_coverage_80_independent_bets": preregistered.finite(
            metrics.get("interval_coverage_80_nonoverlapping")
        ),
        "expected_cap_rate": preregistered.finite(metrics.get("expected_cap_rate")),
        "reason": metrics.get("reason"),
    }


def _research_bins(bins) -> list[dict]:
    rows = []
    for item in bins or []:
        rows.append(
            {
                "lo": preregistered.finite(item.get("lo")),
                "hi": preregistered.finite(item.get("hi")),
                "count": int(item.get("count") or 0),
                "mean_predicted": preregistered.finite(item.get("mean_predicted")),
                "frequency": preregistered.finite(item.get("frequency")),
            }
        )
    return rows


def _research_factors(evaluation: backtest.HorizonEvaluation) -> list[dict]:
    per_factor = (evaluation.metrics or {}).get("per_factor") or {}
    rows = []
    for key, item in per_factor.items():
        definition = factor_by_key.get(key)
        category = item.get("category") or (definition.category if definition else "")
        rows.append(
            {
                "key": key,
                "name": item.get("name") or (definition.name if definition else key),
                "category": category,
                "category_name": CATEGORY_NAMES.get(category, ""),
                "weight": float(item.get("weight") or 0.0),
                "sign": int(item.get("sign") or 0),
                "samples": int(item.get("samples") or 0),
                "hit_rate": preregistered.finite(item.get("hit_rate")),
                "ic": preregistered.finite(item.get("ic")),
                "rank_ic": preregistered.finite(item.get("rank_ic")),
                # 对齐幅度与它的显著性（HAC）；naive_t 一并给出，差值就是重叠样本的虚高量
                "alignment": preregistered.finite(item.get("alignment")),
                "alignment_t": preregistered.finite(item.get("alignment_t")),
                "alignment_p_value": preregistered.finite(item.get("alignment_p_value")),
                "alignment_naive_t": preregistered.finite(item.get("alignment_naive_t")),
            }
        )
    rows.sort(key=lambda row: row["weight"], reverse=True)
    return rows


def _research_verdict(passed_scales: list[int], horizons_payload: list[dict]) -> dict:
    """由数据生成一句诚实的结论；文案不写死「好」或「坏」。"""
    # 第一件事：裁决窗口到底能不能判。判不了就说 pending 与还差多少 ——
    # 拿历史留出期的成绩顶替，等于把预注册的窗口纪律作废。
    pending = [
        item
        for item in horizons_payload
        if not (item.get("forward_readiness") or {}).get("decidable")
    ]
    # 全部尺度都还判不了 → pending。只要有一个尺度能判，就照常走规则并逐条说明
    # 哪些尺度还没到判定条件 —— 把已经能看出来的东西藏起来同样是撒谎。
    if pending and len(pending) == len(horizons_payload):
        shortfalls = []
        for item in pending:
            readiness = item["forward_readiness"]
            shortfalls.append(
                f"{item['horizon_days']} 日 {readiness['independent_bets']}/"
                f"{readiness['required_bets']} 次独立下注"
                f"（还需约 {readiness['approx_trading_days_needed']} 个交易日）"
            )
        return {
            "status": preregistered.STATUS_PENDING,
            "label": "前向窗口尚不可判",
            "detail": (
                f"裁决只认前向留出期（{ACTIVE_HOLDOUT_START.isoformat()} 起）的独立下注："
                + "；".join(shortfalls)
                + f"。{HOLDOUT_START.isoformat()} 起的那一段已被前两轮裁决看过，"
                "只能当历史记录，不作为入选依据；此刻不给出「有优势 / 无优势」的结论。"
            ),
        }

    differences = [
        item["periods"]["forward"]["accuracy_diff_vs_up"]
        for item in horizons_payload
        if item["horizon_days"] != preregistered.TARGET_SCALE
    ]
    others_ok = preregistered.other_scales_ok(differences)
    if preregistered.selected(passed_scales, others_ok=others_ok):
        detail = (
            f"前向留出期有 {len(passed_scales)} 个尺度过线（"
            + "、".join(f"{horizon} 日" for horizon in passed_scales)
            + "）；按预注册规则进入模型换代复核。"
        )
        return {"status": "candidate", "label": "存在过线候选", "detail": detail}

    details = []
    for item in horizons_payload:
        holdout = item["periods"]["forward"]
        accuracy = holdout["accuracy"]
        up = holdout["baseline_up_accuracy"]
        coverage = holdout["interval_coverage_80"]
        count = holdout["effective_sample_size"]
        if accuracy is None or up is None:
            details.append(f"{item['horizon_days']} 日：样本不足")
            continue
        piece = (
            f"{item['horizon_days']} 日命中 {accuracy * 100:.1f}% / "
            f"永远看多 {up * 100:.1f}%（{100 * (accuracy - up):+.1f}pp）"
        )
        if coverage is not None:
            piece += f"，区间覆盖 {coverage * 100:.1f}%（名义 80%）"
        edge_ci = holdout.get("direction_edge_vs_up_ci95")
        if edge_ci:
            piece += (
                f"，相对基准增量 95% CI [{edge_ci[0] * 100:+.1f}, {edge_ci[1] * 100:+.1f}]pp"
            )
        down_calls = holdout.get("down_calls")
        if down_calls is not None:
            down_hits = holdout.get("down_call_accuracy")
            down_edge = holdout.get("down_call_edge_vs_up")
            if down_hits is not None:
                piece += f"，喊跌 {down_calls} 次命中 {down_hits * 100:.1f}%"
                if down_edge is not None:
                    piece += f"（比同日基准 {down_edge * 100:+.1f}pp）"
            else:
                piece += f"，喊跌 {down_calls} 次（不足 30 次，不评命中率）"
        posterior = item.get("forward_posterior")
        if posterior:
            posterior_ci = posterior["ci95"]
            piece += (
                f"，Beta 后验均值 {posterior['mean'] * 100:.1f}%"
                f"（95% CI {posterior_ci[0] * 100:.1f}–{posterior_ci[1] * 100:.1f}%）"
            )
            above = posterior.get("probability_above_threshold")
            if above is not None:
                piece += f"，P(优于永远看多) {above * 100:.0f}%"
            crps = posterior.get("crps_skill_vs_flat")
            if crps is not None:
                piece += f"，CRPS 技能 {crps:+.3f}"
        # 独立下注次数不足时，这个尺度「没被判定」，不是「被判了不及格」
        if count is not None and count < preregistered.MIN_EFFECTIVE_SAMPLES:
            piece += f"，仅约 {count:g} 次独立下注 → 不可判定"
        else:
            piece += f"（独立下注约 {count:g} 次）" if count is not None else ""
        details.append(piece)
    undecidable = [
        item["horizon_days"]
        for item in horizons_payload
        if (item["periods"]["forward"].get("effective_sample_size") or 0)
        < preregistered.MIN_EFFECTIVE_SAMPLES
    ]
    # 还没攒够独立下注的尺度：把「还差多少个交易日」直接写在结论里 ——
    # 只说「样本不足以判定」会让人以为再等几天就行，其实差的是几十上百个交易日。
    waits = {
        item["horizon_days"]: (item.get("forward_readiness") or {}).get(
            "approx_trading_days_needed"
        )
        for item in horizons_payload
    }
    evidence_note = ""
    if undecidable:
        listed = "、".join(
            f"{horizon} 日"
            + (f"（还需约 {waits[horizon]} 个交易日）" if waits.get(horizon) else "")
            for horizon in undecidable
        )
        evidence_note = f"。其中 {listed} 的样本量不足以判定，不计入「未过线」的证据"
    return {
        "status": "no_edge",
        "label": "无统计优势",
        "detail": (
            f"前向留出期（{ACTIVE_HOLDOUT_START.isoformat()} 起）没有尺度满足预注册规则 ①/②："
            + "；".join(details)
            + evidence_note
            + f"。按预注册规则保留 {MODEL_VERSION}，不换模型。"
        ),
    }


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

    # 回测在前、预测在后：落库的 reasoning 会引用「本尺度最近一次回测」的技能结论，
    # 先写预测的话，技能句永远停留在「尚无回测记录」上（这条顺序由测试钉住）。
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

    predictions = []
    for horizon in horizons:
        snapshot = engine.build_snapshot(factors, close, horizon=horizon)
        payload = _prediction_payload(snapshot, close)
        if snapshot.status == engine.STATUS_OK:
            _store_prediction(db, snapshot)
        predictions.append(payload)
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
    """每天每个尺度只留一行快照 —— 跨天追加，当天刷新就地更新。

    去重键 = (model_version, horizon_days, as_of)：

    - 同一天内每两小时一次的重算只更新当天这一行，库里的这一天与页面最后
      看到的结果一致，也不会把表撑成流水账；
    - 新的一天到来时 ``as_of`` 变化，自然追加新行、旧行原样保留 —— 这条历史
      轨迹就是预测的存档，``created_at`` 记录该行首次落库的时刻。

    旧实现按「最新一行是否与之完全相同」去重：同一天重算只要方向或目标价
    变了就再插一行（一天可堆出好几行），而跨天又没有稳定键。现在键就是
    天数与尺度，跨天保留、当天一行。
    """
    row = (
        db.query(Prediction)
        .filter(
            Prediction.model_version == MODEL_VERSION,
            Prediction.horizon_days == snapshot.horizon_days,
            Prediction.as_of == snapshot.as_of,
        )
        .order_by(Prediction.id.desc())
        .first()
    )
    values = {
        "prediction_type": snapshot.direction,
        "target_price": snapshot.target_price,
        "confidence": snapshot.probability_up,
        "timeframe": f"{snapshot.horizon_days}D",
        "reasoning": _reasoning(snapshot, _skill_note(db, snapshot.horizon_days)),
        "factors": stats.json_safe(
            [
                {
                    "key": state.key,
                    "name": state.name,
                    "contribution": state.contribution,
                    "signed_z": state.signed_z,
                }
                for state in snapshot.states
                if state.available
            ]
        ),
        "direction": snapshot.direction,
        "base_price": snapshot.base_price,
        "score": snapshot.score,
        "expected_return": snapshot.expected_return,
        "uncertainty": snapshot.uncertainty,
    }
    if row is not None:
        for field, value in values.items():
            setattr(row, field, value)
        return
    db.add(
        Prediction(
            model_version=MODEL_VERSION,
            horizon_days=snapshot.horizon_days,
            as_of=snapshot.as_of,
            **values,
        )
    )


def _skill_note(db: Session, horizon: int) -> str:
    """这个尺度上模型到底有没有可核实技能 —— 一句话，跟着预测一起落库。

    为什么必须有：页面与历史接口展示的是「方向 + 目标价」，而回测早就知道
    「方向与永远看多逐日一致、幅度不优于预测不动」。技能结论只写在研究页里，
    看预测的人拿不到它，就等于把噪声包装成判断（红线一的另一条入口）。
    评估缺失或样本不足时**如实说不确定**，不许编一个「仅供参考」之类的软话。
    """
    row = (
        db.query(ModelEvaluation)
        .filter(
            ModelEvaluation.model_version == MODEL_VERSION,
            ModelEvaluation.horizon_days == horizon,
        )
        .order_by(ModelEvaluation.evaluated_at.desc(), ModelEvaluation.id.desc())
        .first()
    )
    if row is None:
        return "技能状态：尚无该尺度的回测记录，这条预测没有可核实的胜率背书"
    metrics = row.metrics or {}
    effective = preregistered.finite(metrics.get("effective_sample_size"))
    if effective is None or effective < preregistered.MIN_EFFECTIVE_SAMPLES:
        count = "-" if effective is None else f"{effective:g}"
        return (
            f"技能状态：该尺度只有约 {count} 次独立下注"
            f"（低于判定下限 {preregistered.MIN_EFFECTIVE_SAMPLES}），无法判定有无技能"
        )
    accuracy = preregistered.finite(row.accuracy)
    up = preregistered.finite(row.baseline_up_accuracy)
    difference = preregistered.finite(metrics.get("accuracy_diff_vs_up"))
    magnitude = preregistered.finite(metrics.get("magnitude_skill_vs_flat"))
    down_calls = metrics.get("down_calls")
    pieces = []
    if accuracy is not None and up is not None and difference is not None:
        pieces.append(f"方向 {accuracy * 100:.1f}% 对永远看多 {up * 100:.1f}%（{difference * 100:+.1f}pp）")
    if magnitude is not None:
        pieces.append(f"幅度{'优于' if magnitude > 0 else '不优于'}预测不动（{magnitude:+.3f}）")
    if down_calls is not None:
        pieces.append(f"回测期内喊跌 {down_calls} 次")
    verdict = (
        "有可核实优势"
        if (difference is not None and difference > 0 and (magnitude or 0) > 0)
        else "未跑赢朴素基准"
    )
    stamp = row.evaluated_at.date().isoformat() if row.evaluated_at else "未知时间"
    return f"技能状态（{stamp} 回测，独立下注约 {effective:g} 次）：{verdict}；" + "；".join(pieces)


def _reasoning(snapshot: engine.SignalSnapshot, skill_note: str) -> str:
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
    parts.append(skill_note)
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
            metrics=stats.json_safe(evaluation.metrics),
        )
    )


def full_refresh(db: Session, *, force: bool = True) -> dict:
    """抓取 → 派生 → 落库 → 重算预测 → 回测。限流与耗时见 POST /refresh。"""
    report = sync.run_sync(db, force=force)
    result = refresh_predictions(db, force_backtest=True)
    # 数据变了，研究页的缓存（含旧截止日）必须失效，否则页面讲旧数字
    CacheManager(RESEARCH_CACHE_KEY, ttl=RESEARCH_CACHE_TTL).delete()
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
