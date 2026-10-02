"""factor_observations 的读写（方言中立、幂等）。

两张表各司其职：

- `factor_observations` 是**当前值**，重复抓取幂等（唯一键 factor_key + obs_date）；
- `factor_observation_revisions` 是**追加式流水**，每次写入留一行，永不改写。
  有了它才能回答「某次回测当时看到的输入是什么」—— 见 `load_series_as_of()`。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Iterable, Optional

import statistics

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from app.models.analysis import FactorObservation, FactorObservationRevision
from app.utils import timeutil


def upsert_series(
    db: Session,
    factor_key: str,
    series: pd.Series,
    *,
    source: str,
    meta: Optional[dict] = None,
    commit: bool = True,
    recorded_at: Optional[datetime] = None,
) -> tuple[int, int]:
    """写入一条序列，返回 (新增行数, 更新行数)。

    不用方言特有的 upsert 语法（MySQL 的 ON DUPLICATE KEY 与 SQLite 的
    ON CONFLICT 写法不同）：先查出区间内已有行，再逐条判断新增或修订。
    修订（值变化）也会被记录，因为数据源确实会回修历史（CFTC 就回修过）。

    首见与回修都会往 `factor_observation_revisions` 追加一行（值没变则不追加），
    `recorded_at` 默认取项目时区的当前时间，测试可注入以构造可复核的历史。
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
    # 不变量：不许写入「晚于今天」的观测。行情快照类采集会用「最近一根 K 线 +
    # 1 个交易日」当作可用日（GLD 份额就是这样），而最新 K 线往往就是今天，
    # 于是算出来的是明天 —— 这种行在按日走查的回测里等于把未来当成已知
    # （2026-10-02 实测到 obs_date=2026-10-05 而当天是 10-02）。直接丢弃并告警。
    today = timeutil.today()
    future = [item for item in prepared if item[0] > today]
    if future:
        logger.warning(
            f"[量化] {factor_key} 有 {len(future)} 条观测的日期晚于今天（"
            f"{future[0][0].isoformat()}..{future[-1][0].isoformat()}），"
            "未来日期的行会造成前视，已拒绝写入；请检查该源的「可用日」平移逻辑"
        )
        prepared = [item for item in prepared if item[0] <= today]
    if not prepared:
        return 0, 0
    dates = [item[0] for item in prepared]
    stamp = recorded_at or timeutil.now_naive()

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
    revisions: list[FactorObservationRevision] = []
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
                    # 显式写项目时区：列的 server_default 是 `func.now()`，SQLite 下
                    # 那是 UTC，与 recorded_at 的项目时区差一个偏移（红线五：时间只在
                    # 一个时区里流动）。迁移要把 created_at 抄进流水，两个时钟混在一起
                    # 会让凌晨写入的值渗进前一天的 --as-of 面板。
                    created_at=stamp,
                    updated_at=stamp,
                )
            )
            inserted += 1
        elif abs((row.value or 0.0) - value) > 1e-12 or row.source != source:
            row.value = value
            row.source = source
            row.meta = meta
            row.updated_at = stamp
            updated += 1
        else:
            continue  # 值与来源都没变：幂等重跑不产生流水行
        revisions.append(
            FactorObservationRevision(
                factor_key=factor_key,
                obs_date=obs_date,
                value=value,
                source=source,
                meta=meta,
                recorded_at=stamp,
            )
        )
    db.add_all(revisions)

    if commit:
        db.commit()
    return inserted, updated


def load_series_as_of(
    db: Session,
    as_of: date,
    keys: Optional[Iterable[str]] = None,
) -> dict[str, pd.Series]:
    """按**当时可见**的输入重建因子面板（point-in-time）。

    每个 (factor_key, obs_date) 取 `recorded_at <= as_of` 的最后一条流水 —— 也就是
    「那天的人看到的值」，可能是后来被回修掉的旧值。`as_of` 之前完全没有写入的
    观测一律不出现，所以这条序列不会把未来才补抓的历史漏进过去的面板。
    """
    query = (
        db.query(
            FactorObservationRevision.factor_key,
            FactorObservationRevision.obs_date,
            FactorObservationRevision.value,
            FactorObservationRevision.recorded_at,
        )
        .filter(FactorObservationRevision.recorded_at <= datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59))
        .order_by(
            FactorObservationRevision.factor_key,
            FactorObservationRevision.obs_date,
            FactorObservationRevision.recorded_at,
        )
    )
    if keys is not None:
        query = query.filter(FactorObservationRevision.factor_key.in_(list(keys)))

    collected: dict[str, dict] = {}
    for factor_key, obs_date, value, _recorded_at in query.all():
        # 同一 (key, 日) 后写覆盖先写：按 recorded_at 升序遍历，直接赋值即可
        collected.setdefault(factor_key, {})[pd.Timestamp(obs_date)] = float(value)

    return {
        factor_key: pd.Series(values, name=factor_key).astype("float64").sort_index()
        for factor_key, values in collected.items()
    }


def revision_count(db: Session) -> int:
    """流水行数（回填报告与「这次重跑还是不是同一次实验」的核对用）。"""
    return int(db.query(FactorObservationRevision).count())


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


def earliest_date(db: Session, factor_key: str) -> Optional[date]:
    row = (
        db.query(FactorObservation.obs_date)
        .filter(FactorObservation.factor_key == factor_key)
        .order_by(FactorObservation.obs_date.asc())
        .first()
    )
    return row[0] if row else None


def year_counts(db: Session, factor_key: str) -> dict[int, int]:
    """每个年份的观测数。一次查询、方言中立。"""
    counts: dict[int, int] = {}
    rows = (
        db.query(FactorObservation.obs_date)
        .filter(FactorObservation.factor_key == factor_key)
        .all()
    )
    for (obs_date,) in rows:
        counts[obs_date.year] = counts.get(obs_date.year, 0) + 1
    return counts


def sparse_years_from_counts(
    counts: dict[int, int],
    *,
    window: Optional[Iterable[int]] = None,
    ratio: float = 0.2,
    min_obs: int = 1,
) -> set[int]:
    """相对年样本中位数明显偏低的年份 —— 含窗口内完全没有观测的年份。

    「整年缺口」与「只有零星几行」都要能发现：增量抓取原实现只看首末两个年份，
    ``real_yield_10y`` 在 2018–2025 整段缺失也永远补不上（2026-10-02 实测：
    年份分布 2016=249、2017=1、2026=188）。

    ``window`` 缺省取「首末观测之间的所有年份」；要检查观测范围之外的年份
    （如今年尚未抓到数据）必须显式传入窗口。

    纯函数：计数从 DB（``year_counts``）或已加载的内存面板来，规则只有这一份。
    """
    if not counts:
        return set(window or ())
    threshold = max(float(min_obs), statistics.median(counts.values()) * ratio)
    if window is not None:
        years = list(window)
    else:
        years = range(min(counts), max(counts) + 1)
    return {year for year in years if counts.get(year, 0) < threshold}


def sparse_years(
    db: Session,
    factor_key: str,
    *,
    window: Optional[Iterable[int]] = None,
    ratio: float = 0.2,
    min_obs: int = 1,
) -> set[int]:
    """DB 版：先数每年观测，再走 ``sparse_years_from_counts`` 的同一份规则。"""
    return sparse_years_from_counts(
        year_counts(db, factor_key), window=window, ratio=ratio, min_obs=min_obs
    )


def coverage_rules(
    factor_key: str,
    counts: dict[int, int],
    *,
    window: Optional[Iterable[int]] = None,
    ratio: float = 0.2,
    min_obs: int = 1,
    first_date: Optional[date] = None,
    last_date: Optional[date] = None,
) -> dict:
    """覆盖画像的纯规则：年份计数、缺口年、覆盖窗口、是否仍在积累期。

    少于 2 个年份有数据 → ``accumulating``（新序列允许先入库积累，单独报告）；
    首末观测之间样本数低于年样本中位数 20% 的年份 → ``sparse_years``。
    DB 侧（``coverage``）与页面侧（``coverage_from_index``）共用这一份实现。
    """
    gaps = sorted(
        sparse_years_from_counts(counts, window=window, ratio=ratio, min_obs=min_obs)
    )
    years = sorted(counts)
    return {
        "factor_key": factor_key,
        "observations": sum(counts.values()),
        "years": years,
        "year_counts": counts,
        "sparse_years": gaps,
        "first_date": first_date,
        "last_date": last_date,
        "accumulating": len(years) < 2,
    }


def coverage(
    db: Session,
    factor_key: str,
    *,
    window: Optional[Iterable[int]] = None,
    ratio: float = 0.2,
    min_obs: int = 1,
) -> dict:
    """DB 版覆盖画像：从库里取计数与首末日期，再走 ``coverage_rules``。

    守卫（`tests/unit/quant/test_factor_coverage.py`）与回填报告共用这一份口径。
    """
    return coverage_rules(
        factor_key,
        year_counts(db, factor_key),
        window=window,
        ratio=ratio,
        min_obs=min_obs,
        first_date=earliest_date(db, factor_key),
        last_date=latest_date(db, factor_key),
    )


def coverage_from_index(factor_key: str, index) -> dict:
    """面板版覆盖画像：指数已在内存里，不再为同一事实多打一次库。"""
    stamps = pd.DatetimeIndex(index)
    if stamps.empty:
        return coverage_rules(factor_key, {})
    counts: dict[int, int] = {}
    for stamp in stamps:
        counts[stamp.year] = counts.get(stamp.year, 0) + 1
    return coverage_rules(
        factor_key,
        counts,
        first_date=stamps.min().date(),
        last_date=stamps.max().date(),
    )
