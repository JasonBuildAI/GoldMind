#!/usr/bin/env python3
"""量化因子历史回填：连续多轮同步，把各源能提供的长历史一次补齐。

为什么需要单独的回填入口：

- 常规同步走增量：单轮最多补 3 个缺口年（防止一次抓取超时）。首次安装、
  或修完数据缺口之后，需要连续多轮才能把 10–20 年窗口铺满。
- 回填必须可重复执行：重复运行只做 upsert，不产生重复行。
  ``--dry-run`` 先看清每个序列的年份覆盖与缺口，再决定是否 ``--apply``。

用法：
    python scripts/backfill_quant.py --dry-run --years 20
    python scripts/backfill_quant.py --apply --years 20 --rounds 8

``--apply`` 会真实访问数据源（需要网络）；测试通过注入假 fetcher 完全离线。
回填不写 ``quant_sync_report`` 缓存 —— 那是「最近一轮常规同步」的状态，
不该被回填覆盖。
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Callable, Optional

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal, init_db  # noqa: E402
from app.services.quant import storage, sync  # noqa: E402
from app.services.quant.definitions import BENCHMARK_KEY, EXTRA_SERIES, FACTORS  # noqa: E402
from app.utils import timeutil  # noqa: E402

DEFAULT_YEARS = 20
DEFAULT_ROUNDS = 8
MAX_GAP_PREVIEW = 8


def series_keys() -> list[str]:
    """回填关心的全部序列：因子 + 基准 + 仪表盘额外序列。"""
    return [item.key for item in FACTORS] + [BENCHMARK_KEY] + [item.key for item in EXTRA_SERIES]


def coverage_rows(db, *, years: int, today: date) -> list[dict]:
    window = range(today.year - years, today.year + 1)
    return [storage.coverage(db, key, window=window) for key in series_keys()]


def _preview(years: list[int]) -> str:
    if not years:
        return "无"
    head = ", ".join(str(year) for year in years[:MAX_GAP_PREVIEW])
    return head if len(years) <= MAX_GAP_PREVIEW else f"{head} …（共 {len(years)} 年）"


def format_coverage(rows: list[dict], *, years: int, today: date) -> str:
    lines = [f"序列覆盖（窗口 {today.year - years}–{today.year}；缺口 = 窗口内的稀疏年）:"]
    for row in rows:
        if row["observations"] == 0:
            state = "无数据"
        elif row["accumulating"]:
            state = "积累期"
        elif row["sparse_years"]:
            state = "有缺口"
        else:
            state = "完整"
        lines.append(
            f"  {row['factor_key']:<28} 观测 {row['observations']:>7} | "
            f"有数据年份 {len(row['years']):>2} | {state} | 缺口年: {_preview(row['sparse_years'])}"
        )
    return "\n".join(lines)


def _report_totals(report) -> tuple[int, int]:
    inserted = updated = 0
    for bucket in (report.factor_status, report.extra_status):
        for item in bucket.values():
            if item.get("status") == "ok":
                inserted += int(item.get("rows_inserted") or 0)
                updated += int(item.get("rows_updated") or 0)
    return inserted, updated


def run_backfill(
    db,
    *,
    years: int = DEFAULT_YEARS,
    rounds: int = DEFAULT_ROUNDS,
    today: Optional[date] = None,
    fetchers: Optional[dict] = None,
    sync_fn: Callable = sync.run_sync,
    emit: Callable[[str], None] = print,
) -> dict:
    """连续回填，直到窗口内无缺口、某轮没有新增、或到达轮次上限。

    返回汇总：轮数、累计新增 / 修订行数、停止原因、最终覆盖报告。
    """
    today = today or timeutil.today()
    result = {"rounds": 0, "inserted": 0, "updated": 0, "stopped_reason": "max_rounds"}
    for index in range(1, rounds + 1):
        report = sync_fn(
            db,
            force=True,
            history_years=years,
            today=today,
            fetchers=fetchers,
            use_cache_report=False,
        )
        inserted, updated = _report_totals(report)
        result["rounds"] = index
        result["inserted"] += inserted
        result["updated"] += updated
        remaining = sum(
            len(row["sparse_years"]) for row in coverage_rows(db, years=years, today=today)
        )
        emit(f"[第 {index}/{rounds} 轮] 新增 {inserted} 行 / 修订 {updated} 行；剩余缺口年 {remaining}")
        if remaining == 0:
            result["stopped_reason"] = "no_gaps"
            break
        if inserted == 0:
            result["stopped_reason"] = "no_progress"
            break
    result["coverage"] = coverage_rows(db, years=years, today=today)
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="量化因子历史回填（可重复执行）")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="只读：打印每个序列的年份覆盖与缺口")
    mode.add_argument("--apply", action="store_true", help="真实抓取并写入（需要网络）")
    parser.add_argument(
        "--years", type=int, default=DEFAULT_YEARS, help=f"回填窗口年数（默认 {DEFAULT_YEARS}）"
    )
    parser.add_argument(
        "--rounds", type=int, default=DEFAULT_ROUNDS, help=f"最大轮数（默认 {DEFAULT_ROUNDS}）"
    )
    args = parser.parse_args(argv)

    init_db()
    db = SessionLocal()
    try:
        today = timeutil.today()
        if args.dry_run:
            rows = coverage_rows(db, years=args.years, today=today)
            print(format_coverage(rows, years=args.years, today=today))
            print("dry-run：只读，不抓取、不写库。")
            return 0

        result = run_backfill(db, years=args.years, rounds=args.rounds, today=today)
        print(format_coverage(result["coverage"], years=args.years, today=today))
        print(
            f"完成 {result['rounds']} 轮（{result['stopped_reason']}）："
            f"累计新增 {result['inserted']} 行 / 修订 {result['updated']} 行"
        )
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
