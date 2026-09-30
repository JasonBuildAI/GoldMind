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
    ):
        assert key in stored and not stored[key].empty, f"{key} 没有落库"

    assert all(item["status"] == "ok" for item in report.extra_status.values())
    gold = stored["gold_close"]
    usdcny = stored["usdcny"]
    expected_cny = gold.iloc[-1] * usdcny.iloc[-1] / 31.1035
    assert stored["cny_gold"].iloc[-1] == pytest.approx(expected_cny, rel=1e-9)

    # 派生口径抽查：通胀预期 = 名义 10Y − 实际 10Y
    inflation = stored["inflation_expectation"]
    real = stored["real_yield_10y"]
    assert inflation.iloc[-1] == pytest.approx(3.8 - 1.5 + 0.0, abs=0.05)
    assert real.index[-1] == inflation.index[-1]


@pytest.mark.unit
def test_source_failure_degrades_only_its_own_factors(db_session):
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
