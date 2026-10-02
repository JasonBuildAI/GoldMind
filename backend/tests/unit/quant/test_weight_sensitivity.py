"""权重敏感性（2.0.2 第 6 条）：扰动权重时排序是否稳定，与归一化守卫。

两条纪律：
1. 敏感性只走 ``engine.composite_score`` 同一份公式（``weights_override``），
   不允许脚本另抄一份合成公式 —— 抄一份就等于在两处维护口径。
2. 权重整体缩放不改变得分（按当日可用权重归一）；这条通过变异验证：
   把归一改坏（除以固定总权重）时 ``test_override_is_scale_invariant`` 变红。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.services.quant import engine
from scripts import weight_sensitivity


def _signals(columns: dict[str, np.ndarray], periods: int = 250) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=periods, freq="B")
    return pd.DataFrame(columns, index=index)


def test_override_is_scale_invariant():
    signals = _signals(
        {
            "real_yield_10y": np.linspace(-1.0, 1.5, 250),
            "vix": np.cos(np.arange(250) / 15.0),
        }
    )
    base = engine.composite_score(signals, horizon=20)
    scaled = engine.composite_score(
        signals, horizon=20, weights_override={"real_yield_10y": 7.3, "vix": 2.92}
    )
    pd.testing.assert_series_equal(base, scaled)


def test_zero_weight_drops_the_factor():
    signals = _signals(
        {
            "real_yield_10y": np.linspace(-1.0, 1.5, 250),
            "vix": np.linspace(3.0, -3.0, 250),
        }
    )
    dropped = engine.composite_score(
        signals, horizon=20, weights_override={"real_yield_10y": 1.0, "vix": 0.0}
    )
    pd.testing.assert_series_equal(
        dropped, signals["real_yield_10y"], check_names=False
    )


def test_stable_when_one_factor_dominates_the_ranking():
    dominant = np.sin(np.arange(250) / 12.0) * 3.0
    tiny = np.cos(np.arange(250) / 7.0) * 1e-6
    signals = _signals({"real_yield_10y": dominant, "vix": tiny})

    report = weight_sensitivity.analyse_horizon(
        signals, 20, draws=25, jitter=0.2, seed=7
    )

    assert report["available"] is True
    assert report["verdict"] == "稳定"
    assert report["rank_median"] >= 1.0 - 1e-9
    assert report["sign_flip_rate"] == 0.0
    assert report["max_abs_delta"] > 0.0, "扰动没有进入公式（权重覆盖被静默忽略）"
    assert report["leverage"]["real_yield_10y"] > report["leverage"]["vix"]


def test_flags_sensitive_ranking_when_signals_compete():
    rng = np.random.default_rng(11)
    signals = _signals(
        {
            "real_yield_10y": rng.normal(0.0, 1.0, 250),
            "vix": rng.normal(0.0, 1.0, 250),
        }
    )

    report = weight_sensitivity.analyse_horizon(
        signals, 5, draws=25, jitter=0.7, seed=3
    )

    assert report["available"] is True
    assert report["verdict"] == "对权重敏感"
    assert report["rank_median"] < 0.99


def test_reports_unavailable_without_enough_history():
    signals = _signals(
        {
            "real_yield_10y": np.arange(10, dtype="float64"),
            "vix": np.arange(10, dtype="float64"),
        },
        periods=10,
    )

    report = weight_sensitivity.analyse_horizon(signals, 5, draws=5)

    assert report["available"] is False
    assert "不足" in report["reason"]


def test_markdown_carries_the_honest_verdict():
    symbols = np.sin(np.arange(250) / 9.0)
    signals = _signals({"real_yield_10y": symbols, "vix": symbols * 1e-6})
    report = weight_sensitivity.analyse_horizon(signals, 1, draws=10, jitter=0.2, seed=1)

    markdown = weight_sensitivity.format_markdown(
        [report],
        generated_at="2026-10-03T00:00:00+08:00",
        days=250,
        start="2025-01-01",
        end="2026-09-30",
        draws=10,
        jitter=0.2,
        seed=1,
    )

    assert "权重敏感性报告" in markdown
    assert "稳定" in markdown
    assert "杠杆" in markdown
    assert "real_yield_10y" in markdown