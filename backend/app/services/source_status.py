"""抓取通道的尝试流水，以及给 `GET /api/gold/sources/status` 的可用性汇总。

为什么要单独一张流水表：各通道（量化因子同步 / 消息板块 / RSS / 行情）原本只把
最近一次成败写进各自的缓存或同步报告 —— 缓存会过期、报告会被下一次覆盖，
「这个源最近到底怎么样」无从回答。流水只追加、不覆盖：可用性 = 每个源最近一行。

写入失败绝不抛给抓取方：流水是旁路观测，不是抓取的一部分。
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy import select

from app.models.fetch_attempt import FetchAttempt
from app.utils import timeutil

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"

STATUS_LABELS = {
    STATUS_OK: "可用",
    STATUS_EMPTY: "无数据",
    STATUS_ERROR: "不可用",
    STATUS_SKIPPED: "本轮跳过",
}

CHANNEL_LABELS = {
    "quant_sync": "量化因子同步",
    "news_digest": "消息板块",
    "news_rss": "RSS 新闻",
    "price": "金价与美元指数",
}

# 「最近一次尝试」超过这个年龄（小时）就不再当作新鲜可用：
# 按各通道自己的更新节奏 + 一次容忍来定，而不是拿服务器时钟拍一个数。
STALE_AFTER_HOURS = {
    "quant_sync": 26,
    "news_digest": 3,
    "news_rss": 6,
    "price": 26,
}
DEFAULT_STALE_AFTER_HOURS = 48

# 每次快照最多回扫的流水行数：每个源只关心自己最近一行
MAX_ROWS = 500


def record_attempt(
    *,
    channel: str,
    source_key: str,
    status: str,
    items: Optional[int] = None,
    error: Optional[str] = None,
    started_at: Optional[datetime] = None,
    finished_at: Optional[datetime] = None,
) -> None:
    """记一条抓取尝试（独立会话，失败只写日志）。"""
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        now = timeutil.now_naive()
        session.add(
            FetchAttempt(
                channel=channel,
                source_key=source_key,
                status=status,
                started_at=started_at or now,
                finished_at=finished_at or now,
                items=items,
                error=(str(error)[:500] if error else None),
            )
        )
        session.commit()
    except Exception as exc:  # noqa: BLE001 —— 流水不能反过来把抓取弄挂
        logger.warning(f"[源状态] 尝试流水写入失败（{channel}/{source_key}）：{exc}")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        session.close()


def latest_attempts(db) -> list[FetchAttempt]:
    """每个 (channel, source_key) 的最近一次尝试。

    流水只追加，id 顺序即时间顺序：按 id 倒序取最近 MAX_ROWS 行，
    在内存里挑每个源的第一条 —— 一条 SQL、不依赖窗口函数的方言差异。
    """
    rows = (
        db.execute(select(FetchAttempt).order_by(FetchAttempt.id.desc()).limit(MAX_ROWS))
        .scalars()
        .all()
    )
    seen: dict = {}
    for row in rows:
        key = (row.channel, row.source_key)
        if key not in seen:
            seen[key] = row
    return sorted(seen.values(), key=lambda row: (row.channel, row.source_key))


def _iso(moment: Optional[datetime]) -> Optional[str]:
    return moment.isoformat(sep=" ", timespec="seconds") if moment else None


def payload(db, *, now: Optional[datetime] = None) -> dict:
    """可用性看板：每个源的最近一次尝试 + 汇总计数。"""
    moment = now or timeutil.now_naive()
    counts = {
        "total": 0,
        STATUS_OK: 0,
        STATUS_EMPTY: 0,
        STATUS_ERROR: 0,
        STATUS_SKIPPED: 0,
        "stale": 0,
    }
    sources = []
    for row in latest_attempts(db):
        budget = STALE_AFTER_HOURS.get(row.channel, DEFAULT_STALE_AFTER_HOURS)
        reference = row.finished_at or row.started_at
        age_hours = (
            round((moment - reference).total_seconds() / 3600.0, 1) if reference else None
        )
        stale = bool(age_hours is not None and age_hours > budget and row.status == STATUS_OK)
        sources.append(
            {
                "channel": row.channel,
                "channel_label": CHANNEL_LABELS.get(row.channel, row.channel),
                "source_key": row.source_key,
                "status": row.status,
                "status_label": STATUS_LABELS.get(row.status, row.status),
                "stale": stale,
                "age_hours": age_hours,
                "started_at": _iso(row.started_at),
                "finished_at": _iso(row.finished_at),
                "items": row.items,
                "error": row.error,
            }
        )
        counts["total"] += 1
        counts[row.status] = counts.get(row.status, 0) + 1
        if stale:
            counts["stale"] += 1

    return {
        "generated_at": _iso(moment),
        "summary": counts,
        "sources": sources,
    }


__all__ = [
    "CHANNEL_LABELS",
    "STALE_AFTER_HOURS",
    "STATUS_EMPTY",
    "STATUS_ERROR",
    "STATUS_LABELS",
    "STATUS_OK",
    "STATUS_SKIPPED",
    "latest_attempts",
    "payload",
    "record_attempt",
]
