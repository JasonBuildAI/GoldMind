"""因子同步：抓取 → 派生 → 落库 → 记录报告。

「及时性与可更新性」由三件事保证：

1. **各源按自己的节奏**：纽约联储 6 小时、财政部 12 小时、CFTC / 央行 24 小时、
   行情与新闻 2 小时。未到期的源直接跳过，不重复打上游。
2. **增量抓取**：已经有历史的源只取最近一段（默认往前 10 天），
   首次运行才做长周期回填。
3. **失败不静默**：每个源的错误、每个因子的缺失都会写进同步报告，
   报告进缓存并由 API 原样暴露 —— 界面据此显示「为什么不可用」。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Callable, Dict, Optional

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from app.services.cache_manager import CacheManager
from app.services.quant import storage
from app.services.quant.definitions import BENCHMARK_KEY, EXTRA_SERIES, FACTORS
from app.services.quant.derive import derive_factors
from app.services.quant.sources import (
    cftc,
    news_geo,
    nyfed,
    sina_macro,
    treasury,
    treasury_fiscal,
    yahoo,
)
from app.services.quant.sources.base import SourceError
from app.utils import timeutil

SOURCE_ORDER = ("treasury", "treasury_fiscal", "nyfed", "cftc", "sina_macro", "yahoo", "news_geo")

SOURCE_LABELS = {
    "treasury": "美国财政部收益率曲线",
    "treasury_fiscal": "美国财政部 Fiscal Data（TGA 每日余额）",
    "nyfed": "纽约联储参考利率",
    "cftc": "CFTC 持仓报告",
    "sina_macro": "新浪财经宏观数据（央行储备）",
    "yahoo": "Yahoo Finance 行情",
    "news_geo": "本系统新闻语料",
}

# 每个源最短抓取间隔：数据本身多久更新一次，就多久抓一次。
SOURCE_MIN_INTERVALS: Dict[str, timedelta] = {
    "treasury": timedelta(hours=12),
    "treasury_fiscal": timedelta(hours=12),
    "nyfed": timedelta(hours=6),
    "cftc": timedelta(hours=24),
    "sina_macro": timedelta(hours=24),
    "yahoo": timedelta(hours=2),
    "news_geo": timedelta(hours=2),
}

LAST_FETCH_CACHE_TTL = 30 * 24 * 3600  # 记录保留 30 天，足够判断「到期没有」
REPORT_CACHE_TTL = 7 * 24 * 3600
REPORT_CACHE_KEY = "quant_sync_report"

# 增量抓取时往前多取几天，覆盖数据源的历史回修与节假日
INCREMENTAL_LOOKBACK_DAYS = 10


def source_label(name: str) -> str:
    return SOURCE_LABELS.get(name, name)


def _last_fetch_store(name: str) -> CacheManager:
    return CacheManager(f"quant_last_fetch_{name}", ttl=LAST_FETCH_CACHE_TTL)


def is_due(name: str, *, now_timestamp: Optional[float] = None) -> bool:
    """该源是否到了可以再次抓取的时间。"""
    now_timestamp = now_timestamp if now_timestamp is not None else timeutil.now().timestamp()
    record = _last_fetch_store(name).get() or {}
    last = record.get("at")
    if not last:
        return True
    return (now_timestamp - float(last)) >= SOURCE_MIN_INTERVALS.get(name, timedelta(0)).total_seconds()


def _start_date(db: Session, key: str, today: date, history_years: int) -> date:
    """增量抓取的起点：有历史就从最近一条往前几天，否则回填 N 年。"""
    latest = storage.latest_date(db, key)
    if latest is None:
        return date(today.year - history_years, 1, 1)
    return latest - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)


def _fetch_source(
    name: str,
    db: Session,
    *,
    today: date,
    history_years: int,
    fetchers: Optional[dict] = None,
) -> Dict[str, pd.Series]:
    if fetchers and name in fetchers:
        return fetchers[name]()

    if name == "treasury":
        start = _start_date(db, "real_yield_10y", today, history_years)
        years = sorted({start.year, today.year})
        return treasury.fetch(years)
    if name == "treasury_fiscal":
        start = _start_date(db, "tga", today, history_years)
        return treasury_fiscal.fetch(start, today)
    if name == "nyfed":
        start = _start_date(db, "policy_expectation", today, history_years)
        series = nyfed.fetch(start=start, end=today)
        try:
            series.update(nyfed.fetch_reverserepo())
        except Exception as exc:  # RRP 失败不拖累 EFFR；仪表盘行会如实标不可用
            logger.warning(f"[量化] 纽约联储逆回购结果不可用：{type(exc).__name__}: {exc}")
        return series
    if name == "cftc":
        start = _start_date(db, "cftc_positioning", today, history_years)
        return cftc.fetch(start=start)
    if name == "sina_macro":
        return sina_macro.fetch()
    if name == "yahoo":
        has_history = storage.latest_date(db, BENCHMARK_KEY) is not None
        period = "3mo" if has_history else f"{history_years}y"
        return yahoo.fetch(period=period)
    if name == "news_geo":
        return news_geo.fetch(db)
    raise SourceError(f"未知数据源：{name}")


@dataclass
class SyncReport:
    started_at: str = field(default_factory=lambda: timeutil.now_naive().isoformat(timespec="seconds"))
    finished_at: Optional[str] = None
    source_status: dict = field(default_factory=dict)
    factor_status: dict = field(default_factory=dict)
    extra_status: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        ok_sources = [name for name, item in self.source_status.items() if item.get("status") == "ok"]
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "sources": self.source_status,
            "factors": self.factor_status,
            "extras": self.extra_status,
            "sources_ok": len(ok_sources),
            "sources_total": len(self.source_status),
        }


def run_sync(
    db: Session,
    *,
    force: bool = False,
    history_years: int = 10,
    today: Optional[date] = None,
    fetchers: Optional[dict] = None,
    use_cache_report: bool = True,
) -> SyncReport:
    """一轮完整同步。``fetchers`` 可注入假实现（测试用），键为源名。"""
    today = today or timeutil.today()
    report = SyncReport()
    raw: Dict[str, pd.Series] = {}

    for name in SOURCE_ORDER:
        if not force and not is_due(name):
            report.source_status[name] = {
                "status": "skipped",
                "label": source_label(name),
                "reason": "距上次抓取未超过该源的最小间隔",
            }
            continue

        try:
            series = _fetch_source(
                name, db, today=today, history_years=history_years, fetchers=fetchers
            )
            raw.update(series)
            report.source_status[name] = {
                "status": "ok",
                "label": source_label(name),
                "series": sorted(series),
            }
            _last_fetch_store(name).set({"at": timeutil.now().timestamp()})
        except Exception as exc:  # 网络、格式、空数据都算「该源不可用」
            logger.warning(f"[量化] 数据源 {name} 不可用：{type(exc).__name__}: {exc}")
            report.source_status[name] = {
                "status": "error",
                "label": source_label(name),
                "error": f"{type(exc).__name__}: {exc}",
            }

    derived = derive_factors(raw)

    for factor in FACTORS:
        series = derived.get(factor.key)
        if series is None or series.empty:
            report.factor_status[factor.key] = {
                "status": "unavailable",
                "name": factor.name,
                "reason": _missing_reason(factor.key, report),
            }
            continue
        inserted, updated = storage.upsert_series(
            db, factor.key, series, source=factor.source, commit=False
        )
        report.factor_status[factor.key] = {
            "status": "ok",
            "name": factor.name,
            "rows_inserted": inserted,
            "rows_updated": updated,
            "latest_date": series.index[-1].date().isoformat(),
        }

    benchmark = derived.get(BENCHMARK_KEY)
    if benchmark is not None and not benchmark.empty:
        storage.upsert_series(db, BENCHMARK_KEY, benchmark, source="Yahoo Finance（GC=F 收盘）", commit=False)

    for extra in EXTRA_SERIES:
        series = derived.get(extra.key)
        if series is None or series.empty:
            report.extra_status[extra.key] = {
                "status": "unavailable",
                "name": extra.name,
                "reason": _missing_reason(extra.key, report),
            }
            continue
        inserted, updated = storage.upsert_series(
            db, extra.key, series, source=extra.source, commit=False
        )
        report.extra_status[extra.key] = {
            "status": "ok",
            "name": extra.name,
            "rows_inserted": inserted,
            "rows_updated": updated,
            "latest_date": series.index[-1].date().isoformat(),
        }

    db.commit()

    report.finished_at = timeutil.now_naive().isoformat(timespec="seconds")
    if use_cache_report:
        CacheManager(REPORT_CACHE_KEY, ttl=REPORT_CACHE_TTL).set(report.to_dict())
    logger.info(
        f"[量化] 同步完成：{report.to_dict()['sources_ok']}/{len(report.source_status)} 个源可用，"
        f"{sum(1 for item in report.factor_status.values() if item['status'] == 'ok')}/{len(FACTORS)} 个因子入库"
    )
    return report


def _missing_reason(factor_key: str, report: SyncReport) -> str:
    """把「因子缺失」映射回「哪个源挂了」。"""
    failed = [
        f"{item.get('label', name)}（{item.get('error', '')}）"
        for name, item in report.source_status.items()
        if item.get("status") == "error"
    ]
    if failed:
        return "；".join(failed)
    return "该因子本期没有取到可用数据"


def load_report() -> Optional[dict]:
    return CacheManager(REPORT_CACHE_KEY, ttl=REPORT_CACHE_TTL).get()
