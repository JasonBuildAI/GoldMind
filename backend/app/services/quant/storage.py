"""factor_observations 的读写（方言中立、幂等）。"""
from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.analysis import FactorObservation


def upsert_series(
    db: Session,
    factor_key: str,
    series: pd.Series,
    *,
    source: str,
    meta: Optional[dict] = None,
    commit: bool = True,
) -> tuple[int, int]:
    """写入一条序列，返回 (新增行数, 更新行数)。

    不用方言特有的 upsert 语法（MySQL 的 ON DUPLICATE KEY 与 SQLite 的
    ON CONFLICT 写法不同）：先查出区间内已有行，再逐条判断新增或修订。
    修订（值变化）也会被记录，因为数据源确实会回修历史（CFTC 就回修过）。
    """
    if series is None or series.empty:
        return 0, 0

    prepared: list[tuple[date, float]] = []
    for timestamp, value in series.items():
        if pd.isna(value):
            continue
        prepared.append((pd.Timestamp(timestamp).date(), float(value)))
    if not prepared:
        return 0, 0

    prepared.sort(key=lambda item: item[0])
    dates = [item[0] for item in prepared]

    existing_rows = (
        db.query(FactorObservation)
        .filter(
            FactorObservation.factor_key == factor_key,
            FactorObservation.obs_date >= min(dates),
            FactorObservation.obs_date <= max(dates),
        )
        .all()
    )
    existing = {row.obs_date: row for row in existing_rows}

    inserted = 0
    updated = 0
    for obs_date, value in prepared:
        row = existing.get(obs_date)
        if row is None:
            db.add(
                FactorObservation(
                    factor_key=factor_key,
                    obs_date=obs_date,
                    value=value,
                    source=source,
                    meta=meta,
                )
            )
            inserted += 1
            continue

        if abs((row.value or 0.0) - value) > 1e-12 or row.source != source:
            row.value = value
            row.source = source
            row.meta = meta
            updated += 1

    if commit:
        db.commit()
    return inserted, updated


def load_series(db: Session, factor_key: str) -> pd.Series:
    rows = (
        db.query(FactorObservation.obs_date, FactorObservation.value)
        .filter(FactorObservation.factor_key == factor_key)
        .order_by(FactorObservation.obs_date)
        .all()
    )
    if not rows:
        return pd.Series(dtype="float64", name=factor_key)
    values = {pd.Timestamp(row[0]): float(row[1]) for row in rows}
    return pd.Series(values, name=factor_key).astype("float64")


def load_all(db: Session, keys: Optional[Iterable[str]] = None) -> dict[str, pd.Series]:
    query = db.query(
        FactorObservation.factor_key, FactorObservation.obs_date, FactorObservation.value
    ).order_by(FactorObservation.obs_date)
    if keys is not None:
        query = query.filter(FactorObservation.factor_key.in_(list(keys)))

    collected: dict[str, dict] = {}
    for factor_key, obs_date, value in query.all():
        collected.setdefault(factor_key, {})[pd.Timestamp(obs_date)] = float(value)

    return {
        factor_key: pd.Series(values, name=factor_key).astype("float64").sort_index()
        for factor_key, values in collected.items()
    }


def latest_date(db: Session, factor_key: str) -> Optional[date]:
    row = (
        db.query(FactorObservation.obs_date)
        .filter(FactorObservation.factor_key == factor_key)
        .order_by(FactorObservation.obs_date.desc())
        .first()
    )
    return row[0] if row else None
