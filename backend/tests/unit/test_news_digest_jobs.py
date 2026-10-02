"""消息板块定时任务的注册守卫。

「消息会自己更新」的唯一入口就是调度器里的 `update_news_digest`：
注册代码被改坏时页面不会报错，只会一直停在旧数据上 —— 所以直接钉住
注册结果、任务函数是否接到真实抓取实现、以及会话是否被关闭。
"""
from __future__ import annotations

import asyncio

import pytest

from app import scheduler as sched


class FakeJob:
    def __init__(self, job_id: str, name: str, func):
        self.id = job_id
        self.name = name
        self.func = func
        self.next_run_time = None


class FakeScheduler:
    def __init__(self) -> None:
        self.jobs: dict[str, FakeJob] = {}
        self.started = False

    def add_job(self, func, trigger, **kwargs):
        self.jobs[kwargs["id"]] = FakeJob(kwargs["id"], kwargs.get("name", ""), func)

    def get_jobs(self):
        return list(self.jobs.values())

    def start(self):
        self.started = True


@pytest.fixture
def fake_scheduler(monkeypatch):
    fake = FakeScheduler()
    monkeypatch.setattr(sched, "scheduler", fake)
    monkeypatch.setattr(sched.settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(sched.settings, "QUANT_ENABLED", False)
    return fake


@pytest.mark.unit
def test_init_scheduler_registers_news_digest(fake_scheduler):
    sched.init_scheduler()

    assert "update_news_digest" in fake_scheduler.jobs
    assert fake_scheduler.started is True


@pytest.mark.unit
def test_news_digest_job_runs_the_crawl(fake_scheduler, monkeypatch):
    """任务函数必须真的接到抓取实现上，而不是一个空壳。"""
    calls: list[bool] = []
    monkeypatch.setattr(sched, "_run_news_digest_sync", lambda: calls.append(True))

    sched.init_scheduler()
    asyncio.run(fake_scheduler.jobs["update_news_digest"].func())

    assert calls == [True]


@pytest.mark.unit
def test_news_digest_job_survives_a_crawl_failure(fake_scheduler, monkeypatch):
    def boom():
        raise RuntimeError("全部来源挂掉")

    monkeypatch.setattr(sched, "_run_news_digest_sync", boom)

    sched.init_scheduler()
    asyncio.run(fake_scheduler.jobs["update_news_digest"].func())  # 不应抛异常


@pytest.mark.unit
def test_news_digest_sync_uses_the_service_and_closes_session(monkeypatch):
    import app.database as database
    import app.services.news_digest as news_digest

    class FakeSession:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    session = FakeSession()
    calls = []
    monkeypatch.setattr(database, "SessionLocal", lambda: session)
    monkeypatch.setattr(
        news_digest.NewsDigestService,
        "fetch_all_sources",
        lambda self, **kwargs: calls.append(self.db),
    )

    sched._run_news_digest_sync()

    assert calls == [session]
    assert session.closed is True
