"""数据体检：未来日期、非法数值、重复键、跨库一致性（服务库 ↔ 长库）。

第三轮评审（`docs/specs/2026-10-03-第三轮评审整改.md` 第 16 条）：

- 观测日期不得晚于今天。实际事故：长库 `etf_shares` 的唯一一行是
  2026-10-05（未来日期），任何按日期切分的回测都会把它当成「已知未来」。
- 数值域校验：NaN / ±inf 与越过宽松合理性区间的值必须能被点名。
- 跨库一致性：同一因子在两个库的重叠日期上偏差超阈值就报警 ——
  「同一指标两套数字」正是评审点名的问题。

这里只做**体检与报告**，不代替写库时的守卫（存储层的未来日期闸门另有一层）；
本模块负责发现历史遗留与跨库偏差，脚本入口 `scripts/check_data_sanity.py`。
"""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass
from datetime import date
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.analysis import FactorObservation
from app.utils import timeutil

# 宽松合理性区间：只拦「物理上不可能」的值，不做信号筛选，也不是预测。
# 未列出的因子只做有限性检查 —— 宁可漏报，也不许凭印象定界。
SANITY_BOUNDS: dict[str, tuple[float, float]] = {
    "gold_close": (100.0, 100_000.0),
    # 2001 年人民币金价约 71 元/克，是真实历史值；下限必须覆盖早期黄金牛市前的价格。
    "cny_gold": (20.0, 1_000_000.0),
    "dollar_index": (50.0, 200.0),
    "usdcny": (1.0, 100.0),
    "vix": (1.0, 200.0),
    "gvz": (1.0, 200.0),
    "real_yield_10y": (-20.0, 30.0),
    "inflation_expectation": (-20.0, 30.0),
    "policy_expectation": (-20.0, 30.0),
    "gold_silver_ratio": (1.0, 1000.0),
    "copper_gold_ratio": (0.0001, 100.0),
    "bitcoin": (0.0, 1e9),
    "central_bank": (0.0, 1e12),
    "etf_shares": (0.0, 1e12),
    "rrp": (0.0, 1e13),
    "tga": (-1e13, 1e13),
}


@dataclass(frozen=True)
class Finding:
    """一条体检发现。`detail` 直接进报告，不再加工。"""

    kind: str  # future / nonfinite / bounds / duplicate
    factor_key: str
    obs_date: str
    detail: str


def audit_rows(
    rows: Iterable[tuple[str, str, Optional[float]]],
    *,
    today: date,
    bounds: dict[str, tuple[float, float]] = SANITY_BOUNDS,
    check_duplicates: bool = True,
) -> list[Finding]:
    """对 (因子, 日期字符串, 值) 序列做体检；两个库共用这一份口径。"""
    today_iso = today.isoformat()
    findings: list[Finding] = []
    seen: dict[tuple[str, str], int] = {}
    for key, obs_date, value in rows:
        key = str(key)
        obs_date = str(obs_date or "")
        if obs_date and obs_date > today_iso:
            findings.append(
                Finding(
                    "future",
                    key,
                    obs_date,
                    f"{key} 的观测日期 {obs_date} 晚于今天（{today_iso}）",
                )
            )
        if value is None or not math.isfinite(value):
            findings.append(
                Finding("nonfinite", key, obs_date, f"{key} 在 {obs_date} 的值不是有限数：{value!r}")
            )
        else:
            low_high = bounds.get(key)
            if low_high is not None and not (low_high[0] <= value <= low_high[1]):
                findings.append(
                    Finding(
                        "bounds",
                        key,
                        obs_date,
                        f"{key} 在 {obs_date} 的值 {value} 越过合理性区间 "
                        f"[{low_high[0]}, {low_high[1]}]",
                    )
                )
        seen[(key, obs_date)] = seen.get((key, obs_date), 0) + 1
    if check_duplicates:
        for (key, obs_date), count in seen.items():
            if count > 1:
                findings.append(
                    Finding("duplicate", key, obs_date, f"{key} 在 {obs_date} 有 {count} 行观测（键重复）")
                )
    return findings


def audit_service_store(
    session: Session, *, today: Optional[date] = None, bounds: dict[str, tuple[float, float]] = SANITY_BOUNDS
) -> list[Finding]:
    """服务库（`factor_observations`）体检。

    不做重复键扫描：模型层有 `uq_factor_observation` 唯一约束，重复行进不来；
    留着这条检查就是「看着在守、其实什么都没守」。
    """
    today = today or timeutil.today()
    rows = (
        (key, obs_date.isoformat() if obs_date else "", value)
        for key, obs_date, value in session.execute(
            select(
                FactorObservation.factor_key,
                FactorObservation.obs_date,
                FactorObservation.value,
            )
        )
    )
    return audit_rows(rows, today=today, bounds=bounds, check_duplicates=False)


def purge_future_observations(session: Session, *, today: Optional[date] = None) -> int:
    """删除服务库里观测日期晚于今天的行，返回删除行数（不可逆，先备份）。"""
    today = today or timeutil.today()
    deleted = (
        session.query(FactorObservation)
        .filter(FactorObservation.obs_date > today)
        .delete(synchronize_session=False)
    )
    session.commit()
    return int(deleted or 0)


def audit_long_store(
    connection: sqlite3.Connection, *, today: Optional[date] = None, bounds: dict[str, tuple[float, float]] = SANITY_BOUNDS
) -> list[Finding]:
    """长库（SQLite 回填库）体检。长库不受模型层唯一约束保护，重复键要查。"""
    today = today or timeutil.today()
    rows = connection.execute("SELECT factor_key, obs_date, value FROM factor_observations")
    return audit_rows(
        ((str(key), str(obs_date), value) for key, obs_date, value in rows),
        today=today,
        bounds=bounds,
        check_duplicates=True,
    )


def purge_long_future_observations(connection: sqlite3.Connection, *, today: Optional[date] = None) -> int:
    """删除长库里观测日期晚于今天的行，返回删除行数（不可逆，先备份）。"""
    today = today or timeutil.today()
    cursor = connection.execute("DELETE FROM factor_observations WHERE obs_date > ?", (today.isoformat(),))
    connection.commit()
    return int(cursor.rowcount or 0)


def _load_service_values(session: Session) -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], float] = {}
    for key, obs_date, value in session.execute(
        select(
            FactorObservation.factor_key,
            FactorObservation.obs_date,
            FactorObservation.value,
        )
    ):
        values[(str(key), obs_date.isoformat() if obs_date else "")] = value
    return values


def _load_long_values(connection: sqlite3.Connection) -> dict[tuple[str, str], float]:
    values: dict[tuple[str, str], float] = {}
    for key, obs_date, value in connection.execute(
        "SELECT factor_key, obs_date, value FROM factor_observations"
    ):
        values[(str(key), str(obs_date))] = value
    return values


def compare_stores(
    session: Session,
    connection: sqlite3.Connection,
    *,
    tolerance: float = 1e-6,
    max_examples: int = 8,
) -> dict:
    """比较服务库与长库：覆盖差异、仅单边存在的因子、重叠日期的值偏差。

    偏差判据用相对误差：``|a-b| / max(1, |a|, |b|) > tolerance``。
    只报告、不改数 —— 两个库谁对由人定，脚本的职责是把分歧摆到明面上。
    """
    service = _load_service_values(session)
    long = _load_long_values(connection)
    service_keys = {key for key, _ in service}
    long_keys = {key for key, _ in long}
    common = sorted(service_keys & long_keys)

    by_key: dict[str, list[tuple[tuple[str, str], float]]] = {}
    for pair, value in service.items():
        by_key.setdefault(pair[0], []).append((pair, value))

    report = {
        "service_keys": len(service_keys),
        "long_keys": len(long_keys),
        "common_keys": len(common),
        "only_service": sorted(service_keys - long_keys),
        "only_long": sorted(long_keys - service_keys),
        "keys": [],
        "mismatch_total": 0,
    }
    for key in common:
        overlap = 0
        mismatched = 0
        worst: Optional[dict] = None
        for pair, service_value in by_key.get(key, []):
            long_value = long.get(pair)
            if long_value is None:
                continue
            overlap += 1
            denominator = max(1.0, abs(service_value), abs(long_value))
            relative = abs(service_value - long_value) / denominator
            if relative > tolerance:
                mismatched += 1
                if worst is None or relative > worst["relative_diff"]:
                    worst = {
                        "obs_date": pair[1],
                        "service": service_value,
                        "long": long_value,
                        "relative_diff": round(relative, 8),
                    }
        if mismatched:
            report["mismatch_total"] += mismatched
            report["keys"].append(
                {
                    "factor_key": key,
                    "overlap": overlap,
                    "mismatched": mismatched,
                    "worst": worst,
                }
            )
    report["keys"].sort(key=lambda item: item["mismatched"], reverse=True)
    report["keys"] = report["keys"][:max_examples]
    return report
