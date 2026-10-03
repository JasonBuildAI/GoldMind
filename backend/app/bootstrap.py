"""启动引导：把「填好 ``backend/.env`` → 启动」变成系统唯一的运行入口。

人工步骤（``init_db.py`` / ``backfill_quant.py`` / 各 ``migrate_*.py`` / 体检）从此全部是
**可选运维工具**；启动引导按阶段自动完成，幂等、可中断续跑、失败下轮重试。

本模块当前覆盖第一段：**自动迁移**。

- 迁移注册表（``MIGRATIONS``）+ ``schema_migrations`` 表：应用过的迁移记录在案，
  重复启动不会重放；
- 幂等：每条迁移沿用原脚本的纯函数判定（按「当前库长什么样」决定动不动手），
  迁移实现与运维 CLI 共用同一份代码（``backend/scripts/``），不抄第二遍口径；
- 备份：SQLite 在**会改动既有表**的迁移执行前，把库文件复制到
  ``backend/backups/``（.gitignore 覆盖）；备份失败即中止该条迁移 ——
  宁可停在旧状态，也不在无备份的情况下改库；
- MySQL：只做加列 / 建表 / 改列型，不删除任何数据；自动备份不代跑 mysqldump
  （如实标注为不支持，见 README「全自动运行」）。

后续阶段（覆盖度检测、冷启动回填、首轮分析）挂在同一个入口上，见
``docs/specs/2026-10-03-2.0.2-整改与自动化.md`` 第二节。
"""
from __future__ import annotations

import importlib
import shutil
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Optional

from loguru import logger
from sqlalchemy import Column, DateTime, Engine, MetaData, String, Table, Text, inspect, select

from app.config import settings
from app.utils import timeutil

BACKEND_DIR = Path(__file__).resolve().parent.parent
BACKUP_DIR = BACKEND_DIR / "backups"

# SQLite 迁移前备份保留份数（自动每日备份的保留策略另见调度层）
MIGRATION_BACKUP_KEEP = 20

REGISTRY_TABLE = "schema_migrations"

# 注册表定义走 Core Table，不手写 SQL：`key` 是 MySQL 保留字，裸写会在 MySQL 上
# 直接 1064 语法报错（2026-10-03 真实库实测）；Core 交给方言按需加引号
# （MySQL 反引号 / SQLite 双引号），两库共用同一份定义。
REGISTRY = Table(
    REGISTRY_TABLE,
    MetaData(),
    Column("key", String(64), primary_key=True),
    Column("description", Text, nullable=True),
    Column("note", Text, nullable=True),
    Column("applied_at", DateTime, nullable=False),
)


@dataclass(frozen=True)
class Migration:
    """一条迁移：key 是记录在 ``schema_migrations`` 里的唯一标识。

    ``alters_existing`` 表示「会改动既有表」—— SQLite 下这类迁移执行前必须先备份。
    ``applier`` 给定时优先使用（少数迁移需要方言分支），否则按
    ``module.entry`` 导入调用（与运维 CLI 同一份实现）。
    """

    key: str
    description: str
    module: str
    alters_existing: bool = True
    entry: str = "apply_migration"
    applier: Optional[Callable[[Engine], str]] = None


def _apply_enum_values(engine: Engine) -> str:
    """枚举列取值修正：MySQL 专属（SQLite 不做 ENUM 大小写比较）。"""
    if engine.dialect.name != "mysql":
        return f"{engine.dialect.name} 下不适用（枚举取值只有 MySQL 需要修正）"
    _ensure_sys_path()
    from scripts import fix_enum_columns

    return "；".join(fix_enum_columns.apply(engine))


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        key="quant-tables",
        description="建出量化三表、补 predictions 的量化列、补写修订流水",
        module="scripts.migrate_quant",
    ),
    Migration(
        key="institution-view-columns",
        description="机构观点表补列（as_of_date / source）",
        module="scripts.migrate_institution_views",
    ),
    Migration(
        key="news-digest-url-text",
        description="news_digest_items.url 从 VARCHAR(500) 迁到 TEXT",
        module="scripts.migrate_news_digest_url",
        entry="apply",
    ),
    Migration(
        key="news-digest-translation-columns",
        description="消息板块补中文译文列（title_zh / brief_zh / translated_at / translation_model）",
        module="scripts.migrate_news_digest_translation",
        entry="apply",
    ),
    Migration(
        key="enum-values-uppercase",
        description="枚举列取值改为与模型一致的大写（仅 MySQL）",
        module="scripts.fix_enum_columns",
        applier=_apply_enum_values,
    ),
)

MIGRATIONS_BY_KEY = {migration.key: migration for migration in MIGRATIONS}

assert len(MIGRATIONS_BY_KEY) == len(MIGRATIONS), "迁移 key 必须唯一"


def _ensure_sys_path() -> None:
    """scripts/ 不在 app 包内：导入前确保 backend 在 sys.path 上。"""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))


def ensure_registry(engine: Engine) -> None:
    """建出 ``schema_migrations`` 表（幂等）。"""
    REGISTRY.create(engine, checkfirst=True)


def applied_keys(engine: Engine) -> set[str]:
    ensure_registry(engine)
    with engine.connect() as conn:
        rows = conn.execute(select(REGISTRY.c.key)).all()
    return {str(row[0]) for row in rows}


def _record(engine: Engine, migration: Migration, note: str) -> None:
    with engine.begin() as conn:
        conn.execute(
            REGISTRY.insert().values(
                key=migration.key,
                description=migration.description,
                note=note[:2000],
                # naive datetime（项目时区），秒级精度与旧手写 SQL 一致
                applied_at=timeutil.now_naive().replace(microsecond=0),
            )
        )


def _sqlite_file(engine: Engine) -> Optional[Path]:
    """SQLite 库文件路径；内存库返回 None。"""
    if engine.dialect.name != "sqlite":
        return None
    database = engine.url.database
    if not database or database == ":memory:":
        return None
    return Path(database)


def backup_sqlite(engine: Engine, migration_key: str) -> Optional[Path]:
    """迁移前备份 SQLite 库文件；非 SQLite / 内存库返回 None。

    备份失败会抛出异常 —— 调用方（``run_migrations``）据此拒绝执行迁移。
    """
    source = _sqlite_file(engine)
    if source is None:
        return None
    if not source.exists():  # 全新库，还没有可备份的内容
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = timeutil.now_naive().strftime("%Y%m%d-%H%M%S")
    target = BACKUP_DIR / f"{source.stem}-{stamp}-pre-{migration_key}.db"
    shutil.copy2(source, target)
    logger.info(f"[引导] 迁移前备份：{target}")
    _prune_migration_backups()
    return target


def _prune_migration_backups() -> None:
    files = sorted(BACKUP_DIR.glob("*-pre-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    for stale in files[MIGRATION_BACKUP_KEEP:]:
        try:
            stale.unlink()
        except OSError as exc:  # 清理失败不影响迁移；下一轮再清
            logger.warning(f"[引导] 备份清理失败：{stale}（{exc}）")


def _describe(result) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, (list, tuple)):
        return "；".join(str(item) for item in result) or "无操作"
    if hasattr(result, "statements"):
        # 计划对象（如机构观点迁移）：只记计数 —— note 要能一眼读懂，不是整份计划的倾倒场
        backfill = getattr(result, "backfill", [])
        copies = getattr(result, "copies", [])
        return (
            f"{len(result.statements)} 条 DDL；回填 {len(backfill)} 行；"
            f"机构观点对齐 {len(copies)} 条"
        )
    return str(result)


def _apply(migration: Migration, engine: Engine) -> str:
    if migration.applier is not None:
        return _describe(migration.applier(engine))
    _ensure_sys_path()
    module = importlib.import_module(migration.module)
    function = getattr(module, migration.entry)
    return _describe(function(engine))


def run_migrations(engine: Engine) -> list[dict]:
    """应用尚未记录的迁移；返回逐条结果（applied / already / failed）。

    失败的迁移**不记录**：下一次启动会重试（错误原文进日志与返回值，
    页面在 /health 里能看到「引导停在哪一步」）。
    """
    ensure_registry(engine)
    done = applied_keys(engine)
    results: list[dict] = []
    for migration in MIGRATIONS:
        if migration.key in done:
            results.append({"key": migration.key, "status": "already"})
            continue
        backup: Optional[Path] = None
        try:
            if migration.alters_existing:
                backup = backup_sqlite(engine, migration.key)
            note = _apply(migration, engine)
        except Exception as exc:  # noqa: BLE001 —— 迁移失败必须是「可重试」而不是崩溃
            logger.error(f"[引导] 迁移 {migration.key} 失败（未记录，下轮重试）：{exc}")
            results.append(
                {"key": migration.key, "status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            )
            continue
        _record(engine, migration, note)
        logger.info(f"[引导] 迁移 {migration.key} 完成：{note[:200]}")
        results.append(
            {
                "key": migration.key,
                "status": "applied",
                "note": note,
                "backup": str(backup) if backup else None,
            }
        )
    return results


def registry_snapshot(engine: Engine) -> dict:
    """给 /health 用的迁移进度快照。"""
    done = applied_keys(engine)
    return {
        "applied": sorted(done),
        "pending": [migration.key for migration in MIGRATIONS if migration.key not in done],
        "total": len(MIGRATIONS),
    }


__all__ = [
    "BACKUP_DIR",
    "MIGRATIONS",
    "MIGRATIONS_BY_KEY",
    "Migration",
    "applied_keys",
    "backup_sqlite",
    "ensure_registry",
    "registry_snapshot",
    "run_migrations",
]


# --------------------------------------------------------------------------- #
# B2：覆盖度检测 → 数据回填 → 首轮分析（零人工冷启动）
#
# 阶段清单是「填完 .env 之后系统自己会做的全部事情」，/health 按它报告进度：
# 每阶段要么真正执行，要么给出**为什么可以跳过**的明确理由；失败不阻塞后续
# 阶段（例如新闻源挂了仍可回填价格），但会在快照里如实标 failed。
# --------------------------------------------------------------------------- #

# 金价少于这个行数视为「没有可用历史」（分析需要价格窗口与统计量）
MIN_GOLD_PRICE_ROWS = 250
# 最新价格早于这个天数视为过期，需要在启动时补差
PRICE_STALE_DAYS = 7
# 最近 24 小时没有任何新闻 → 启动时抓一轮
NEWS_FRESH_HOURS = 24

PHASE_ORDER: tuple[str, ...] = (
    "coverage",
    "align_stores",
    "price_history",
    "news",
    "quant_history",
    "revisions",
    "align_stores_final",
    "analyses",
)

PHASE_LABELS: dict[str, str] = {
    "coverage": "检测数据覆盖度",
    "align_stores": "对齐本地研究长库",
    "price_history": "回填金价与美元指数",
    "news": "抓取新闻与高权威消息",
    "quant_history": "回填量化因子历史",
    "revisions": "补齐因子修订流水",
    "align_stores_final": "回填后再次对齐本地研究长库",
    "analyses": "触发首轮 AI 分析",
}


class _Progress:
    """引导进度（进程内单例）：后台线程写，``/health`` 读。"""

    def __init__(self) -> None:
        import threading as _threading

        self._lock = _threading.Lock()
        self._phases: dict[str, dict] = {}
        self.gaps: dict = {}
        self.migration: dict = {"status": "pending", "snapshot": None, "error": None}
        self.ready = False
        self.error: Optional[str] = None
        self.started_at: Optional[str] = None
        self.finished_at: Optional[str] = None

    def reset(self) -> None:
        with self._lock:
            self._phases = {}
            self.gaps = {}
            self.ready = False
            self.error = None
            self.started_at = timeutil.now_iso()
            self.finished_at = None

    def start(self, key: str, label: Optional[str] = None) -> None:
        with self._lock:
            self._phases[key] = {
                "key": key,
                "label": label or PHASE_LABELS.get(key, key),
                "status": "running",
                "note": None,
                "at": timeutil.now_iso(),
            }

    def finish(self, key: str, status: str, note: Optional[str] = None) -> None:
        with self._lock:
            phase = self._phases.setdefault(
                key, {"key": key, "label": PHASE_LABELS.get(key, key)}
            )
            phase.update(status=status, note=note, at=timeutil.now_iso())

    def set_gaps(self, gaps: Optional[dict]) -> None:
        with self._lock:
            self.gaps = gaps or {}

    def set_migrations(self, snapshot: Optional[dict], *, error: Optional[str] = None) -> None:
        """由 main 的迁移阶段调用；status 沿用 B1 的语义（pending/done/failed）。"""
        with self._lock:
            self.migration = {
                "status": "failed" if error else "done",
                "snapshot": snapshot,
                "error": error,
            }
            if error:
                self.error = error
            self.finished_at = timeutil.now_iso()
            self.ready = not error

    def disabled(self) -> None:
        with self._lock:
            self.migration = {"status": "disabled", "snapshot": None, "error": None}
            self.ready = True
            self.finished_at = timeutil.now_iso()

    def complete(self, *, ready: bool, error: Optional[str] = None) -> None:
        with self._lock:
            self.ready = ready
            if error:
                self.error = error
            self.finished_at = timeutil.now_iso()

    def mark_skipped(self, reason: str) -> None:
        """整条数据管线被显式关闭（如 SCHEDULER_ENABLED=false）时的诚实记录。"""
        for key in PHASE_ORDER:
            self.start(key)
            self.finish(key, "skipped", reason)
        self.complete(ready=True)

    def snapshot(self) -> dict:
        with self._lock:
            phases = [self._phases[key] for key in PHASE_ORDER if key in self._phases]
            migration = dict(self.migration)
            gaps = dict(self.gaps)
            running = any(phase["status"] == "running" for phase in phases)
            failed = [phase for phase in phases if phase["status"] == "failed"]
            done = [phase for phase in phases if phase["status"] in {"done", "skipped"}]
            started_at = self.started_at
            finished_at = self.finished_at
            ready = self.ready
            error = self.error

        if migration["status"] == "disabled":
            status = "disabled"
        elif migration["status"] == "failed":
            status = "failed"
        elif running or (phases and len(done) < len(phases)):
            status = "running"
        else:
            status = "done"
        if migration["status"] == "pending" and not phases:
            status = "pending"

        return {
            "enabled": bool(settings.AUTO_BOOTSTRAP),
            "status": status,
            "ready": bool(ready),
            "step": {
                "index": len(done),
                "total": len(phases) or len(PHASE_ORDER),
            },
            "phases": phases,
            "gaps": gaps,
            "error": error or migration.get("error") or (failed[0]["note"] if failed else None),
            "started_at": started_at,
            "finished_at": finished_at,
            "migrations": migration.get("snapshot"),
        }


progress = _Progress()


@dataclass(frozen=True)
class _Context:
    engine: Engine
    today: date


def _today() -> date:
    return timeutil.today()


# --------------------------------------------------------------------------- #
# 各阶段实现
# --------------------------------------------------------------------------- #
def _phase_coverage(ctx: _Context, db) -> dict:
    """只读：把「缺什么」摆出来，供后续阶段与 /health 使用。"""
    from sqlalchemy import func

    from app.config import settings as current_settings
    from app.models.gold_price import DollarIndex, GoldPrice
    from app.models.news import GoldNews

    gold_count = int(db.query(func.count(GoldPrice.id)).scalar() or 0)
    gold_last = db.query(func.max(GoldPrice.date)).scalar()
    dollar_count = int(db.query(func.count(DollarIndex.id)).scalar() or 0)
    dollar_last = db.query(func.max(DollarIndex.date)).scalar()
    news_count = int(db.query(func.count(GoldNews.id)).scalar() or 0)
    news_last = db.query(func.max(GoldNews.published_at)).scalar()

    digest_count = 0
    digest_last = None
    try:
        from app.models.news_digest import NewsDigestItem

        digest_count = int(db.query(func.count(NewsDigestItem.id)).scalar() or 0)
        digest_last = db.query(func.max(NewsDigestItem.published_at)).scalar()
    except Exception as exc:  # 表缺失时如实降级，不影响其它阶段
        logger.warning(f"[引导] 消息板块覆盖度检测失败：{exc}")

    quant_missing: list[str] = []
    quant_gaps = 0
    try:
        from scripts.backfill_quant import coverage_rows

        rows = coverage_rows(db, years=int(current_settings.QUANT_BACKFILL_YEARS), today=ctx.today)
        for row in rows:
            if row["observations"] == 0:
                quant_missing.append(row["factor_key"])
            quant_gaps += len(row["sparse_years"])
    except Exception as exc:
        logger.warning(f"[引导] 量化覆盖度检测失败：{exc}")

    gaps = {
        "gold_prices": {
            "rows": gold_count,
            "last_date": gold_last.isoformat() if hasattr(gold_last, "isoformat") else (str(gold_last) if gold_last else None),
        },
        "dollar_index": {
            "rows": dollar_count,
            "last_date": dollar_last.isoformat() if hasattr(dollar_last, "isoformat") else (str(dollar_last) if dollar_last else None),
        },
        "gold_news": {
            "rows": news_count,
            "last_published_at": news_last.isoformat() if hasattr(news_last, "isoformat") else (str(news_last) if news_last else None),
        },
        "news_digest": {
            "rows": digest_count,
            "last_published_at": digest_last.isoformat() if hasattr(digest_last, "isoformat") else (str(digest_last) if digest_last else None),
        },
        "quant": {
            "series_without_data": sorted(quant_missing),
            "sparse_year_count": int(quant_gaps),
            "window_years": int(current_settings.QUANT_BACKFILL_YEARS),
        },
    }
    progress.set_gaps(gaps)
    return {"status": "done", "gaps": gaps, "note": "覆盖度检测完成"}


def _phase_align_stores(ctx: _Context, db) -> dict:
    """把本地研究长库对齐到服务库口径（存在才做；不存在即跳过）。

    这一步在引导里跑两次：第一次（`align_stores`）把长库已有的历史**导入**
    服务库，避免回填阶段重复联网抓取；第二次（`align_stores_final`）在
    回填之后把服务库新写入的行**同步回**长库，让一次启动就收敛。
    2026-10-03 冷启动验收实测：只有第一次对齐时，长库要等下一次重启才拿到
    本轮回填的 7428 行量化历史。
    """
    from app.services import store_alignment

    if not store_alignment.DEFAULT_LONG_DB.exists():
        return {"status": "skipped", "note": "本地研究长库不存在（全新克隆 / CI），无需对齐"}

    result = store_alignment.align_stores(ctx.engine)
    if result.get("status") == "absent":
        return {"status": "skipped", "note": "长库没有 factor_observations 表"}
    note = (
        f"服务库补入 {result['inserted_into_service']} 行；"
        f"长库修正 {result['updated_in_long']} 行、补入 {result['inserted_into_long']} 行；"
        f"对齐前冲突 {result['conflicts_before']} 行"
    )
    return {"status": "done", "note": note, "result": result}


def _phase_price_history(ctx: _Context, db) -> dict:
    """金价 / 美元指数历史：覆盖不足或过期时抓一轮（增量 upsert）。"""
    from datetime import timedelta

    from sqlalchemy import func

    from app.models.gold_price import DollarIndex, GoldPrice

    gold_count = int(db.query(func.count(GoldPrice.id)).scalar() or 0)
    gold_last = db.query(func.max(GoldPrice.date)).scalar()
    stale_before = ctx.today - timedelta(days=PRICE_STALE_DAYS)
    needs_gold = gold_count < MIN_GOLD_PRICE_ROWS or (
        hasattr(gold_last, "toordinal") and gold_last < stale_before
    )
    if not needs_gold:
        return {
            "status": "skipped",
            "note": f"已有 {gold_count} 行金价（最新 {gold_last}），无需回填",
        }

    _ensure_sys_path()
    import seed_data

    gold_rows = seed_data.fetch_gold_history() or []
    saved_gold = seed_data.save_gold_prices(db, gold_rows)
    dollar_rows = seed_data.fetch_dollar_index_history() or []
    saved_dollar = seed_data.save_dollar_index(db, dollar_rows)

    total_after = int(db.query(func.count(GoldPrice.id)).scalar() or 0)
    if total_after < MIN_GOLD_PRICE_ROWS:
        return {
            "status": "failed",
            "note": (
                f"数据源不可达或返回为空：金价仍只有 {total_after} 行"
                f"（写入 {saved_gold} 行）——下一轮启动自动重试"
            ),
        }
    return {
        "status": "done",
        "note": f"金价写入 {saved_gold} 行、美元指数写入 {saved_dollar} 行（现共 {total_after} 行）",
    }


def _phase_news(ctx: _Context, db) -> dict:
    """RSS 新闻与高权威消息：最近 24 小时为空时抓一轮。"""
    from datetime import timedelta

    from sqlalchemy import func

    from app.models.news import GoldNews

    threshold = timeutil.now_naive() - timedelta(hours=NEWS_FRESH_HOURS)
    fresh_news = int(
        db.query(func.count(GoldNews.id)).filter(GoldNews.published_at >= threshold).scalar() or 0
    )
    news_note = None
    if fresh_news == 0:
        from app.services.news_service import NewsService

        service = NewsService(db)
        fetched = service.fetch_all_rss_news(limit_per_source=10)
        saved = sum(1 for item in fetched if service.save_news(item))
        news_note = f"RSS 抓到 {len(fetched)} 条、写入 {saved} 条"
    else:
        news_note = f"最近 {NEWS_FRESH_HOURS} 小时已有 {fresh_news} 条新闻"

    digest_note = None
    try:
        from app.models.news_digest import NewsDigestItem
        from app.services.news_digest import NewsDigestService

        fresh_digest = int(
            db.query(func.count(NewsDigestItem.id))
            .filter(NewsDigestItem.published_at >= threshold)
            .scalar()
            or 0
        )
        if fresh_digest == 0:
            report = NewsDigestService(db).fetch_all_sources(limit=10)
            digest_note = (
                f"消息板块抓取 {report.get('ok_sources', 0)}/{report.get('total_sources', 0)} 源成功，"
                f"入库 {report.get('saved', 0)} 条"
            )
        else:
            digest_note = f"最近 {NEWS_FRESH_HOURS} 小时已有 {fresh_digest} 条消息"
    except Exception as exc:  # 消息板块失败不拖垮新闻主链路
        digest_note = f"消息板块抓取失败：{type(exc).__name__}: {exc}"

    failed = fresh_news == 0 and "写入 0 条" in (news_note or "")
    return {
        "status": "failed" if failed else "done",
        "note": f"{news_note}；{digest_note}",
    }


def _phase_quant_history(ctx: _Context, db) -> dict:
    """量化因子历史：窗口内没有任何观测的序列才触发整轮回填（可断点续跑）。"""
    from app.config import settings as current_settings
    from scripts import backfill_quant

    rows = backfill_quant.coverage_rows(
        db, years=int(current_settings.QUANT_BACKFILL_YEARS), today=ctx.today
    )
    missing = [row["factor_key"] for row in rows if row["observations"] == 0]
    if not missing:
        return {
            "status": "skipped",
            "note": f"{len(rows)} 条序列窗口内均有数据，交给日常同步",
        }

    result = backfill_quant.run_backfill(
        db,
        years=int(current_settings.QUANT_BACKFILL_YEARS),
        rounds=8,
        today=ctx.today,
        emit=lambda line: logger.info(f"[引导] {line}"),
    )
    remaining = sum(
        len(row["sparse_years"]) for row in result["coverage"]
    )
    note = (
        f"回填 {result['rounds']} 轮（{result['stopped_reason']}）："
        f"新增 {result['inserted']} 行 / 修订 {result['updated']} 行；"
        f"仍缺 {remaining} 个稀疏年（源本身不提供的历史如实留空）"
    )
    return {"status": "done", "note": note}


def _phase_revisions(ctx: _Context, db) -> dict:
    """老库升级路径：观测表里有、修订流水里没有的行补进流水。"""
    _ensure_sys_path()
    from scripts import migrate_quant

    pending = migrate_quant.ledger_backfill_rows(ctx.engine)
    if pending == 0:
        return {"status": "skipped", "note": "修订流水已完整"}
    seeded = migrate_quant.seed_ledger(ctx.engine)
    return {"status": "done", "note": f"补齐修订流水 {seeded} 行"}


def _phase_analyses(ctx: _Context, db, *, force: bool = False) -> dict:
    """数据就绪后自动跑五个分析（受指纹门控与每日预算约束）。

    ``force=True``（配置热更新后）跳过输入指纹门控：换了供应商 / 模型，
    旧指纹对应的缓存结果是另一份产物，必须重算。
    """
    from app.services.llm_provider import is_configured

    if not is_configured():
        return {
            "status": "skipped",
            "note": "LLM 未配置：数据层照常运行，配好 backend/.env 后自动补一轮（无需重启）",
        }

    from app.services.analysis_input import load_analysis_news
    from app.services.bearish_factor_service import BearishFactorService
    from app.services.bullish_factor_service import BullishFactorService
    from app.services.gold_service import GoldService, format_market_status
    from app.services.institution_prediction_service import InstitutionPredictionService
    from app.services.investment_advice_service import InvestmentAdviceService
    from app.services.market_summary_service import MarketSummaryService

    notes: list[str] = []

    bullish_service = BullishFactorService(db)
    bearish_service = BearishFactorService(db)
    institution_service = InstitutionPredictionService(db)

    for name, service in (
        ("看涨", bullish_service),
        ("看跌", bearish_service),
        ("机构", institution_service),
    ):
        try:
            service.refresh_analysis_sync(force=force)
            notes.append(f"{name}✓")
        except Exception as exc:  # 单个分析失败不拖垮其它分析
            notes.append(f"{name}✗({type(exc).__name__})")

    stats = GoldService(db).get_statistics() or {}
    market_status = format_market_status(stats)
    bullish = bullish_service.get_bullish_factors(use_cache=True).get("bullish_factors", [])
    bearish = bearish_service.get_bearish_factors(use_cache=True).get("bearish_factors", [])
    institutions = institution_service.get_institution_predictions(use_cache=True).get(
        "institutions", []
    )

    try:
        InvestmentAdviceService(db).refresh_analysis_sync(
            market_status, bullish, bearish, institutions, force=force
        )
        notes.append("策略✓")
    except Exception as exc:
        notes.append(f"策略✗({type(exc).__name__})")

    try:
        MarketSummaryService(db).get_market_summary(
            market_status=market_status,
            bullish_factors=bullish,
            bearish_factors=bearish,
            institution_predictions=institutions,
            recent_news=load_analysis_news(db),
            use_cache=False,
            force=force,
        )
        notes.append("总结✓")
    except Exception as exc:
        notes.append(f"总结✗({type(exc).__name__})")

    return {"status": "done", "note": "、".join(notes)}


STEPS: tuple[tuple[str, str, Callable], ...] = (
    ("coverage", PHASE_LABELS["coverage"], _phase_coverage),
    ("align_stores", PHASE_LABELS["align_stores"], _phase_align_stores),
    ("price_history", PHASE_LABELS["price_history"], _phase_price_history),
    ("news", PHASE_LABELS["news"], _phase_news),
    ("quant_history", PHASE_LABELS["quant_history"], _phase_quant_history),
    ("revisions", PHASE_LABELS["revisions"], _phase_revisions),
    ("align_stores_final", PHASE_LABELS["align_stores_final"], _phase_align_stores),
    ("analyses", PHASE_LABELS["analyses"], _phase_analyses),
)


def run_bootstrap(
    engine: Engine,
    *,
    steps: Optional[dict] = None,
    today: Optional[date] = None,
    session_factory: Optional[Callable] = None,
) -> dict:
    """按序执行全部数据阶段；返回最终快照。

    ``steps`` 便于测试注入假源 / 假分析（键为阶段 key）；生产路径不传。
    单阶段失败只记录、不中止：价格源挂了仍要抓新闻、补因子。
    """
    from app.database import SessionLocal

    ctx = _Context(engine=engine, today=today or _today())
    factory = session_factory or SessionLocal
    overrides = steps or {}
    progress.reset()

    for key, label, function in STEPS:
        runner = overrides.get(key, function)
        progress.start(key, label)
        db = factory()
        try:
            result = runner(ctx, db) or {}
        except Exception as exc:  # noqa: BLE001 —— 失败可重试，下轮启动重跑
            logger.error(f"[引导] 阶段 {key} 失败：{exc}")
            progress.finish(key, "failed", f"{type(exc).__name__}: {exc}")
            continue
        finally:
            db.close()
        status = str(result.get("status") or "done")
        if key == "coverage" and isinstance(result.get("gaps"), dict):
            progress.set_gaps(result["gaps"])
        progress.finish(key, status, result.get("note"))

    snapshot = progress.snapshot()
    failed = [phase for phase in snapshot["phases"] if phase["status"] == "failed"]
    progress.complete(
        ready=not failed,
        error=("；".join(f"{phase['key']}: {phase['note']}" for phase in failed) or None),
    )
    return progress.snapshot()


def warm_analyses(engine: Engine, *, force: bool = False) -> dict:
    """配置热更新后立即补一轮分析（不触碰引导进度快照）。"""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        return _phase_analyses(
            _Context(engine=engine, today=_today()), db, force=force
        ) or {}
    finally:
        db.close()


def start_background(engine: Engine) -> dict:
    """在 lifespan 里调用：数据阶段放后台线程跑，不阻塞服务启动。"""
    import threading

    if not settings.AUTO_BOOTSTRAP:
        progress.disabled()
        return progress.snapshot()
    if not settings.SCHEDULER_ENABLED:
        progress.mark_skipped(
            "SCHEDULER_ENABLED=false：启动引导只做建表与迁移，数据回填与首轮分析交给外部流程"
        )
        return progress.snapshot()

    thread = threading.Thread(
        target=run_bootstrap, args=(engine,), name="goldmind-bootstrap", daemon=True
    )
    thread.start()
    return progress.snapshot()