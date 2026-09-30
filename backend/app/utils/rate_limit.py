"""滑动窗口限流器。

为什么单独成模块：原实现把请求记录挂在中间件函数对象上，并且只清理时间戳、
**从不删除 IP 键** —— 一个「来过一次就再也没来」的 IP 会永久占着内存，
长期运行必然无界增长。它还对所有路径一视同仁，既包括健康检查，
也包括会触发付费 LLM 调用的接口。
"""
from __future__ import annotations

import threading
import time
from typing import Dict, List, Optional, Tuple

# 跟踪的 key 超过该数量时做一次全量清理
_SWEEP_THRESHOLD = 1024


class SlidingWindowRateLimiter:
    """按 key（通常是客户端 IP）计数的滑动窗口限流器。

    线程安全。内存占用与「窗口内有活动的 key 数量」成正比，
    而不是历史 key 总数：访问时清理该 key 的过期时间戳，
    键数量超阈值时再全量清理一次。
    """

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        if limit <= 0:
            raise ValueError("limit 必须为正数")
        if window_seconds <= 0:
            raise ValueError("window_seconds 必须为正数")
        self.limit = limit
        self.window = window_seconds
        self._records: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, now: Optional[float] = None) -> Tuple[bool, int]:
        """记录一次请求并判断是否放行。

        Args:
            key: 限流维度，通常是客户端 IP。
            now: 仅测试使用的时间源（单调秒）。

        Returns:
            ``(是否放行, 建议的重试等待秒数)``；放行时等待秒数为 0。
        """
        current = time.monotonic() if now is None else now
        cutoff = current - self.window

        with self._lock:
            timestamps = [t for t in self._records.get(key, []) if t > cutoff]

            if len(timestamps) >= self.limit:
                # 保留窗口内的记录，供后续请求继续判断
                self._records[key] = timestamps
                oldest = timestamps[0]
                retry_after = max(1, int(self.window - (current - oldest)) + 1)
                return False, retry_after

            timestamps.append(current)
            self._records[key] = timestamps
            self._sweep(cutoff)
            return True, 0

    def _sweep(self, cutoff: float) -> None:
        """键数量超阈值时清理所有已完全过期的键。

        调用方必须已持有 ``self._lock``。
        """
        if len(self._records) < _SWEEP_THRESHOLD:
            return
        stale = [k for k, ts in self._records.items() if not any(t > cutoff for t in ts)]
        for k in stale:
            del self._records[k]

    def tracked_keys(self) -> int:
        """当前仍在跟踪的 key 数量（供测试与监控使用）。"""
        with self._lock:
            return len(self._records)
