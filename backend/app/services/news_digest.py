"""消息板块：高权威黄金资讯的抓取、评分与分窗精选。

设计约定（规约见 `docs/specs/2026-10-02-消息板块.md`）：

- 消息与既有 `gold_news` **完全隔离**（独立表、独立抓取节奏），不进入任何 LLM
  prompt 窗口 —— 既有分析行为不受影响。
- 评分**完全确定性**：重要性 / 置信度由来源权威、黄金相关度、同题覆盖与时效算出，
  不调用 LLM。抓不到就如实为空：无链接或无发布时间的条目跳过并计入报告；
  空库返回 `has_data=False` 与原因，页面显示「不可用」。
- 同题聚类只做保守合并（Jaccard 阈值 + 至少共享两个词），宁可少合并，
  也不把「金价上涨」和「金价下跌」并成一条。
"""
from __future__ import annotations

import html as html_lib
import math
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Sequence, Tuple

import feedparser
import requests
from loguru import logger
from sqlalchemy.orm import Session

from app.config import settings
from app.models.news_digest import NewsDigestItem
from app.services.cache_manager import CacheManager
from app.services.news_service import normalize_url, to_local_naive
from app.utils import timeutil

# --------------------------------------------------------------------------- #
# 来源池
# --------------------------------------------------------------------------- #
# 格式 "名称|URL|tier|relevance"；tier ∈ {1,2}，relevance ∈ {gold,monetary}。
# 全部地址在 2026-10-02 实测可用（见 spec 第 2.1 节）：
#   - 直连：美联储 / 欧洲央行 / 彭博社 / MINING.COM / 英为财情
#   - Google News 限定域名：路透社 / 美联社 / 世界黄金协会 / 金融时报 /
#     华尔街日报 / CNBC / MarketWatch / Kitco（这些机构的官方 RSS 已下线，
#     用失效地址等于编造能力）
DEFAULT_DIGEST_SOURCES = (
    "美联储（货币政策）|https://www.federalreserve.gov/feeds/press_monetary.xml|1|monetary,"
    "欧洲央行（新闻稿）|https://www.ecb.europa.eu/rss/press.html|1|monetary,"
    "路透社|https://news.google.com/rss/search?q=gold+site%3Areuters.com+when%3A30d&hl=en-US&gl=US&ceid=US%3Aen|1|gold,"
    "美联社|https://news.google.com/rss/search?q=gold+site%3Aapnews.com+when%3A30d&hl=en-US&gl=US&ceid=US%3Aen|1|gold,"
    "世界黄金协会|https://news.google.com/rss/search?q=gold+site%3Agold.org+when%3A30d&hl=en-US&gl=US&ceid=US%3Aen|1|gold,"
    "彭博社|https://feeds.bloomberg.com/markets/news.rss|2|gold,"
    "金融时报|https://news.google.com/rss/search?q=gold+site%3Aft.com+when%3A30d&hl=en-US&gl=US&ceid=US%3Aen|2|gold,"
    "华尔街日报|https://news.google.com/rss/search?q=gold+site%3Awsj.com+when%3A30d&hl=en-US&gl=US&ceid=US%3Aen|2|gold,"
    "CNBC|https://news.google.com/rss/search?q=gold+site%3Acnbc.com+when%3A30d&hl=en-US&gl=US&ceid=US%3Aen|2|gold,"
    "MarketWatch|https://news.google.com/rss/search?q=gold+site%3Amarketwatch.com+when%3A30d&hl=en-US&gl=US&ceid=US%3Aen|2|gold,"
    "Kitco News|https://news.google.com/rss/search?q=gold+site%3Akitco.com+when%3A30d&hl=en-US&gl=US&ceid=US%3Aen|2|gold,"
    "MINING.COM|https://www.mining.com/feed/|2|gold,"
    "英为财情|https://www.investing.com/rss/news_11.rss|2|gold"
)

FETCH_TIMEOUT_SECONDS = 10
PER_SOURCE_LIMIT = 40
SUMMARY_MAX_CHARS = 1200
FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126 Safari/537.36"
    )
}

# 抓取报告（最近一次）写进缓存，GET 时读出展示。TTL 取 30 天：
# 「上次抓取是 3 天前」这类状态不该因为 TTL 变短而消失。
FETCH_STATUS_CACHE_KEY = "news_digest_fetch_status"
FETCH_STATUS_TTL = 30 * 24 * 3600

# 三个窗口：24 小时 / 7 天 / 30 天。窗口只是对同一份评分的过滤视图 ——
# 同一事件在不同窗口分数一致，重叠是预期行为而不是去重目标。
WINDOWS: Tuple[Tuple[str, str, int], ...] = (
    ("24h", "24 小时内", 24),
    ("7d", "7 天内", 24 * 7),
    ("30d", "30 天内", 24 * 30),
)
TOP_ITEMS_PER_WINDOW = 10
MAX_RELATED_ITEMS = 5

# 评分权重（与 spec 第 2.3 节逐项一致）：
#   重要性 = 0.40·权威 + 0.25·相关 + 0.20·覆盖 + 0.15·时效
#   置信度 = 0.45·权威 + 0.30·覆盖 + 0.25·相关
IMPORTANCE_WEIGHTS = {"authority": 0.40, "relevance": 0.25, "coverage": 0.20, "recency": 0.15}
CONFIDENCE_WEIGHTS = {"authority": 0.45, "coverage": 0.30, "relevance": 0.25}
TIER_AUTHORITY = {1: 1.0, 2: 0.65}
TIER_LABELS = {1: "一级信源", 2: "二级信源"}
RECENCY_SCALE_HOURS = 168.0

# --------------------------------------------------------------------------- #
# 关键词
# --------------------------------------------------------------------------- #
_GOLD_SPECIFIC = re.compile(r"(gold\s+prices?|gold\s+market|bullion|xau|precious\s+metals?)", re.I)
# "gold" 加否定环视排除非金融语境 —— 体育金 / 奖项 / 时尚（如 "wins her third swimming
# gold medal"、"Eala's gold dream ends in Nagoya"）。这类条目在美联社、路透社等综合源里
# 真实存在，不排除就会混进榜单；名单按真实抓取到的误判样本维护，加样例前先改测试。
_GOLD_WORD = re.compile(r"\bgold\b(?!\s+(?:medals?|awards?|records?|cups?|dreams?))", re.I)
# 习语「go for gold」= 争冠 / 夺魁，与贵金属无关（如 "Saint Laurent goes for gold in
# Paris show"）。它出现在 gold 之前，否定环视管不到，单列一条。
_GOLD_IDIOM = re.compile(r"\b(?:go|goes|going|went)\s+for\s+gold\b", re.I)
_MONETARY = re.compile(
    r"\b(fomc|federal\s+reserve|fed|ecb|monetary\s+policy|interest\s+rates?|"
    r"rate\s+(?:cut|hike|rise|hold)|inflation|cpi|pce|central\s+banks?|"
    r"treasury\s+yields?|money\s+supply)\b",
    re.I,
)

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "for", "as", "at", "by", "from", "in", "of",
        "on", "to", "with", "is", "are", "was", "were", "be", "been", "it", "its",
        "this", "that", "these", "those", "after", "before", "over", "under", "new",
        "says", "say", "will", "has", "have", "had", "not", "but", "amid", "ahead",
        "than", "up", "down", "out", "into", "its", "his", "her", "their", "our",
    }
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def matches_relevance(title: str, summary: str, mode: str) -> bool:
    """这条消息与黄金（或货币政策）相关吗？

    `gold` 模式：必须命中金融语境的黄金词；体育 / 时尚等隐喻不算
    （`gold medal`、`gold dream`、`go for gold`）。
    `monetary` 模式：官方央行源额外接受 FOMC / 利率 / 通胀 / 央行等货币词 ——
    货币政策类信息天然与金价相关，不能因为标题里没有 "gold" 就丢掉。
    """
    text = f"{title} {summary}"
    if _GOLD_SPECIFIC.search(text):
        return True
    if _GOLD_WORD.search(text) and not _GOLD_IDIOM.search(text):
        return True
    if mode == "monetary" and _MONETARY.search(text):
        return True
    return False


def relevance_score(title: str, summary: str) -> float:
    """黄金相关度 [0, 1]：标题命中按 2 倍于摘要计，归一化上限 4.5 分。"""
    score = 0.0
    if _GOLD_SPECIFIC.search(title):
        score += 3.0
    elif _GOLD_WORD.search(title):
        score += 1.5
    if _GOLD_SPECIFIC.search(summary):
        score += 1.0
    elif _GOLD_WORD.search(summary):
        score += 0.5
    # 货币词只是黄金语境的补充：标题里没有黄金词时，权重低于笼统的 "gold"。
    if _MONETARY.search(title):
        score += 1.0
    if _MONETARY.search(summary):
        score += 0.25
    return min(1.0, score / 4.5)


def normalize_source_key(source: str) -> str:
    """来源标识：小写、压缩空白。用于聚类时统计「多少家不同来源」同题报道。"""
    return _WS_RE.sub(" ", (source or "").strip()).lower()


def title_tokens(title: str) -> frozenset:
    """标题归一化为词集合：小写、去停用词、丢弃长度 < 3 的词。"""
    return frozenset(
        token
        for token in _TOKEN_RE.findall((title or "").lower())
        if len(token) >= 3 and token not in _STOPWORDS
    )


# --------------------------------------------------------------------------- #
# 抓取
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SourceSpec:
    name: str
    url: str
    tier: int
    relevance: str


@dataclass
class SourceFetchResult:
    spec: SourceSpec
    entries: int = 0
    kept: int = 0
    skipped_no_title: int = 0
    skipped_no_url: int = 0
    skipped_no_time: int = 0
    skipped_filtered: int = 0
    error: Optional[str] = None
    items: List[Dict[str, Any]] = field(default_factory=list)


def parse_digest_sources(raw: Optional[str]) -> List[SourceSpec]:
    """把 ``"名称|URL|tier|relevance,..."`` 解析成来源列表；坏项直接跳过。"""
    specs: List[SourceSpec] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        parts = [part.strip() for part in item.split("|")]
        if len(parts) != 4:
            continue
        name, url, tier_text, relevance = parts
        if not name or not url:
            continue
        if tier_text not in ("1", "2"):
            continue
        if relevance not in ("gold", "monetary"):
            continue
        specs.append(SourceSpec(name=name, url=url, tier=int(tier_text), relevance=relevance))
    return specs


def configured_sources() -> List[SourceSpec]:
    """已配置的来源；未配置时回落内置默认池。"""
    return parse_digest_sources(settings.NEWS_DIGEST_SOURCES) or parse_digest_sources(
        DEFAULT_DIGEST_SOURCES
    )


def _clean_title(title: str, *candidate_sources: str) -> str:
    """去掉 Google News 之类的来源后缀（"标题 - Reuters"），便于聚类与展示。"""
    cleaned = title
    for source in candidate_sources:
        if not source:
            continue
        suffix = f" - {source}"
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].strip()
    return cleaned


def _clean_summary(raw: str) -> str:
    """去 HTML 标签、反转义实体、压缩空白，并截断到存储上限。"""
    text = html_lib.unescape(_TAG_RE.sub(" ", raw or ""))
    return _WS_RE.sub(" ", text).strip()[:SUMMARY_MAX_CHARS]


def fetch_source(spec: SourceSpec, limit: int = PER_SOURCE_LIMIT) -> SourceFetchResult:
    """抓取单个来源。

    用 ``requests`` 取字节再交 feedparser：``feedparser.parse(url)`` 没有超时参数，
    上游挂起会拖死线程。单源失败由调用方兜底，不影响其他来源。
    """
    result = SourceFetchResult(spec=spec)
    try:
        response = requests.get(spec.url, timeout=FETCH_TIMEOUT_SECONDS, headers=FETCH_HEADERS)
        if response.status_code >= 400:
            raise RuntimeError(f"HTTP {response.status_code}")
        feed = feedparser.parse(response.content)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"[:200]
        return result

    entries = list(feed.entries[:limit])
    result.entries = len(entries)
    fetched_at = timeutil.now_naive()

    for entry in entries:
        entry_source = ""
        source_field = entry.get("source")
        if isinstance(source_field, dict):
            entry_source = str(source_field.get("title") or "").strip()

        title = _clean_title(
            str(entry.get("title") or "").strip(), entry_source, spec.name
        )
        if not title:
            result.skipped_no_title += 1
            continue

        url = normalize_url(str(entry.get("link") or ""))
        if not url:
            result.skipped_no_url += 1
            continue

        # RSS 的 published_parsed 是 UTC，统一换算成项目时区的本地时间再入库
        published_at = to_local_naive(entry.get("published_parsed") or entry.get("updated_parsed"))
        if published_at is None:
            # 没有发布时间就无法进入任何时间窗口 —— 不猜测、不用抓取时刻顶替
            result.skipped_no_time += 1
            continue

        summary = _clean_summary(str(entry.get("summary") or entry.get("description") or ""))
        if not matches_relevance(title, summary, spec.relevance):
            result.skipped_filtered += 1
            continue

        display_source = entry_source or spec.name
        result.items.append(
            {
                "title": title,
                "summary": summary,
                "url": url,
                "published_at": published_at,
                "fetched_at": fetched_at,
                "source": display_source,
                "source_key": normalize_source_key(display_source),
                "authority_tier": spec.tier,
            }
        )
        result.kept += 1

    return result


def _fetch_source_safe(spec: SourceSpec, limit: int) -> SourceFetchResult:
    try:
        return fetch_source(spec, limit)
    except Exception as exc:  # fetch_source 已兜底，这里挡住意料之外的异常
        result = SourceFetchResult(spec=spec)
        result.error = f"{type(exc).__name__}: {exc}"[:200]
        return result


def last_fetch_report() -> Optional[Dict[str, Any]]:
    """最近一次抓取报告（来自缓存）；从未抓取过时为 None。"""
    return CacheManager(FETCH_STATUS_CACHE_KEY, ttl=FETCH_STATUS_TTL).get()


class NewsDigestService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # 抓取
    # ------------------------------------------------------------------ #
    def fetch_all_sources(self, limit: int = PER_SOURCE_LIMIT) -> Dict[str, Any]:
        """并发抓取全部来源 → 去重落库 → 返回抓取报告（并写入缓存）。"""
        specs = configured_sources()
        results: List[SourceFetchResult] = []
        if specs:
            with ThreadPoolExecutor(max_workers=min(8, len(specs))) as pool:
                futures = [pool.submit(_fetch_source_safe, spec, limit) for spec in specs]
                results = [future.result() for future in futures]

        fetched = [item for result in results for item in result.items]
        inserted = self._save_items(fetched)

        sources_payload = [
            {
                "name": result.spec.name,
                "status": "error" if result.error else "ok",
                "entries": result.entries,
                "kept": result.kept,
                "new": sum(1 for item in result.items if item["url"] in inserted),
                "error": result.error,
            }
            for result in results
        ]
        report = {
            "fetched_at": timeutil.now_str(),
            "total_sources": len(results),
            "ok_sources": sum(1 for result in results if not result.error),
            "failed_sources": sum(1 for result in results if result.error),
            "entries": sum(result.entries for result in results),
            "kept": sum(result.kept for result in results),
            "new_items": len(inserted),
            "duplicates": sum(result.kept for result in results) - len(inserted),
            "skipped_no_title": sum(result.skipped_no_title for result in results),
            "skipped_no_url": sum(result.skipped_no_url for result in results),
            "skipped_no_time": sum(result.skipped_no_time for result in results),
            "skipped_filtered": sum(result.skipped_filtered for result in results),
            "sources": sources_payload,
        }
        CacheManager(FETCH_STATUS_CACHE_KEY, ttl=FETCH_STATUS_TTL).set(report)
        logger.info(
            f"[消息板块] 抓取完成：{report['ok_sources']}/{report['total_sources']} 源成功，"
            f"新增 {report['new_items']} 条"
        )
        return report

    def _save_items(self, items: Sequence[Dict[str, Any]]) -> set:
        """按规范化 URL 去重后落库；返回实际插入的 URL 集合。"""
        if not items:
            return set()

        urls = list({item["url"] for item in items})
        existing: set = set()
        for start in range(0, len(urls), 200):
            chunk = urls[start : start + 200]
            existing.update(
                row[0]
                for row in self.db.query(NewsDigestItem.url)
                .filter(NewsDigestItem.url.in_(chunk))
                .all()
            )

        inserted: set = set()
        for item in items:
            url = item["url"]
            if url in existing or url in inserted:
                continue
            self.db.add(NewsDigestItem(**item))
            inserted.add(url)

        if not inserted:
            return set()
        try:
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            logger.error(f"[消息板块] 落库失败：{exc}")
            return set()
        return inserted


# --------------------------------------------------------------------------- #
# 评分与聚类
# --------------------------------------------------------------------------- #
@dataclass
class DigestRecord:
    id: int
    title: str
    summary: str
    source: str
    source_key: str
    tier: int
    url: str
    published_at: datetime
    age_hours: float = 0.0
    relevance: float = 0.0
    importance: float = 0.0
    confidence: float = 0.0
    signals: List[str] = field(default_factory=list)


def _apply_scores(record: DigestRecord, coverage: int) -> None:
    authority = TIER_AUTHORITY.get(record.tier, 0.65)
    coverage_score = min(1.0, max(0.0, (coverage - 1) / 2.0))
    recency = math.exp(-record.age_hours / RECENCY_SCALE_HOURS)
    record.importance = round(
        100
        * (
            IMPORTANCE_WEIGHTS["authority"] * authority
            + IMPORTANCE_WEIGHTS["relevance"] * record.relevance
            + IMPORTANCE_WEIGHTS["coverage"] * coverage_score
            + IMPORTANCE_WEIGHTS["recency"] * recency
        ),
        1,
    )
    record.confidence = round(
        100
        * (
            CONFIDENCE_WEIGHTS["authority"] * authority
            + CONFIDENCE_WEIGHTS["coverage"] * coverage_score
            + CONFIDENCE_WEIGHTS["relevance"] * record.relevance
        ),
        1,
    )
    record.signals = _build_signals(record, coverage)


def _build_signals(record: DigestRecord, coverage: int) -> List[str]:
    """评分依据（展开区展示）：让人看懂「为什么它排在前面」。"""
    signals = [
        "一级信源：官方 / 通讯社 / 行业机构"
        if record.tier == 1
        else "二级信源：专业财经媒体"
    ]
    if coverage >= 2:
        signals.append(f"{coverage} 家来源同题报道")
    if _GOLD_SPECIFIC.search(record.title) or _GOLD_WORD.search(record.title):
        signals.append("标题含黄金关键词")
    elif _MONETARY.search(record.title):
        signals.append("标题含货币政策关键词")
    if record.age_hours <= 24:
        signals.append("24 小时内发布")
    return signals


def cluster_indices(
    token_sets: Sequence[frozenset],
    *,
    jaccard_threshold: float = 0.6,
    min_shared: int = 2,
) -> List[List[int]]:
    """并查集聚类：Jaccard ≥ 阈值且共享 ≥ min_shared 个词才算同题。

    只对「共享罕见词」的候选对做比较（高频词如 gold 直接跳过），
    避免 n² 全量配对；宁可少合并，也不把对立的两条并在一个簇里。
    """
    n = len(token_sets)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        root_a, root_b = find(a), find(b)
        if root_a != root_b:
            parent[max(root_a, root_b)] = min(root_a, root_b)

    inverted: Dict[str, List[int]] = {}
    for index, tokens in enumerate(token_sets):
        for token in tokens:
            inverted.setdefault(token, []).append(index)

    df_cap = max(20, n // 10)
    seen_pairs: set = set()
    for token, ids in inverted.items():
        if len(ids) > df_cap:
            continue
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                pair = (ids[i], ids[j])
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                shared = len(token_sets[pair[0]] & token_sets[pair[1]])
                if shared < min_shared:
                    continue
                union_size = len(token_sets[pair[0]] | token_sets[pair[1]])
                if union_size and shared / union_size >= jaccard_threshold:
                    union(pair[0], pair[1])

    groups: Dict[int, List[int]] = {}
    for index in range(n):
        groups.setdefault(find(index), []).append(index)
    return [groups[root] for root in sorted(groups)]


def _rank_key(record: DigestRecord) -> Tuple[float, float, float, int]:
    """排序键：重要性 → 置信度 → 发布时间 → id（全部降序，结果确定）。"""
    return (-record.importance, -record.confidence, -record.published_at.timestamp(), -record.id)


def _representative_key(record: DigestRecord) -> Tuple[float, float, float, int]:
    return (record.importance, record.confidence, record.published_at.timestamp(), record.id)


def _item_payload(
    record: DigestRecord,
    *,
    rank: int,
    coverage: int,
    related: Sequence[DigestRecord],
) -> Dict[str, Any]:
    return {
        "rank": rank,
        "id": record.id,
        "title": record.title,
        "summary": record.summary,
        "source": record.source,
        "tier": record.tier,
        "tier_label": TIER_LABELS.get(record.tier, "二级信源"),
        "url": record.url,
        "published_at": record.published_at,
        "age_hours": round(record.age_hours, 1),
        "importance": record.importance,
        "confidence": record.confidence,
        "signals": list(record.signals),
        "coverage_count": coverage,
        "related": [
            {
                "title": item.title,
                "source": item.source,
                "url": item.url,
                "published_at": item.published_at,
            }
            for item in related
        ],
    }


def _unavailable_reason(last_fetch: Optional[Dict[str, Any]]) -> str:
    if not last_fetch:
        return "尚未抓取过消息。点击「抓取最新消息」从高权威来源拉取。"
    ok_sources = int(last_fetch.get("ok_sources") or 0)
    total_sources = int(last_fetch.get("total_sources") or 0)
    stamp = last_fetch.get("fetched_at") or "时间未知"
    if ok_sources == 0:
        return f"上次抓取（{stamp}）全部 {total_sources} 个来源均失败，请稍后点击「抓取最新消息」重试。"
    return "上次抓取成功，但最近 30 天内没有符合「高权威 + 黄金相关」条件的消息。"


def build_digest_payload(db: Session, *, now: Optional[datetime] = None) -> Dict[str, Any]:
    """从数据库构建整份消息精选（GET 接口的响应体）。

    先对最近 30 天全集评分并聚类，再把三个窗口作为过滤视图输出 ——
    同一事件在不同窗口的分数完全一致，重叠是设计行为。
    """
    moment = now or timeutil.now_naive()
    horizon_hours = WINDOWS[-1][2]
    rows = (
        db.query(NewsDigestItem)
        .filter(NewsDigestItem.published_at >= moment - timedelta(hours=horizon_hours))
        .all()
    )
    records = [
        DigestRecord(
            id=row.id,
            title=(row.title or "").strip(),
            summary=(row.summary or "").strip(),
            source=(row.source or "").strip(),
            source_key=(row.source_key or "").strip() or normalize_source_key(row.source or ""),
            tier=int(row.authority_tier or 2),
            url=(row.url or "").strip(),
            published_at=row.published_at,
        )
        for row in rows
        if row.title and row.url and row.published_at
    ]
    for record in records:
        record.age_hours = max(0.0, (moment - record.published_at).total_seconds() / 3600.0)
        record.relevance = relevance_score(record.title, record.summary)

    representatives: List[Tuple[DigestRecord, int, List[DigestRecord]]] = []
    for member_ids in cluster_indices([title_tokens(record.title) for record in records]):
        members = [records[index] for index in member_ids]
        coverage = len({member.source_key or normalize_source_key(member.source) for member in members})
        for member in members:
            _apply_scores(member, coverage)
        representative = max(members, key=_representative_key)
        related = sorted(
            (member for member in members if member is not representative),
            key=lambda member: (member.tier, -member.published_at.timestamp()),
        )
        representatives.append((representative, coverage, related[:MAX_RELATED_ITEMS]))

    windows: List[Dict[str, Any]] = []
    for key, label, hours in WINDOWS:
        cutoff = moment - timedelta(hours=hours)
        visible = [
            (record, coverage, related)
            for record, coverage, related in representatives
            if record.published_at >= cutoff
        ]
        visible.sort(key=lambda triple: _rank_key(triple[0]))
        windows.append(
            {
                "key": key,
                "label": label,
                "hours": hours,
                "total_clusters": len(visible),
                "items": [
                    _item_payload(record, rank=index + 1, coverage=coverage, related=related)
                    for index, (record, coverage, related) in enumerate(
                        visible[:TOP_ITEMS_PER_WINDOW]
                    )
                ],
            }
        )

    has_data = any(window["items"] for window in windows)
    last_fetch = last_fetch_report()
    return {
        "generated_at": timeutil.now_str(),
        "has_data": has_data,
        "unavailable_reason": None if has_data else _unavailable_reason(last_fetch),
        "last_fetch": last_fetch,
        "windows": windows,
    }
