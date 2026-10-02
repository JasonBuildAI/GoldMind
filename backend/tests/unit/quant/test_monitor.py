"""监测仪表盘：逐行信号规则、数值口径与降级。"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from app.services.quant import monitor, storage


def _series(values, *, periods=None, end="2026-09-30") -> pd.Series:
    if periods is None:
        periods = len(values)
    return pd.Series(values, index=pd.date_range(end=end, periods=periods, freq="B"), dtype="float64")


@pytest.mark.parametrize(
    "key, bull_values, bear_values",
    [
        ("real_yield_10y", [2.0] * 6 + [1.7], [2.0] * 6 + [2.3]),
        ("inflation_expectation", [2.0] * 6 + [2.3], [2.0] * 6 + [1.7]),
        ("dollar_index", [100.0] * 6 + [98.0], [100.0] * 6 + [102.0]),
        ("policy_expectation", [1.0] * 6 + [0.7], [1.0] * 6 + [1.3]),
        ("central_bank", [7600.0, 7610.0], [7600.0, 7590.0]),
        ("etf_shares", [260_000_000.0, 261_000_000.0], [260_000_000.0, 259_000_000.0]),
        ("vix", [18.0] * 6 + [30.0], [18.0] * 6 + [12.0]),
        ("credit_appetite", [0.0] * 6 + [-3.0], [0.0] * 6 + [3.0]),
        ("tga", [900_000.0] * 21 + [840_000.0], [900_000.0] * 21 + [960_000.0]),
        ("rrp", [300.0] * 21 + [240.0], [300.0] * 21 + [380.0]),
    ],
)
def test_threshold_rules_flip_with_constructed_data(key, bull_values, bear_values):
    bull_signal, _ = monitor._rule(key, _series(bull_values))
    bear_signal, _ = monitor._rule(key, _series(bear_values))

    assert bull_signal == monitor.SIGNAL_BULL, f"{key} 的看涨方向判反了"
    assert bear_signal == monitor.SIGNAL_BEAR, f"{key} 的看跌方向判反了"


def test_cftc_crowding_is_contrarian():
    calm = [100.0, 101.0] * 30

    crowded_long, _ = monitor._rule("cftc_positioning", _series(calm + [140.0]))
    crowded_short, _ = monitor._rule("cftc_positioning", _series(calm + [60.0]))
    balanced, _ = monitor._rule("cftc_positioning", _series(calm + [100.5]))

    assert crowded_long == monitor.SIGNAL_BEAR, "多头拥挤应当看跌"
    assert crowded_short == monitor.SIGNAL_BULL, "空头拥挤应当看涨"
    assert balanced == monitor.SIGNAL_NEUTRAL


def test_info_rows_never_get_a_direction():
    for key in ("usdcny", "cny_gold", "cftc_oi"):
        signal, change = monitor._rule(key, _series([7.0] * 10))
        assert signal is None, f"{key} 是信息行，不应该有多空信号"
        assert change is not None


def test_monitor_reports_values_changes_and_dates(db_session):
    calendar = pd.date_range(end="2026-09-30", periods=200, freq="B")
    gold = pd.Series(np.linspace(2000.0, 2400.0, len(calendar)), index=calendar)
    storage.upsert_series(db_session, "gold_close", gold, source="测试夹具")
    yields = pd.Series([2.0] * 199 + [1.7], index=calendar)
    storage.upsert_series(db_session, "real_yield_10y", yields, source="测试夹具")

    result = monitor.build_monitor(db_session)

    rows = {row["key"]: row for row in result["rows"]}
    assert len(result["rows"]) >= 10
    assert rows["real_yield_10y"]["signal"] == "bull"
    assert rows["real_yield_10y"]["value"] == pytest.approx(1.7)
    assert rows["real_yield_10y"]["change"] == pytest.approx(-0.3)
    assert rows["real_yield_10y"]["obs_date"] == "2026-09-30"
    assert rows["ma200"]["status"] == "ok"
    expected_ma = gold.rolling(200, min_periods=120).mean().iloc[-1]
    assert rows["ma200"]["value"] == pytest.approx(expected_ma)
    assert rows["ma200"]["change"] == pytest.approx((gold.iloc[-1] / expected_ma - 1) * 100)
    assert result["as_of"] == date(2026, 9, 30)

    for row in result["rows"]:
        assert row["status"] in ("ok", "unavailable", "stale")
        if row["status"] == "unavailable":
            assert row["reason"], f"{row['key']} 不可用却没有原因"
            assert row["value"] is None
        else:
            assert row["value"] is not None
            assert row["obs_date"] is not None


def test_empty_database_marks_every_row_unavailable_with_reason(db_session):
    result = monitor.build_monitor(db_session)

    assert result["rows"]
    for row in result["rows"]:
        assert row["status"] == "unavailable"
        assert row["reason"]
        assert row["signal"] is None
        assert row["signal_label"] == "不可用"


def test_shanghai_premium_is_honestly_unavailable_without_its_two_series(db_session):
    """缺上海金或缺折算价时必须标不可用 —— 不许拿单边序列冒充溢价。"""
    result = monitor.build_monitor(db_session)

    row = next(item for item in result["rows"] if item["key"] == "shanghai_premium")
    assert row["status"] == "unavailable"
    assert "缺少" in row["reason"]


def test_shanghai_premium_is_computed_from_sge_and_the_converted_price(db_session):
    """SGE 收盘 − 折算价（元/克）：两条序列都在时才给值，且只作信息行。"""
    from app.services.quant import storage

    index = pd.date_range(end="2026-10-02", periods=30, freq="B")
    storage.upsert_series(
        db_session, "sge_gold", pd.Series(610.0, index=index), source="测试夹具", commit=False
    )
    storage.upsert_series(
        db_session, "cny_gold", pd.Series(600.0, index=index), source="测试夹具", commit=False
    )
    db_session.commit()

    row = next(
        item for item in monitor.build_monitor(db_session)["rows"]
        if item["key"] == "shanghai_premium"
    )
    assert row["status"] == "ok"
    assert row["value"] == 10.0
    assert row["obs_date"] == "2026-10-02"
    # 信息行：有水位、没有多空方向（溢价尚未通过预注册检验）。
    assert row["signal"] is None


def test_ma200_without_enough_history_is_unavailable(db_session):
    short = _series([2000.0] * 50, periods=50)
    storage.upsert_series(db_session, "gold_close", short, source="测试夹具")

    result = monitor.build_monitor(db_session)

    row = next(item for item in result["rows"] if item["key"] == "ma200")
    assert row["status"] == "unavailable"
    assert "历史样本不足" in row["reason"]


def test_the_cftc_ratio_row_is_shown_as_a_percentage(db_session):
    """`cftc_net_oi_ratio` 存的是**比值**（0.40），行定义的单位是 `%`。

    不换算就会把「净多头占未平仓 40%」印成「0.40 %」—— 差 100 倍，而这一行是给
    用户看的水位，错了不会被任何东西发现（它是信息行，没有阈值规则兜底）。

    变异验证：去掉 `RowSpec.display_scale` 的换算（或把它改成 1.0），本测试必红。
    """
    calendar = pd.date_range(end="2026-09-30", periods=30, freq="B")
    gold = pd.Series(np.linspace(2000.0, 2400.0, len(calendar)), index=calendar)
    storage.upsert_series(db_session, "gold_close", gold, source="测试夹具")
    ratio = pd.Series([0.38, 0.40], index=calendar[-2:])
    storage.upsert_series(db_session, "cftc_net_oi_ratio", ratio, source="测试夹具")

    rows = {row["key"]: row for row in monitor.build_monitor(db_session)["rows"]}

    row = rows["cftc_net_oi_ratio"]
    assert row["unit"] == "%"
    assert row["value"] == pytest.approx(40.0), f"比值没有换算成百分比：{row['value']}"
    # 变化量同样要按同一个比例换算（+2pp，而不是 +0.02）
    assert row["change"] == pytest.approx(2.0)


def test_stale_rows_keep_the_number_but_lose_the_signal(db_session):
    """仪表盘按声明的更新节奏判陈旧：数值与观测日照示，但不再给多空方向。

    变异验证：把 `_freshness` 的 `age > budget` 改成恒 False（等于不判陈旧），
    本测试第一条断言必红。陈旧分支在算信号之前就返回，所以「带着方向显示陈旧值」
    这条路在结构上不存在 —— 断言 `signal is None` 是把这个结构钉住，防止以后
    有人把返回顺序挪到 `_rule` 之后。
    """
    calendar = pd.date_range(end="2026-09-30", periods=200, freq="B")
    gold = pd.Series(np.linspace(2000.0, 2400.0, len(calendar)), index=calendar)
    storage.upsert_series(db_session, "gold_close", gold, source="测试夹具")

    # 周频序列（cftc_positioning，上限 14 天）最后一次观测停在 40 天前
    weekly = pd.Series(
        [100.0, 101.0] * 20, index=pd.date_range(end="2026-08-21", periods=40, freq="W-FRI")
    )
    storage.upsert_series(db_session, "cftc_positioning", weekly, source="测试夹具")
    # 日频序列照常更新 —— 用来证明判定不是「一律陈旧」
    vix = pd.Series([18.0] * 199 + [30.0], index=calendar)
    storage.upsert_series(db_session, "vix", vix, source="测试夹具")

    rows = {row["key"]: row for row in monitor.build_monitor(db_session)["rows"]}

    stale = rows["cftc_positioning"]
    assert stale["status"] == monitor.STATUS_STALE
    assert stale["signal"] is None and stale["signal_label"] == "陈旧"
    assert stale["value"] == pytest.approx(101.0)
    assert stale["obs_date"] == "2026-08-21"
    assert "40 天" in stale["reason"]
    # 参照系是金价日历（红线五），不是服务器时间
    assert rows["vix"]["status"] == "ok" and rows["vix"]["signal"] == "bull"


def test_every_info_key_is_a_real_row_and_stays_directionless():
    """信息行的名单必须与行定义同源，且**每一条**都不许多空。

    覆盖第二轮新接入的五条（GVZ / 金银比 / 铜金比 / CFTC 占比 / GPR）：它们在 26 年面板上
    都没过筛选闸门，仪表盘只报水位。变异验证：把其中任何一个键从 ``INFO_KEYS`` 里删掉，
    第一条断言就红（`_rule` 会对未知键直接抛）。
    """
    keys = {spec.key for spec in monitor.ROW_SPECS}

    assert monitor.INFO_KEYS <= keys, f"INFO_KEYS 里有没定义成行的键：{monitor.INFO_KEYS - keys}"
    for key in sorted(monitor.INFO_KEYS):
        signal, change = monitor._rule(key, _series([100.0] * 12))
        assert signal is None, f"{key} 是信息行，不该给出 {signal}"
        assert change is not None


def test_the_second_round_sources_are_on_the_dashboard():
    """第二轮花力气接进来的信息源，必须在这张表上看得见（哪怕暂时不可用）。

    它们此刻在项目库里是 0 行（实测），所以正确的表现是「不可用 + 原因」，
    而不是从仪表盘上消失 —— 消失了就等于没人再关心它有没有数。
    """
    new_keys = {"gvz", "gold_silver_ratio", "copper_gold_ratio", "cftc_net_oi_ratio", "gpr_daily"}
    by_key = {spec.key: spec for spec in monitor.ROW_SPECS}
    assert new_keys <= set(by_key), f"仪表盘缺这些第二轮信息源：{sorted(new_keys - set(by_key))}"

    close = _series(np.linspace(2000.0, 2600.0, 400))
    for key in sorted(new_keys):
        row = monitor._build_row(by_key[key], None, close)
        assert row.status == "unavailable", row.to_dict()
        assert row.signal is None and row.signal_label == "不可用"
        assert row.reason, f"{key} 的不可用行必须写清原因"
        assert by_key[key].note.startswith("信息行"), by_key[key].note
        assert "实测" in by_key[key].note or "测不到" in by_key[key].note, (
            f"{key} 的说明要写清「为什么不给方向」的实测依据：{by_key[key].note}"
        )


def test_monitor_rows_only_reference_series_the_data_layer_actually_defines():
    """行定义里的 key 必须在数据层有真源 —— 拼错一个键的故障是「永远不可用」，很隐蔽。

    变异验证：把某个 RowSpec 的 key 改成一个不存在的名字，本测试红。
    """
    from app.services.quant.definitions import EXTRA_SERIES, FACTORS

    # 由本模块自己算、不是入库序列的行：ma200 读基准价，cny_gold 是折算价，
    # shanghai_premium 由 sge_gold 与 cny_gold 两条序列现算。
    computed = {"ma200", "cny_gold", "shanghai_premium"}
    defined = {factor.key for factor in FACTORS} | {item.key for item in EXTRA_SERIES}

    orphans = {spec.key for spec in monitor.ROW_SPECS} - defined - computed
    assert not orphans, f"这些监控行的 key 在数据层没有定义：{sorted(orphans)}"


def test_an_info_row_with_thin_history_still_shows_its_water_level():
    """信息行的意义就在「只有几条观测」的阶段：值照给，只是没有方向。

    这钉的是 ``INFO_KEYS`` 的作用 —— 不在名单里的键历史不足时会被标成「样本不足」，
    于是刚接入、只有两三条观测的新序列在仪表盘上永远只有一个警告，看不到水位。
    变异验证：把 ``gvz`` 从 ``INFO_KEYS`` 里删掉，本测试红（signal_label 变成「样本不足」）。
    """
    close = _series(np.linspace(2000.0, 2600.0, 400))
    spec = next(item for item in monitor.ROW_SPECS if item.key == "gvz")

    row = monitor._build_row(spec, _series([24.0, 25.0, 24.5]), close)

    assert row.status == "ok", row.to_dict()
    assert row.signal is None and row.signal_label == "信息"
    assert row.value == pytest.approx(24.5)
