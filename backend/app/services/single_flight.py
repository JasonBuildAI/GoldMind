"""后台任务的单飞去重（single-flight）。

各分析服务在缓存未命中时都会触发一次后台分析。原实现**每次触发都往线程池里塞一个
任务**，于是 N 个并发请求就会把同一次分析重复执行 N 遍 —— 而每一遍都真实调用付费
LLM。服务刚启动、或缓存刚过期的时刻，恰恰是并发最高的时刻，浪费最明显。

本模块保证：同一个 key 同时只允许一个任务在执行，重复触发直接跳过（不排队）。
"""
from __future__ import annotations

import threading
from typing import Dict


class SingleFlight:
    """按 key 去重的任务守卫。"""

    def __init__(self) -> None:
        self._locks: Dict[str, threading.Lock] = {}
        self._registry_lock = threading.Lock()

    def _lock_for(self, key: str) -> threading.Lock:
        with self._registry_lock:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def try_begin(self, key: str) -> bool:
        """尝试占用 key。

        Returns:
            True 表示调用方拿到了执行权，必须在结束后调用 :meth:`end`；
            False 表示同 key 已有任务在跑，调用方应直接跳过。
        """
        return self._lock_for(key).acquire(blocking=False)

    def end(self, key: str) -> None:
        """释放 key。未持有时静默忽略（避免在异常路径上二次抛错）。"""
        try:
            self._lock_for(key).release()
        except RuntimeError:
            pass

    def is_running(self, key: str) -> bool:
        """key 当前是否被占用（供测试与监控使用）。"""
        lock = self._lock_for(key)
        acquired = lock.acquire(blocking=False)
        if acquired:
            lock.release()
            return False
        return True


# 全局单例：各服务用自己的 key，互不影响
single_flight = SingleFlight()
