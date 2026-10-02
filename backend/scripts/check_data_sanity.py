#!/usr/bin/env python
"""数据体检：未来日期 / 非法数值 / 跨库一致性（spec 2026-10-03 第 16 条）。

用法（在 backend 目录下）：

    python scripts/check_data_sanity.py                  # 只体检，不改数据
    python scripts/check_data_sanity.py --strict         # 跨库偏差也算失败
    python scripts/check_data_sanity.py --fix            # 删除未来日期观测（先备份！）
    python scripts/check_data_sanity.py --long-db path/to/long.db

退出码：0 = 干净；1 = 有发现（或 --strict 下有跨库偏差）；2 = 库打不开。
`--fix` 只删「观测日期晚于今天」的行，且会打印删除行数与回滚提示；
改库前必须先把库文件备份到仓库外（见 `scripts/backup_db.py` 与
`docs/specs/2026-10-03-第三轮评审整改.md` 的回滚约定）。
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402
from app.services import data_sanity  # noqa: E402
from app.utils import timeutil  # noqa: E402

DEFAULT_LONG_DB = BACKEND_DIR / "goldmind-long.db"
MAX_DETAIL_LINES = 20

KIND_LABELS = {
    "future": "未来日期",
    "nonfinite": "非法数值（NaN/inf）",
    "bounds": "越过合理性区间",
    "duplicate": "重复键",
}


def _report_findings(lines: list[str], label: str, findings: list[data_sanity.Finding]) -> None:
    if not findings:
        lines.append(f"[{label}] 无发现")
        return
    by_kind: dict[str, int] = {}
    for finding in findings:
        by_kind[finding.kind] = by_kind.get(finding.kind, 0) + 1
    summary = "；".join(f"{KIND_LABELS.get(kind, kind)} {count} 条" for kind, count in sorted(by_kind.items()))
    lines.append(f"[{label}] {summary}")
    for finding in findings[:MAX_DETAIL_LINES]:
        lines.append(f"  - {finding.detail}")
    if len(findings) > MAX_DETAIL_LINES:
        lines.append(f"  - ……另有 {len(findings) - MAX_DETAIL_LINES} 条，未逐条展开")


def run(
    database_url: Optional[str] = None,
    long_db: Optional[Path] = None,
    *,
    fix: bool = False,
    strict: bool = False,
    tolerance: float = 1e-6,
    today: Optional[date] = None,
) -> tuple[int, list[str]]:
    """体检（可选修复）。返回 (退出码, 报告行)；测试直接调用这个入口。"""
    lines: list[str] = []
    today = today or timeutil.today()
    url = database_url or settings.DATABASE_URL
    # settings.DATABASE_URL 是 SecretStr（防日志泄露）；这里必须显式解包。
    if hasattr(url, "get_secret_value"):
        url = url.get_secret_value()

    try:
        engine = create_engine(url)
        connection = engine.connect()
        connection.close()
    except Exception as exc:  # 库不可达：如实报告，不猜
        return 2, [f"服务库打不开（{url.split('@')[-1]}）：{exc}"]

    with Session(engine) as session:
        findings = data_sanity.audit_service_store(session, today=today)
        if fix and any(finding.kind == "future" for finding in findings):
            deleted = data_sanity.purge_future_observations(session, today=today)
            lines.append(f"[服务库] 已删除 {deleted} 行未来日期观测；回滚：用备份库覆盖本库")
            findings = data_sanity.audit_service_store(session, today=today)
        _report_findings(lines, f"服务库 {url.split('@')[-1]}（今天 {today.isoformat()}）", findings)
        service_problems = len(findings)

        mismatches = 0
        long_path = long_db
        if long_path is None:
            lines.append("[长库] 未提供长库路径，跳过跨库检查")
        elif not Path(long_path).exists():
            return 2, lines + [f"[长库] 文件不存在：{long_path}"]
        else:
            long_connection = sqlite3.connect(str(long_path))
            try:
                long_findings = data_sanity.audit_long_store(long_connection, today=today)
                if fix and any(finding.kind == "future" for finding in long_findings):
                    deleted = data_sanity.purge_long_future_observations(long_connection, today=today)
                    lines.append(f"[长库] 已删除 {deleted} 行未来日期观测；回滚：用备份文件覆盖本文件")
                    long_findings = data_sanity.audit_long_store(long_connection, today=today)
                _report_findings(lines, f"长库 {Path(long_path).name}", long_findings)
                service_problems += len(long_findings)

                report = data_sanity.compare_stores(session, long_connection, tolerance=tolerance)
                mismatches = report["mismatch_total"]
                lines.append(
                    "[跨库一致性] 共同因子 {common}：服务库 {service} / 长库 {long}；"
                    "仅服务库 {only_service}；仅长库 {only_long}；重叠不一致 {mismatch}".format(
                        common=report["common_keys"],
                        service=report["service_keys"],
                        long=report["long_keys"],
                        only_service=report["only_service"] or "无",
                        only_long=report["only_long"] or "无",
                        mismatch=mismatches,
                    )
                )
                for item in report["keys"]:
                    lines.append(
                        f"  - {item['factor_key']}：重叠 {item['overlap']} 行，不一致 "
                        f"{item['mismatched']} 行；最差 {item['worst']['obs_date']} "
                        f"服务库 {item['worst']['service']} vs 长库 {item['worst']['long']}"
                        f"（相对偏差 {item['worst']['relative_diff']}）"
                    )
            finally:
                long_connection.close()

    if service_problems:
        return 1, lines + [f"结论：发现 {service_problems} 条结构性问题（--fix 可清理未来日期）"]
    if strict and mismatches:
        return 1, lines + [f"结论：--strict 下跨库不一致 {mismatches} 行，需要人工核对"]
    return 0, lines + ["结论：体检通过"]


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="数据体检：未来日期 / 非法数值 / 跨库一致性")
    parser.add_argument("--long-db", type=Path, default=None, help=f"长库路径（默认 {DEFAULT_LONG_DB.name}）")
    parser.add_argument("--fix", action="store_true", help="删除未来日期观测（不可逆，先备份）")
    parser.add_argument("--strict", action="store_true", help="跨库不一致也算失败")
    parser.add_argument("--tolerance", type=float, default=1e-6, help="跨库重叠值的相对容差（默认 1e-6）")
    args = parser.parse_args(argv)

    long_db = args.long_db or (DEFAULT_LONG_DB if DEFAULT_LONG_DB.exists() else None)
    code, lines = run(long_db=long_db, fix=args.fix, strict=args.strict, tolerance=args.tolerance)
    for line in lines:
        print(line)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
