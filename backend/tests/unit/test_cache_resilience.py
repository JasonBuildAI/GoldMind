"""缓存的降级行为。

回归背景：`CACHE_DIR` 指向一个不可用的路径（已存在的文件、只读挂载、权限不足）时，
`_resolve_cache_dir()` 在**导入期**就抛 FileExistsError，于是
`import app.services.cache_manager` 失败，凡是依赖它的接口全部 500 —— 服务连启动都做不到。

缓存只是加速手段。它不可用应当是「慢一点」，不是「挂掉」。
"""
from __future__ import annotations

import pytest


@pytest.mark.unit
def test_cache_dir_does_not_raise_when_the_path_is_a_file(tmp_path, monkeypatch):
    """CACHE_DIR 指向一个已存在的文件时，不应抛异常。"""
    from app.config import settings
    from app.services import cache_manager

    # 不能用 tmp_path/"cache"：conftest 的 _isolate_cache_dir 已经把那个名字
    # 建成目录了，再往同名路径写文件会 PermissionError。
    blocker = tmp_path / "cache_blocked_by_a_file"
    blocker.write_text("not a directory", encoding="utf-8")

    monkeypatch.setattr(settings, "CACHE_DIR", str(blocker))
    monkeypatch.setattr(cache_manager, "_FILE_CACHE_ENABLED", True)

    resolved = cache_manager._resolve_cache_dir()  # 不应抛

    assert resolved == blocker
    assert cache_manager._FILE_CACHE_ENABLED is False, "应当关掉文件缓存"


@pytest.mark.unit
def test_cache_dir_stays_enabled_for_a_normal_directory(tmp_path, monkeypatch):
    from app.config import settings
    from app.services import cache_manager

    target = tmp_path / "cache"
    monkeypatch.setattr(settings, "CACHE_DIR", str(target))
    monkeypatch.setattr(cache_manager, "_FILE_CACHE_ENABLED", False)

    resolved = cache_manager._resolve_cache_dir()

    assert resolved == target
    assert resolved.is_dir()
    assert cache_manager._FILE_CACHE_ENABLED is True, "正常目录应当启用文件缓存"


@pytest.mark.unit
def test_memory_cache_still_works_without_the_file_cache(monkeypatch):
    """文件缓存关掉后，内存缓存必须照常工作 —— 这是降级而不是失效。"""
    from app.services import cache_manager

    monkeypatch.setattr(cache_manager, "_FILE_CACHE_ENABLED", False)
    cache = cache_manager.CacheManager("resilience_probe", ttl=60)

    cache.set({"value": 42})

    assert cache.get() == {"value": 42}
    assert cache.exists() is True


@pytest.mark.unit
def test_get_cache_status_reports_availability(monkeypatch):
    from app.services import cache_manager

    monkeypatch.setattr(cache_manager, "_FILE_CACHE_ENABLED", False)

    status = cache_manager.get_cache_status()

    assert status["file_cache_enabled"] is False
    assert status["file_cache_keys"] == [], "不可用时不该去 glob 目录"


@pytest.mark.integration
def test_health_reports_a_disabled_file_cache_as_degraded(client, monkeypatch):
    """文件缓存被关掉是降级状态，`/health` 不该报 ok。"""
    from app.services import cache_manager

    monkeypatch.setattr(cache_manager, "_FILE_CACHE_ENABLED", False)

    cache_section = client.get("/health").json()["services"]["cache"]

    assert cache_section["status"] == "degraded"
    assert cache_section["file_cache_enabled"] is False


@pytest.mark.integration
def test_health_reports_a_working_file_cache_as_ok(client, monkeypatch):
    from app.services import cache_manager

    monkeypatch.setattr(cache_manager, "_FILE_CACHE_ENABLED", True)

    cache_section = client.get("/health").json()["services"]["cache"]

    assert cache_section["status"] == "ok"
    assert cache_section["file_cache_enabled"] is True


@pytest.mark.integration
def test_endpoints_survive_a_disabled_file_cache(client, seed_gold_prices, monkeypatch):
    """回归：缓存目录不可用时，5 个接口直接 500。

    受影响的正是那些会碰缓存的接口（stats / prices / 各 AI 分析）。
    """
    from app.services import cache_manager

    monkeypatch.setattr(cache_manager, "_FILE_CACHE_ENABLED", False)
    seed_gold_prices(days=5)

    paths = [
        "/health",
        "/api/gold/stats",
        "/api/gold/latest",
        "/api/gold/prices/daily",
        "/api/gold/prices/correlation",
        "/api/gold/factors",
        "/api/gold/news",
        "/api/gold/predictions",
        "/api/gold/bullish-factors-ai",
        "/api/gold/bearish-factors-ai",
        "/api/gold/institution-predictions-ai",
        "/api/gold/investment-advice-ai",
        "/api/gold/market-summary-ai",
    ]

    failures = []
    for path in paths:
        response = client.get(path)
        if response.status_code >= 500:
            failures.append(f"{path} -> {response.status_code}")

    assert not failures, "文件缓存不可用时这些接口不该 5xx：\n" + "\n".join(failures)


@pytest.mark.integration
def test_corrupt_cache_files_do_not_break_endpoints(client, seed_gold_prices, monkeypatch):
    """缓存文件损坏（写到一半、被手工改坏）时，接口应当当作缓存未命中。"""
    from app.services import cache_manager

    seed_gold_prices(days=5)
    cache_dir = cache_manager.CACHE_DIR
    for name in ("bullish_factors", "bearish_factors", "market_summary",
                 "realtime_gold_price", "investment_advice"):
        (cache_dir / f"{name}.json").write_text("{ not valid json", encoding="utf-8")

    for path in ("/api/gold/stats", "/api/gold/bullish-factors-ai",
                 "/api/gold/market-summary-ai", "/api/gold/investment-advice-ai"):
        response = client.get(path)
        assert response.status_code < 500, f"{path} 遇到损坏缓存时返回 {response.status_code}"


# --------------------------------------------------------------------------- #
# 并发写入
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_concurrent_writes_to_the_same_key_all_succeed(monkeypatch):
    """回归：同一个缓存键被并发写时，写入会失败。

    原实现固定用 `<key>.tmp` 作临时文件名，于是并发写会争抢同一个文件：
    Windows 上稳定报 WinError 32 / 5（写入直接失败），
    Linux 上没有那个文件锁，会写出交错的内容或把半成品 rename 成正式文件。
    实测 8 线程 × 25 轮即可复现一批失败。

    现在每次写入用独立临时文件，并按 key 串行化替换。
    """
    import json
    import threading

    from app.services import cache_manager

    failures: list[str] = []
    monkeypatch.setattr(
        cache_manager.logger, "error", lambda msg, *a, **k: failures.append(str(msg))
    )

    cache = cache_manager.CacheManager("concurrent_probe", ttl=3600)
    payload = "x" * 50_000

    def worker(n: int) -> None:
        for r in range(10):
            cache.set({"writer": n, "round": r, "blob": payload})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not failures, f"并发写入出现失败：{failures[:3]}"

    # 最终文件必须是完整合法的 JSON，而不是交错出来的半成品
    parsed = json.loads(cache.file_path.read_text(encoding="utf-8"))
    assert len(parsed["data"]["blob"]) == len(payload)
    assert not list(cache.file_path.parent.glob("*.tmp")), "留下了临时文件"


@pytest.mark.unit
def test_cache_write_does_not_use_a_shared_temp_name(monkeypatch):
    """临时文件名必须每次唯一 —— 固定名字正是竞态的根源。"""
    import tempfile

    from app.services import cache_manager

    cache = cache_manager.CacheManager("temp_name_probe", ttl=3600)
    seen: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def spy(*args, **kwargs):
        result = real_mkstemp(*args, **kwargs)
        seen.append(result[1])
        return result

    monkeypatch.setattr(cache_manager.tempfile, "mkstemp", spy)

    cache.set({"a": 1})
    cache.set({"a": 2})

    assert len(seen) == 2
    assert seen[0] != seen[1], "两次写入用了同一个临时文件名"


@pytest.mark.unit
def test_cache_write_self_heals_a_deleted_directory(tmp_path, monkeypatch):
    """缓存目录在运行期被删掉时，写入应当自建目录，而不是一直 ENOENT。

    回归：CI 的 E2E 里 global-setup 会清空 ``backend/e2e-cache``，之后后端进程
    持有的目录不存在，每一笔文件缓存写入都失败（日志实证）。
    写入前补一次 mkdir 即可自愈；文件缓存是加速手段，不该静默失效。
    """
    import json
    import shutil

    from app.services import cache_manager

    monkeypatch.setattr(cache_manager, "_FILE_CACHE_ENABLED", True)
    cache = cache_manager.CacheManager("self_heal_probe", ttl=3600)

    target = tmp_path / "runtime-cache"
    monkeypatch.setattr(cache, "file_path", target / "self_heal_probe.json")

    cache.set({"value": 1})                      # 目录不存在 -> 应当自建
    assert cache.file_path.exists(), "首次写入没有创建目录"

    shutil.rmtree(target)                        # 运行期被删掉
    cache.set({"value": 2})                      # 应当自愈
    payload = json.loads(cache.file_path.read_text(encoding="utf-8"))
    assert payload["data"] == {"value": 2}


@pytest.mark.unit
def test_delete_invalidates_memory_and_file_cache(monkeypatch):
    """`delete()` 必须同时清掉内存与文件 —— full_refresh 靠它让研究页立刻换数字。"""
    from app.services import cache_manager

    cache = cache_manager.CacheManager("delete_probe", ttl=3600)
    cache.set({"value": 1})
    assert cache.exists() is True
    assert cache.file_path.exists()

    cache.delete()

    assert cache.get() is None
    assert cache.exists() is False
    assert not cache.file_path.exists()

    cache.delete()  # 文件本就不存在：幂等，不抛
