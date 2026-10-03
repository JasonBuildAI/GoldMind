"""消息板块译文列迁移：给 `news_digest_items` 加四个中文列。

2026-10-03 起消息板块会把英文标题与摘要交给 LLM 批量译成中文（标题 + 2–3 句导语），
译文与英文原文**并存**存储。四个新列全部可空：

    title_zh            VARCHAR(500)   中文标题；NULL = 尚未翻译
    brief_zh            TEXT           中文导语（压缩自来源摘要）
    translated_at       TIMESTAMP      这条译文何时产出
    translation_model   VARCHAR(100)   产出译文的模型名（换模型后可识别为陈旧）

为什么需要这个脚本：模型加了列，`Base.metadata.create_all` **不会**改既有的表
（`checkfirst` 只建缺失的表）。新库直接按新模型建表，老库必须显式补列 ——
不补的话，抓取到第一条消息就会 `no such column: news_digest_items.title_zh`。

只加列，**不删任何行、不改任何既有列**；旧代码看不见新列，回滚代码后照常工作。

用法：

    python scripts/migrate_news_digest_translation.py              # dry-run（默认）
    python scripts/migrate_news_digest_translation.py --apply      # 执行
    python scripts/migrate_news_digest_translation.py --rollback           # 打印回滚计划
    python scripts/migrate_news_digest_translation.py --rollback --apply   # 真删列（会丢译文）

回滚守卫：库里已经有译文时拒绝执行 —— 删列等于把译文全丢掉，那不是回滚，
是破坏性动作，必须先人工确认（把已知的译文导出或明确放弃）。
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

from sqlalchemy import Engine, inspect, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine as default_engine  # noqa: E402

TABLE = "news_digest_items"

# 顺序即 ALTER 的执行顺序；类型按方言给（两种库都接受这组写法）。
NEW_COLUMNS: tuple[tuple[str, str], ...] = (
    ("title_zh", "VARCHAR(500)"),
    ("brief_zh", "TEXT"),
    ("translated_at", "TIMESTAMP"),
    ("translation_model", "VARCHAR(100)"),
)


@dataclass
class Plan:
    """一次迁移计划：statements 为空表示无需动手。"""

    statements: list[str]
    reason: str

    @property
    def needed(self) -> bool:
        return bool(self.statements)


def plan_for(*, table_exists: bool, existing_columns: Sequence[str]) -> Plan:
    """升级判定（纯函数，测试不依赖任何真实数据库）。"""
    if not table_exists:
        return Plan([], f"表 {TABLE} 不存在：首次启动会按新模型建表，无需迁移")
    present = {name.lower() for name in existing_columns}
    missing = [(name, ddl) for name, ddl in NEW_COLUMNS if name.lower() not in present]
    if not missing:
        return Plan([], f"{TABLE} 四个译文列都已存在，无需迁移")
    statements = [f"ALTER TABLE {TABLE} ADD COLUMN {name} {ddl}" for name, ddl in missing]
    return Plan(statements, f"给 {TABLE} 补 {len(missing)} 个译文列：" + "、".join(n for n, _ in missing))


def rollback_for(*, table_exists: bool, existing_columns: Sequence[str], translated_rows: int) -> Plan:
    """回滚判定（纯函数）：会丢译文时拒绝执行。"""
    if not table_exists:
        return Plan([], f"表 {TABLE} 不存在，无需回滚")
    present = {name.lower() for name in existing_columns}
    dropping = [name for name, _ in NEW_COLUMNS if name.lower() in present]
    if not dropping:
        return Plan([], f"{TABLE} 没有译文列，无需回滚")
    if translated_rows > 0:
        return Plan(
            [],
            f"库里有 {translated_rows} 行已翻译的消息，删列会把译文全部丢掉，拒绝执行"
            "（要放弃译文请先人工导出或备份数据库）",
        )
    statements = [f"ALTER TABLE {TABLE} DROP COLUMN {name}" for name in dropping]
    return Plan(statements, f"从 {TABLE} 删掉 {len(dropping)} 个译文列（库里没有译文）")


def describe(bind: Engine) -> tuple[bool, list[str]]:
    """返回（表是否存在, 现有列名）。"""
    inspector = inspect(bind)
    if not inspector.has_table(TABLE):
        return False, []
    return True, [column["name"] for column in inspector.get_columns(TABLE)]


def translated_row_count(bind: Engine) -> int:
    """已翻译的行数；表或列不存在时按 0 计（没什么可丢的）。"""
    table_exists, columns = describe(bind)
    if not table_exists or "title_zh" not in {name.lower() for name in columns}:
        return 0
    with bind.connect() as conn:
        value = conn.execute(
            text(f"SELECT COUNT(*) FROM {TABLE} WHERE title_zh IS NOT NULL")
        ).scalar()
    return int(value or 0)


def apply(bind: Engine) -> str:
    """启动引导入口：幂等地补齐四个译文列，返回做了什么。

    与 CLI 共用 ``describe`` / ``plan_for`` 同一份判定 —— 引导与手工运维不会出现两套口径。
    """
    table_exists, columns = describe(bind)
    plan = plan_for(table_exists=table_exists, existing_columns=columns)
    if not plan.needed:
        return plan.reason
    with bind.begin() as conn:
        for statement in plan.statements:
            conn.execute(text(statement))
    return f"{plan.reason}（已执行）"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=f"{TABLE} 译文列迁移（只加列，不删行）")
    parser.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划（默认行为）")
    parser.add_argument("--rollback", action="store_true", help="打印 / 执行删列回滚")
    args = parser.parse_args(argv)

    table_exists, columns = describe(default_engine)
    print(f"数据库：{default_engine.url.render_as_string(hide_password=True)}")
    print(f"表 {TABLE}：{'存在' if table_exists else '不存在'}，现有 {len(columns)} 列")

    if args.rollback:
        plan = rollback_for(
            table_exists=table_exists,
            existing_columns=columns,
            translated_rows=translated_row_count(default_engine),
        )
        print(f"[回滚] {plan.reason}")
        if not plan.needed:
            return 1 if "拒绝执行" in plan.reason else 0
        for statement in plan.statements:
            print(f"  {statement}")
        if not args.apply:
            print("（dry-run：加 --apply 执行）")
            return 0
        with default_engine.begin() as conn:
            for statement in plan.statements:
                conn.execute(text(statement))
        print("回滚完成。行数据未删除（只有译文列被删）。")
        return 0

    plan = plan_for(table_exists=table_exists, existing_columns=columns)
    print(f"[迁移] {plan.reason}")
    if not plan.needed:
        return 0
    for statement in plan.statements:
        print(f"  {statement}")
    if not args.apply:
        print("（dry-run：加 --apply 执行）")
        return 0
    with default_engine.begin() as conn:
        for statement in plan.statements:
            conn.execute(text(statement))
    print("迁移完成。行数据未删除。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
