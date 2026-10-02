"""量化因子数据源的解析与发布滞后。

全部用夹具文本 / 假客户端，不出网（`conftest.py` 也有出网兜底）。
重点不是「能跑」，而是**单位与日期口径**：这里错一天，回测就会出现前视。
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from app.services.quant.derive import derive_factors, seasonal_expectation
from app.services.quant.sources import (
    cftc,
    gpr,
    news_geo,
    nyfed,
    sina_macro,
    treasury,
    treasury_fiscal,
    yahoo,
)
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


@pytest.mark.unit
def test_cftc_open_interest_uses_the_same_report_lag():
    rows = [
        {
            "report_date_as_yyyy_mm_dd": "2026-09-22T00:00:00.000",
            "noncomm_positions_long_all": "246102",
            "noncomm_positions_short_all": "28355",
            "open_interest_all": "571291",
        }
    ]
    fake = FakeGet({"jun7-fc8e": FakeResponse(payload=rows)})

    series = cftc.fetch(date(2026, 1, 1), get=fake)

    assert series["cftc_net"].iloc[0] == pytest.approx(246102 - 28355)
    assert series["cftc_oi"].index[0] == pd.Timestamp("2026-09-28")
    assert series["cftc_oi"].iloc[0] == pytest.approx(571291)


TGA_PAYLOAD = {
    "data": [
        {
            "record_date": "2026-09-25",
            "account_type": "Treasury General Account (TGA) Closing Balance",
            "open_today_bal": "945290",
            "close_today_bal": "null",
        },
        {
            "record_date": "2026-09-25",
            "account_type": "Total TGA Deposits (Table II)",
            "open_today_bal": "49518",
            "close_today_bal": "null",
        },
        {
            "record_date": "2026-09-24",
            "account_type": "Treasury General Account (TGA) Closing Balance",
            "open_today_bal": "924627",
            "close_today_bal": "null",
        },
    ],
    "meta": {"total-pages": 1},
}


@pytest.mark.unit
def test_treasury_fiscal_reads_the_closing_balance_and_shifts_a_day():
    fake = FakeGet({"operating_cash_balance": FakeResponse(payload=TGA_PAYLOAD)})

    series = treasury_fiscal.fetch(date(2026, 9, 1), date(2026, 9, 30), get=fake)

    tga = series["tga"]
    # 09/25 是周五 → 可用日 09/28（周一）
    assert tga.index[-1] == pd.Timestamp("2026-09-28")
    assert tga.iloc[-1] == pytest.approx(945290.0)
    assert len(tga) == 2  # Deposits 行不是余额，不参与


@pytest.mark.unit
def test_treasury_fiscal_requires_a_closing_row():
    payload = {"data": [{"record_date": "2026-09-25", "account_type": "Total TGA Deposits (Table II)"}]}
    with pytest.raises(SourceError, match="TGA"):
        treasury_fiscal.parse_operating_cash(payload)


RP_PAYLOAD = {
    "repo": {
        "operations": [
            {
                "operationDate": "2026-09-30",
                "operationType": "Reverse Repo",
                "totalAmtAccepted": 9_000_000_000,
            },
            {
                "operationDate": "2026-09-30",
                "operationType": "Reverse Repo",
                "totalAmtAccepted": 2_539_000_000,
            },
            {
                "operationDate": "2026-09-30",
                "operationType": "Repo",
                "totalAmtAccepted": 1_000_000_000,
            },
            {
                "operationDate": "2026-09-29",
                "operationType": "Reverse Repo",
                "totalAmtAccepted": 11_000_000_000,
            },
        ]
    }
}


@pytest.mark.unit
def test_nyfed_rrp_sums_the_day_and_shifts_to_next_business_day():
    fake = FakeGet({"reverserepo": FakeResponse(payload=RP_PAYLOAD)})

    series = nyfed.fetch_reverserepo(get=fake)["rrp"]

    # 09/29 是周二 → 09/30；09/30 是周三 → 10/01
    assert series.index[0] == pd.Timestamp("2026-09-30")
    assert series[series.index[0]] == pytest.approx(110.0)
    assert series.index[-1] == pd.Timestamp("2026-10-01")
    # 同一天两笔逆回购相加（9 + 2.539 = 11.539 bn = 115.39 亿美元）；Repo 不计入
    assert series.iloc[-1] == pytest.approx(115.39)


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
def test_yahoo_maps_cny_to_usdcny():
    assert yahoo.SYMBOLS["CNY=X"] == "usdcny"
    frame = pd.DataFrame(
        [[4000.0, 7.12], [4010.0, 7.10]],
        index=pd.to_datetime(["2026-09-28", "2026-09-29"]),
        columns=pd.MultiIndex.from_tuples([("Close", "GC=F"), ("Close", "CNY=X")]),
    )

    series = yahoo.parse_close_frame(frame, {"GC=F": "gold_close", "CNY=X": "usdcny"})

    assert series["usdcny"].iloc[-1] == pytest.approx(7.10)


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


@pytest.mark.unit
def test_derive_cny_gold_converts_with_troy_ounce():
    index = pd.date_range("2026-09-01", periods=5, freq="B")
    gold = pd.Series([4000.0] * 5, index=index)
    usdcny = pd.Series([7.10] * 5, index=index)

    derived = derive_factors({"gold_close": gold, "usdcny": usdcny})

    expected = 4000.0 * 7.10 / 31.1035
    assert derived["cny_gold"].iloc[-1] == pytest.approx(expected, rel=1e-9)
    assert derived["usdcny"].iloc[-1] == pytest.approx(7.10)


@pytest.mark.unit
def test_derive_passes_monitor_extras_through():
    index = pd.date_range("2026-09-01", periods=5, freq="B")
    raw = {
        "tga": pd.Series([900_000.0] * 5, index=index),
        "rrp": pd.Series([300.0] * 5, index=index),
        "cftc_oi": pd.Series([500_000.0] * 5, index=index),
    }

    derived = derive_factors(raw)

    assert derived["tga"].iloc[-1] == pytest.approx(900_000.0)
    assert derived["rrp"].iloc[-1] == pytest.approx(300.0)
    assert derived["cftc_oi"].iloc[-1] == pytest.approx(500_000.0)



@pytest.mark.unit
def test_yahoo_maps_new_candidate_symbols():
    assert yahoo.SYMBOLS["^GVZ"] == "gvz"
    assert yahoo.SYMBOLS["SI=F"] == "silver_close"
    assert yahoo.SYMBOLS["HG=F"] == "copper_close"


@pytest.mark.unit
def test_derive_new_candidate_series():
    index = pd.date_range("2026-09-01", periods=5, freq="B")
    raw = {
        "gold_close": pd.Series([4000.0] * 5, index=index),
        "silver_close": pd.Series([50.0] * 5, index=index),
        "copper_close": pd.Series([5.0] * 5, index=index),
        "cftc_net": pd.Series([200_000.0] * 5, index=index),
        "cftc_oi": pd.Series([500_000.0] * 5, index=index),
        "gvz": pd.Series([22.0] * 5, index=index),
        "gpr_daily": pd.Series([150.0] * 5, index=index),
    }

    derived = derive_factors(raw)

    assert derived["gold_silver_ratio"].iloc[-1] == pytest.approx(80.0)
    assert derived["copper_gold_ratio"].iloc[-1] == pytest.approx(5.0 / 4000.0)
    assert derived["cftc_net_oi_ratio"].iloc[-1] == pytest.approx(0.4)
    assert derived["gvz"].iloc[-1] == pytest.approx(22.0)
    assert derived["gpr_daily"].iloc[-1] == pytest.approx(150.0)

    # 缺原始序列时对应比例不产出 —— 不补零、不用默认值
    partial = derive_factors({"gold_close": raw["gold_close"]})
    assert "gold_silver_ratio" not in partial
    assert "copper_gold_ratio" not in partial
    assert "cftc_net_oi_ratio" not in partial


class _FakeSheet:
    """xlrd sheet 的最小替身：只实现本模块用到的三个属性 / 方法。"""

    def __init__(self, rows):
        self._rows = rows
        self.nrows = len(rows)
        self.ncols = len(rows[0]) if rows else 0

    def cell_value(self, row, column):
        return self._rows[row][column]


def _gpr_sheet(values):
    rows = [["DAY", "N10D", "GPRD"]]
    rows.extend(values)
    return _FakeSheet(rows)


@pytest.mark.unit
def test_gpr_parses_the_daily_index():
    rows = [
        {"DAY": "19850101", "GPRD": 230.039},
        {"DAY": 19850102.0, "GPRD": 115.677},
        {"DAY": "oops", "GPRD": 1.0},
        {"DAY": "19850103", "GPRD": "not-a-number"},
    ]

    series = gpr.parse_rows(rows)

    assert list(series.index) == [pd.Timestamp("1985-01-01"), pd.Timestamp("1985-01-02")]
    assert series.iloc[-1] == pytest.approx(115.677)


@pytest.mark.unit
def test_gpr_sheet_maps_headers_and_requires_a_plausible_size():
    values = [["19850101", 1.0, 100.0]] * gpr.MIN_DATA_ROWS
    values[-1] = ["20260930", 1.0, 150.571]

    series = gpr.parse_sheet(_gpr_sheet(values))

    assert series.index[-1] == pd.Timestamp("2026-09-30")
    assert series.iloc[-1] == pytest.approx(150.571)

    with pytest.raises(SourceError):
        gpr.parse_sheet(_gpr_sheet([["19850101", 1.0, 100.0]]))
    with pytest.raises(SourceError):
        gpr.parse_rows([])


@pytest.mark.unit
def test_gpr_fetch_returns_parsed_series_and_reports_http_errors(monkeypatch):
    class _Response:
        def __init__(self, status_code, content=b""):
            self.status_code = status_code
            self.content = content

    parsed = pd.Series([150.571], index=[pd.Timestamp("2026-09-30")], name="gpr_daily")
    monkeypatch.setattr(gpr, "parse_workbook", lambda content: parsed)

    ok = gpr.fetch(get=lambda url, **kwargs: _Response(200, b"fake"))

    # 值原样保留，日期右移一个工作日（见下一条用例）
    assert list(ok["gpr_daily"]) == [150.571]
    assert ok["gpr_daily"].index[0] == pd.Timestamp("2026-10-01")
    with pytest.raises(SourceError):
        gpr.fetch(get=lambda url, **kwargs: _Response(503))


@pytest.mark.unit
def test_gpr_fetch_shifts_the_index_to_the_next_trading_day(monkeypatch):
    """GPRD(D) 不可能在 D 日黄金收盘前拿到，必须右移一个工作日。

    官方 `.xls` 是周期性刷新的工作簿（不是逐日发布的接口），所以 D 日的指数值
    在 D 日盘中根本不在手上。其它后发布源（财政部收益率曲线 15:30 ET、EFFR 次日
    9:00 ET、TGA 次日 16:00 ET）一律走 `shift_to_next_trading_day`，GPR 此前漏了 ——
    第二轮引用它的那几行实测 t 值因此带前视偏差。

    变异验证：去掉 `shift_to_next_trading_day` 本测试必红。
    """
    class _Response:
        status_code = 200
        content = b"fake"

    parsed = pd.Series(
        [120.0, 130.0],
        index=[pd.Timestamp("2026-01-05"), pd.Timestamp("2026-01-06")],
        name="gpr_daily",
    )
    monkeypatch.setattr(gpr, "parse_workbook", lambda content: parsed)

    series = gpr.fetch(get=lambda url, **kwargs: _Response())["gpr_daily"]

    assert list(series.index) == [pd.Timestamp("2026-01-06"), pd.Timestamp("2026-01-07")]
    assert list(series) == [120.0, 130.0]

