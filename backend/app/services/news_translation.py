"""消息板块的中文翻译：把英文标题与摘要变成中文标题 + 中文导语。

消息板块的 13 个来源全是英文 RSS（央行 / 通讯社 / 行业机构 / 专业财经）。
读者要的是「这条讲了什么」，而不是自己翻译一遍。本模块负责这件事，
并且**只做这一件事**：评分、聚类与排序仍然完全由英文原文的确定性口径决定
（`services/news_digest.py`），中文不参与打分，也不进入任何分析 prompt。

## 三条不能妥协的约定

1. **不许添加原文没有的事实**（`AGENTS.md` 红线 1 在这条链路上的落地）。
   `brief_zh` 只能压缩来源摘要里已有的信息；数字、机构名、目标价、日期、
   背景与因果解释，原文没写就不写。prompt 里逐条声明，代码侧再做一次校验：
   译不出来就留空，绝不编一段中文顶上。
2. **中文是叠加，不是替换**。`title` / `summary` 永远保留英文原样，
   页面同时给出两者，读者可以逐条核对。
3. **降级要说清原因**。LLM 未配置 / 预算用尽 / 调用失败 / 结果解析不了 ——
   各给一句具体原因，页面对应显示「中文翻译暂不可用（原因）」。

## 费用

一次 `translate_pending()` 只发**一次** chat 调用（一批最多
`NEWS_TRANSLATE_BATCH` 条），并且只取**尚未翻译**的条目（按发布时间倒序，
最新优先 = 页面上看得见的优先）。已经翻好的条目永不重复调用。
调用统一经 `services/llm_provider.py`（红线 3），每日预算在那里扣。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence

from loguru import logger
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.models.news_digest import NewsDigestItem
from app.services import llm_gate, llm_provider
from app.services.cache_manager import CacheManager
from app.services.web_search_service import extract_json_object
from app.utils import timeutil

# 提示词里每条摘要的截断长度：够模型判断「这条讲了什么」，又不至于让
# 30 条挤爆单次输出额度。
PROMPT_SUMMARY_CHARS = 600
# 译文入库前的上限（模型偶尔会写长；超出就截断，不因为长度整条丢掉）。
TITLE_ZH_MAX_CHARS = 120
BRIEF_ZH_MAX_CHARS = 200

# 最近一次翻译报告写进缓存，GET 时读出展示（与抓取报告同一套做法）。
# TTL 取 30 天：「上次翻译为什么失败」这类状态不该因为 TTL 变短而消失。
STATUS_CACHE_KEY = "news_digest_translation_status"
STATUS_TTL = 30 * 24 * 3600

# 提示词里的硬约束集中在这里 —— 它有守卫（tests/unit/test_prompt_discipline.py
# 与 tests/unit/test_news_translation.py 都盯着这几句）。
TRANSLATION_PROMPT = """你是财经新闻的中文编辑。下面每一条都是一则英文财经消息的**全部可用信息**：
标题，以及来源 RSS 提供的摘要。请为每一条产出中文标题与中文导语。

硬约束（违反即作废）：
1. 只使用给出的原文信息。原文没有提到的数字、机构名、目标价、日期、背景与因果解释，
   一律不许出现在译文里；不确定的信息省略，不要猜、不要补充常识。
2. title_zh 是标题的直译：保持原意与语气，不加评论、不扩写、不加副标题。
3. brief_zh 用 2-3 句中文说清这条消息讲了什么，只能压缩已有事实；
   摘要为空时 brief_zh 给空字符串（不要用标题编一段导语）。
4. 机构名 / 公司名 / 人名 / 品种名按中文财经媒体通用译法；没有通用译法时保留英文原名。
5. 不要输出链接、评分、建议或任何解释文字。

只输出一个 JSON 对象，前后都不要有别的内容：
{"items":[{"id":1,"title_zh":"中文标题","brief_zh":"中文导语"}]}
id 必须原样返回，条目数与输入一致。

待翻译条目：
"""


@dataclass
class TranslationReport:
    """一次翻译的结果。`reason` 是给页面看的一句话，成功且无待翻时为 None。"""

    requested: int = 0
    translated: int = 0
    failed: int = 0
    reason: Optional[str] = None
    model: Optional[str] = None
    at: Optional[str] = None
    failed_ids: List[int] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requested": self.requested,
            "translated": self.translated,
            "failed": self.failed,
            "reason": self.reason,
            "model": self.model,
            "at": self.at,
            "failed_ids": list(self.failed_ids),
        }


# --------------------------------------------------------------------------- #
# 纯函数：拼 prompt 与校验模型输出（不碰数据库、不碰网络，可以直接单测）
# --------------------------------------------------------------------------- #
def build_translation_prompt(items: Sequence[Dict[str, Any]]) -> str:
    """把待翻译条目拼成一次调用的 prompt。

    `items` 每项需要 `id` / `source` / `tier_label` / `title` / `summary`。
    """
    blocks: List[str] = []
    for item in items:
        summary = (item.get("summary") or "").strip()
        blocks.append(
            "\n".join(
                [
                    f"[{item['id']}] 来源：{item.get('source') or '未知来源'}"
                    f"（{item.get('tier_label') or '来源级别未知'}）",
                    f"标题：{item.get('title') or ''}",
                    f"摘要：{summary[:PROMPT_SUMMARY_CHARS] if summary else '（来源未提供摘要）'}",
                ]
            )
        )
    return TRANSLATION_PROMPT + "\n\n".join(blocks)


def parse_translation_payload(
    content: str, allowed_ids: Iterable[int]
) -> Dict[int, Dict[str, str]]:
    """解析模型输出，返回 {id: {"title_zh": …, "brief_zh": …}}。

    校验是确定性的、**不信任模型**：id 不在本批输入集合内直接丢弃
    （模型偶尔会把上一批的 id 抄回来）；`title_zh` 为空则该条整条丢弃
    （没有中文标题的「译文」没有意义）；`brief_zh` 为空是允许的
    （来源本来就没有摘要）。整段解析不了就返回空字典，由调用方如实计失败。
    """
    payload = extract_json_object(content)
    if not payload:
        return {}
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        return {}

    allowed = {int(value) for value in allowed_ids}
    parsed: Dict[int, Dict[str, str]] = {}
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        try:
            entry_id = int(entry.get("id"))
        except (TypeError, ValueError):
            continue
        if entry_id not in allowed:
            continue
        title_zh = str(entry.get("title_zh") or "").strip()
        if not title_zh:
            continue
        brief_zh = str(entry.get("brief_zh") or "").strip()
        parsed[entry_id] = {
            "title_zh": title_zh[:TITLE_ZH_MAX_CHARS],
            # 空导语存 NULL 而不是空字符串：NULL 的含义才是「没有」。
            "brief_zh": brief_zh[:BRIEF_ZH_MAX_CHARS] or None,
        }
    return parsed


# --------------------------------------------------------------------------- #
# 服务
# --------------------------------------------------------------------------- #
def _needs_translation(model: Optional[str]) -> Any:
    """「这条还没有可用的译文」的判定。

    `model` 给定时，`translation_model` 与它不一致也算待翻译 —— 换了模型，
    旧译文是另一份产物，缓存不该复用。模型未知（LLM 未配置）时只按
    「有没有中文」判定：那时页面要回答的是「哪些条目还没有中文」。
    """
    conditions = [
        NewsDigestItem.title_zh.is_(None),
        func.trim(NewsDigestItem.title_zh) == "",
    ]
    if model:
        conditions.append(NewsDigestItem.translation_model.is_(None))
        conditions.append(NewsDigestItem.translation_model != model)
    return or_(*conditions)


class NewsTranslationService:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # 待翻译集合
    # ------------------------------------------------------------------ #
    def pending_rows(
        self, *, limit: int, model: Optional[str], window_hours: int = 24 * 30
    ) -> List[NewsDigestItem]:
        """尚未翻译的条目，按发布时间倒序（最新的先翻 —— 页面上先被看到的先有中文）。"""
        since = timeutil.now_naive()
        return (
            self.db.query(NewsDigestItem)
            .filter(
                NewsDigestItem.published_at >= since - timedelta(hours=window_hours),
                NewsDigestItem.published_at <= since,
                _needs_translation(model),
            )
            .order_by(NewsDigestItem.published_at.desc(), NewsDigestItem.id.desc())
            .limit(max(0, int(limit)))
            .all()
        )

    def pending_count(self, *, model: Optional[str], window_hours: int = 24 * 30) -> int:
        since = timeutil.now_naive()
        return int(
            self.db.query(func.count(NewsDigestItem.id))
            .filter(
                NewsDigestItem.published_at >= since - timedelta(hours=window_hours),
                NewsDigestItem.published_at <= since,
                _needs_translation(model),
            )
            .scalar()
            or 0
        )

    # ------------------------------------------------------------------ #
    # 翻译
    # ------------------------------------------------------------------ #
    def translate_pending(self, *, limit: Optional[int] = None) -> TranslationReport:
        """翻一批待翻译条目并落库；返回报告（含失败原因）。

        **任何情况下都不抛异常** —— 抓取与启动引导都会调用它，
        翻译失败不该让抓取本身失败（那是两件事）。
        """
        model = llm_provider.get_model_name() if llm_provider.is_configured() else None
        report = TranslationReport(model=model, at=timeutil.now_str())

        if not settings.NEWS_TRANSLATE_ENABLED:
            report.reason = "中文翻译已关闭（NEWS_TRANSLATE_ENABLED=false）"
            self._store_report(report)
            return report
        if model is None:
            report.reason = "LLM 未配置：中文标题与导语暂不可用（见 backend/.env 的 LLM 三项）"
            self._store_report(report)
            return report

        batch = int(limit if limit is not None else settings.NEWS_TRANSLATE_BATCH)
        rows = self.pending_rows(limit=batch, model=model)
        report.requested = len(rows)
        if not rows:
            self._store_report(report)
            return report

        items = [self._prompt_item(row) for row in rows]
        prompt = build_translation_prompt(items)
        try:
            llm = llm_provider.get_chat_llm(temperature=0.2)
            response = llm_provider.invoke_with_retries(llm, prompt)
        except llm_gate.LLMBudgetExceeded:
            report.reason = (
                "当日 LLM 调用预算已用尽（LLM_DAILY_CALL_BUDGET）；"
                "次日自动恢复，也可在 backend/.env 里调大上限。"
            )
            report.failed = len(rows)
            logger.warning("[消息翻译] 当日预算用尽，本轮未翻译")
            self._store_report(report)
            return report
        except Exception as exc:  # noqa: BLE001 —— 翻译失败不该拖垮抓取
            report.reason = f"翻译调用失败：{type(exc).__name__}"
            report.failed = len(rows)
            logger.error(f"[消息翻译] 调用失败：{exc}")
            self._store_report(report)
            return report

        parsed = parse_translation_payload(
            getattr(response, "content", "") or "", [row.id for row in rows]
        )
        report.translated = self._save(rows, parsed, model=model)
        report.failed = len(rows) - report.translated
        report.failed_ids = [row.id for row in rows if row.id not in parsed]
        if report.translated == 0:
            report.reason = "翻译结果无法解析：本轮没有写入任何中文（不摆编出来的内容）"
            logger.warning(
                "[消息翻译] 模型输出解析不出任何条目"
                f"（{llm_provider.describe_completion(response)}）"
            )
        elif report.failed:
            report.reason = f"本轮有 {report.failed} 条没有拿到可用译文"
        self._store_report(report)
        logger.info(
            f"[消息翻译] 本批 {report.requested} 条，写入 {report.translated} 条，"
            f"失败 {report.failed} 条"
        )
        return report

    # ------------------------------------------------------------------ #
    # 内部
    # ------------------------------------------------------------------ #
    @staticmethod
    def _prompt_item(row: NewsDigestItem) -> Dict[str, Any]:
        from app.services.news_digest import TIER_LABELS

        return {
            "id": row.id,
            "source": row.source,
            "tier_label": TIER_LABELS.get(int(row.authority_tier or 2), "二级信源"),
            "title": row.title,
            "summary": row.summary,
        }

    def _save(
        self, rows: Sequence[NewsDigestItem], parsed: Dict[int, Dict[str, str]], *, model: str
    ) -> int:
        """把通过的译文写回库；返回写入条数。

        只 UPDATE 目标行的三个字段，不动英文原文、不删行。
        """
        by_id = {row.id: row for row in rows}
        written = 0
        for entry_id, payload in parsed.items():
            row = by_id.get(entry_id)
            if row is None:  # parse 已经过滤过，这里再挡一次
                continue
            row.title_zh = payload["title_zh"]
            row.brief_zh = payload["brief_zh"]
            row.translated_at = timeutil.now_naive()
            row.translation_model = model
            written += 1
        if written:
            try:
                self.db.commit()
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                logger.error(f"[消息翻译] 落库失败：{exc}")
                return 0
        return written

    @staticmethod
    def _store_report(report: TranslationReport) -> None:
        CacheManager(STATUS_CACHE_KEY, ttl=STATUS_TTL).set(report.to_dict())


def last_translation_report() -> Optional[Dict[str, Any]]:
    """最近一次翻译报告（来自缓存）；从未跑过时为 None。"""
    return CacheManager(STATUS_CACHE_KEY, ttl=STATUS_TTL).get()


def translation_status(db: Session) -> Dict[str, Any]:
    """给 GET 响应用的翻译状态（**不发起任何 LLM 调用**）。

    `reason` 只在「确实还有待翻译的条目、而当前翻不了」时给出 ——
    全都翻好了就没有理由可讲，返回 None 而不是一句套话。
    """
    enabled = bool(settings.NEWS_TRANSLATE_ENABLED)
    configured = llm_provider.is_configured()
    model = llm_provider.get_model_name() if configured else None

    # 待翻译 = 最近 30 天里还没有中文的条目。**总是**数一遍（哪怕开关关着、
    # 或者 LLM 没配）—— 页面要回答的是「哪些条目还没有中文」，不是「现在能不能翻」。
    pending = NewsTranslationService(db).pending_count(model=model)

    reason: Optional[str] = None
    if pending:
        if not enabled:
            reason = "中文翻译已关闭（NEWS_TRANSLATE_ENABLED=false）"
        elif not configured:
            reason = "LLM 未配置：中文标题与导语暂不可用（见 backend/.env 的 LLM 三项）"
        else:
            last = last_translation_report() or {}
            reason = last.get("reason")
    return {
        "enabled": enabled,
        "model": model,
        "pending": pending,
        "reason": reason,
    }


def translate_pending(db: Session, *, limit: Optional[int] = None) -> TranslationReport:
    """模块级入口：抓取流程与启动引导都用这个。"""
    return NewsTranslationService(db).translate_pending(limit=limit)


__all__ = [
    "BRIEF_ZH_MAX_CHARS",
    "NewsTranslationService",
    "TITLE_ZH_MAX_CHARS",
    "TRANSLATION_PROMPT",
    "TranslationReport",
    "build_translation_prompt",
    "last_translation_report",
    "parse_translation_payload",
    "translate_pending",
    "translation_status",
]
