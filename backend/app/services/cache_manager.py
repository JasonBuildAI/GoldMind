"""缓存管理器 - 支持多进程共享

使用文件缓存实现多进程间的缓存共享
"""
import json
import os
import tempfile
import threading
import time

from typing import Any, Dict, Optional
from pathlib import Path

from app.utils import timeutil
from app.config import settings
from loguru import logger

# 缓存目录
# 文件缓存是否可用。目录建不出来时置 False，退化为纯内存缓存。
#
# 缓存只是加速手段，不该因为它不可用就让整个服务起不来 ——
# 原实现在这里直接抛，`import app.services.cache_manager` 就失败，
# 凡是（直接或间接）依赖它的接口全部 500，服务连启动都做不到。
_FILE_CACHE_ENABLED = True

def _resolve_cache_dir() -> Path:
    """解析缓存目录。

    可用 ``CACHE_DIR`` 覆盖，默认 ``backend/cache``。
    可配置的意义在于让测试使用独立目录 —— 否则测试会读写开发时的缓存，
    既让结果依赖历史状态，也可能把开发缓存改坏。

    目录不可用时**不抛异常**，只记一条警告并关掉文件缓存：
    常见原因有 ``CACHE_DIR`` 指向一个已存在的文件、挂载卷只读、权限不足。
    """
    global _FILE_CACHE_ENABLED

    configured = (settings.CACHE_DIR or "").strip()
    base = Path(configured) if configured else Path(__file__).parent.parent.parent / "cache"

    try:
        base.mkdir(parents=True, exist_ok=True)
        if not base.is_dir():
            raise NotADirectoryError(f"{base} 已存在但不是目录")
        # 成功即（重新）启用：这个函数如实报告当前状态，而不是只单向下调。
        _FILE_CACHE_ENABLED = True
    except OSError as exc:
        _FILE_CACHE_ENABLED = False
        logger.warning(
            f"[CacheManager] 缓存目录不可用（{base}）：{exc}。"
            "将只使用内存缓存：功能不受影响，只是多进程之间不再共享缓存。"
        )

    return base

CACHE_DIR = _resolve_cache_dir()

# 内存缓存（进程内）
_memory_cache = {}
_memory_cache_lock = threading.Lock()

# 每个缓存键一把写入锁。
#
# 为什么需要：`os.replace` 是原子的，但**同一个目标文件**被并发替换时，
# Windows 会直接报 WinError 5（拒绝访问）—— 原子性保证的是「不会读到半成品」，
# 不保证「并发替换都能成功」。实测 8 线程写同一个键会稳定失败一批。
# 锁把同一个键的写入串行化；不同键之间仍然并行。
#
# 跨进程（多 uvicorn worker）靠 _replace_with_retry 的重试兜底。
_file_write_locks: Dict[str, threading.Lock] = {}
_file_write_locks_guard = threading.Lock()

def _write_lock_for(cache_key: str) -> threading.Lock:
    with _file_write_locks_guard:
        return _file_write_locks.setdefault(cache_key, threading.Lock())

def _replace_with_retry(source: Path, target: Path, attempts: int = 5) -> None:
    """把 source 原子地替换成 target，遇到瞬时占用就重试。

    Windows 上若目标文件正被另一个进程打开（多 worker 同时写同一个键），
    os.replace 会抛 PermissionError。短暂重试通常就过去了。
    """
    last: Optional[PermissionError] = None
    for i in range(attempts):
        try:
            os.replace(source, target)
            return
        except PermissionError as exc:      # Windows 的占用 / 拒绝访问
            last = exc
            time.sleep(0.02 * (i + 1))
    if last is not None:
        raise last

# 分析结果的缓存时长（秒）。
#
# **必须 >= `UPDATE_AI_ANALYSIS_CRON` 的间隔**（当前 2 小时），原因：
# 缓存过期时会有一个用户请求触发一次**按需的付费 LLM 分析**，
# 而调度器本来马上就会刷新同一份结果。
# 机构预测原先用 3600（1 小时）而调度器每 2 小时才刷新一次 ——
# 于是每个周期都白白多花一次分析。
#
# 这条关系由 tests/unit/test_cache_ttl_vs_schedule.py 守住。
AI_ANALYSIS_CACHE_TTL = 7200

# 实时金价：这是「取一次外部行情」的缓存，与上面的分析缓存节奏完全不同
REALTIME_PRICE_CACHE_TTL = 30


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_key: str, ttl: int = AI_ANALYSIS_CACHE_TTL):
        """
        Args:
            cache_key: 缓存键
            ttl: 缓存过期时间（秒），默认见 AI_ANALYSIS_CACHE_TTL
        """
        self.cache_key = cache_key
        self.ttl = ttl
        self.file_path = CACHE_DIR / f"{cache_key}.json"
    
    def get(self) -> Optional[Dict[str, Any]]:
        """获取缓存数据（先查内存，再查文件）"""
        # 1. 检查内存缓存
        with _memory_cache_lock:
            if self.cache_key in _memory_cache:
                data, timestamp = _memory_cache[self.cache_key]
                if time.time() - timestamp < self.ttl:
                    return data
        
        # 2. 检查文件缓存
        if not _FILE_CACHE_ENABLED:
            return None
        try:
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    cached = json.load(f)
                    timestamp = cached.get('_timestamp', 0)
                    if time.time() - timestamp < self.ttl:
                        data = cached.get('data')
                        # 更新内存缓存
                        with _memory_cache_lock:
                            _memory_cache[self.cache_key] = (data, timestamp)
                        return data
        except Exception as e:
            logger.error(f"[CacheManager] 读取文件缓存失败: {e}")
        
        return None
    
    def set(self, data: Dict[str, Any]) -> None:
        """设置缓存数据（同时更新内存和文件，使用原子写入保证一致性）"""
        timestamp = time.time()
        
        # 1. 更新内存缓存
        with _memory_cache_lock:
            _memory_cache[self.cache_key] = (data, timestamp)
        
        # 2. 更新文件缓存（原子写入）
        if not _FILE_CACHE_ENABLED:
            return
        temp_path: Optional[Path] = None
        try:
            cache_data = {
                'data': data,
                '_timestamp': timestamp,
                '_created_at': timeutil.now_iso()
            }

            # 每次写入用**独立的**临时文件名。
            #
            # 原实现固定用 `<key>.tmp`，同一个键被并发写时会争抢同一个临时文件 ——
            # 多线程（刷新接口 + 后台分析）与多 worker 进程都会撞上：
            #   Windows：表现为 WinError 32 / 5，写入直接失败；
            #   Linux：没有那个文件锁，会写出交错的内容，或把半成品 rename 成正式文件。
            # 实测 8 线程 × 25 轮写同一个键，稳定复现一批写入失败。
            fd, temp_name = tempfile.mkstemp(
                dir=str(self.file_path.parent),
                prefix=f".{self.cache_key}.",
                suffix=".tmp",
            )
            temp_path = Path(temp_name)
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            # 同一个键的写入串行化：os.replace 原子，但并发替换同一目标在
            # Windows 上会报 WinError 5。不同键之间不受影响。
            with _write_lock_for(self.cache_key):
                _replace_with_retry(temp_path, self.file_path)
            temp_path = None      # 已成功替换，不用再清理

        except Exception as e:
            logger.error(f"[CacheManager] 写入文件缓存失败: {e}")
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass
    
    def exists(self) -> bool:
        """检查缓存是否存在且有效"""
        return self.get() is not None

def get_cache_status():
    """获取缓存状态。"""
    with _memory_cache_lock:
        memory_keys = list(_memory_cache.keys())

    file_keys: list[str] = []
    if _FILE_CACHE_ENABLED:
        try:
            file_keys = [f.stem for f in CACHE_DIR.glob("*.json")]
        except OSError as exc:
            # CACHE_DIR 指向文件之类的情况：报告为空，而不是让 /health 崩掉
            logger.warning(f"[CacheManager] 读取缓存目录失败: {exc}")

    return {
        "memory_cache_keys": memory_keys,
        "file_cache_keys": file_keys,
        "cache_dir": str(CACHE_DIR),
        # 让 /health 能说明「文件缓存为什么没生效」
        "file_cache_enabled": _FILE_CACHE_ENABLED,
    }
