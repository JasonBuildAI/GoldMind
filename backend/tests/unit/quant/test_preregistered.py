"""预注册判定：谓词边界、缺数字的行为、入选规则。

规则文本的唯一真源是 spec 6.1；这里的用例把「实现与文本同义」钉在可执行的
边界上 —— 看到留出期成绩之后再改判定，先红的就是这些用例。
"""
from __future__ import annotations

import pytest

from app.services.quant import preregistered


def _passing_rule_input(**overrides) -> preregistered.RuleInput:
    base = dict(
        accuracy_ci_low=0.60,
        baseline_up=0.58,
        accuracy_diff_vs_up=0.02,
        brier_skill_score=0.05,
        brier_skill_p_value=0.01,
        coverage_80=0.79,
        baseline_coverage_80=0.70,
    )
    base.update(overrides)
    return preregistered.RuleInput(**base)


def test_rule_1_requires_ci_low_strictly_above_always_up():
    assert preregistered.rule_flags(_passing_rule_input())["rule_1"] is True
    # CI 下界恰好等于基准率：不显著，不算过线
    flags = preregistered.rule_flags(_passing_rule_input(accuracy_ci_low=0.58))
    assert flags["rule_1"] is False
    # 样本不足时 CI 是 None：缺数字不是证据
    flags = preregistered.rule_flags(_passing_rule_input(accuracy_ci_low=None))
    assert flags["rule_1"] is False


def test_rule_2_needs_accuracy_skill_and_coverage_together():
    assert preregistered.rule_flags(_passing_rule_input())["rule_2"] is True
    # 命中率劣化超过 1pp
    flags = preregistered.rule_flags(_passing_rule_input(accuracy_diff_vs_up=-0.011))
    assert flags["rule_2"] is False
    # 技能分为正、但 p 值不到显著性（0.05 是开区间边界）
    flags = preregistered.rule_flags(_passing_rule_input(brier_skill_p_value=0.05))
    assert flags["rule_2"] is False
    # 技能分不显著为正
    flags = preregistered.rule_flags(
        _passing_rule_input(brier_skill_score=-0.01, brier_skill_p_value=0.001)
    )
    assert flags["rule_2"] is False
    # 覆盖率没有比基准更接近 80%
    flags = preregistered.rule_flags(
        _passing_rule_input(coverage_80=0.65, baseline_coverage_80=0.70)
    )
    assert flags["rule_2"] is False


def test_missing_or_non_finite_numbers_never_pass():
    flags = preregistered.rule_flags(
        preregistered.RuleInput(
            accuracy_ci_low=float("nan"),
            baseline_up=float("inf"),
            accuracy_diff_vs_up=None,
            brier_skill_score=float("nan"),
            brier_skill_p_value=None,
            coverage_80=None,
            baseline_coverage_80=None,
        )
    )

    assert flags == {
        "rule_1": False,
        "rule_2": False,
        "pass": False,
        # 没有独立下注次数这个数，就不许反过来宣称「样本不足」：按可判定走既有规则
        "sufficient": True,
        "status": "fail",
        "effective_sample_size": None,
    }


def test_selected_follows_the_three_scale_or_target_rule():
    assert preregistered.selected([1, 5, 20], others_ok=False) is True     # ≥3/5 尺度
    assert preregistered.selected([250], others_ok=True) is True           # 目标尺度 + 其它不恶化
    assert preregistered.selected([250], others_ok=False) is False
    assert preregistered.selected([5, 20], others_ok=True) is False        # 不足 3 个且缺目标


def test_other_scales_exclude_the_target_and_require_numbers():
    horizons = (1, 5, 20, 60, 250)
    # 目标尺度哪怕很差也不参与「其它尺度」；-0.02 恰好压线算过
    assert preregistered.other_scales_ok(
        [0.0, -0.02, 0.0, 0.0, -0.50], horizons=horizons
    ) is True
    assert preregistered.other_scales_ok(
        [0.0, -0.021, 0.0, 0.0, 0.0], horizons=horizons
    ) is False
    assert preregistered.other_scales_ok(
        [0.0, None, 0.0, 0.0, 0.0], horizons=horizons
    ) is False


def test_finite_maps_nan_and_inf_to_none():
    assert preregistered.finite(None) is None
    assert preregistered.finite("abc") is None
    assert preregistered.finite(float("nan")) is None
    assert preregistered.finite(float("inf")) is None
    assert preregistered.finite(0.5) == pytest.approx(0.5)


def test_rule_input_reads_the_holdout_evaluation_contract():
    class _Evaluation:
        metrics = {
            "accuracy_ci95": [0.55, 0.65],
            "accuracy_diff_vs_up": 0.01,
            "brier_skill_score": 0.03,
            "brier_skill_p_value": 0.02,
            "interval_coverage_80": 0.81,
        }
        baseline_up_accuracy = 0.60

    data = preregistered.rule_input(_Evaluation(), _Evaluation())

    assert data == preregistered.RuleInput(
        accuracy_ci_low=0.55,
        baseline_up=0.60,
        accuracy_diff_vs_up=0.01,
        brier_skill_score=0.03,
        brier_skill_p_value=0.02,
        coverage_80=0.81,
        baseline_coverage_80=0.81,
    )

def test_a_scale_with_too_few_independent_bets_is_undecidable_not_failed():
    """独立下注次数不足 → status=insufficient，且不许说成「未过线」。

    留出期的 250 日尺度就是这种情形：506 个重叠样本折算下来只有 2 次下注，
    而「永远看多」= 100%，规则 ① 结构上不可能满足、规则 ② 的 Brier 基准差为 0 也无定义。
    把这些读成「模型不及格」就是把噪声当证据。

    变异验证：把 ``MIN_EFFECTIVE_SAMPLES`` 改成 0（等于取消这道闸）本测试必红；
    把折算次数与阈值比反（``>`` 写成 ``<``）也必红。
    """
    passing = preregistered.RuleInput(
        accuracy_ci_low=0.70,
        baseline_up=0.60,
        accuracy_diff_vs_up=0.10,
        coverage_80=0.80,
        baseline_coverage_80=0.70,
        effective_sample_size=float(preregistered.MIN_EFFECTIVE_SAMPLES),
    )
    assert preregistered.rule_flags(passing)["status"] == "pass"

    thin = preregistered.RuleInput(
        accuracy_ci_low=0.70,
        baseline_up=0.60,
        accuracy_diff_vs_up=0.10,
        coverage_80=0.80,
        baseline_coverage_80=0.70,
        effective_sample_size=2.0,
    )
    flags = preregistered.rule_flags(thin)
    assert flags["status"] == "insufficient"
    assert flags["sufficient"] is False
    assert flags["pass"] is False
    assert flags["rule_1"] is False and flags["rule_2"] is False
    assert flags["effective_sample_size"] == 2.0

    # 没有这个数字时不臆断：按可判定处理，交给「缺数即不成立」那套既有规则
    assert preregistered.rule_flags(passing)["sufficient"] is True

