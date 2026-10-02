"""Yahoo Finance：多资产日线收盘与 GLD 份额快照。

yfinance 已是项目依赖（历史回填在用），这里只做两件事：批量取日线，
以及取 GLD 的份额快照。下载器与 info 读取都可注入 —— 测试用假实现。

份额（shares outstanding）是 ETF 的申赎结果，等价于资金进出；
它没有免费的历史序列，因此**从第一次采集开始积累**，此前的回测里该因子不可用。
"""
from __future__ import annotations

from datetime import date
from typing import Callable, Optional

import pandas as pd

from app.services.quant.sources.base import SourceError, clean_series
from app.utils import timeutil

# Yahoo 代码 → 序列名
SYMBOLS = {
    "GC=F": "gold_close",
    "DX-Y.NYB": "dxy",
    "^VIX": "vix",
    "HYG": "hyg",
    "IEF": "ief",
    "BTC-USD": "btc",
    "SPY": "spy",
    "CNY=X": "usdcny",
    # 下一轮预测的候选信息源：本轮只入库积累覆盖，不进因子集
    # （是否采用由下一轮预注册决定，见 docs/specs/2026-10-02-量化策略提升路线图.md）。
    "^GVZ": "gvz",
    "SI=F": "silver_close",
    "HG=F": "copper_close",
    # 基准对照序列（第四轮）：ETF 跟踪现货、不含展期，供研究台做基准敏感性对照
    "GLD": "gld_close",
}

ETF_SHARES_SYMBOL = "GLD"


def default_download(symbols: list[str], period: str) -> pd.DataFrame:
    import yfinance as yf

    return yf.download(
        symbols,
        period=period,
        interval="1d",
        progress=False,
        auto_adjust=False,
        group_by="column",
        threads=True,
    )


def default_info(symbol: str) -> dict:
    import yfinance as yf

    return yf.Ticker(symbol).info or {}


def parse_close_frame(frame: pd.DataFrame, symbols: dict[str, str]) -> dict[str, pd.Series]:
    """从 yfinance 的收盘价表里取出每个代码的 Close 序列。"""
    if frame is None or len(frame) == 0:
        raise SourceError("Yahoo 日线数据为空")

    series: dict[str, pd.Series] = {}
    is_multi = isinstance(frame.columns, pd.MultiIndex)

    for symbol, name in symbols.items():
        if is_multi:
            if ("Close", symbol) not in frame.columns:
                continue
            column = frame[("Close", symbol)]
        else:
            if "Close" not in frame.columns:
                continue
            column = frame["Close"]

        values = {}
        for timestamp, value in column.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if pd.isna(numeric):
                continue
            values[pd.Timestamp(timestamp).normalize()] = numeric

        cleaned = clean_series(values, name=name)
        if not cleaned.empty:
            series[name] = cleaned

    if "gold_close" not in series:
        raise SourceError("Yahoo 日线里没有黄金收盘价（GC=F）")
    return series


def parse_shares(info: dict) -> float:
    """从 quoteSummary 风格的信息里取 GLD 份额；缺失时用净资产/净值兜底。"""
    shares = info.get("sharesOutstanding")
    if shares:
        return float(shares)

    net_assets = info.get("netAssets") or info.get("totalAssets")
    nav = info.get("navPrice")
    if net_assets and nav:
        return float(net_assets) / float(nav)

    raise SourceError("Yahoo 未返回 GLD 份额（sharesOutstanding / netAssets）")


def fetch(
    *,
    period: str = "10y",
    with_etf_shares: bool = True,
    downloader: Optional[Callable] = None,
    info_getter: Optional[Callable] = None,
    symbols: Optional[dict[str, str]] = None,
) -> dict[str, pd.Series]:
    download = downloader or default_download
    get_info = info_getter or default_info
    symbol_map = symbols or SYMBOLS

    frame = download(list(symbol_map.keys()), period)
    series = parse_close_frame(frame, symbol_map)

    if with_etf_shares:
        try:
            shares = parse_shares(get_info(ETF_SHARES_SYMBOL) or {})
            # 份额是上一个美股交易日的快照，最早次日起可用；但「次日」不得
            # 晚于今天 —— 数据源给的最后一根 K 线常常就是今天，+1 个交易日
            # 会算出明天（2026-10-02 周五实测入库过 2026-10-05 的行），
            # 那是「预言」不是观测。存储层也会兜底拒绝，源层先不制造它。
            candidate = pd.Timestamp(series["gold_close"].index[-1]) + pd.tseries.offsets.BDay(1)
            usable_date = min(candidate.date(), timeutil.today())
            series["gld_shares"] = pd.Series(
                {pd.Timestamp(usable_date): shares}, dtype="float64", name="gld_shares"
            )
        except SourceError:
            # 份额取不到不影响其它序列（它是最年轻的一个因子）。
            pass

    return series
