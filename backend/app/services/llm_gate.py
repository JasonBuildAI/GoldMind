"""LLM 调用门控：输入指纹去重 + 每日调用预算（2.0.2 第 19 条）。

两件事，都为了同一条底线：**付费调用只花在有信息增量的地方**。

1. **输入指纹**：把 prompt 里易变的时间戳等值剔除后做 sha256。若某服务本次
   输入指纹与上次成功产出的指纹相同（且缓存里还有那份结果），就不再调用 LLM，
   直接复用缓存 —— 输入没变，模型只会再生成一遍同一份内容。
   POST 刷新是用户的显式意图，传 ``force=True`` 跳过该门控。
2. **每日预算**：`LLM_DAILY_CALL_BUDGET`（默认 200）限制一天内真实的 chat 调用
   次数。计数发生在每次真正发起调用之前（失败/被风控的尝试同样计入 —— 端点是
   按请求计费的）。用尽后抛 :class:`LLMBudgetExceeded`，各分析服务照常走
   「暂不可用」路径，不会编造内容。

状态落在缓存目录的 `llm_gate.json`（与 CacheManager 同一个目录，测试用的
`CACHE_DIR` 隔离对它同样生效）。日期口径走 `timeutil.today()`（项目时区红线）。

约定：预算是**安全阀**，不是计费系统 —— 多进程同时跑时计数可能低估
（每进程各写各读），所以它是「大致上限」。真实账单以端点侧为准。
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from app.config import settings
from app.utils import timeutil
from loguru import logger


class LLMBudgetExceeded(RuntimeError):
    """当日 LLM 调用预算已用尽。调用方应如实返回「暂不可用」。"""


_STATE_LOCK = threading.Lock()
_STATE_NAME = "llm_gate.json"


def _state_path() -> Path:
    # 延迟导入 cache_manager：它负责解析缓存目录（含测试用的 CACHE_DIR 覆盖），
    # 且避免模块级循环导入。
    from app.services import cache_manager

    return Path(cache_manager.CACHE_DIR) / _STATE_NAME


def _load_state() -> Dict[str, Any]:
    path = _state_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"fingerprints": {}, "calls": {}}
    except OSError as exc:  # 状态盘坏了不该拖垮分析：退化为「无记录」
        logger.warning(f"[LLMGate] 状态文件不可读（{path}）：{exc}")
        return {"fingerprints": {}, "calls": {}}
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"[LLMGate] 状态文件不是合法 JSON（{path}），按空状态处理")
        return {"fingerprints": {}, "calls": {}}
    state.setdefault("fingerprints", {})
    state.setdefault("calls", {})
    return state


def _save_state(state: Dict[str, Any]) -> None:
    path = _state_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, path)
    except OSError as exc:
        # 状态写不进去只影响门控与预算的精度，不该让分析失败。
        logger.warning(f"[LLMGate] 状态文件写入失败（{path}）：{exc}")


def prompt_fingerprint(prompt: str, *, volatile: Iterable[object] = ()) -> str:
    """prompt → 指纹。`volatile` 里列出的值是每次调用都会变的部分（如时间戳），

    先替换成占位符再哈希 —— 否则指纹永远不相等，门控等于没写。
    只剔除调用方**明确声明**的易变值：少剔一个最多是「多花一次调用」，
    多剔一个就会在输入真变了时错误地跳过（更危险）。
    """
    text = prompt
    for value in volatile:
        if value:
            text = text.replace(str(value), "\u0000volatile\u0000")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class CallGate:
    """指纹与预算的持久化门控。状态小、读写便宜，直接走文件。"""

    def is_unchanged(self, key: str, fingerprint: str) -> bool:
        with _STATE_LOCK:
            state = _load_state()
            recorded = state["fingerprints"].get(key) or {}
            return recorded.get("fingerprint") == fingerprint

    def record(self, key: str, fingerprint: str) -> None:
        """记录一次**成功产出**的输入指纹（跳过与失败都不记录）。"""
        with _STATE_LOCK:
            state = _load_state()
            state["fingerprints"][key] = {
                "fingerprint": fingerprint,
                "at": timeutil.now_iso(),
            }
            _save_state(state)

    def calls_today(self) -> int:
        state = _load_state()
        return int(state["calls"].get(timeutil.today().isoformat(), 0))

    def budget(self) -> int:
        return int(settings.LLM_DAILY_CALL_BUDGET)

    def remaining(self) -> Optional[int]:
        """剩余额度；未设上限（budget ≤ 0）时返回 None。"""
        if self.budget() <= 0:
            return None
        return max(0, self.budget() - self.calls_today())

    def ensure_budget(self) -> None:
        if self.budget() <= 0:
            return
        used = self.calls_today()
        if used >= self.budget():
            raise LLMBudgetExceeded(
                f"当日 LLM 调用预算已用尽（{used}/{self.budget()}，口径 {timeutil.today()}）；"
                "调大 LLM_DAILY_CALL_BUDGET 或等次日自动恢复。"
            )

    def note_call(self, count: int = 1) -> int:
        """记一次真实调用（在发起之前调用），返回今日累计次数。"""
        today = timeutil.today().isoformat()
        with _STATE_LOCK:
            state = _load_state()
            state["calls"][today] = int(state["calls"].get(today, 0)) + count
            # 只保留最近 7 天，避免文件无限增长
            for day in sorted(state["calls"])[:-7]:
                state["calls"].pop(day, None)
            _save_state(state)
            return state["calls"][today]

    def skip_if_unchanged(self, key: str, fingerprint: str, cache: Any) -> Optional[Dict[str, Any]]:
        """输入没变且缓存里还有结果时返回缓存，否则 None。"""
        if not self.is_unchanged(key, fingerprint):
            return None
        cached = cache.get() if cache is not None else None
        if cached:
            logger.info(f"[LLMGate] {key} 输入指纹未变，跳过 LLM 重算（复用缓存）")
            return cached
        return None

    def reset_fingerprints(self) -> None:
        """清空输入指纹（供应商 / 模型热切换后，旧模型的缓存结果不得复用）。

        只清指纹，**不动**当日调用计数：钱已经花出去了，预算是事实记录。
        """
        with _STATE_LOCK:
            state = _load_state()
            state["fingerprints"] = {}
            _save_state(state)

    def snapshot(self) -> Dict[str, Any]:
        """供 /health 展示的只读快照（不含 prompt / 密钥）。"""
        state = _load_state()
        return {
            "calls_today": self.calls_today(),
            "budget": self.budget(),
            "remaining": self.remaining(),
            "tracked_inputs": sorted(state["fingerprints"].keys()),
        }


gate = CallGate()


def reset_fingerprints() -> None:
    """模块级入口：配置热更新时由 config_watch 调用。"""
    gate.reset_fingerprints()
