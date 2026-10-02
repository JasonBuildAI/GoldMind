"""消息板块 url 列迁移：VARCHAR(500) → TEXT。

2026-10-02 的真实故障：Google News 的文章链接实测最长 517 字符，超过
`news_digest_items.url` 的 `VARCHAR(500)`。MySQL 拒绝整批 INSERT
（`Data too long for column 'url'`）并整体回滚，而 SQLite 不强制 VARCHAR 长度 ——
测试全绿、真实部署一条也落不了库。本脚本把既有库的该列迁到 TEXT。

只改列类型，**不删任何行**；去重用的前缀索引 `ix_news_digest_items_url (url(191))`
在 TEXT 上依然有效（MySQL 对 TEXT 本来就必须用前缀索引）。

SQLite 不强制 VARCHAR 长度（TEXT affinity），没有可迁的东西 —— 脚本会说明并直接通过。

用法：

    python scripts/migrate_news_digest_url.py                # dry-run（默认）
    python scripts/migrate_news_digest_url.py --apply        # 执行
    python scripts/migrate_news_digest_url.py --rollback             # 打印回滚计划
    python scripts/migrate_news_digest_url.py --rollback --apply     # 回滚为 VARCHAR(500)

回滚守卫：库里存在超过 500 字符的 url 时拒绝执行（转换会截断数据），
并打印超长行数；宁可保持 TEXT，也不静默丢数据。
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from sqlalchemy import Engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine as default_engine  # noqa: E402

TABLE = "news_digest_items"
COLUMN = "url"
OLD_LIMIT = 500
NEW_TYPE = "TEXT"


@dataclass
class Plan:
    """一条迁移计划：statement 为 None 表示无需动手。"""

    statement: Optional[str]
    reason: str

    @property
    def needed(self) -> bool:
        return self.statement is not None


def plan_for(*, dialect: str, table_exists: bool, current_type: Optional[str]) -> Plan:
    """升级判定（纯函数，测试不依赖 MySQL）。"""
    if not table_exists:
        return Plan(None, f"表 {TABLE} 不存在：首次启动会按新模型建表，无需迁移")
    if dialect == "sqlite":
        return Plan(None, "SQLite 不强制 VARCHAR 长度（TEXT affinity），无需迁移")
    type_text = (current_type or "").upper()
    if NEW_TYPE in type_text:
        return Plan(None, f"{COLUMN} 已是 {NEW_TYPE}，无需迁移")
    if dialect == "mysql":
        return Plan(
            f"ALTER TABLE {TABLE} MODIFY {COLUMN} {NEW_TYPE} NOT NULL",
            f"把 {COLUMN} 从 {current_type} 迁到 {NEW_TYPE}",
        )
    return Plan(None, f"未适配的方言 {dialect}：请手工把 {COLUMN} 改为 {NEW_TYPE}")


def rollback_for(
    *, dialect: str, current_type: Optional[str], max_url_chars: Optional[int]
) -> Plan:
    """回滚判定（纯函数）：会截断数据时拒绝执行。"""
    if dialect != "mysql":
        return Plan(None, f"{dialect} 下没有需要回滚的列类型")
    if NEW_TYPE not in (current_type or "").upper():
        return Plan(None, f"{COLUMN} 不是 {NEW_TYPE}，无需回滚")
    if max_url_chars is not None and max_url_chars > OLD_LIMIT:
        return Plan(
            None,
            f"库里有 {max_url_chars} 字符的 {COLUMN}，回滚为 VARCHAR({OLD_LIMIT}) "
            f"会截断数据，拒绝执行",
        )
    return Plan(
        f"ALTER TABLE {TABLE} MODIFY {COLUMN} VARCHAR({OLD_LIMIT}) NOT NULL",
        f"把 {COLUMN} 回滚为 VARCHAR({OLD_LIMIT})",
    )


def describe(bind: Engine) -> Tuple[bool, Optional[str]]:
    """返回（表是否存在, url 列的数据库侧类型）。"""
    inspector = inspect(bind)
    if not inspector.has_table(TABLE):
        return False, None
    for column in inspector.get_columns(TABLE):
        if column["name"].lower() == COLUMN:
            return True, column["type"].compile(dialect=bind.dialect)
    return True, None


def longest_url(bind: Engine) -> Optional[int]:
    """库里 url 的最大字符数；没有行时返回 None。"""
    length_fn = "CHAR_LENGTH" if bind.dialect.name == "mysql" else "LENGTH"
    with bind.connect() as conn:
        value = conn.execute(text(f"SELECT MAX({length_fn}({COLUMN})) FROM {TABLE}")).scalar()
    return int(value) if value is not None else None


def apply(bind: Engine) -> str:
    """自动迁移入口（启动引导调用）：幂等把 url 列迁到 TEXT，返回做了什么。

    与 CLI 共用 ``describe`` / ``plan_for`` 同一份判定 —— 引导与手工运维不会出现两套口径。
    """
    table_exists, current_type = describe(bind)
    plan = plan_for(
        dialect=bind.dialect.name,
        table_exists=table_exists,
        current_type=current_type,
    )
    if not plan.needed:
        return plan.reason
    with bind.begin() as conn:
        conn.execute(text(plan.statement))
    return f"{plan.reason}（已执行）"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=f"{TABLE}.{COLUMN} 列迁移（只改列型，不删行）")
    parser.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划（默认行为）")
    parser.add_argument("--rollback", action="store_true", help=f"回滚为 VARCHAR({OLD_LIMIT})")
    args = parser.parse_args(argv)

    table_exists, current_type = describe(default_engine)
    print(f"数据库：{default_engine.url.render_as_string(hide_password=True)}")
    print(f"当前列型：{TABLE}.{COLUMN} = {current_type if table_exists else '<表不存在>'}")

    if args.rollback:
        plan = rollback_for(
            dialect=default_engine.dialect.name,
            current_type=current_type,
            max_url_chars=longest_url(default_engine) if table_exists else None,
        )
        print(f"[回滚] {plan.reason}")
        if not plan.needed:
            return 1 if "拒绝执行" in plan.reason else 0
        print(f"  {plan.statement}")
        if not args.apply:
            print("（dry-run：加 --apply 执行）")
            return 0
        with default_engine.begin() as conn:
            conn.execute(text(plan.statement))
        print("回滚完成。行数据未删除。")
        return 0

    plan = plan_for(
        dialect=default_engine.dialect.name,
        table_exists=table_exists,
        current_type=current_type,
    )
    print(f"[迁移] {plan.reason}")
    if not plan.needed:
        return 0
    print(f"  {plan.statement}")
    if not args.apply:
        print("（dry-run：加 --apply 执行）")
        return 0
    with default_engine.begin() as conn:
        conn.execute(text(plan.statement))
    print("迁移完成。行数据未删除。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
