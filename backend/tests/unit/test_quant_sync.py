"""同步编排：派生、落库、幂等、单源失败降级、节流跳过。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services.quant import storage, sync as quant_sync


def _index(periods: int = 300) -> pd.DatetimeIndex:
    return pd.date_range(end="2026-09-30", periods=periods, freq="B")


def _raw_bundle(periods: int = 850) -> dict:
    index = _index(periods)
    steps = np.arange(periods, dtype="float64")
    return {
        "ust_real_10y": pd.Series(1.5 + steps * 0.001, index=index),
        "ust_nominal_10y": pd.Series(3.8 + steps * 0.001, index=index),
        "ust_nominal_2y": pd.Series(3.0 + steps * 0.001, index=index),
        "effr": pd.Series(2.5 + steps * 0.0005, index=index),
        "gold_close": pd.Series(2000 + steps * 5, index=index),
        "dxy": pd.Series(100 + steps * 0.05, index=index),
        "vix": pd.Series(15 + np.sin(steps / 10), index=index),
        "hyg": pd.Series(80 + steps * 0.02, index=index),
        "ief": pd.Series(95 + steps * 0.01, index=index),
        "btc": pd.Series(60000 + steps * 20, index=index),
        "spy": pd.Series(500 + steps * 0.5, index=index),
        "gld_shares": pd.Series(260_000_000.0, index=index[-1:]),
        "cftc_net": pd.Series(150_000 + steps[::5] * 100, index=index[::5]),
        "cb_gold_reserves": pd.Series(7600 + steps[::21] * 10, index=index[::21]),
        "news_geo_intensity": pd.Series(5 + np.cos(steps[-60:] / 7), index=index[-60:]),
        "usdcny": pd.Series(7.0 + steps * 0.0001, index=index),
        "tga": pd.Series(900_000 + steps * 100, index=index),
        "rrp": pd.Series(300 + np.sin(steps / 5), index=index),
        "cftc_oi": pd.Series(500_000 + steps[::5] * 2, index=index[::5]),
        "gvz": pd.Series(15 + np.sin(steps / 30), index=index),
        "silver_close": pd.Series(30 + steps * 0.01, index=index),
        "copper_close": pd.Series(4 + steps * 0.001, index=index),
        "gpr_daily": pd.Series(120 + np.cos(steps / 40), index=index),
    }


def _fetchers(*, failing: tuple[str, ...] = ()) -> dict:
    bundle = _raw_bundle()

    def make(name: str):
        def fetcher():
            if name in failing:
                raise RuntimeError(f"{name} 不可用（测试注入）")
            if name == "treasury":
                return {key: bundle[key] for key in ("ust_real_10y", "ust_nominal_10y", "ust_nominal_2y")}
            if name == "treasury_fiscal":
                return {"tga": bundle["tga"]}
            if name == "nyfed":
                return {"effr": bundle["effr"], "rrp": bundle["rrp"]}
            if name == "cftc":
                return {"cftc_net": bundle["cftc_net"], "cftc_oi": bundle["cftc_oi"]}
            if name == "gpr":
                return {"gpr_daily": bundle["gpr_daily"]}
            if name == "sina_macro":
                return {"cb_gold_reserves": bundle["cb_gold_reserves"]}
            if name == "yahoo":
                return {
                    key: bundle[key]
                    for key in (
                        "gold_close",
                        "dxy",
                        "vix",
                        "hyg",
                        "ief",
                        "btc",
                        "spy",
                        "gld_shares",
                        "usdcny",
                        "gvz",
                        "silver_close",
                        "copper_close",
                    )
                }
            if name == "news_geo":
                return {"news_geo_intensity": bundle["news_geo_intensity"]}
            raise AssertionError(name)

        return fetcher

    return {name: make(name) for name in quant_sync.SOURCE_ORDER}


@pytest.mark.unit
def test_sync_derives_and_stores_every_available_factor(db_session):
    report = quant_sync.run_sync(db_session, force=True, fetchers=_fetchers())

    assert report.source_status["yahoo"]["status"] == "ok"
    stored = storage.load_all(db_session)

    for key in (
        "real_yield_10y",
        "policy_expectation",
        "inflation_expectation",
        "dollar_index",
        "vix",
        "credit_appetite",
        "geopolitical",
        "central_bank",
        "cftc_positioning",
        "etf_shares",
        "momentum",
        "seasonality",
        "bitcoin",
        "risk_appetite",
        "gold_close",
        "usdcny",
        "cny_gold",
        "tga",
        "rrp",
        "cftc_oi",
        "gvz",
        "gold_silver_ratio",
        "copper_gold_ratio",
        "cftc_net_oi_ratio",
        "gpr_daily",
    ):
        assert key in stored and not stored[key].empty, f"{key} 没有落库"

    assert all(item["status"] == "ok" for item in report.extra_status.values())
    gold = stored["gold_close"]
    usdcny = stored["usdcny"]
    expected_cny = gold.iloc[-1] * usdcny.iloc[-1] / 31.1035
    assert stored["cny_gold"].iloc[-1] == pytest.approx(expected_cny, rel=1e-9)

    # 下一轮候选序列：比例口径必须与原始序列一致，且确实落库
    bundle = _raw_bundle()
    assert stored["gold_silver_ratio"].iloc[-1] == pytest.approx(
        bundle["gold_close"].iloc[-1] / bundle["silver_close"].iloc[-1], rel=1e-9
    )
    assert stored["copper_gold_ratio"].iloc[-1] == pytest.approx(
        bundle["copper_close"].iloc[-1] / bundle["gold_close"].iloc[-1], rel=1e-9
    )
    assert stored["cftc_net_oi_ratio"].iloc[-1] == pytest.approx(
        bundle["cftc_net"].iloc[-1] / bundle["cftc_oi"].iloc[-1], rel=1e-9
    )
    assert stored["gpr_daily"].iloc[-1] == pytest.approx(bundle["gpr_daily"].iloc[-1])

    # 派生口径抽查：通胀预期 = 名义 10Y − 实际 10Y
    inflation = stored["inflation_expectation"]
    real = stored["real_yield_10y"]
    assert inflation.iloc[-1] == pytest.approx(3.8 - 1.5 + 0.0, abs=0.05)
    assert real.index[-1] == inflation.index[-1]


@pytest.mark.unit
def test_source_failure_degrades_only_its_own_factors(db_session):
    # 纯降级场景：外部行情源挂了、本地行情表也没有数据 —— 这时才真没有
    # 基准价可用。（本地有数据时的兜底路径见下一个用例。）
    _clear_local_prices(db_session)
    report = quant_sync.run_sync(db_session, force=True, fetchers=_fetchers(failing=("yahoo",)))

    assert report.source_status["yahoo"]["status"] == "error"
    assert "测试注入" in report.source_status["yahoo"]["error"]
    assert report.factor_status["dollar_index"]["status"] == "unavailable"
    assert "Yahoo Finance 行情" in report.factor_status["dollar_index"]["reason"]

    # 其它源的因子照常入库
    stored = storage.load_all(db_session)
    assert "real_yield_10y" in stored
    assert "dollar_index" not in stored
    # 基准价格序列也来自 yahoo，缺了它就不该出现
    assert "gold_close" not in stored
    assert "usdcny" not in stored
    assert "cny_gold" not in stored


def _clear_local_prices(db) -> None:
    from app.models.gold_price import DollarIndex, GoldPrice

    db.query(GoldPrice).delete()
    db.query(DollarIndex).delete()
    db.commit()


@pytest.mark.unit
def test_yahoo_failure_falls_back_to_local_price_tables(db_session, seed_gold_prices):
    """Yahoo 被限流时（实测 YFRateLimitError），用主数据管道已同步的本地日线兜底。

    量化引擎不该因为第三方行情站限流就整片「缺少黄金价格序列」—— 基准价、
    动量、季节性与美元因子都能用本地行情照常算，来源如实标注为兜底。
    """
    seed_gold_prices(days=120, start=2600.0, step=5.0)

    report = quant_sync.run_sync(db_session, force=True, fetchers=_fetchers(failing=("yahoo",)))

    assert report.source_status["yahoo"]["status"] == "error"
    assert report.source_status["local_prices"]["status"] == "ok"
    assert "gold_close" in report.source_status["local_prices"]["note"]

    stored = storage.load_all(db_session)
    assert not stored["gold_close"].empty, "基准价必须可用"
    assert not stored["dollar_index"].empty, "美元因子必须可用"
    assert not stored["momentum"].empty, "基准价到位后动量应能算出来"

    from app.models.analysis import FactorObservation

    sources = {
        row[0]
        for row in db_session.query(FactorObservation.source)
        .filter(FactorObservation.factor_key.in_(["gold_close", "dollar_index"]))
        .distinct()
    }
    assert sources, "兜底数据必须落库"
    assert all("本地行情表" in source for source in sources), "来源必须如实标注为兜底"


@pytest.mark.unit
def test_skipped_yahoo_round_does_not_inject_local_fallback(db_session, seed_gold_prices):
    """源被节流跳过（未到期）时不许注入本地兜底：那不是「失败」，也不该写入。"""
    seed_gold_prices(days=120)
    quant_sync.run_sync(db_session, force=True, fetchers=_fetchers())

    second = quant_sync.run_sync(db_session, force=False, fetchers=_fetchers(failing=("yahoo",)))

    assert second.source_status["yahoo"]["status"] == "skipped"
    assert "local_prices" not in second.source_status


@pytest.mark.unit
def test_second_run_without_force_skips_sources(db_session):
    quant_sync.run_sync(db_session, force=True, fetchers=_fetchers())
    second = quant_sync.run_sync(db_session, force=False, fetchers=_fetchers())

    assert all(item["status"] == "skipped" for item in second.source_status.values())
    assert second.to_dict()["sources_ok"] == 0


@pytest.mark.unit
def test_rerun_is_idempotent_and_records_revisions(db_session):
    quant_sync.run_sync(db_session, force=True, fetchers=_fetchers())
    before = len(storage.load_series(db_session, "real_yield_10y"))

    second = quant_sync.run_sync(db_session, force=True, fetchers=_fetchers())
    after = len(storage.load_series(db_session, "real_yield_10y"))
    assert after == before, "重复同步不应产生重复行"
    assert second.factor_status["real_yield_10y"]["rows_inserted"] == 0

    # 数据源回修：同一个日期给出新值 → 更新而不是新增
    revised = _raw_bundle()
    revised["ust_real_10y"].iloc[-1] = 9.99
    def revised_fetcher():
        return {
            "ust_real_10y": revised["ust_real_10y"],
            "ust_nominal_10y": revised["ust_nominal_10y"],
            "ust_nominal_2y": revised["ust_nominal_2y"],
        }

    fetchers = _fetchers()
    fetchers["treasury"] = revised_fetcher
    third = quant_sync.run_sync(db_session, force=True, fetchers=fetchers)

    assert third.factor_status["real_yield_10y"]["rows_updated"] >= 1
    assert storage.load_series(db_session, "real_yield_10y").iloc[-1] == pytest.approx(9.99)


@pytest.mark.unit
def test_report_is_cached_for_the_api(db_session):
    quant_sync.run_sync(db_session, force=True, fetchers=_fetchers())
    cached = quant_sync.load_report()
    assert cached is not None
    assert "sources" in cached and "factors" in cached
