"""预注册硬规则的唯一实现（spec `2026-10-02-量化策略提升路线图.md` 6.1）。

研究台（``scripts/quant_lab.py``）与研究接口（``GET /api/gold/quant/research``）
都调用这里的判定函数 —— 规则常量与谓词只写一次，避免两边各写一遍、悄悄分叉。
看到留出期成绩之后修改这里的常量 = 破坏预注册；
``tests/unit/quant/test_quant_lab.py`` 会把常量与 spec 文本逐项对齐。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

# 预注册常量（与 spec 6.1 一字不差地对应）
TARGET_SCALE = 250
RULE_2_ACCURACY_TOLERANCE = -0.01   # 命中率不劣化 ≤1pp
RULE_OTHER_SCALE_TOLERANCE = -0.02  # 其它尺度不恶化 ≤2pp
RULE_2_BRIER_P = 0.05               # Brier 技能分显著为正（HAC DM 单尾）
INTERVAL_NOMINAL = 0.80             # 名义覆盖率
MIN_PASSING_SCALES = 3              # ≥3/5 尺度成立


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


def rule_flags(data: RuleInput) -> dict:
    """逐尺度判定 ① / ②（细则见 spec 6.1）。"""
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
    return {"rule_1": bool(rule_1), "rule_2": bool(rule_2), "pass": bool(rule_1 or rule_2)}


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
