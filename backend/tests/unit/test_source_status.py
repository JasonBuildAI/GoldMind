"""抓取尝试流水与可用性汇总。

变异验证（见 commit message body）：
- 汇总取「每个源最旧一行」而不是最新 → 最新态测试必红；
- 把过期判定反过来（stale 当作新鲜）→ 过期测试必红。
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.services import source_status
from app.utils import timeutil


def _stamp(hours_ago: float = 0.0) -> datetime:
    return timeutil.now_naive() - timedelta(hours=hours_ago)


@pytest.mark.unit
def test_record_and_latest_attempt_wins(db_session):
    source_status.record_attempt(
        channel="quant_sync", source_key="yahoo", status=source_status.STATUS_ERROR,
        error="boom", started_at=_stamp(3),
    )
    source_status.record_attempt(
        channel="quant_sync", source_key="yahoo", status=source_status.STATUS_OK,
        items=26, started_at=_stamp(1),
    )

    rows = source_status.latest_attempts(db_session)

    assert len(rows) == 1
    assert rows[0].status == source_status.STATUS_OK, "必须取最近一次尝试，而不是第一次"
    assert rows[0].items == 26


@pytest.mark.unit
def test_payload_flags_a_stale_ok_source(db_session):
    known = datetime(2026, 10, 3, 12, 0, 0)
    source_status.record_attempt(
        channel="quant_sync", source_key="yahoo", status=source_status.STATUS_OK,
        items=26, started_at=known - timedelta(hours=30),
        finished_at=known - timedelta(hours=30),
    )
    source_status.record_attempt(
        channel="news_digest", source_key="路透社", status=source_status.STATUS_OK,
        items=5, started_at=known - timedelta(hours=1),
        finished_at=known - timedelta(hours=1),
    )

    body = source_status.payload(db_session, now=known)

    by_key = {item["source_key"]: item for item in body["sources"]}
    assert by_key["yahoo"]["stale"] is True
    assert by_key["yahoo"]["age_hours"] == pytest.approx(30.0, abs=0.1)
    assert by_key["路透社"]["stale"] is False
    assert body["summary"]["total"] == 2
    assert body["summary"]["stale"] == 1
    assert body["summary"][source_status.STATUS_OK] == 2


@pytest.mark.unit
def test_payload_is_empty_before_any_attempt(db_session):
    body = source_status.payload(db_session)

    assert body["sources"] == []
    assert body["summary"]["total"] == 0
