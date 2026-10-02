"""统计工具：HAC 与朴素标准误的差别、自助覆盖、DM 判定、技能分与分桶。"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.quant import stats


def _ar1(count: int = 1200, rho: float = 0.9, seed: int = 3) -> np.ndarray:
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 1.0, count)
    values = np.empty(count, dtype="float64")
    values[0] = noise[0]
    for index in range(1, count):
        values[index] = rho * values[index - 1] + noise[index]
    return values + 5.0


@pytest.mark.unit
def test_hac_standard_error_exceeds_naive_on_autocorrelated_series():
    values = _ar1()
    naive = float(values.std(ddof=1) / np.sqrt(len(values)))

    hac = stats.newey_west_se(values, lags=50)

    assert hac > naive * 2.0, "强正自相关下 HAC 标准误必须明显大于朴素标准误"


@pytest.mark.unit
def test_hac_standard_error_is_close_to_naive_for_iid_series():
    rng = np.random.default_rng(11)
    values = rng.normal(0.0, 1.0, 4000)
    naive = float(values.std(ddof=1) / np.sqrt(len(values)))

    hac = stats.newey_west_se(values)

    assert 0.7 * naive < hac < 1.4 * naive, f"HAC={hac:.5f} 偏离朴素={naive:.5f} 太多"


@pytest.mark.unit
def test_block_bootstrap_interval_covers_the_true_mean():
    values = _ar1(count=1500, rho=0.85)

    lower, upper = stats.block_bootstrap_ci(values, block=25, n=800, seed=7)

    assert lower < 5.0 < upper, f"真实均值 5.0 不在区间 [{lower:.3f}, {upper:.3f}] 内"
    assert lower < values.mean() < upper


@pytest.mark.unit
def test_block_bootstrap_is_deterministic_per_seed():
    values = _ar1(count=300)

    first = stats.block_bootstrap_ci(values, block=10, n=200, seed=99)
    again = stats.block_bootstrap_ci(values, block=10, n=200, seed=99)
    different = stats.block_bootstrap_ci(values, block=10, n=200, seed=100)

    assert first == again
    assert first != different


@pytest.mark.unit
def test_diebold_mariano_is_not_significant_for_identical_losses():
    rng = np.random.default_rng(5)
    loss = rng.gamma(2.0, 1.0, 500)

    result = stats.diebold_mariano(loss, loss.copy())

    assert abs(result["mean_diff"]) < 1e-12
    assert result["p_value"] > 0.95 or np.isnan(result["statistic"])


@pytest.mark.unit
def test_diebold_mariano_detects_a_clearly_better_model():
    rng = np.random.default_rng(6)
    loss_a = rng.gamma(2.0, 1.0, 400)
    loss_b = 0.5 * loss_a

    result = stats.diebold_mariano(loss_a, loss_b)

    assert result["mean_diff"] > 0, "loss_a 更高 → d = a − b 应为正"
    assert result["p_value"] < 0.01, "损失差近 50% 时应高度显著"


@pytest.mark.unit
def test_brier_skill_score_bounds_and_reference():
    outcomes = np.array([1, 0, 1, 0, 1, 0, 0, 1], dtype="float64")
    perfect = stats.brier_skill_score(outcomes, outcomes)
    base_rate = float(outcomes.mean())
    no_skill = stats.brier_skill_score(np.full_like(outcomes, base_rate), outcomes)

    assert perfect == pytest.approx(1.0)
    assert no_skill == pytest.approx(0.0, abs=1e-12)
    assert stats.brier_skill_score(np.zeros_like(outcomes), outcomes) < 0.0


@pytest.mark.unit
def test_reliability_bins_partition_samples_and_report_frequencies():
    probabilities = [0.05, 0.15, 0.55, 0.55, 0.95, 0.95]
    outcomes = [0, 0, 0, 1, 1, 1]

    rows = stats.reliability_bins(probabilities, outcomes, bins=10)

    assert len(rows) == 10
    assert sum(row["count"] for row in rows) == len(probabilities)
    fifth = rows[5]
    assert fifth["count"] == 2
    assert fifth["mean_predicted"] == pytest.approx(0.55)
    assert fifth["frequency"] == pytest.approx(0.5)
    assert rows[0]["mean_predicted"] == pytest.approx(0.05)
    assert rows[0]["frequency"] == pytest.approx(0.0)


@pytest.mark.unit
def test_effective_sample_size_deflates_overlapping_windows():
    assert stats.effective_sample_size(1000, 1) == 1000.0
    assert stats.effective_sample_size(1000, 20) == 50.0
    assert stats.effective_sample_size(0, 250) == 0.0


@pytest.mark.unit
def test_hac_t_statistic_rejects_a_shifted_mean():
    rng = np.random.default_rng(8)
    values = rng.normal(1.0, 1.0, 500)

    result = stats.hac_t_statistic(values, mu=0.0)

    assert result["statistic"] > 5.0
    assert result["p_value"] < 1e-6
    assert result["sample_size"] == 500


@pytest.mark.unit
def test_one_sided_alternative_halves_the_tail():
    rng = np.random.default_rng(12)
    values = rng.normal(0.35, 1.0, 600)

    greater = stats.hac_t_statistic(values, alternative="greater")
    two_sided = stats.hac_t_statistic(values)

    assert greater["p_value"] == pytest.approx(two_sided["p_value"] / 2.0, rel=0.02)
    with pytest.raises(ValueError):
        stats.hac_t_statistic(values, alternative="sideways")


def test_nonoverlapping_keeps_the_latest_point_and_drops_the_overlap():
    """stride = h 时相邻样本不再共享信息，且锚点在尾部（最近的下注必须留下）。

    11 个样本 / stride 3：尾锚取 [1,4,7,10]，头锚取 [0,3,6,9] —— 用 len 不是 stride
    整数倍的长度，才能把「锚在头部」这种变异打红（10 个样本时两种锚法结果相同）。
    """
    values = list(range(11))

    picked = stats.nonoverlapping(values, 3)

    assert list(picked) == [1, 4, 7, 10]
    assert stats.nonoverlapping(values, 1).tolist() == values
    assert list(stats.nonoverlapping([1.0, np.nan, 2.0, 3.0], 2)) == [1.0, 3.0]
    # 空输入不炸
    assert list(stats.nonoverlapping([], 5)) == []


def test_nonoverlapping_shrinks_a_long_horizon_sample_to_the_honest_size():
    """250 日尺度：506 个重叠样本只等于 2 次独立下注 —— 非重叠口径必须这么小。"""
    values = np.arange(506, dtype="float64")

    assert len(stats.nonoverlapping(values, 250)) == 3
    assert stats.effective_sample_size(506, 250) == pytest.approx(2.024)
