"""零人工冷启动的数据阶段：覆盖度检测、按需回填、首轮分析的编排与降级。

这些守卫对应 2.0.2 的硬目标「配置 LLM 是唯一人工输入」：
每一步的跳过都必须有明确理由，失败必须如实记录而不是假装完成。

变异验证（commit body 有记录）：
- 把覆盖度阶段改成永远回填 → 新鲜度跳过用例必红；
- 把新闻阶段「0 条入库」也标成 done → 诚实降级用例必红；
- 从 STEPS 里删掉任一阶段 → 清单用例必红；
- 让 run_bootstrap 忽略 steps 注入 → 注入用例必红。
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


def _ctx(today: date | None = None) -> bootstrap._Context:
    from app.database import engine

    return bootstrap._Context(engine=engine, today=today or timeutil.today())


# --------------------------------------------------------------------------- #
# 阶段清单
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_steps_cover_every_phase_in_order():
    keys = [key for key, _, _ in bootstrap.STEPS]

    assert keys == list(bootstrap.PHASE_ORDER), "STEPS 与 PHASE_ORDER 必须一一对应且同序"
    assert set(bootstrap.PHASE_LABELS) == set(bootstrap.PHASE_ORDER), "每个阶段都要有人话标签"
    assert all(label for _, label, _ in bootstrap.STEPS)


# --------------------------------------------------------------------------- #
# 覆盖度
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_coverage_reports_empty_database_gaps(db_session):
    result = bootstrap._phase_coverage(_ctx(), db_session)

    assert result["status"] == "done"
    gaps = bootstrap.progress.snapshot()["gaps"]
    assert gaps["gold_prices"]["rows"] == 0
    assert gaps["dollar_index"]["rows"] == 0
    assert gaps["news_digest"]["rows"] == 0
    assert gaps["quant"]["series_without_data"], "空库必须点名所有没有数据的因子序列"
    assert gaps["quant"]["window_years"] == settings.QUANT_BACKFILL_YEARS


# --------------------------------------------------------------------------- #
# 金价 / 美元指数
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_price_phase_skips_when_history_is_fresh(db_session, monkeypatch):
    from app.models.gold_price import GoldPrice

    today = timeutil.today()
    for offset in range(bootstrap.MIN_GOLD_PRICE_ROWS):
        db_session.add(
            GoldPrice(
                date=today - timedelta(days=offset),
                open_price=1,
                high_price=1,
                low_price=1,
                close_price=1,
            )
        )
    db_session.commit()

    def _boom():
        raise AssertionError("已足够新鲜的历史不该再访问数据源")

    monkeypatch.setattr("seed_data.fetch_gold_history", _boom)
    result = bootstrap._phase_price_history(_ctx(today), db_session)

    assert result["status"] == "skipped"
    assert "无需回填" in result["note"]


@pytest.mark.unit
def test_price_phase_backfills_from_sources_when_empty(db_session, monkeypatch):
    gold_rows = [
        {
            "date": date(2025, 1, 1) + timedelta(days=index),
            "open_price": 2000 + index,
            "high_price": 2010 + index,
            "low_price": 1990 + index,
            "close_price": 2005 + index,
            "volume": 10,
        }
        for index in range(bootstrap.MIN_GOLD_PRICE_ROWS + 5)
    ]
    dollar_rows = [
        {
            "date": date(2025, 1, 1) + timedelta(days=index),
            "open_price": 100,
            "high_price": 101,
            "low_price": 99,
            "close_price": 100,
        }
        for index in range(20)
    ]
    monkeypatch.setattr("seed_data.fetch_gold_history", lambda: gold_rows)
    monkeypatch.setattr("seed_data.fetch_dollar_index_history", lambda: dollar_rows)

    result = bootstrap._phase_price_history(_ctx(date(2025, 12, 31)), db_session)

    from app.models.gold_price import DollarIndex, GoldPrice

    assert result["status"] == "done"
    assert db_session.query(GoldPrice).count() == len(gold_rows)
    assert db_session.query(DollarIndex).count() == len(dollar_rows)
    assert "金价写入" in result["note"]


@pytest.mark.unit
def test_price_phase_reports_failure_when_source_returns_nothing(db_session, monkeypatch):
    monkeypatch.setattr("seed_data.fetch_gold_history", list)
    monkeypatch.setattr("seed_data.fetch_dollar_index_history", list)

    result = bootstrap._phase_price_history(_ctx(), db_session)

    assert result["status"] == "failed"
    assert "下一轮启动自动重试" in result["note"]


# --------------------------------------------------------------------------- #
# 新闻 / 消息板块
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_news_phase_skips_rss_when_recent_news_exists(db_session, monkeypatch, seed_news):
    seed_news(count=2, hours_ago=1)
    calls = {"rss": 0}

    def _boom(*args, **kwargs):
        calls["rss"] += 1
        raise AssertionError("最近 24 小时已有新闻时不该再抓 RSS")

    monkeypatch.setattr("app.services.news_service.NewsService.fetch_all_rss_news", _boom)
    monkeypatch.setattr(
        "app.services.news_digest.NewsDigestService.fetch_all_sources",
        lambda self, limit=10: {"ok_sources": 1, "total_sources": 1, "saved": 1},
    )

    result = bootstrap._phase_news(_ctx(), db_session)

    assert calls["rss"] == 0
    assert result["status"] == "done"


@pytest.mark.unit
def test_news_phase_fetches_and_saves_when_empty(db_session, monkeypatch):
    item = {
        "title": "引导测试新闻",
        "content": "内容",
        "source": "引导测试源",
        "url": "https://example.invalid/bootstrap-news",
        "published_at": timeutil.now_naive(),
    }
    monkeypatch.setattr(
        "app.services.news_service.NewsService.fetch_all_rss_news",
        lambda self, limit_per_source=10: [item],
    )
    monkeypatch.setattr(
        "app.services.news_digest.NewsDigestService.fetch_all_sources",
        lambda self, limit=10: {"ok_sources": 1, "total_sources": 1, "saved": 2},
    )

    result = bootstrap._phase_news(_ctx(), db_session)

    from app.models.news import GoldNews

    assert result["status"] == "done"
    assert "写入 1 条" in result["note"]
    assert db_session.query(GoldNews).count() == 1


@pytest.mark.unit
def test_news_phase_is_honest_when_all_sources_return_nothing(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.news_service.NewsService.fetch_all_rss_news",
        lambda self, limit_per_source=10: [],
    )
    monkeypatch.setattr(
        "app.services.news_digest.NewsDigestService.fetch_all_sources",
        lambda self, limit=10: {"ok_sources": 0, "total_sources": 3, "saved": 0},
    )

    result = bootstrap._phase_news(_ctx(), db_session)

    assert result["status"] == "failed", "一条都没抓到却标 done 等于骗自己"
    assert "写入 0 条" in result["note"]


# --------------------------------------------------------------------------- #
# 量化因子
# --------------------------------------------------------------------------- #
def _coverage_row(key: str, observations: int, sparse=()) -> dict:
    return {
        "factor_key": key,
        "observations": observations,
        "sparse_years": list(sparse),
        "years": [2026] if observations else [],
        "accumulating": False,
    }


@pytest.mark.unit
def test_quant_phase_skips_when_all_series_have_data(db_session, monkeypatch):
    monkeypatch.setattr(
        "scripts.backfill_quant.coverage_rows",
        lambda db, *, years, today: [_coverage_row("gold_close", 5000)],
    )
    called = {"n": 0}

    def _boom(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("没有缺失序列时不该跑整轮回填")

    monkeypatch.setattr("scripts.backfill_quant.run_backfill", _boom)

    result = bootstrap._phase_quant_history(_ctx(), db_session)

    assert result["status"] == "skipped"
    assert called["n"] == 0


@pytest.mark.unit
def test_quant_phase_runs_backfill_for_missing_series(db_session, monkeypatch):
    monkeypatch.setattr(
        "scripts.backfill_quant.coverage_rows",
        lambda db, *, years, today: [
            _coverage_row("gpr_daily", 0),
            _coverage_row("central_bank", 40, sparse=[1990]),
        ],
    )
    captured: dict = {}

    def fake_run(db, *, years, rounds, today, emit):
        captured.update(years=years, rounds=rounds)
        emit("假回填")
        return {
            "rounds": 2,
            "stopped_reason": "no_progress",
            "inserted": 5,
            "updated": 1,
            "coverage": [{"sparse_years": [1990]}],
        }

    monkeypatch.setattr("scripts.backfill_quant.run_backfill", fake_run)

    result = bootstrap._phase_quant_history(_ctx(), db_session)

    assert result["status"] == "done"
    assert captured["years"] == settings.QUANT_BACKFILL_YEARS
    assert "新增 5 行" in result["note"]


@pytest.mark.unit
def test_revision_phase_uses_ledger_backfill_helper(db_session, monkeypatch):
    monkeypatch.setattr("scripts.migrate_quant.ledger_backfill_rows", lambda bind: 3)
    monkeypatch.setattr("scripts.migrate_quant.seed_ledger", lambda bind: 3)

    result = bootstrap._phase_revisions(_ctx(), db_session)

    assert result["status"] == "done"
    assert "3 行" in result["note"]


@pytest.mark.unit
def test_revision_phase_skips_when_ledger_is_complete(db_session, monkeypatch):
    monkeypatch.setattr("scripts.migrate_quant.ledger_backfill_rows", lambda bind: 0)

    def _boom(bind):
        raise AssertionError("流水已完整时不该再写")

    monkeypatch.setattr("scripts.migrate_quant.seed_ledger", _boom)

    result = bootstrap._phase_revisions(_ctx(), db_session)

    assert result["status"] == "skipped"


# --------------------------------------------------------------------------- #
# 首轮分析
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_analyses_phase_degrades_honestly_without_llm(db_session, monkeypatch):
    monkeypatch.setattr("app.services.llm_provider.is_configured", lambda: False)

    result = bootstrap._phase_analyses(_ctx(), db_session)

    assert result["status"] == "skipped"
    assert "LLM 未配置" in result["note"]


# --------------------------------------------------------------------------- #
# 编排
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_run_bootstrap_injects_steps_and_survives_single_failure():
    from app.database import SessionLocal, engine

    seen: list[str] = []

    def make_runner(name: str):
        def runner(ctx, db):
            seen.append(name)
            return {"status": "done", "note": name}

        return runner

    def boom(ctx, db):
        raise RuntimeError("源站不可达")

    steps = {key: make_runner(key) for key, _, _ in bootstrap.STEPS}
    steps["news"] = boom

    snapshot = bootstrap.run_bootstrap(engine, steps=steps, session_factory=SessionLocal)

    assert seen == [key for key, _, _ in bootstrap.STEPS if key != "news"]
    phases = {phase["key"]: phase for phase in snapshot["phases"]}
    assert phases["news"]["status"] == "failed"
    assert "源站不可达" in phases["news"]["note"]
    assert phases["analyses"]["status"] == "done", "单阶段失败不得中断后续阶段"
    assert snapshot["ready"] is False
    assert "news" in snapshot["error"], "失败的阶段必须在总快照里点名"
    assert snapshot["step"] == {"index": 6, "total": 7}
    assert snapshot["started_at"] and snapshot["finished_at"]


@pytest.mark.unit
def test_run_bootstrap_ready_when_all_steps_complete():
    from app.database import SessionLocal, engine

    steps = {key: (lambda ctx, db: {"status": "done", "note": key}) for key, _, _ in bootstrap.STEPS}

    snapshot = bootstrap.run_bootstrap(engine, steps=steps, session_factory=SessionLocal)

    assert snapshot["status"] == "done"
    assert snapshot["ready"] is True
    assert snapshot["error"] is None
    assert snapshot["step"]["index"] == snapshot["step"]["total"] == len(bootstrap.STEPS)


@pytest.mark.unit
def test_start_background_marks_skipped_when_scheduler_disabled(monkeypatch):
    from app.database import engine

    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)

    snapshot = bootstrap.start_background(engine)

    assert snapshot["enabled"] is True
    assert snapshot["status"] == "done"
    assert snapshot["ready"] is True
    assert all(phase["status"] == "skipped" for phase in snapshot["phases"])
    assert any("SCHEDULER_ENABLED" in (phase["note"] or "") for phase in snapshot["phases"])


@pytest.mark.unit
def test_start_background_respects_disabled_bootstrap(monkeypatch):
    from app.database import engine

    monkeypatch.setattr(settings, "AUTO_BOOTSTRAP", False)

    snapshot = bootstrap.start_background(engine)

    assert snapshot["enabled"] is False
    assert snapshot["status"] == "disabled"
    assert snapshot["ready"] is True