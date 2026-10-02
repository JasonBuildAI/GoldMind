"""\`GET /api/gold/sources/status\` 的形状与落库联动。"""
from __future__ import annotations

import pytest


@pytest.mark.integration
def test_sources_status_is_empty_without_attempts(client):
    body = client.get("/api/gold/sources/status").json()

    assert body["sources"] == []
    assert body["summary"]["total"] == 0


@pytest.mark.integration
def test_sources_status_reflects_recorded_attempts(client):
    from app.services import source_status

    source_status.record_attempt(
        channel="price", source_key="gold_realtime", status=source_status.STATUS_OK, items=1
    )

    body = client.get("/api/gold/sources/status").json()

    assert body["summary"]["total"] == 1
    row = body["sources"][0]
    assert row["channel_label"] == "金价与美元指数"
    assert row["status_label"] == "可用"
    assert row["stale"] is False
    assert row["items"] == 1
