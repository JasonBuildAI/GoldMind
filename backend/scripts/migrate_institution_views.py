"""机构观点的数据库迁移：只加列、只补数据，**不删任何行**。

背景：`institution_views` 里长期存在两套名字 —— 规范名
（`高盛 (Goldman Sachs)`）与别名（`Goldman Sachs`）。2026-10-01 06:01 的一次
抓取没有找到新研报，把规范行的真实目标价覆盖成了「暂无」，而真实的
5400 / 5000 / 6300 / 6000 只留在别名行里（updated_at = 2026-02-08）。
本脚本把两边接上：

1. 加两列：`as_of_date DATE NULL`、`source VARCHAR(50) NULL`；
2. 回填 `as_of_date = DATE(updated_at)`（历史行没有更可靠的日期来源，
   如实标注「最近一次核实」为入库时间）；
3. 把别名行里**最新的真实预测**复制进规范行（source=legacy）——只在规范行
   缺失真实目标价时执行；规范行已有真实数据则不动，绝不覆盖。

不删除任何行：别名行留在库里作历史记录，读取侧按机构注册表只认规范行
（见 `app/services/institution_prediction_service.py`）。

用法：

    python scripts/migrate_institution_views.py              # dry-run（默认）
    python scripts/migrate_institution_views.py --apply      # 执行
    python scripts/migrate_institution_views.py --drop-columns           # 打印回滚计划
    python scripts/migrate_institution_views.py --drop-columns --apply   # 回滚（删两列，不删行）
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import Engine, inspect, text  # noqa: E402

import app.models  # noqa: F401,E402  确保所有模型都已注册到 metadata
from app.database import Base, engine as default_engine  # noqa: E402
from app.services.institution_prediction_service import INSTITUTIONS, match_institution  # noqa: E402

TABLE = "institution_views"
NEW_COLUMNS = ("as_of_date", "source")


@dataclass
class CopyPlan:
    """把一条别名行的真实预测复制进规范行。"""

    canonical_name: str
    alias_name: str
    action: str  # "insert"（规范行不存在）或 "update"（规范行存在但没有真实目标价）
    target_price: float
    as_of_date: Optional[date]
    rating: str
    timeframe: str
    reasoning: str
    key_points: Any
    updated_at: Any


@dataclass
class MigrationPlan:
    statements: List[str] = field(default_factory=list)
    backfill: List[tuple] = field(default_factory=list)  # [(id, date)]
    copies: List[CopyPlan] = field(default_factory=list)


def _existing_columns(bind: Engine) -> set[str]:
    return {col["name"].lower() for col in inspect(bind).get_columns(TABLE)}


def missing_columns(bind: Engine) -> List[tuple[str, str]]:
    """模型里有、库里没有的新增列，[(列名, 类型 SQL)]。"""
    existing = _existing_columns(bind)
    table = Base.metadata.tables[TABLE]
    missing: List[tuple[str, str]] = []
    for name in NEW_COLUMNS:
        if name in existing:
            continue
        column = table.columns[name]
        missing.append((column.name, column.type.compile(dialect=bind.dialect)))
    return missing


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text_value = str(value).strip()
    if not text_value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text_value[:19], fmt).date()
        except ValueError:
            continue
    return None


def _load_rows(bind: Engine) -> List[Dict[str, Any]]:
    existing = _existing_columns(bind)
    columns = [
        "id", "institution_name", "logo", "rating", "target_price",
        "timeframe", "reasoning", "key_points", "updated_at",
    ]
    for optional in NEW_COLUMNS:
        if optional in existing:
            columns.append(optional)

    with bind.connect() as conn:
        result = conn.execute(text(f"SELECT {', '.join(columns)} FROM {TABLE} ORDER BY id"))
        return [dict(row._mapping) for row in result]


def build_plan(bind: Engine) -> MigrationPlan:
    """纯读取：算出要执行的 DDL、要回填的行、要复制的别名预测。"""
    plan = MigrationPlan()
    plan.statements = [
        f"ALTER TABLE {TABLE} ADD COLUMN {name} {type_sql}"
        for name, type_sql in missing_columns(bind)
    ]

    rows = _load_rows(bind)

    for row in rows:
        if row.get("as_of_date") is not None:
            continue
        day = _as_date(row.get("updated_at"))
        if day is not None:
            plan.backfill.append((row["id"], day))

    by_name = {row["institution_name"]: row for row in rows}
    for inst in INSTITUTIONS:
        alias_rows = [
            row
            for row in rows
            if row["institution_name"] != inst.name
            and match_institution(row["institution_name"]) is inst
            and row.get("target_price") is not None
        ]
        if not alias_rows:
            continue

        best = max(
            alias_rows,
            key=lambda row: (_as_date(row.get("updated_at")) or date.min, row["id"]),
        )
        canonical = by_name.get(inst.name)
        if canonical is not None and canonical.get("target_price") is not None:
            continue  # 规范行已有真实数据：不覆盖

        plan.copies.append(
            CopyPlan(
                canonical_name=inst.name,
                alias_name=best["institution_name"],
                action="update" if canonical is not None else "insert",
                target_price=float(best["target_price"]),
                as_of_date=_as_date(best.get("updated_at")),
                rating=best.get("rating") or "neutral",
                timeframe=best.get("timeframe") or "",
                reasoning=best.get("reasoning") or "",
                key_points=best.get("key_points"),
                updated_at=best.get("updated_at"),
            )
        )

    return plan


def apply_migration(bind: Engine, dry_run: bool = False) -> MigrationPlan:
    """执行迁移；dry_run 时只返回计划，不落任何写操作。重复执行安全。"""
    plan = build_plan(bind)
    if dry_run:
        return plan

    with bind.begin() as conn:
        for statement in plan.statements:
            conn.execute(text(statement))

    if plan.backfill or plan.copies:
        with bind.begin() as conn:
            for row_id, day in plan.backfill:
                conn.execute(
                    text(f"UPDATE {TABLE} SET as_of_date = :day WHERE id = :id AND as_of_date IS NULL"),
                    {"day": day.isoformat() if day else None, "id": row_id},
                )
            for copy in plan.copies:
                payload = {
                    "name": copy.canonical_name,
                    "rating": copy.rating,
                    "target_price": copy.target_price,
                    "timeframe": copy.timeframe,
                    "reasoning": copy.reasoning,
                    "key_points": copy.key_points,
                    "as_of_date": copy.as_of_date.isoformat() if copy.as_of_date else None,
                    "updated_at": copy.updated_at,
                }
                if copy.action == "update":
                    conn.execute(
                        text(
                            f"UPDATE {TABLE} SET rating = :rating, target_price = :target_price,"
                            " timeframe = :timeframe, reasoning = :reasoning, key_points = :key_points,"
                            " as_of_date = :as_of_date, source = 'legacy', updated_at = :updated_at"
                            " WHERE institution_name = :name"
                        ),
                        payload,
                    )
                else:
                    conn.execute(
                        text(
                            f"INSERT INTO {TABLE} (institution_name, rating, target_price, timeframe,"
                            " reasoning, key_points, as_of_date, source, updated_at)"
                            " VALUES (:name, :rating, :target_price, :timeframe, :reasoning,"
                            " :key_points, :as_of_date, 'legacy', :updated_at)"
                        ),
                        payload,
                    )

    return plan


def drop_columns(bind: Engine, dry_run: bool = True) -> List[str]:
    """回滚：删掉本脚本新增的两列（不删任何行）。"""
    existing = _existing_columns(bind)
    statements = [
        f"ALTER TABLE {TABLE} DROP COLUMN {name}"
        for name in NEW_COLUMNS
        if name in existing
    ]
    if not dry_run:
        with bind.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
    return statements


def _print_plan(plan: MigrationPlan) -> None:
    print("计划（dry-run，不会执行任何写操作）：")
    if not plan.statements and not plan.backfill and not plan.copies:
        print("  无需迁移：两列已存在，且没有可回填/可复制的数据。")
        return
    for statement in plan.statements:
        print(f"  {statement}")
    if plan.backfill:
        print(f"  回填 as_of_date = DATE(updated_at)：{len(plan.backfill)} 行")
    if plan.copies:
        print(f"  复制别名真实预测 → 规范行：{len(plan.copies)} 行")
        for copy in plan.copies:
            day = copy.as_of_date.isoformat() if copy.as_of_date else "无"
            print(
                f"    [{copy.action}] {copy.canonical_name} ← {copy.alias_name}："
                f"target={copy.target_price}，as_of={day}"
            )
    print()
    print("执行：python scripts/migrate_institution_views.py --apply")


def main() -> int:
    try:  # Windows 控制台默认可能是 GBK，中文计划会直接抛 UnicodeEncodeError
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="institution_views 迁移（只加列/补数据，不删行）")
    parser.add_argument("--apply", action="store_true", help="真正执行（默认 dry-run）")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划（默认行为）")
    parser.add_argument("--drop-columns", action="store_true", help="回滚：删除 as_of_date / source 两列")
    args = parser.parse_args()

    if args.drop_columns:
        statements = drop_columns(default_engine, dry_run=not args.apply)
        if not statements:
            print("无需回滚：两列不存在。行数据未做任何改动。")
        elif args.apply:
            print("已删除以下列（行数据全部保留）：")
            for statement in statements:
                print(f"  {statement}")
        else:
            print("回滚计划（未执行；加 --apply 才真正删列，行数据保留）：")
            for statement in statements:
                print(f"  {statement}")
        return 0

    plan = apply_migration(default_engine, dry_run=not args.apply)
    if args.apply:
        print(
            f"完成：DDL {len(plan.statements)} 条，回填 {len(plan.backfill)} 行，"
            f"复制 {len(plan.copies)} 行；没有删除任何行。"
        )
    else:
        _print_plan(plan)
    return 0


if __name__ == "__main__":
    sys.exit(main())
