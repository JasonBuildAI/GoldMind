#!/usr/bin/env python3
"""为端到端测试准备一个 SQLite 数据库，并填入确定性的示例数据。

为什么要单独写这个：端到端测试需要后端真的跑起来，而后端默认连 MySQL。
本脚本让整条链路（浏览器 → 前端 → 后端 → 数据库）都能在没有 MySQL 的
环境下跑通，且数据是固定的，因此断言可以精确。

用法：
    python scripts/dev_seed_sqlite.py --db e2e.db

数据（与 backend/tests/e2e/test_full_flow.py 保持一致）：
    金价  2025-01-02 起连续 10 个交易日，2600 起、每步 +10 → 最后一天 2690
    美元指数 同步 10 天
    新闻  3 条，发布于 1 小时前
    消息  3 条：一组同题报道（两家来源，1-2 小时前）+ 一条 26 小时前的消息
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DAYS = 10
START_PRICE = 2600.0
STEP = 10.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(BACKEND_DIR / "e2e.db"))
    parser.add_argument("--days", type=int, default=DAYS)
    args = parser.parse_args()

    db_path = Path(args.db)

    # 必须在导入 app.* 之前设置，否则 app.config 会用 .env 里的 MySQL 地址
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["SCHEDULER_ENABLED"] = "false"

    import app.models  # noqa: F401  注册全部模型
    from app.database import Base, SessionLocal, engine
    from app.models.gold_price import DollarIndex, GoldPrice
    from app.models.news import GoldNews, SentimentType
    from app.models.news_digest import NewsDigestItem
    from app.utils import timeutil

    # 用 drop_all + create_all 重建，而不是删除数据库文件：
    # Windows 上若后端进程仍持有该文件，unlink 会抛 WinError 32。
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    base = date(2025, 1, 2)
    for i in range(args.days):
        day = base + timedelta(days=i)
        price = START_PRICE + STEP * i
        db.add(
            GoldPrice(
                date=day,
                open_price=price,
                high_price=price + 5,
                low_price=price - 5,
                close_price=price,
                volume=1000 + i,
                change_percent=0.5,
            )
        )
        db.add(
            DollarIndex(
                date=day,
                open_price=108.0 - i * 0.1,
                high_price=108.2 - i * 0.1,
                low_price=107.8 - i * 0.1,
                close_price=108.0 - i * 0.1,
            )
        )

    now = datetime.now()
    for i in range(3):
        db.add(
            GoldNews(
                title=f"端到端新闻 {i}",
                content=f"端到端新闻内容 {i}",
                source="E2E",
                url=f"https://example.invalid/e2e/{i}",
                published_at=now - timedelta(hours=1 + i),
                sentiment=SentimentType.NEUTRAL,
            )
        )

    db.commit()

    # 消息板块：一组同题报道（两家来源）+ 一条只在 7 天窗口出现（26 小时前）的消息。
    # 时间用项目时区（timeutil），与窗口口径一致。
    digest_now = timeutil.now_naive()
    digest_rows = [
        ("Gold hits record high on central bank buying", "路透社", "reuters", 1, 1.5),
        ("Gold hits record high on central bank demand", "美联社", "ap", 1, 1.2),
        ("Gold steadies ahead of US payrolls data", "Kitco News", "kitco news", 2, 26.0),
    ]
    for index, (title, source, source_key, tier, hours_ago) in enumerate(digest_rows):
        db.add(
            NewsDigestItem(
                title=title,
                summary=f"端到端消息摘要 {index}",
                source=source,
                source_key=source_key,
                authority_tier=tier,
                url=f"https://example.invalid/e2e/digest/{index}",
                published_at=digest_now - timedelta(hours=hours_ago),
                fetched_at=digest_now,
            )
        )
    db.commit()
    db.close()

    print(
        f"[seed] {db_path} 已就绪：{args.days} 天行情 + 3 条新闻 + {len(digest_rows)} 条消息",
        flush=True,
    )
    print(f"[seed] 最后收盘价应为 {START_PRICE + STEP * (args.days - 1):.2f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
