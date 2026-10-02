#!/usr/bin/env python
"""信源可达性核验：把「哪个源现在能用」变成一条可复跑的命令（2.0.2 第 3、4 条）。

用法（在 backend 目录下）：

    python scripts/probe_sources.py            # 人类可读表格
    python scripts/probe_sources.py --json     # 机器可读（供文档 / CI 记录）
    python scripts/probe_sources.py --only rss # 只验某一类

本脚本只做一次带超时的抓取，不写库、不改配置、不调用 LLM。
结论按实测写：不可达就打印不可达与原因，**不编造**（红线一）。
外部源的可达性会随时间变化，所以结论必须能随时复跑复核，
文档里记录的是「某日实测」而不是永久承诺。
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import feedparser  # noqa: E402
import requests  # noqa: E402

DEFAULT_TIMEOUT = 12
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass(frozen=True)
class SourceProbe:
    """一个待核验的源。kind 决定用哪种抓法。"""

    name: str
    kind: str  # http / rss / sge / jin10
    url: str
    note: str = ""


@dataclass(frozen=True)
class ProbeResult:
    name: str
    kind: str
    ok: bool
    detail: str


SOURCES: tuple[SourceProbe, ...] = (
    SourceProbe("腾讯财经 hf_GC", "http", "https://qt.gtimg.cn/q=hf_GC", "实时金价首选源"),
    SourceProbe(
        "新浪财经 hf_GC", "http", "https://hq.sinajs.cn/list=hf_GC", "需要 Referer；GBK"
    ),
    SourceProbe(
        "新浪财经 DINIW", "http", "https://hq.sinajs.cn/list=DINIW", "美元指数实时值"
    ),
    SourceProbe(
        "上海黄金交易所 Au99.99",
        "sge",
        "https://www.sge.com.cn/graph/Dailyhq?instid=Au99.99",
        "人民币金价与上海金溢价的原始源",
    ),
    SourceProbe(
        "金十数据快讯",
        "jin10",
        "https://flash-api.jin10.com/get_flash_list?channel=-8200&vip=1",
        "需要 x-app-id 头；2026-10-03 实测 502（网页可访问、API 不可用）",
    ),
    SourceProbe(
        "Google News RSS（黄金）",
        "rss",
        "https://news.google.com/rss/search?q=gold+when%3A1d&hl=en-US&gl=US&ceid=US%3Aen",
        "消息板块的聚合入口之一",
    ),
    SourceProbe("WSJ Markets RSS", "rss", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    SourceProbe(
        "CNBC Markets RSS", "rss", "https://www.cnbc.com/id/100003114/device/rss/rss.html"
    ),
    SourceProbe("MINING.COM RSS", "rss", "https://www.mining.com/feed/", "2026-10-03 实测 403"),
    SourceProbe("Bloomberg Markets RSS", "rss", "https://feeds.bloomberg.com/markets/news.rss"),
    SourceProbe(
        "Investing.com RSS", "rss", "https://www.investing.com/rss/news_11.rss"
    ),
    SourceProbe("世界黄金协会（gold.org）", "http", "https://www.gold.org/goldhub"),
    SourceProbe(
        "Yahoo GC=F 日线",
        "http",
        "https://query1.finance.yahoo.com/v8/finance/chart/GC=F?range=5d&interval=1d",
    ),
    SourceProbe(
        "FX168 RSS（已失效）", "rss", "https://www.fx168.com/rss/gold.xml", "记录不可达"
    ),
    SourceProbe(
        "Kitco RSS（已失效）", "rss", "https://www.kitco.com/rss/KitcoNews.xml", "记录不可达"
    ),
)


def _http_probe(url: str, headers: dict[str, str], timeout: int) -> tuple[bool, str]:
    response = requests.get(url, headers=headers, timeout=timeout)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    return True, f"HTTP 200，{len(response.content)} 字节"


def _rss_probe(url: str, headers: dict[str, str], timeout: int) -> tuple[bool, str]:
    feed = feedparser.parse(url)
    entries = len(getattr(feed, "entries", []) or [])
    if entries:
        return True, f"条目 {entries} 条"
    status = getattr(feed, "status", None)
    if status and status != 200:
        return False, f"HTTP {status}，0 条目"
    return False, "可连接但 0 条目"


def _sge_probe(url: str, headers: dict[str, str], timeout: int) -> tuple[bool, str]:
    response = requests.get(url, headers=headers, timeout=timeout)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return False, "返回不是 JSON"
    # SGE 的形状是 {"time": [[日期, 开盘, 最高, 最低, 收盘], ...]}；
    # 老版本 / 其它端点可能用 data 包装，所以两个键都认。
    if isinstance(payload, list):
        rows = payload
    else:
        rows = payload.get("time") or payload.get("data") or []
    if not rows:
        return False, "JSON 里没有数据行"
    first = rows[0]
    if not isinstance(first, (list, tuple)) or len(first) < 2:
        return False, f"数据行形状不认识：{str(first)[:60]}"
    return True, f"数据行 {len(rows)} 条，{rows[0][0]} → {rows[-1][0]}"


def _jin10_probe(url: str, headers: dict[str, str], timeout: int) -> tuple[bool, str]:
    response = requests.get(url, headers=headers, timeout=timeout)
    if response.status_code != 200:
        return False, f"HTTP {response.status_code}"
    try:
        payload = response.json()
    except ValueError:
        return False, "返回不是 JSON"
    items = payload.get("data") if isinstance(payload, dict) else None
    if not items:
        return False, "JSON 里没有 data 条目"
    return True, f"快讯 {len(items)} 条"


_PROBES: dict[str, Callable[[str, dict[str, str], int], tuple[bool, str]]] = {
    "http": _http_probe,
    "rss": _rss_probe,
    "sge": _sge_probe,
    "jin10": _jin10_probe,
}


def probe(source: SourceProbe, *, timeout: int = DEFAULT_TIMEOUT) -> ProbeResult:
    """核验单个源；任何异常都折算成「不可达 + 原因」，不向上抛。"""
    headers = {"User-Agent": USER_AGENT}
    if "sinajs" in source.url:
        headers["Referer"] = "https://finance.sina.com.cn"
    if source.kind == "jin10":
        headers["x-app-id"] = "bVBF4FyRTn5NJF5n"
    try:
        ok, detail = _PROBES[source.kind](source.url, headers, timeout)
    except Exception as exc:  # 网络 / 解析 / 超时
        ok, detail = False, f"{type(exc).__name__}: {exc}"
    return ProbeResult(name=source.name, kind=source.kind, ok=ok, detail=detail)


def probe_all(
    sources: Iterable[SourceProbe] = SOURCES, *, timeout: int = DEFAULT_TIMEOUT
) -> list[ProbeResult]:
    return [probe(source, timeout=timeout) for source in sources]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="信源可达性核验（不写库、不改配置）")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument("--only", choices=sorted(_PROBES), help="只验某一类源")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    args = parser.parse_args(argv)

    sources = [s for s in SOURCES if args.only is None or s.kind == args.only]
    results = probe_all(sources, timeout=args.timeout)
    if args.json:
        print(json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2))
    else:
        for item in results:
            mark = "可达" if item.ok else "不可达"
            print(f"[{mark}] {item.name}（{item.kind}）：{item.detail}")
        reachable = sum(1 for item in results if item.ok)
        print(f"结论：{reachable}/{len(results)} 个源可达（其余按实测记为不可达）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
