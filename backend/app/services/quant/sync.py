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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.news_digest import NewsDigestItem
from app.services import source_status
from app.services.cache_manager import CacheManager
from app.services.quant import derive, storage
from app.services.quant.definitions import BENCHMARK_KEY, EXTRA_SERIES, FACTORS
from app.services.quant.derive import derive_factors
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
from app.utils import timeutil

SOURCE_ORDER = ("treasury", "treasury_fiscal", "nyfed", "cftc", "gpr", "sina_macro", "yahoo", "news_geo")

# 每个原始序列由哪个源抓 —— 与 `_fetch_source` 的分支、`yahoo.SYMBOLS` 一一对应。
# 用途只有一个：把「因子缺失」归因到真正喂它的源（见 `_missing_reason`）。
# 守卫：`tests/unit/test_quant_sync.py` 断言它与 `derive.required_raw_keys()` 完全对齐。
RAW_KEY_SOURCES: dict[str, str] = {
    "ust_real_10y": "treasury",
    "ust_nominal_2y": "treasury",
    "ust_nominal_10y": "treasury",
    "tga": "treasury_fiscal",
    "effr": "nyfed",
    "rrp": "nyfed",
    "cftc_net": "cftc",
    "cftc_oi": "cftc",
    "gpr_daily": "gpr",
    "cb_gold_reserves": "sina_macro",
    "gold_close": "yahoo",
    "dxy": "yahoo",
    "vix": "yahoo",
    "hyg": "yahoo",
    "ief": "yahoo",
    "btc": "yahoo",
    "spy": "yahoo",
    "usdcny": "yahoo",
    "gld_shares": "yahoo",
    "gvz": "yahoo",
    "silver_close": "yahoo",
    "copper_close": "yahoo",
    "news_geo_intensity": "news_geo",
    "gld_close": "yahoo",
    # 不是外部源：由本库消息板块（news_digest_items）计数而来
    "digest_gold_count": "news_digest",
}

# 本地源：不由 _fetch_source 抓取，而是在 run_sync 里从本库现成数据派生
# （目前只有消息板块计数 news_digest）。它们同样必须在 SOURCE_LABELS 里有标签，
# 否则「因子为什么缺失」会退回那句无用的兜底文本。
LOCAL_SOURCES = frozenset({"news_digest"})


SOURCE_LABELS = {
    "treasury": "美国财政部收益率曲线",
    "treasury_fiscal": "美国财政部 Fiscal Data（TGA 每日余额）",
    "nyfed": "纽约联储参考利率",
    "cftc": "CFTC 持仓报告",
    "gpr": "GPR 官方日度地缘风险指数（Iacoviello & Papaioannou .xls）",
    "sina_macro": "新浪财经宏观数据（央行储备）",
    "yahoo": "Yahoo Finance 行情",
    "news_geo": "本系统新闻语料",
    "news_digest": "消息板块（本库高权威消息计数）",
}

# 每个源最短抓取间隔：数据本身多久更新一次，就多久抓一次。
SOURCE_MIN_INTERVALS: Dict[str, timedelta] = {
    "treasury": timedelta(hours=12),
    "treasury_fiscal": timedelta(hours=12),
    "nyfed": timedelta(hours=6),
    "cftc": timedelta(hours=24),
    "gpr": timedelta(hours=24),
    "sina_macro": timedelta(hours=24),
    "yahoo": timedelta(hours=2),
    "news_geo": timedelta(hours=2),
}

LAST_FETCH_CACHE_TTL = 30 * 24 * 3600  # 记录保留 30 天，足够判断「到期没有」
REPORT_CACHE_TTL = 7 * 24 * 3600
REPORT_CACHE_KEY = "quant_sync_report"

# 增量抓取时往前多取几天，覆盖数据源的历史回修与节假日
INCREMENTAL_LOOKBACK_DAYS = 10

# Yahoo 源「历史已铺满」的判据覆盖这些序列：任一序列历史不足，就按请求窗口
# 重新拉长周期。新增序列（GVZ / 金银比 / 铜金比）上线时，老库因此能一次补齐
# 长历史，而不是永远只积累最近 3 个月。
YAHOO_COVERAGE_KEYS = (BENCHMARK_KEY, "gvz", "gold_silver_ratio", "copper_gold_ratio", "gld_close")

# 外部行情源（Yahoo）不可用时的本地兜底。主数据管道每个交易日把腾讯行情的
# 纽约金价与美元指数写进 gold_prices / dollar_index 表；Yahoo 被限流或宕机时
# （实测：连续回填后 Yahoo 会返回 YFRateLimitError: Too Many Requests），
# 量化引擎不该因此整片「缺少黄金价格序列」—— 基准价、动量、季节性与美元因子
# 都可以用本地日线照常算。只决定「数据从哪来」，不改因子集合/权重/变换。
_LOCAL_PRICE_FALLBACKS = (
    ("gold_close", BENCHMARK_KEY, "本地行情表（腾讯-纽约黄金；Yahoo 不可用时的兜底）"),
    ("dxy", "dollar_index", "本地行情表（腾讯-美元指数；Yahoo 不可用时的兜底）"),
)


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


# 历史起点晚于窗口起点多少天以内仍算「窗口已铺到」：源本身就只从窗口附近开始
# （例如逆回购 2013 年才有、TGA 日报 2005 年才有）时不每轮全量重抓。
HISTORY_START_GRACE_DAYS = 30


def _start_date(db: Session, key: str, today: date, history_years: int) -> date:
    """增量抓取的起点：历史明显短于请求窗口就从窗口起点回填，否则只往前几天。

    只看最近一条（原实现）会让「先上线、后加源」的历史缺口永远补不上：
    库里的最早观测停在 2026 年，窗口起点却是 2006 年，每轮只抓最近 10 天。
    """
    window_start = date(today.year - history_years, 1, 1)
    earliest = storage.earliest_date(db, key)
    latest = storage.latest_date(db, key)
    if earliest is None or latest is None:
        return window_start
    if (earliest - window_start).days > HISTORY_START_GRACE_DAYS:
        return window_start
    return latest - timedelta(days=INCREMENTAL_LOOKBACK_DAYS)


# 单轮同步最多补的缺口年数：一年 = 两张 CSV（名义 + 实际），再多容易超时；
# 剩下的缺口由下一轮（或 backfill 脚本）继续补。
MAX_GAP_YEARS_PER_SYNC = 3


def _years_to_fetch(
    db: Session,
    key: str,
    today: date,
    history_years: int,
    *,
    max_years: int = MAX_GAP_YEARS_PER_SYNC,
) -> list[int]:
    """要抓取的年份：优先补窗口内的缺口年（新的年份优先，单轮 ≤N 年）。

    原实现是 ``sorted({start.year, today.year})`` —— 只请求首尾两年。增量路径里
    start 就是「最近一条观测往回 10 天」，于是中间整段缺口永远补不上
    （2026-10-02 实测：``real_yield_10y`` 在 2018–2025 无观测）。
    """
    window = list(range(today.year - history_years, today.year + 1))
    gaps = storage.sparse_years(db, key, window=window)
    if gaps:
        return sorted(gaps, reverse=True)[:max_years]

    latest = storage.latest_date(db, key)
    if latest is None:
        return window[-max_years:]
    # 没有缺口：只刷新「最近一次观测所在年 + 今年」，覆盖跨年与历史回修。
    return sorted({latest.year, today.year})


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
        years = _years_to_fetch(db, "real_yield_10y", today, history_years)
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
    if name == "gpr":
        return gpr.fetch()
    if name == "sina_macro":
        return sina_macro.fetch()
    if name == "yahoo":
        # 所有日线序列（金价、GVZ、金银比、铜金比）的历史都不短于请求窗口的
        # 90% 才退化成 3 个月增量；否则按窗口回填 —— 回填与增量共用同一路径。
        required_span = int(history_years * 365 * 0.9)
        spans = []
        for key in YAHOO_COVERAGE_KEYS:
            earliest = storage.earliest_date(db, key)
            latest = storage.latest_date(db, key)
            if earliest is None or latest is None:
                spans.append(None)
            else:
                spans.append((latest - earliest).days)
        long_enough = all(span is not None and span >= required_span for span in spans)
        period = "3mo" if long_enough else f"{history_years}y"
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


def _local_price_series(db: Session, raw_key: str) -> pd.Series:
    """从本地行情表读一条「日期 → 收盘价」序列；空表返回空 Series。"""
    from sqlalchemy import select

    from app.models.gold_price import DollarIndex, GoldPrice

    model = GoldPrice if raw_key == "gold_close" else DollarIndex
    rows = db.execute(select(model.date, model.close_price).order_by(model.date)).all()
    rows = [(row[0], float(row[1])) for row in rows if row[1] is not None]
    if not rows:
        return pd.Series(dtype="float64")
    index = pd.DatetimeIndex([pd.Timestamp(day) for day, _ in rows])
    return pd.Series([value for _, value in rows], index=index, name=raw_key)


def _apply_local_price_fallbacks(
    db: Session, raw: Dict[str, pd.Series], report: SyncReport
) -> Dict[str, str]:
    """外部行情源不可用时，用本地已同步日线兜底；返回 {序列名: 实际来源标签}。

    报告里会多出一行 `local_prices`，且**不覆盖**外部源自己的 error 状态 ——
    「Yahoo 不可用」与「本轮用了本地基准」两件事同时可见，不遮掩。
    """
    # 只在本轮**真的尝试过且失败**时兜底。源被节流跳过（未到期）的轮次里
    # raw 本来就没有行情序列，那时注入本地数据会让「跳过」变成一次真实写入，
    # 报告也会被污染成「有源可用」。
    if report.source_status.get("yahoo", {}).get("status") != "error":
        return {}

    used: Dict[str, str] = {}
    for raw_key, series_key, label in _LOCAL_PRICE_FALLBACKS:
        current = raw.get(raw_key)
        if current is not None and not current.empty:
            continue
        local = _local_price_series(db, raw_key)
        if local.empty:
            continue
        raw[raw_key] = local
        used[series_key] = label

    if used:
        report.source_status["local_prices"] = {
            "status": "ok",
            "label": "本地行情表（外部行情源不可用时的兜底）",
            "note": "改用本地已同步日线：" + "、".join(sorted(used)),
        }
        logger.warning(
            "[量化] 外部行情源不可用，以下序列改用本地行情表兜底：" + "、".join(sorted(used))
        )
    return used


def _digest_count_series(db: Session) -> pd.Series:
    """消息板块每日入库条数（高权威，抓取时已按黄金/货币相关性过滤）。

    时间口径：\`published_at\` 在抓取时已换算进 \`SCHEDULER_TIMEZONE\`（红线五），
    这里只按日期聚合，不再做时区运算。
    """
    days = [
        moment.date()
        for (moment,) in db.execute(select(NewsDigestItem.published_at)).all()
        if moment is not None
    ]
    if not days:
        return pd.Series(dtype="float64")
    counts: Dict[object, int] = {}
    for day in days:
        counts[day] = counts.get(day, 0) + 1
    return pd.Series(counts, dtype="float64").sort_index()


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
            source_status.record_attempt(
                channel="quant_sync", source_key=name, status=source_status.STATUS_SKIPPED
            )
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
            source_status.record_attempt(
                channel="quant_sync",
                source_key=name,
                status=source_status.STATUS_OK,
                items=len(series),
            )
            _last_fetch_store(name).set({"at": timeutil.now().timestamp()})
        except Exception as exc:  # 网络、格式、空数据都算「该源不可用」
            logger.warning(f"[量化] 数据源 {name} 不可用：{type(exc).__name__}: {exc}")
            report.source_status[name] = {
                "status": "error",
                "label": source_label(name),
                "error": f"{type(exc).__name__}: {exc}",
            }
            source_status.record_attempt(
                channel="quant_sync",
                source_key=name,
                status=source_status.STATUS_ERROR,
                error=f"{type(exc).__name__}: {exc}",
            )

    fallback_sources = _apply_local_price_fallbacks(db, raw, report)

    # 高权威消息强度：数据来自消息板块本库（不是外部源），先转成原始序列再派生
    digest_counts = _digest_count_series(db)
    if not digest_counts.empty:
        raw["digest_gold_count"] = digest_counts

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
            db,
            factor.key,
            series,
            source=fallback_sources.get(factor.key, factor.source),
            commit=False,
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
        storage.upsert_series(
            db,
            BENCHMARK_KEY,
            benchmark,
            source=fallback_sources.get(BENCHMARK_KEY, "Yahoo Finance（GC=F 收盘）"),
            commit=False,
        )

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
    """把「因子缺失」归因到**真正喂它的源**，并把「报错」与「未到期」分开说。

    `derive.FACTOR_RAW_KEYS` 给出这个因子依赖哪些原始序列，`RAW_KEY_SOURCES` 再把
    原始序列映射回源；只有这些源里状态不是 ``ok`` 的才写进原因。

    旧实现罗列**所有**报错源、且完全不用 ``factor_key``：某因子因自身原因缺失、
    另一个源恰好报错时，原因就写成了那个源。而「本轮未到期（跳过）」的源根本不进
    原因，页面只能说「该因子本期没有取到可用数据」—— 用户无从判断该等下一轮还是
    该去查源。两件事的处置完全不同，必须分开写。
    """
    sources: list[str] = []
    for raw_key in derive.FACTOR_RAW_KEYS.get(factor_key, ()):
        name = RAW_KEY_SOURCES.get(raw_key)
        if name and name not in sources:
            sources.append(name)

    problems = []
    for name in sources:
        item = report.source_status.get(name) or {}
        status = item.get("status")
        label = item.get("label") or source_label(name)
        if status == "error":
            problems.append(f"{label} 报错（{item.get('error') or '原因未知'}）")
        elif status == "skipped":
            problems.append(
                f"{label} 本轮未到期（{item.get('reason') or '距上次抓取未超过该源的最小间隔'}）"
            )
    if problems:
        return "；".join(problems)
    return "该因子本期没有取到可用数据"


def load_report() -> Optional[dict]:
    return CacheManager(REPORT_CACHE_KEY, ttl=REPORT_CACHE_TTL).get()
