"""量化定时任务的注册守卫。

「及时性与可更新性」的入口就是调度器里的这两个任务：定期同步因子、定期重算
预测。注册代码被改坏（任务没进调度器）时页面不会报错，只会一直停在旧数据上，
而所有单元测试仍然全绿 —— 所以这里直接钉住注册结果本身。
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
    monkeypatch.setattr(sched.settings, "QUANT_ENABLED", True)
    return fake


def test_init_scheduler_registers_factor_sync(fake_scheduler):
    sched.init_scheduler()

    assert "update_factors" in fake_scheduler.jobs
    assert fake_scheduler.started is True


def test_factor_sync_job_runs_the_quant_sync(fake_scheduler, monkeypatch):
    """任务函数必须真的接到 run_sync 上，而不是接到一个空实现。"""
    calls = []
    monkeypatch.setattr(sched, "_run_factors_sync", lambda: calls.append(True))

    sched.init_scheduler()
    asyncio.run(fake_scheduler.jobs["update_factors"].func())

    assert calls == [True]


def test_quant_jobs_are_skipped_when_disabled(fake_scheduler, monkeypatch):
    monkeypatch.setattr(sched.settings, "QUANT_ENABLED", False)

    sched.init_scheduler()

    assert "update_factors" not in fake_scheduler.jobs


def test_sync_job_is_registered_before_the_scheduler_starts(monkeypatch):
    """APScheduler 启动后再 add_job 需要 wakeup；这里要求注册全部发生在 start 之前。"""
    order: list[str] = []

    class OrderedScheduler(FakeScheduler):
        def add_job(self, func, trigger, **kwargs):
            order.append("add")
            super().add_job(func, trigger, **kwargs)

        def start(self):
            order.append("start")
            super().start()

    fake = OrderedScheduler()
    monkeypatch.setattr(sched, "scheduler", fake)
    monkeypatch.setattr(sched.settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(sched.settings, "QUANT_ENABLED", True)
    sched.init_scheduler()

    assert order[-2:] == ["add", "start"]
