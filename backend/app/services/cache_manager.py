"""缓存管理器 - 支持多进程共享

使用文件缓存实现多进程间的缓存共享
"""
import json
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional
from pathlib import Path

# 缓存目录
CACHE_DIR = Path(__file__).parent.parent.parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)

# 内存缓存（进程内）
_memory_cache = {}
_memory_cache_lock = threading.Lock()


class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_key: str, ttl: int = 7200):
        """
        Args:
            cache_key: 缓存键
            ttl: 缓存过期时间（秒），默认2小时
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
            print(f"[CacheManager] 读取文件缓存失败: {e}")
        
        return None
    
    def set(self, data: Dict[str, Any]) -> None:
        """设置缓存数据（同时更新内存和文件，使用原子写入保证一致性）"""
        timestamp = time.time()
        
        # 1. 更新内存缓存
        with _memory_cache_lock:
            _memory_cache[self.cache_key] = (data, timestamp)
        
        # 2. 更新文件缓存（使用原子写入避免并发冲突和文件损坏）
        try:
            cache_data = {
                'data': data,
                '_timestamp': timestamp,
                '_created_at': datetime.now().isoformat()
            }
            
            # 使用临时文件+原子重命名，避免写入中断导致文件损坏
            temp_file = self.file_path.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            # 原子重命名（Windows/Linux都安全，保证文件完整性）
            temp_file.replace(self.file_path)
            
        except Exception as e:
            print(f"[CacheManager] 写入文件缓存失败: {e}")
            # 清理临时文件（如果存在）
            try:
                temp_file = self.file_path.with_suffix('.tmp')
                if temp_file.exists():
                    temp_file.unlink()
            except:
                pass
    
    def delete(self) -> None:
        """删除缓存"""
        # 删除内存缓存
        with _memory_cache_lock:
            if self.cache_key in _memory_cache:
                del _memory_cache[self.cache_key]
        
        # 删除文件缓存
        try:
            if self.file_path.exists():
                self.file_path.unlink()
        except Exception as e:
            print(f"[CacheManager] 删除文件缓存失败: {e}")
    
    def exists(self) -> bool:
        """检查缓存是否存在且有效"""
        return self.get() is not None


def clear_all_cache():
    """清除所有缓存"""
    global _memory_cache
    with _memory_cache_lock:
        _memory_cache.clear()
    
    # 清除文件缓存
    try:
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
    except Exception as e:
        print(f"[CacheManager] 清除文件缓存失败: {e}")


def get_cache_status():
    """获取缓存状态"""
    with _memory_cache_lock:
        memory_keys = list(_memory_cache.keys())
    
    file_keys = [f.stem for f in CACHE_DIR.glob("*.json")]
    
    return {
        "memory_cache_keys": memory_keys,
        "file_cache_keys": file_keys,
        "cache_dir": str(CACHE_DIR)
    }
