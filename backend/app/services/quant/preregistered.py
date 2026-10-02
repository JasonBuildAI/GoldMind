"""预注册硬规则的唯一实现（spec `2026-10-02-量化策略提升路线图.md` 6.1）。

研究台（``scripts/quant_lab.py``）与研究接口（``GET /api/gold/quant/research``）
都调用这里的判定函数 —— 规则常量与谓词只写一次，避免两边各写一遍、悄悄分叉。
看到留出期成绩之后修改这里的常量 = 破坏预注册；
``tests/unit/quant/test_quant_lab.py`` 会把常量与 spec 文本逐项对齐。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from app.services.quant.definitions import ACTIVE_HOLDOUT_START

# 预注册常量（与 spec 6.1 一字不差地对应）
TARGET_SCALE = 250
RULE_2_ACCURACY_TOLERANCE = -0.01   # 命中率不劣化 ≤1pp
RULE_OTHER_SCALE_TOLERANCE = -0.02  # 其它尺度不恶化 ≤2pp
RULE_2_BRIER_P = 0.05               # Brier 技能分显著为正（HAC DM 单尾）
INTERVAL_NOMINAL = 0.80             # 名义覆盖率
MIN_PASSING_SCALES = 3              # ≥3/5 尺度成立
# 一个尺度的「可判定性」下限：重叠样本折算后的独立下注次数低于此数，就不许把
# 「未过线」当成结论 —— 这是**报告口径**，不是入选规则：①/② 的常量一字不动。
# 依据：250 日留出期 506 个重叠样本 = 2 次独立下注，覆盖率 24.1% 的 CI 是 [4%, 45%]
# （docs/specs/2026-10-02-量化引擎第二轮预注册.md 一、为什么目标定义必须换）。
MIN_EFFECTIVE_SAMPLES = 20

# 裁决层的前向窗口状态：还没积累够独立下注时说 pending，不说「没过线」——
# 「还不知道」和「知道了，是坏的」是两件事，混在一起就把窗口纪律变成了装饰。
STATUS_PENDING = "pending"


def forward_window_readiness(
    index, horizon: int, *, start: date = ACTIVE_HOLDOUT_START,
    realized_bets: Optional[int] = None,
) -> dict:
    """裁决窗口现在能不能判：把已经积累多少、还差多少摊开说。

    ``index`` 是价格序列的日期索引（DatetimeIndex / 任何带 ``.date()`` 的序列）。
    「独立下注」= 窗口内的观测数按尺度折算（``observations // horizon``），
    与回测里 stride = h 的抽样同一口径；要够 ``MIN_EFFECTIVE_SAMPLES`` 次才可判。

    ``realized_bets`` 给定时以它为准 —— 调用方能拿到回测**实际**数出来的下注次数
    （``metrics.nonoverlapping_samples``）时就应该传：日历折算会把最后 h 行也算进去，
    而那些行的 h 日前瞻收益还没实现、进不了评估掩码，于是 readiness 可能报「可判」
    而 ``rule_flags`` 同时报「独立下注不足」。同一页面上两个数各说各话，
    正是第二轮要消灭的那类失真。
    """
    observations = sum(1 for moment in index if moment.date() >= start)
    if realized_bets is None:
        bets = observations // horizon if horizon > 0 else 0
    else:
        bets = max(0, int(realized_bets))
    required = MIN_EFFECTIVE_SAMPLES
    return {
        "window_start": start.isoformat(),
        "observations": int(observations),
        "independent_bets": int(bets),
        "required_bets": int(required),
        "decidable": bets >= required,
        "shortfall_bets": int(max(0, required - bets)),
        "approx_trading_days_needed": int(max(0, required * horizon - observations)),
    }


def finite(value) -> Optional[float]:
    """NaN / inf 视为「没有这个数字」—— 判定与 JSON 都不该看到 NaN。"""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


@dataclass(frozen=True)
class RuleInput:
    """一次（候选，尺度，留出期）判定的全部输入；缺任何一项按「不成立」处理。"""

    accuracy_ci_low: Optional[float] = None
    baseline_up: Optional[float] = None
    accuracy_diff_vs_up: Optional[float] = None
    brier_skill_score: Optional[float] = None
    brier_skill_p_value: Optional[float] = None
    coverage_80: Optional[float] = None
    baseline_coverage_80: Optional[float] = None
    effective_sample_size: Optional[float] = None


def rule_flags(data: RuleInput) -> dict:
    """逐尺度判定 ① / ②（细则见 spec 6.1），并给出该尺度**可不可判定**。

    `status` 取 `insufficient` / `pass` / `fail`：独立下注次数不足时既不说「过线」
    也不说「未过线」—— 一个 2 个观测撑起来的命中率没有资格被当成证据。
    """
    count = finite(data.effective_sample_size)
    if count is not None and count < MIN_EFFECTIVE_SAMPLES:
        return {
            "rule_1": False,
            "rule_2": False,
            "pass": False,
            "sufficient": False,
            "status": "insufficient",
            "effective_sample_size": count,
        }

    ci_low = finite(data.accuracy_ci_low)
    up = finite(data.baseline_up)
    rule_1 = ci_low is not None and up is not None and ci_low > up

    coverage = finite(data.coverage_80)
    base_coverage = finite(data.baseline_coverage_80)
    closer_to_80 = (
        coverage is not None
        and base_coverage is not None
        and abs(coverage - INTERVAL_NOMINAL) < abs(base_coverage - INTERVAL_NOMINAL)
    )
    difference = finite(data.accuracy_diff_vs_up)
    not_worse = difference is not None and difference >= RULE_2_ACCURACY_TOLERANCE
    skill = finite(data.brier_skill_score)
    skill_p = finite(data.brier_skill_p_value)
    skill_significant = (
        skill is not None and skill > 0 and skill_p is not None and skill_p < RULE_2_BRIER_P
    )
    rule_2 = not_worse and skill_significant and closer_to_80
    passed = bool(rule_1 or rule_2)
    return {
        "rule_1": bool(rule_1),
        "rule_2": bool(rule_2),
        "pass": passed,
        "sufficient": True,
        "status": "pass" if passed else "fail",
        "effective_sample_size": count,
    }


def rule_input(evaluation, baseline) -> RuleInput:
    """从一次 ``HorizonEvaluation``（候选与基准）构造判定输入。"""
    candidate_metrics = getattr(evaluation, "metrics", None) or {}
    baseline_metrics = getattr(baseline, "metrics", None) or {}
    accuracy_ci = candidate_metrics.get("accuracy_ci95") or (None, None)
    return RuleInput(
        accuracy_ci_low=accuracy_ci[0],
        baseline_up=getattr(evaluation, "baseline_up_accuracy", None),
        accuracy_diff_vs_up=candidate_metrics.get("accuracy_diff_vs_up"),
        brier_skill_score=candidate_metrics.get("brier_skill_score"),
        brier_skill_p_value=candidate_metrics.get("brier_skill_p_value"),
        coverage_80=candidate_metrics.get("interval_coverage_80"),
        baseline_coverage_80=baseline_metrics.get("interval_coverage_80"),
        effective_sample_size=candidate_metrics.get("effective_sample_size"),
    )


def selected(
    passed_scales: Sequence[int],
    *,
    others_ok: bool,
    target_scale: int = TARGET_SCALE,
) -> bool:
    """入选判定：≥3/5 尺度成立，或目标尺度成立且其它尺度不恶化 ≤2pp。"""
    if len(passed_scales) >= MIN_PASSING_SCALES:
        return True
    return bool(target_scale in passed_scales and others_ok)


def other_scales_ok(differences: Sequence[Optional[float]], *, target_scale: int = TARGET_SCALE,
                    horizons: Sequence[int] = ()) -> bool:
    """其它尺度相对「永远看多」不恶化 ≤2pp（缺数字不算过线）。"""
    pairs = list(zip(horizons, differences)) if horizons else [(None, d) for d in differences]
    checked = [(h, d) for h, d in pairs if h != target_scale]
    return all(finite(d) is not None and finite(d) >= RULE_OTHER_SCALE_TOLERANCE for _, d in checked)
