"""调度器自愈接线：coalesce / misfire / 互斥、启动补差、每日运维任务。

变异验证（commit body 有记录）：
- 从任一任务去掉 JOB_DEFAULTS → 自愈参数用例必红；
- 不注册 daily_maintenance → 任务清单用例必红；
- 去掉启动补差 → 补差用例必红。
"""
from __future__ import annotations

import pytest

from app import scheduler as sched
from app.config import settings


class _FakeScheduler:
    def __init__(self) -> None:
        self.jobs: list[dict] = []
        self.running = False

    def add_job(self, func, trigger=None, **kwargs):
        self.jobs.append({"func": getattr(func, "__name__", str(func)), "trigger": trigger, **kwargs})

    def start(self) -> None:
        self.running = True

    def get_jobs(self):
        return []

    def shutdown(self) -> None:
        self.running = False


EXPECTED_RECURRING = {
    "update_prices",
    "update_dollar_index",
    "update_news",
    "update_news_digest",
    "update_ai_analysis",
    "update_factors",
    "update_quant_prediction",
    "daily_maintenance",
}
EXPECTED_CATCHUP = {"startup_prices", "startup_dollar", "startup_news", "startup_news_digest"}


@pytest.fixture
def fake_scheduler(monkeypatch):
    fake = _FakeScheduler()
    monkeypatch.setattr(sched, "scheduler", fake)
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", True)
    monkeypatch.setattr(settings, "QUANT_ENABLED", True)
    return fake


@pytest.mark.unit
def test_every_job_carries_self_healing_defaults(fake_scheduler):
    sched.init_scheduler()

    assert fake_scheduler.running
    assert fake_scheduler.jobs, "调度器必须注册任务"
    for job in fake_scheduler.jobs:
        assert job.get("coalesce") is True, f"{job['id']} 缺少 coalesce（错过窗口会重复补跑）"
        assert int(job.get("misfire_grace_time") or 0) == 3600, f"{job['id']} 缺少迟到宽限"
        assert job.get("max_instances") == 1, f"{job['id']} 允许并发执行"
        assert job.get("replace_existing") is True


@pytest.mark.unit
def test_expected_recurring_jobs_are_registered(fake_scheduler):
    sched.init_scheduler()

    ids = {job["id"] for job in fake_scheduler.jobs}
    missing = EXPECTED_RECURRING - ids
    assert not missing, f"少了调度任务：{missing}"


@pytest.mark.unit
def test_startup_catchup_runs_without_waiting_for_cron(fake_scheduler):
    sched.init_scheduler()

    by_id = {job["id"]: job for job in fake_scheduler.jobs}
    assert EXPECTED_CATCHUP <= set(by_id), "启动补差任务未注册"
    for job_id in EXPECTED_CATCHUP:
        assert by_id[job_id]["trigger"] == "date", "补差必须是启动后一次性触发"
        assert by_id[job_id]["run_date"] is not None