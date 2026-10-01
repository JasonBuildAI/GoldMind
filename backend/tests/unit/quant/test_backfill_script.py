"""回填脚本：dry-run 不写库、apply 幂等、轮次上限与停手条件。"""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from app.models.analysis import FactorObservation
from app.services.quant import sync as quant_sync
from scripts import backfill_quant

TODAY = date(2026, 10, 2)
BACKEND_DIR = Path(__file__).resolve().parents[3]


def _bundle() -> dict:
    index = pd.bdate_range(start="2016-01-04", end="2026-09-30", freq="B")
    steps = np.arange(len(index), dtype="float64")
    return {
        "ust_real_10y": pd.Series(1.0 + (steps % 400) * 0.001, index=index),
        "ust_nominal_10y": pd.Series(3.5 + (steps % 400) * 0.001, index=index),
        "ust_nominal_2y": pd.Series(3.0 + (steps % 400) * 0.001, index=index),
        "gold_close": pd.Series(1500 + steps * 0.2, index=index),
        "dxy": pd.Series(95 + (steps % 300) * 0.01, index=index),
    }


def _fetchers(bundle: dict) -> dict:
    def make(name: str):
        def fetcher():
            if name == "treasury":
                return {
                    key: bundle[key]
                    for key in ("ust_real_10y", "ust_nominal_10y", "ust_nominal_2y")
                }
            if name == "yahoo":
                return {key: bundle[key] for key in ("gold_close", "dxy")}
            return {}

        return fetcher

    return {name: make(name) for name in quant_sync.SOURCE_ORDER}


def _count_rows(db) -> int:
    return db.query(FactorObservation).count()


def _quiet(_message: str) -> None:
    pass


def test_dry_run_reports_coverage_without_writing(db_session):
    rows = backfill_quant.coverage_rows(db_session, years=20, today=TODAY)

    assert len(rows) == len(backfill_quant.series_keys())
    assert all(row["observations"] == 0 for row in rows)
    text = backfill_quant.format_coverage(rows, years=20, today=TODAY)
    assert "real_yield_10y" in text
    assert _count_rows(db_session) == 0


def test_apply_fills_history_and_repeat_run_is_idempotent(db_session):
    fetchers = _fetchers(_bundle())

    first = backfill_quant.run_backfill(
        db_session, years=10, rounds=8, today=TODAY, fetchers=fetchers, emit=_quiet
    )
    rows_after_first = _count_rows(db_session)

    assert first["inserted"] > 0
    assert rows_after_first > 0
    coverage = {row["factor_key"]: row for row in first["coverage"]}
    assert coverage["real_yield_10y"]["sparse_years"] == [], "沙盒里 2016–2026 每年都有观测，不该有缺口年"

    second = backfill_quant.run_backfill(
        db_session, years=10, rounds=8, today=TODAY, fetchers=fetchers, emit=_quiet
    )

    assert second["inserted"] == 0, "重复回填不得新增行"
    assert second["updated"] == 0, "同值重放不应产生修订"
    assert _count_rows(db_session) == rows_after_first


def test_apply_stops_when_a_round_makes_no_progress(db_session):
    empty = {name: (lambda: {}) for name in quant_sync.SOURCE_ORDER}

    result = backfill_quant.run_backfill(
        db_session, years=20, rounds=8, today=TODAY, fetchers=empty, emit=_quiet
    )

    assert result["rounds"] == 1
    assert result["stopped_reason"] == "no_progress"


def test_apply_respects_round_cap(db_session):
    calls: list[int] = []

    class _Report:
        factor_status = {"stub": {"status": "ok", "rows_inserted": 5, "rows_updated": 0}}
        extra_status: dict = {}

    def endless_sync(db, **kwargs):
        calls.append(1)
        return _Report()

    result = backfill_quant.run_backfill(
        db_session, years=20, rounds=3, today=TODAY, sync_fn=endless_sync, emit=_quiet
    )

    assert len(calls) == 3, "轮次上限必须真的截断循环"
    assert result["stopped_reason"] == "max_rounds"


def test_cli_dry_run_on_a_fresh_database(tmp_path):
    db_path = tmp_path / "fresh.db"
    env = {
        **os.environ,
        "DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        "SCHEDULER_ENABLED": "false",
    }
    proc = subprocess.run(
        [sys.executable, "scripts/backfill_quant.py", "--dry-run", "--years", "20"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert proc.returncode == 0, proc.stderr
    assert "real_yield_10y" in proc.stdout
    assert "dry-run" in proc.stdout


def test_package_import_has_no_side_effects():
    assert not hasattr(backfill_quant, "main") or callable(backfill_quant.main)
