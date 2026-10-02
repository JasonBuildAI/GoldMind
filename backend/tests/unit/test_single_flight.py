"""单飞去重守卫的测试。

背景：各分析服务在缓存未命中时会触发一次后台分析。原实现每次触发都往线程池塞一个
任务，N 个并发请求就会把同一次分析重复执行 N 遍 —— 每一遍都真实调用付费 LLM。
"""
import threading
import time

import pytest

from app.services.single_flight import SingleFlight, single_flight


# --------------------------------------------------------------------------- #
# 守卫本身
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_first_begin_wins_and_second_is_rejected():
    guard = SingleFlight()

    assert guard.try_begin("k") is True
    assert guard.try_begin("k") is False

    guard.end("k")
    assert guard.try_begin("k") is True
    guard.end("k")


@pytest.mark.unit
def test_keys_are_independent():
    guard = SingleFlight()

    assert guard.try_begin("a") is True
    assert guard.try_begin("b") is True

    guard.end("a")
    guard.end("b")


@pytest.mark.unit
def test_end_without_begin_is_ignored():
    """异常路径上可能重复释放，不能因此抛错。"""
    guard = SingleFlight()

    guard.end("never-started")  # 不应抛异常


@pytest.mark.unit
def test_is_running_reflects_state():
    guard = SingleFlight()

    assert guard.is_running("k") is False
    guard.try_begin("k")
    assert guard.is_running("k") is True
    guard.end("k")
    assert guard.is_running("k") is False


@pytest.mark.unit
def test_only_one_of_many_threads_wins():
    """并发争抢时恰好一个线程拿到执行权。"""
    guard = SingleFlight()
    winners: list[int] = []
    start = threading.Barrier(16)

    def contender(index: int) -> None:
        start.wait(timeout=5)
        if guard.try_begin("shared"):
            winners.append(index)

    threads = [threading.Thread(target=contender, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert len(winners) == 1, f"应当只有一个线程拿到执行权，实际 {len(winners)} 个"


# --------------------------------------------------------------------------- #
# 接入效果：真实的后台触发逻辑
# --------------------------------------------------------------------------- #
@pytest.mark.integration
@pytest.mark.real_background
def test_repeated_triggers_run_the_analysis_once(db_session, monkeypatch):
    """回归：连续触发多次，后台分析只应真正执行一次。"""
    from app.services.bullish_factor_service import BullishFactorService

    key = BullishFactorService._ANALYSIS_KEY
    single_flight.end(key)  # 确保起点干净

    service = BullishFactorService(db_session)

    runs: list[int] = []
    started = threading.Event()
    release = threading.Event()

    def slow_task(*, force: bool = False) -> None:
        runs.append(1)
        started.set()
        release.wait(timeout=10)

    monkeypatch.setattr(service, "_background_analysis_task", slow_task)

    # 第一次触发应当启动任务，并在整个执行期间占住这个 key
    for _ in range(5):
        service._trigger_background_analysis()

    assert started.wait(timeout=5), "后台任务没有启动"

    # 任务仍在运行，此时再触发多次都不应排队
    for _ in range(5):
        service._trigger_background_analysis()

    release.set()

    # 等 key 释放
    deadline = time.time() + 5
    while single_flight.is_running(key) and time.time() < deadline:
        time.sleep(0.02)

    assert len(runs) == 1, f"后台分析应只执行一次，实际执行了 {len(runs)} 次"


@pytest.mark.integration
@pytest.mark.real_background
def test_key_is_released_after_the_task_finishes(db_session, monkeypatch):
    """任务结束后必须释放，否则该服务再也不会更新分析。"""
    from app.services.bearish_factor_service import BearishFactorService

    key = BearishFactorService._ANALYSIS_KEY
    single_flight.end(key)

    service = BearishFactorService(db_session)
    done = threading.Event()

    def quick_task(*, force: bool = False) -> None:
        done.set()

    monkeypatch.setattr(service, "_background_analysis_task", quick_task)

    service._trigger_background_analysis()
    assert done.wait(timeout=5)

    deadline = time.time() + 5
    while single_flight.is_running(key) and time.time() < deadline:
        time.sleep(0.02)

    assert single_flight.is_running(key) is False, "任务结束后必须释放 key"

    # 释放之后还能再次触发
    service._trigger_background_analysis()
    assert done.wait(timeout=5)


@pytest.mark.integration
@pytest.mark.real_background
def test_submit_failure_releases_the_key(db_session, monkeypatch):
    """线程池提交失败时必须释放 key，否则该服务的分析会永久卡死。"""
    import app.services.bullish_factor_service as bullish_module
    from app.services.bullish_factor_service import BullishFactorService

    key = BullishFactorService._ANALYSIS_KEY
    single_flight.end(key)

    class _BrokenExecutor:
        def submit(self, *args, **kwargs):
            raise RuntimeError("线程池已关闭")

    monkeypatch.setattr(bullish_module, "_executor", _BrokenExecutor())

    service = BullishFactorService(db_session)
    service._trigger_background_analysis()  # 不应抛异常

    assert single_flight.is_running(key) is False, "提交失败后必须释放 key"


@pytest.mark.integration
def test_scheduled_refresh_skips_when_an_analysis_is_already_running(db_session, monkeypatch):
    """定时任务与后台任务撞车时不应重复调用付费 LLM。

    定时任务走的是 refresh_analysis_sync，它原先绕过了后台触发那条路径，
    因此即使加了单飞也仍可能与启动预热的后台任务重复执行。
    """
    from app.services.bullish_factor_service import BullishFactorService

    key = BullishFactorService._ANALYSIS_KEY
    single_flight.end(key)

    service = BullishFactorService(db_session)
    calls: list[int] = []

    def fake_analyze(db, *, force: bool = False):
        calls.append(1)
        return {"bullish_factors": [], "analysis_summary": "", "last_updated": ""}

    monkeypatch.setattr(service.analyzer, "analyze", fake_analyze)

    # 模拟「后台分析正在跑」
    assert single_flight.try_begin(key) is True
    service.refresh_analysis_sync()
    assert calls == [], "已有分析在跑时，定时刷新不应再调用模型"
    single_flight.end(key)

    # 释放之后应当正常执行
    service.refresh_analysis_sync()
    assert len(calls) == 1


@pytest.mark.integration
def test_scheduled_refresh_releases_the_key_on_success(db_session, monkeypatch):
    """定时刷新正常结束后也要释放，否则后续刷新会被永久跳过。"""
    from app.services.bearish_factor_service import BearishFactorService

    key = BearishFactorService._ANALYSIS_KEY
    single_flight.end(key)

    service = BearishFactorService(db_session)
    monkeypatch.setattr(
        service.analyzer,
        "analyze",
        lambda db, *, force=False: {"bearish_factors": [], "analysis_summary": "", "last_updated": ""},
    )

    service.refresh_analysis_sync()

    assert single_flight.is_running(key) is False
