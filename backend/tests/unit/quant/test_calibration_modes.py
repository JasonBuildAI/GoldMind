"""校准样本的三档取法（第三轮候选 C0 / C1 / C2）：接线正确性，不是统计优劣。

判据本身写在 spec 第二轮 §六.5（C1）与第三轮 §一（C2）—— 都是「开发期 60 日覆盖率 ≥ 0.78
且宽度 ≤ 线上的 1.05 倍」，由研究台跑出来裁决；这一文件只保证三件事：

1. 默认口径（``row``）与改动之前逐值相同 —— 不许因为加了候选而动了线上数；
2. ``bet`` / ``bet_window`` 口径真的「每注才更新一次」，而不是把常数换了个写法；
3. 未知口径一律抛错，不许静默退回默认。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import engine
from scripts import quant_lab


def _frame(factors, close, horizon: int, mode: str) -> pd.DataFrame:
    signals = engine.build_signals(factors, close.index)
    score = engine.composite_score(signals, horizon=horizon)
    return engine.build_prediction_frame(score, close, horizon, calibration_mode=mode)


@pytest.mark.unit
def test_row_mode_is_the_unchanged_online_path(make_panel):
    factors, close = make_panel(pd.date_range("2015-01-02", "2026-06-30", freq="B"))

    default = _frame(factors, close, 20, engine.CALIBRATION_ROW)
    explicit = _frame(factors, close, 20, "row")

    pd.testing.assert_frame_equal(default, explicit)


@pytest.mark.unit
def test_bet_mode_updates_alpha_only_once_per_bet(make_panel):
    """``bet`` 口径的签名：α 每 ``horizon`` 行才动一次，中间的行沿用同一条分布。

    变异验证：把 ``stride=horizon if per_bet else 1`` 改回恒 1，α 就会逐行变动，
    「只在整注处更新」那条断言必红；把 γ / 半衰期两档常数控成同一个值，
    第一组断言（与 row 不同）必红。
    """
    factors, close = make_panel(pd.date_range("2012-01-03", "2026-06-30", freq="B"))
    horizon = 20

    row = _frame(factors, close, horizon, engine.CALIBRATION_ROW)
    bet = _frame(factors, close, horizon, engine.CALIBRATION_BET)

    usable = row["interval_alpha"].notna() & bet["interval_alpha"].notna()
    assert int(usable.sum()) > 500, "样本太少，这两条断言什么都判不了"
    row_alpha = row["interval_alpha"][usable].to_numpy(dtype="float64")
    bet_alpha = bet["interval_alpha"][usable].to_numpy(dtype="float64")
    assert not np.allclose(row_alpha, bet_alpha), "两档算出同一条 α 路径，说明 stride 没生效"

    # 每注口径下，α 的变化次数应当≈ 注数，而不是行数
    changes = int((np.diff(bet_alpha) != 0).sum())
    bets = int(len(bet_alpha) // horizon)
    assert changes <= bets + 2, f"α 每行都在动（变化 {changes} 次 / 注数 {bets}）"
    assert changes >= bets // 2, f"α 几乎冻住（变化 {changes} 次 / 注数 {bets}）"
    assert int((np.diff(row_alpha) != 0).sum()) > 5 * bets, "对照组的 α 本该逐行变化"


@pytest.mark.unit
def test_the_bet_preset_is_exactly_the_four_numbers_written_in_the_spec():
    """C1 是四个数一起定义的候选：取样单位、学习速率、半衰期、回看窗。

    变异验证：把 ``calibration_settings`` 里 bet 档的任何一项换成 row 档的值（γ 0.05→0.01、
    半衰期 60→250、window None→750、stride horizon→1），本测试对应那一条断言必红。
    """
    row = engine.calibration_settings(engine.CALIBRATION_ROW, 60)
    bet = engine.calibration_settings(engine.CALIBRATION_BET, 60)

    assert row == {
        "gamma": engine.ACI_GAMMA,
        "half_life": engine.ACI_HALF_LIFE,
        "window": engine.CALIBRATION_WINDOW,
        "stride": 1,
    }
    assert bet == {"gamma": 0.05, "half_life": 60, "window": None, "stride": 60}
    assert bet["stride"] == 60 and row["stride"] == 1


@pytest.mark.unit
def test_the_bet_window_preset_keeps_c1_learning_and_adds_the_calendar_equivalent_window():
    """C2 = C1 + 回看窗：学习速率逐值不动，只有 ``window`` 是新加的那一个自变量。

    变异验证：把 ``window`` 换成 ``None``（退化成 C1）、把 ``CALIBRATION_WINDOW // horizon``
    改回固定 750（丢掉日历折算）、或把下界 ``MIN_ERRORS_FOR_SIGMA`` 拿掉（250 日尺度会从
    3 个样本里取分位），对应断言都会红。
    """
    bet = engine.calibration_settings(engine.CALIBRATION_BET, 60)
    bet_window = engine.calibration_settings(engine.CALIBRATION_BET_WINDOW, 60)

    assert bet_window["gamma"] == bet["gamma"] == engine.ACI_GAMMA_BET
    assert bet_window["half_life"] == bet["half_life"] == engine.ACI_HALF_LIFE_BET
    assert bet_window["stride"] == bet["stride"] == 60
    assert bet["window"] is None, "C1 的定义就是「不设窗」，改它等于偷换候选"

    # 窗随尺度按日历等值折算，并被 min_samples 托底。四个分辨率下的取值先写在
    # spec 第三轮 §二.1 的表里，这里逐值钉住 —— 折算规则改了必须两处一起改。
    resolved = {
        horizon: engine.calibration_settings(engine.CALIBRATION_BET_WINDOW, horizon)["window"]
        for horizon in (1, 5, 20, 60, 250)
    }
    assert resolved == {1: 750, 5: 150, 20: 60, 60: 60, 250: 60}
    assert resolved[5] == engine.CALIBRATION_WINDOW // 5
    assert resolved[1] == engine.CALIBRATION_WINDOW

    for horizon in resolved:
        settings = engine.calibration_settings(engine.CALIBRATION_BET_WINDOW, horizon)
        assert settings["window"] >= engine.MIN_ERRORS_FOR_SIGMA
        assert settings["stride"] == max(1, horizon)


@pytest.mark.unit
def test_an_unknown_calibration_mode_is_refused():
    index = pd.date_range("2020-01-01", periods=80, freq="B")
    close = pd.Series(np.linspace(1500.0, 1600.0, len(index)), index=index)
    score = pd.Series(np.zeros(len(index)), index=index)

    with pytest.raises(ValueError):
        engine.build_prediction_frame(score, close, 5, calibration_mode="weekly")


@pytest.mark.unit
def test_the_control_candidate_dedupes_with_the_baseline_and_c1_does_not():
    """C0 是控制候选：口径与 B0 完全一致，研究台按参数指纹只算一次。"""
    by_key = quant_lab.CANDIDATES_BY_KEY

    assert by_key["C0"].run_key() == by_key["B0"].run_key()
    assert by_key["C1"].run_key() != by_key["B0"].run_key()
    assert by_key["C1"].calibration_mode == engine.CALIBRATION_BET
    assert by_key["C2"].calibration_mode == engine.CALIBRATION_BET_WINDOW
    assert by_key["C2"].run_key() != by_key["C1"].run_key()
    assert quant_lab.GROUP_LABELS["calibration"] in {
        quant_lab.GROUP_LABELS[candidate.group] for candidate in quant_lab.CANDIDATES
    }
