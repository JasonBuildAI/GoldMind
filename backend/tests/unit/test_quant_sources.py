"""量化因子数据源的解析与发布滞后。

全部用夹具文本 / 假客户端，不出网（`conftest.py` 也有出网兜底）。
重点不是「能跑」，而是**单位与日期口径**：这里错一天，回测就会出现前视。
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.services.quant.derive import derive_factors, seasonal_expectation
from app.services.quant.sources import cftc, news_geo, nyfed, sina_macro, treasury, yahoo
from app.services.quant.sources.base import SourceError


class FakeResponse:
    def __init__(self, text: str = "", payload=None, status_code: int = 200):
        self.text = text
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


class FakeGet:
    """按 URL 关键字路由的假客户端；记录每次调用，便于断言。"""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, url: str, params=None, timeout=None):
        self.calls.append((url, params or {}))
        for key, response in self.responses.items():
            if key in url:
                if isinstance(response, Exception):
                    raise response
                return response
        raise AssertionError(f"没有为 {url} 准备假响应")


NOMINAL_CSV = """Date,"1 Mo","2 Mo","3 Mo","1 Yr","2 Yr","5 Yr","10 Yr","30 Yr"
09/29/2026,4.04,4.18,4.25,4.58,4.89,5.06,5.26,5.59
09/28/2026,4.04,4.20,4.28,4.59,4.92,5.06,5.24,5.56
"""

REAL_CSV = """Date,"5 YR","7 YR","10 YR","20 YR","30 YR"
09/29/2026,2.72,2.80,2.91,3.15,3.29
09/28/2026,2.73,2.80,2.90,3.14,3.28
"""


@pytest.mark.unit
def test_treasury_parses_curves_and_shifts_by_one_business_day():
    fake = FakeGet({"daily_treasury_yield_curve": FakeResponse(text=NOMINAL_CSV),
                    "daily_treasury_real_yield_curve": FakeResponse(text=REAL_CSV)})

    series = treasury.fetch([2026], get=fake)

    # 09/29/2026 是周二 → 可用日 09/30（周三）
    assert series["ust_real_10y"].index[-1] == pd.Timestamp("2026-09-30")
    assert series["ust_real_10y"].iloc[-1] == pytest.approx(2.91)
    assert series["ust_nominal_2y"].iloc[-1] == pytest.approx(4.89)
    assert series["ust_nominal_10y"].iloc[-1] == pytest.approx(5.26)


@pytest.mark.unit
def test_treasury_missing_column_is_a_source_error():
    broken = """Date,"1 Mo","3 Mo"
09/29/2026,4.04,4.25
"""
    with pytest.raises(SourceError, match="10 Yr"):
        treasury.parse_curve_csv(broken, "10 Yr")


@pytest.mark.unit
def test_nyfed_effr_is_shifted_and_parsed():
    payload = {
        "refRates": [
            {"effectiveDate": "2026-09-29", "type": "EFFR", "percentRate": 3.88},
            {"effectiveDate": "2026-09-28", "type": "EFFR", "percentRate": 3.88},
            {"effectiveDate": "2026-09-29", "type": "SOFR", "percentRate": 3.90},
        ]
    }
    fake = FakeGet({"effr": FakeResponse(payload=payload)})

    series = nyfed.fetch(date(2016, 1, 1), date(2026, 9, 30), get=fake)["effr"]

    assert len(series) == 2
    assert series.iloc[-1] == pytest.approx(3.88)
    assert series.index[-1] == pd.Timestamp("2026-09-30")


@pytest.mark.unit
def test_cftc_net_position_and_report_lag():
    rows = [
        {
            "report_date_as_yyyy_mm_dd": "2026-09-22T00:00:00.000",
            "noncomm_positions_long_all": "246102",
            "noncomm_positions_short_all": "28355",
        }
    ]
    series = cftc.parse_rows(rows)

    # 周二报告 + 4 个工作日 = 下周一可用
    assert series.index[0] == pd.Timestamp("2026-09-28")
    assert series.iloc[0] == pytest.approx(246102 - 28355)


SINA_PAYLOAD = (
    "/*<script>location.href='//sina.com';</script>*/\n"
    'SINAREMOTECALLCALLBACK1601651495761(({config:{all:[[0,"统计时间"],[1,"黄金储备","万盎司"]]},'
    'count:"3",data:[["2026.8","7673.00","34383.25"],["2026.7","7608.00","34187.76"],'
    '["2026.6","7544.00","34162.62"]]}))'
)


@pytest.mark.unit
def test_sina_macro_parses_jsonp_and_uses_publication_day():
    total, rows = sina_macro.parse_payload(SINA_PAYLOAD)
    assert total == 3
    assert rows[0][1] == "7673.00"

    series = sina_macro.parse_reserves(rows)
    # 2026 年 8 月的储备，次月 8 日可用
    assert pd.Timestamp("2026-09-08") in series.index
    assert series[pd.Timestamp("2026-09-08")] == pytest.approx(7673.00)


@pytest.mark.unit
def test_sina_macro_rejects_unexpected_payload():
    with pytest.raises(SourceError):
        sina_macro.parse_payload("<html>接口改版了</html>")


def _yahoo_frame() -> pd.DataFrame:
    index = pd.to_datetime(["2026-09-28", "2026-09-29"])
    columns = pd.MultiIndex.from_tuples(
        [("Close", "GC=F"), ("Close", "^VIX"), ("Open", "GC=F")]
    )
    return pd.DataFrame(
        [[4000.0, 15.0, 3990.0], [4184.4, 16.2, 4010.0]], index=index, columns=columns
    )


@pytest.mark.unit
def test_yahoo_close_frame_parses_multiindex():
    series = yahoo.parse_close_frame(
        _yahoo_frame(), {"GC=F": "gold_close", "^VIX": "vix", "HYG": "hyg"}
    )
    assert set(series) == {"gold_close", "vix"}
    assert series["gold_close"].iloc[-1] == pytest.approx(4184.4)
    assert series["vix"].index[-1] == pd.Timestamp("2026-09-29")


@pytest.mark.unit
def test_yahoo_requires_gold_close():
    frame = _yahoo_frame()
    with pytest.raises(SourceError):
        yahoo.parse_close_frame(frame, {"^VIX": "vix"})


@pytest.mark.unit
def test_yahoo_shares_falls_back_to_net_assets():
    assert yahoo.parse_shares({"sharesOutstanding": 260300000}) == pytest.approx(260300000)
    assert yahoo.parse_shares({"netAssets": 1000.0, "navPrice": 100.0}) == pytest.approx(10.0)
    with pytest.raises(SourceError):
        yahoo.parse_shares({})


@pytest.mark.unit
def test_news_geo_intensity_is_a_seven_day_ratio():
    base = pd.Timestamp("2026-09-01")
    published = [
        (base + pd.Timedelta(days=0), "Gold rises on Fed cut bets"),
        (base + pd.Timedelta(days=0), "Market update"),
        (base + pd.Timedelta(days=1), "War risk lifts haven demand"),
        (base + pd.Timedelta(days=1), "Earnings recap"),
        (base + pd.Timedelta(days=1), "Oil steady"),
    ]
    series = news_geo.compute_series(published)

    # 第 2 天：7 日窗口内 1 条地缘 / 共 5 条 = 20%
    assert series[pd.Timestamp("2026-09-02")] == pytest.approx(20.0)


@pytest.mark.unit
def test_news_geo_needs_enough_news():
    published = [(pd.Timestamp("2026-09-01"), "War risk")]
    with pytest.raises(SourceError):
        news_geo.compute_series(published)


@pytest.mark.unit
def test_seasonal_expectation_uses_only_prior_years():
    # 每年 1 月的日收益：2022 = +1%，2023 = +2%，2024 = +3%，2025 = +4%，2026 = +5%
    index = []
    daily_returns = []
    for year, monthly_return in ((2022, 0.01), (2023, 0.02), (2024, 0.03), (2025, 0.04), (2026, 0.05)):
        for day in range(1, 11):
            index.append(pd.Timestamp(year=year, month=1, day=day))
            daily_returns.append(monthly_return)
    # 用「给定的日收益率」反推价格，保证 pct_change 精确等于上面设定的值
    prices = 100 * (1 + pd.Series(daily_returns, index=index)).cumprod()

    seasonal = seasonal_expectation(prices)

    # 2025 年 1 月：用 2022-2024 三年均值 (1+2+3)/3 = 2%
    assert seasonal[pd.Timestamp("2025-01-10")] == pytest.approx(2.0, abs=0.05)
    # 2026 年 1 月：用最近 6 年内可得的 2022-2025 四年均值 (1+2+3+4)/4 = 2.5%
    assert seasonal[pd.Timestamp("2026-01-10")] == pytest.approx(2.5, abs=0.05)
    # 2024 年 1 月只有 1 个往年样本（2023），不足 3 年 → 不给估计
    assert pd.Timestamp("2024-01-10") not in seasonal.index


@pytest.mark.unit
def test_derive_factors_units():
    index = pd.date_range("2026-01-01", periods=90, freq="B")
    gold = pd.Series([100 * (1.001 ** i) for i in range(len(index))], index=index)
    dxy = pd.Series([100.0 + i * 0.1 for i in range(len(index))], index=index)
    real = pd.Series([2.0 + i * 0.01 for i in range(len(index))], index=index)
    nominal10 = real + 2.3

    derived = derive_factors(
        {
            "gold_close": gold,
            "dxy": dxy,
            "ust_real_10y": real,
            "ust_nominal_10y": nominal10,
            "ust_nominal_2y": real + 0.5,
            "effr": real - 0.5,
        }
    )

    assert derived["inflation_expectation"].iloc[-1] == pytest.approx(2.3)
    assert derived["policy_expectation"].iloc[-1] == pytest.approx(1.0)
    # 60 日动量：价格是日度复利 0.1%，60 个交易日约 6.2%
    assert derived["momentum"].iloc[-1] == pytest.approx((1.001 ** 60 - 1) * 100, rel=1e-6)
    # 没有 hyg/ief 时不会凭空产出信用因子
    assert "credit_appetite" not in derived
