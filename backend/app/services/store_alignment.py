"""服务库 ↔ 本地研究长库的对齐（2.0.2 第 14 条）。

背景：本机有一份 26 年面板 `backend/goldmind-long.db`（gitignored 的本地研究副本，
供 `scripts/quant_lab.py` 离线放大样本用），服务库（SQLite / MySQL）是页面与调度器
真正读写的生产库。两者历史上由不同代际的回填脚本写入，出现了三类分歧：

1. **服务库缺日期** —— 长库有的历史日期服务库没有（研究副本先行）；
2. **长库缺日期 / 值过期** —— 服务库有、长库没有，或重叠日期数值不一致
   （典型：GPR 在旧版流水线里没有做发布滞后右移，整条序列错位一天）；
3. **键覆盖不同** —— 仅服务库或仅长库存在的序列（不强制对齐，如实报告）。

对齐方向是**不对称**的，因为两个库的角色不对称：

- 服务库缺的日期 → 从长库 **insert-only** 补入（历史回填，不动已有值；写入经
  `storage.upsert_series`，因此修订流水同样生成，`--as-of` 的语义保持正确）；
- 长库与服务库不一致的值 → **以服务库为准**覆盖长库。长库是派生出来的研究副本，
  跟随生产口径；反过来把可能过期的研究值写回生产库才是危险方向。
- 长库独有的日期**不删除**（append-only），`check_data_sanity --strict` 只把
  「重叠不一致」计为失败。

幂等：对齐后再次运行是 no-op。长库不存在（全新克隆 / CI）时直接返回 absent。
"""
from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger
from sqlalchemy import Engine, create_engine, inspect, select, text

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_LONG_DB = BACKEND_DIR / "goldmind-long.db"

# 与 scripts/check_data_sanity.py 同一判据：相对误差 > tolerance 才算不一致
DEFAULT_TOLERANCE = 1e-6


def _as_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text_value = str(value)[:10]
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text_value, fmt).date()
        except ValueError:
            continue
    return None


def _value_differs(a: float, b: float, tolerance: float) -> bool:
    denominator = max(1.0, abs(a), abs(b))
    return abs(a - b) / denominator > tolerance


def _load_rows(connection, table: str = "factor_observations") -> Dict[str, Dict[date, dict]]:
    """``{factor_key: {obs_date: {"value": float, "source": str|None}}}``。"""
    rows: Dict[str, Dict[date, dict]] = {}
    for key, obs_date, value, source in connection.execute(
        text(f"SELECT factor_key, obs_date, value, source FROM {table}")
    ):
        day = _as_date(obs_date)
        if key is None or day is None or value is None:
            continue
        rows.setdefault(str(key), {})[day] = {
            "value": float(value),
            "source": None if source is None else str(source),
        }
    return rows


def align_stores(
    service_engine: Engine,
    *,
    long_db: Optional[Path] = None,
    tolerance: float = DEFAULT_TOLERANCE,
) -> Dict[str, Any]:
    """执行双向对齐；返回统计与对齐前的分歧摘要。"""
    long_path = Path(long_db) if long_db is not None else DEFAULT_LONG_DB
    if not long_path.exists():
        return {"status": "absent", "long_db": str(long_path)}

    long_engine = create_engine(f"sqlite:///{long_path.as_posix()}")
    try:
        tables = set(inspect(long_engine).get_table_names())
        if "factor_observations" not in tables:
            return {"status": "absent", "long_db": str(long_path), "note": "长库没有 factor_observations 表"}

        with service_engine.connect() as service_conn, long_engine.connect() as long_conn:
            service_rows = _load_rows(service_conn)
            long_rows = _load_rows(long_conn)

        stats = {
            "status": "done",
            "long_db": str(long_path),
            "keys_checked": 0,
            "conflicts_before": 0,
            "updated_in_long": 0,
            "inserted_into_long": 0,
            "inserted_into_service": 0,
            "worst_conflict": None,
        }

        long_conn = sqlite3.connect(str(long_path))
        try:
            for key in sorted(set(service_rows) | set(long_rows)):
                service = service_rows.get(key, {})
                long = long_rows.get(key, {})
                if not service and not long:
                    continue
                stats["keys_checked"] += 1

                # 1) 长库 → 服务库：只补服务库缺的日期（insert-only）
                missing = [day for day in sorted(long) if day not in service]
                if missing:
                    _insert_missing_into_service(service_engine, key, {day: long[day] for day in missing})
                    stats["inserted_into_service"] += len(missing)

                # 2) 服务库 → 长库：冲突覆盖 + 长库缺的日期补入
                updates: list[tuple[float, str, str, str]] = []
                for day, entry in service.items():
                    existing = long.get(day)
                    if existing is None:
                        # 列顺序必须与下面的 INSERT 一致：(factor_key, obs_date, value, source)
                        updates.append((key, day.isoformat(), entry["value"], entry["source"] or "服务库"))
                        stats["inserted_into_long"] += 1
                        continue
                    if _value_differs(entry["value"], existing["value"], tolerance):
                        relative = abs(entry["value"] - existing["value"]) / max(
                            1.0, abs(entry["value"]), abs(existing["value"])
                        )
                        stats["conflicts_before"] += 1
                        stats["updated_in_long"] += 1
                        if stats["worst_conflict"] is None or relative > stats["worst_conflict"]["relative_diff"]:
                            stats["worst_conflict"] = {
                                "factor_key": key,
                                "obs_date": day.isoformat(),
                                "service": entry["value"],
                                "long": existing["value"],
                                "relative_diff": round(relative, 8),
                            }
                        updates.append((key, day.isoformat(), entry["value"], entry["source"] or "服务库"))
                if updates:
                    with long_conn:
                        long_conn.executemany(
                            "INSERT INTO factor_observations "
                            "(factor_key, obs_date, value, source) VALUES (?, ?, ?, ?) "
                            "ON CONFLICT(factor_key, obs_date) DO UPDATE SET "
                            "value=excluded.value, source=excluded.source, updated_at=CURRENT_TIMESTAMP",
                            updates,
                        )

        finally:
            long_conn.close()

        logger.info(
            f"[对齐] 服务库补入 {stats['inserted_into_service']} 行；"
            f"长库更新 {stats['updated_in_long']} 行（对齐前冲突 {stats['conflicts_before']} 行）"
        )
        return stats
    finally:
        long_engine.dispose()


def _insert_missing_into_service(engine: Engine, key: str, rows: Dict[date, dict]) -> None:
    """把长库独有的历史日期补进服务库（经 upsert_series，带修订流水）。"""
    import pandas as pd

    from app.services.quant import storage

    series = pd.Series(
        {pd.Timestamp(day): entry["value"] for day, entry in sorted(rows.items())},
        name=key,
    )
    sources = {entry["source"] for entry in rows.values() if entry["source"]}
    source = next(iter(sources)) if len(sources) == 1 else "长库对齐"
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        storage.upsert_series(db, key, series, source=source, commit=True)
    finally:
        db.close()