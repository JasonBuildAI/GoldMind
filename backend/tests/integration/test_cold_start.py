"""零人工冷启动（CI 版本）：空库 + 假源 + 假 LLM，不跑任何手工命令直达可用状态。

真实源 + 真实 LLM 的完整验收在本地执行（见 README「全自动运行」与
`docs/specs/2026-10-03-2.0.2-整改与自动化-plan.md` 的 D 段）；这里用假源保证
CI 快速、确定，且覆盖的是**同一条** `bootstrap.run_bootstrap` 编排路径。

变异验证（commit body 有记录）：
- 让第二次启动重新插入价格 → 幂等断言必红；
- 让 LLM 未配置时分析阶段假装 done → 降级断言必红。
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from app import bootstrap
from app.config import settings
from app.utils import timeutil


@pytest.fixture(autouse=True)
def _fresh_progress():
    bootstrap.progress.reset()
    yield
    bootstrap.progress.reset()


def _fake_gold_rows(count: int) -> list[dict]:
    end = timeutil.today()
    return [
        {
            "date": end - timedelta(days=count - 1 - index),
            "open_price": 2000.0 + index,
            "high_price": 2010.0 + index,
            "low_price": 1990.0 + index,
            "close_price": 2005.0 + index,
            "volume": 100,
        }
        for index in range(count)
    ]


def _fake_dollar_rows(count: int) -> list[dict]:
    end = timeutil.today()
    return [
        {
            "date": end - timedelta(days=count - 1 - index),
            "open_price": 100.0,
            "high_price": 101.0,
            "low_price": 99.0,
            "close_price": 100.5,
        }
        for index in range(count)
    ]


def _wire_fake_sources(monkeypatch, *, gold_rows: int = bootstrap.MIN_GOLD_PRICE_ROWS + 5):
    # 对齐阶段默认读本机的研究长库（存在就不该被测试依赖，CI 上也没有）
    from pathlib import Path

    from app.services import store_alignment

    monkeypatch.setattr(
        store_alignment, "DEFAULT_LONG_DB", Path("no-such-long-db-for-tests.db")
    )
    monkeypatch.setattr("seed_data.fetch_gold_history", lambda: _fake_gold_rows(gold_rows))
    monkeypatch.setattr("seed_data.fetch_dollar_index_history", lambda: _fake_dollar_rows(10))

    now = timeutil.now_naive()
    news_items = [
        {
            "title": f"冷启动新闻 {index}",
            "content": "内容",
            "source": "冷启动测试源",
            "url": f"https://example.invalid/cold-start/{index}",
            "published_at": now,
        }
        for index in range(2)
    ]
    monkeypatch.setattr(
        "app.services.news_service.NewsService.fetch_all_rss_news",
        lambda self, limit_per_source=10: news_items,
    )
    monkeypatch.setattr(
        "app.services.news_digest.NewsDigestService.fetch_all_sources",
        lambda self, limit=10: {"ok_sources": 3, "total_sources": 12, "saved": 4},
    )

    def fake_backfill(db, *, years, rounds, today, emit):
        import pandas as pd

        from app.services.quant import storage

        index = pd.date_range(end=pd.Timestamp(today), periods=5, freq="B")
        inserted, _ = storage.upsert_series(
            db,
            "gold_close",
            pd.Series([2500.0, 2510.0, 2505.0, 2520.0, 2530.0], index=index, name="gold_close"),
            source="冷启动测试",
            commit=True,
        )
        emit(f"假回填写入 {inserted} 行")
        return {
            "rounds": 1,
            "stopped_reason": "no_progress",
            "inserted": inserted,
            "updated": 0,
            "coverage": [],
        }

    monkeypatch.setattr("scripts.backfill_quant.run_backfill", fake_backfill)


@pytest.mark.integration
def test_cold_start_reaches_a_usable_state_without_manual_commands(
    db_session, monkeypatch
):
    from app.database import SessionLocal, engine
    from app.models.gold_price import DollarIndex, GoldPrice
    from app.models.news import GoldNews
    from app.models.analysis import FactorObservation

    _wire_fake_sources(monkeypatch)
    # 这一步按 .env 里「LLM 尚未配置」的真实降级语义走（CI 不接任何模型）
    monkeypatch.setattr("app.services.llm_provider.is_configured", lambda: False)

    snapshot = bootstrap.run_bootstrap(engine, session_factory=SessionLocal)

    assert snapshot["status"] == "done", snapshot.get("error")
    assert snapshot["ready"] is True
    assert [phase["key"] for phase in snapshot["phases"]] == list(bootstrap.PHASE_ORDER)
    assert all(phase["status"] in {"done", "skipped"} for phase in snapshot["phases"])
    assert snapshot["step"] == {"index": 7, "total": 7}

    assert db_session.query(GoldPrice).count() == bootstrap.MIN_GOLD_PRICE_ROWS + 5
    assert db_session.query(DollarIndex).count() == 10
    assert db_session.query(GoldNews).count() == 2
    assert db_session.query(FactorObservation).count() >= 5, "量化面板必须有数据"

    phases = {phase["key"]: phase for phase in snapshot["phases"]}
    assert phases["analyses"]["status"] == "skipped"
    assert "LLM 未配置" in phases["analyses"]["note"], "没配 LLM 必须如实说，不许假装分析过"
    # 缺口快照是**回填前**的探针结果：空库必须如实报 0，随后阶段才去抓取
    assert snapshot["gaps"]["gold_prices"]["rows"] == 0
    assert snapshot["gaps"]["quant"]["series_without_data"]


@pytest.mark.integration
def test_second_start_is_idempotent(db_session, monkeypatch):
    from app.database import SessionLocal, engine
    from app.models.analysis import FactorObservation
    from app.models.gold_price import GoldPrice
    from app.models.news import GoldNews

    _wire_fake_sources(monkeypatch)
    monkeypatch.setattr("app.services.llm_provider.is_configured", lambda: False)

    bootstrap.run_bootstrap(engine, session_factory=SessionLocal)
    counts_before = (
        db_session.query(GoldPrice).count(),
        db_session.query(GoldNews).count(),
        db_session.query(FactorObservation).count(),
    )

    second = bootstrap.run_bootstrap(engine, session_factory=SessionLocal)

    counts_after = (
        db_session.query(GoldPrice).count(),
        db_session.query(GoldNews).count(),
        db_session.query(FactorObservation).count(),
    )
    assert counts_after == counts_before, "重复启动不得重复回填"
    assert second["ready"] is True
    phases = {phase["key"]: phase for phase in second["phases"]}
    assert phases["price_history"]["status"] == "skipped", "已有新鲜历史必须跳过抓取"
    assert phases["news"]["status"] == "done"
    assert "已有" in phases["news"]["note"], "新闻热点已有内容时应说明而非重复抓取"


@pytest.mark.integration
def test_warm_analyses_runs_when_the_llm_appears(monkeypatch, db_session, fake_llm, seed_gold_prices, seed_news):
    """配置好 LLM 后无需重启：warm_analyses 直接补一轮（watcher 调用的入口）。"""
    from app.database import engine

    seed_gold_prices(days=30)
    seed_news(count=2, hours_ago=1)
    monkeypatch.setattr("app.services.llm_provider.is_configured", lambda: True)

    result = bootstrap.warm_analyses(engine, force=True)

    assert isinstance(result, dict)
    assert result.get("status") == "done"
    for label in ("看涨", "看跌", "机构", "策略", "总结"):
        assert label in result.get("note", ""), f"分析阶段必须覆盖 {label}"