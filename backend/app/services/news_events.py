"""确定性事件标注 + 聚合入口识别（2.0.2 第 4、5 条）。

为什么是确定性规则而不是 LLM：事件标签会拼进 prompt、显示在页面上，
它必须可复现、可测试、可解释 —— 同一个标题任何时候都该得到同一组标签。
规则只认「明确的写法」，宁可漏标也不猜（红线一：不编）。

事件条件分布（「FOMC 后 5 日金价分布」那一类）**未落地**：它需要一份
免费、可核实的官方日历，本轮核验过的公开源都不可达，所以不写进页面。

聚合入口识别：Google News 这类聚合器的链接指向聚合页而不是原始媒体，
读的人会把「聚合条目」误当成「媒体直发」。识别出来的条目标 `via_aggregator`，
提示词与界面都照实说明。
"""
from __future__ import annotations

import re
from typing import Iterable, Optional
from urllib.parse import urlsplit

EVENT_FOMC = "fomc"
EVENT_CPI = "cpi"
EVENT_NFP = "nfp"
EVENT_CENTRAL_BANK = "central_bank_decision"
EVENT_CENTRAL_BANK_GOLD = "central_bank_gold"

# 展示顺序固定：界面与 prompt 都按这个顺序排，避免同一条新闻两处顺序不同。
EVENT_ORDER: tuple[str, ...] = (
    EVENT_FOMC,
    EVENT_CPI,
    EVENT_NFP,
    EVENT_CENTRAL_BANK,
    EVENT_CENTRAL_BANK_GOLD,
)

EVENT_LABELS = {
    EVENT_FOMC: "FOMC",
    EVENT_CPI: "美国CPI",
    EVENT_NFP: "非农就业",
    EVENT_CENTRAL_BANK: "央行决议",
    EVENT_CENTRAL_BANK_GOLD: "央行购金",
}


def _compile(*patterns: str) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)


# 每条规则是「关键词 A 且 关键词 B」的组合式匹配（single 表示只用一条正则）。
# 组合式是为了压误报：见到「gold reserve」本身不等于央行在购金。
_RULES: tuple[tuple[str, tuple[re.Pattern[str], ...], tuple[re.Pattern[str], ...]], ...] = (
    (
        EVENT_FOMC,
        # FOMC 这个词本身只在联储议息语境里出现，不需要再配动作词。
        _compile(r"\bfomc\b", r"联邦公开市场委员会"),
        (),
    ),
    (
        EVENT_CPI,
        _compile(r"\bcpi\b", r"consumer price index", r"消费者物价", r"通胀数据"),
        (),
    ),
    (
        EVENT_NFP,
        _compile(r"\bnfp\b", r"non-?farm payrolls?", r"非农"),
        (),
    ),
    (
        EVENT_CENTRAL_BANK,
        _compile(
            r"\becb\b",
            r"\bboj\b",
            r"\bpboc\b",
            r"人民银行",
            r"央行",
            r"\bcentral bank\b",
            r"\bfed\b",
            r"美联储",
        ),
        _compile(
            r"决议",
            r"议息",
            r"利率决定",
            r"维持利率",
            r"\brate (decision|hike|cut|hold)\b",
            r"\bpolicy (rate|decision)\b",
            r"\bholds? rates?\b",
        ),
    ),
    (
        EVENT_CENTRAL_BANK_GOLD,
        _compile(r"央行", r"\bcentral bank\b", r"人民银行", r"官方储备", r"official reserves"),
        _compile(
            r"购金",
            r"增持",
            r"黄金储备",
            r"增加黄金",
            r"\bgold (reserves?|buying|purchases?|holdings?)\b",
        ),
    ),
)

# 聚合入口的域名：命中即标 via_aggregator，提示「这是聚合页，不是媒体直发」。
AGGREGATOR_HOSTS: tuple[str, ...] = ("news.google.com",)


def _text(title: Optional[str], summary: Optional[str]) -> str:
    return " ".join(part for part in (title or "", summary or "") if part)


def tag_events(title: Optional[str], summary: Optional[str] = None) -> list[str]:
    """给一条新闻打事件标签（确定性，返回固定顺序的 id 列表）。

    组合规则：先命中「主体关键词」，再在全文里命中「动作关键词」——
    两者同时出现才算，避免一条讲「金价」的新闻因为正文提到 reserve 被误标。
    """
    text = _text(title, summary)
    if not text.strip():
        return []
    tags: list[str] = []
    for event, subjects, actions in _RULES:
        if not any(pattern.search(text) for pattern in subjects):
            continue
        if actions and not any(pattern.search(text) for pattern in actions):
            continue
        tags.append(event)
    return sorted(tags, key=EVENT_ORDER.index)


def event_labels(tags: Iterable[str]) -> list[str]:
    """把事件 id 翻成中文标签；认不出的 id 原样返回（不猜）。"""
    return [EVENT_LABELS.get(tag, tag) for tag in tags]


def describe_events(tags: Iterable[str]) -> str:
    """一行事件说明（给 prompt 用）；没有标签时返回空串。"""
    labels = event_labels(tags)
    return "、".join(labels)


def is_aggregator_url(url: Optional[str]) -> bool:
    """URL 是否来自聚合入口（如 Google News RSS）。"""
    if not url:
        return False
    try:
        host = (urlsplit(str(url)).hostname or "").lower()
    except ValueError:
        return False
    return any(host == candidate or host.endswith("." + candidate) for candidate in AGGREGATOR_HOSTS)
