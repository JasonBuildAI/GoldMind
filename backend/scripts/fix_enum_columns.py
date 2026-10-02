#!/usr/bin/env python3
"""把历史遗留的枚举列取值修正为与 SQLAlchemy 模型一致。

## 背景

`schema.sql` 曾经把枚举列声明成小写：

    sentiment ENUM('positive', 'negative', 'neutral')

而 `Column(Enum(SentimentType))` 存的是**枚举名** —— `POSITIVE`。
MySQL 的 ENUM 比较不区分大小写，所以写入**不会报错**：它会成功，并被规范成
小写存下来。但读回来时 SQLAlchemy 按枚举名查 `'positive'`，查不到，直接抛

    LookupError: 'neutral' is not among the defined enum values

表现为「写得进去、读不出来」：`/api/gold/news`、`/api/gold/factors` 全部 500。

`schema.sql` 已修正，**新库不会再有问题**；这个脚本用于修正**已经建好的旧库**。

## 用法

    cd backend
    python scripts/fix_enum_columns.py            # 修正（幂等）
    python scripts/fix_enum_columns.py --dry-run  # 只看会改什么

库连接取自 `DATABASE_URL`（与后端应用、`init_db.py` 同一个来源），
也可以直接给 `--database-url` 覆盖。

## 回滚

修正前的取值会打印出来。要回滚就把 ENUM 列表改回小写即可 ——
但因为旧取值正是导致读取失败的原因，正常情况下不需要回滚。
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from typing import Optional

# (表, 列, 期望的取值) —— 期望值就是 SQLAlchemy 存进去的枚举名
TARGETS: list[tuple[str, str, list[str]]] = [
    ("gold_news", "sentiment", ["POSITIVE", "NEGATIVE", "NEUTRAL"]),
    ("market_factors", "type", ["BULLISH", "BEARISH"]),
    ("market_factors", "impact", ["HIGH", "MEDIUM", "LOW"]),
]


def _connect(database_url: Optional[str], dry_run: bool):
    import pymysql

    if database_url:
        from urllib.parse import urlparse

        parsed = urlparse(database_url)
        return pymysql.connect(
            host=parsed.hostname or "localhost",
            port=parsed.port or 3306,
            user=parsed.username or "root",
            password=parsed.password or "",
            database=(parsed.path or "/").lstrip("/") or None,
            charset="utf8mb4",
            autocommit=not dry_run,
        )

    # 与 init_db.py / seed_data.py 用同一个来源，避免各说各话
    from app.database import mysql_connection_params

    return pymysql.connect(
        **mysql_connection_params(include_database=True),
        autocommit=not dry_run,
    )


def _current_values(column_type: str) -> list[str]:
    return re.findall(r"'([^']*)'", column_type)


def fix_column(cur, table: str, column: str, wanted: list[str], dry_run: bool) -> str:
    cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE %s", (column,))
    row = cur.fetchone()
    if not row:
        return f"跳过（{table}.{column} 不存在）"

    _, column_type, nullable, _, default, _ = row
    current = _current_values(column_type)

    if current == wanted:
        return f"已一致，无需修改（{current}）"

    # 已有数据先转成大写，避免 ALTER 时匹配不上而被清成空串
    cur.execute(
        f"UPDATE `{table}` SET `{column}` = UPPER(`{column}`) "
        f"WHERE `{column}` IS NOT NULL"
    )
    moved = cur.rowcount

    definition = "ENUM(" + ", ".join(f"'{v}'" for v in wanted) + ")"
    definition += " NULL" if nullable == "YES" else " NOT NULL"
    if default is not None:
        definition += f" DEFAULT '{str(default).upper()}'"

    if dry_run:
        return f"将执行 ALTER（当前 {current} -> {wanted}，会改写 {moved} 行）"

    cur.execute(f"ALTER TABLE `{table}` MODIFY COLUMN `{column}` {definition}")
    return f"已修正（{current} -> {wanted}，改写 {moved} 行）"


def main() -> int:
    try:  # Windows 控制台默认可能是 GBK，直接打印 emoji 会抛 UnicodeEncodeError
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="修正枚举列取值，使其与模型一致")
    parser.add_argument("--dry-run", action="store_true", help="只显示会做什么")
    parser.add_argument("--database-url", default=None, help="覆盖库连接")
    args = parser.parse_args()

    try:
        conn = _connect(args.database_url, args.dry_run)
    except Exception as exc:
        print(f"❌ 连不上数据库: {exc}")
        return 1

    print("=" * 64)
    print("修正枚举列取值" + ("（dry-run，不会写入）" if args.dry_run else ""))
    print("=" * 64)

    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DATABASE()")
            print(f"数据库: {cur.fetchone()[0]}\n")
            for table, column, wanted in TARGETS:
                print(f"  {table}.{column}: {fix_column(cur, table, column, wanted, args.dry_run)}")
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    print("\n✅ 完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
