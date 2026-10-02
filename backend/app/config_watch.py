"""`backend/.env` 热监听（2.0.2）：LLM 配置一出现/变化就自动生效，无需重启。

系统唯一的硬目标：填好 `backend/.env` 之后不再需要任何人工操作。但「填好」
可能发生在进程已经跑起来之后 —— 启动时没配 LLM、后来才补上，旧行为要求
重启进程。本模块每 `POLL_SECONDS` 秒读一次 .env 的键值快照：

- `LLM_*` 出现 / 修改 / 删除 → 就地重载对应字段、丢弃缓存的 LLM 客户端与
  输入指纹（旧供应商的缓存结果不得复用），随后在后台立即触发一轮**强制**
  分析（force=True，不受指纹门控影响）。
- 非 LLM 的变化（如 DATABASE_URL）→ 不改运行中的状态，只在快照里如实提示
  「需重启才能生效」。
- `CONFIG_WATCH=false`、或 `SCHEDULER_ENABLED=false`（测试/外部调度模式）
  → 不启动监听线程，`/health` 的 `config_watch` 如实显示 disabled 及原因。

安全：内存快照只保留键名与值（值来自本地 .env，从不外发）；`/health` 只暴露
**文件名** `.env`，不暴露服务器路径。监听或重载失败不抛出 —— 记录在状态里，
下一轮继续尝试。
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Callable, Optional

from dotenv import dotenv_values
from loguru import logger

from app.config import BACKEND_DIR, reload_settings, settings
from app.utils import timeutil

DEFAULT_ENV_PATH = BACKEND_DIR / ".env"
POLL_SECONDS = 10.0
HOT_PREFIX = "LLM_"


class ConfigWatch:
    """.env 键值快照 + 热重载；一个进程一个实例（见模块级 ``watcher``）。"""

    def __init__(self, env_path: Optional[Path] = None) -> None:
        self.env_path = Path(env_path) if env_path else DEFAULT_ENV_PATH
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._values: dict[str, str] = {}
        self._primed = False
        self._status = "disabled"
        self._last_check_at: Optional[str] = None
        self._last_reload_at: Optional[str] = None
        self._reloaded_keys: list[str] = []
        self._note: Optional[str] = None
        self._trigger: Optional[Callable[[], Any]] = None

    # ------------------------------------------------------------------ #
    # 读取与快照
    # ------------------------------------------------------------------ #
    def _read(self) -> Optional[dict[str, str]]:
        if not self.env_path.exists():
            return {}
        try:
            return {
                key: value
                for key, value in dotenv_values(self.env_path).items()
                if value is not None
            }
        except OSError as exc:
            with self._lock:
                self._status = "failed"
                self._note = f".env 读取失败：{type(exc).__name__}"
            logger.warning(f"[配置监听] .env 读取失败：{exc}")
            return None

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "enabled": bool(settings.CONFIG_WATCH),
                "status": self._status,
                "env_file": self.env_path.name,
                "interval_seconds": POLL_SECONDS,
                "last_check_at": self._last_check_at,
                "last_reload_at": self._last_reload_at,
                "reloaded_keys": list(self._reloaded_keys),
                "note": self._note,
            }

    # ------------------------------------------------------------------ #
    # 一次检查
    # ------------------------------------------------------------------ #
    def prime(self) -> dict:
        """记录初始快照（启动时不把既有配置当成「刚变化」）。"""
        current = self._read()
        with self._lock:
            if current is not None:
                self._values = current
            self._primed = True
            if self._status != "failed":
                self._status = "watching"
            self._last_check_at = timeutil.now_iso()
        return self.snapshot()

    def check_once(self, *, trigger: bool = True) -> dict:
        """比对一次快照；发生变化时按热/冷规则处理。可测试、可手工调用。"""
        current = self._read()
        if current is None:
            return self.snapshot()

        with self._lock:
            before = self._values
            self._values = current
            self._last_check_at = timeutil.now_iso()
            primed = self._primed
            self._primed = True
            if not primed:
                self._status = "watching"

        if not primed:
            return self.snapshot()

        changed = {
            key for key in set(before) | set(current) if before.get(key) != current.get(key)
        }
        if not changed:
            return self.snapshot()

        hot = sorted(key for key in changed if key.startswith(HOT_PREFIX))
        cold = sorted(key for key in changed if not key.startswith(HOT_PREFIX))
        if not hot:
            with self._lock:
                self._note = (
                    f"检测到非 LLM 配置变化（{'、'.join(cold)}）：需重启进程才能生效"
                )
            return self.snapshot()

        try:
            reloaded = reload_settings(self.env_path, changed_keys=set(hot))
        except Exception as exc:  # noqa: BLE001 —— 重载失败不能让监听线程死掉
            with self._lock:
                self._status = "failed"
                self._note = f"配置重载失败：{type(exc).__name__}: {exc}"
            logger.error(f"[配置监听] 热重载失败：{exc}")
            return self.snapshot()

        # 旧客户端 / 旧指纹都属于旧配置，必须丢弃；额度计数保留（钱已经花了）
        from app.services import llm_gate, llm_provider

        llm_provider.reset_clients()
        llm_gate.reset_fingerprints()

        notes = [f"已热重载 {'、'.join(reloaded or hot)}，LLM 客户端缓存已重置"]
        if cold:
            notes.append(f"以下项需重启：{'、'.join(cold)}")

        triggered = False
        if llm_provider.is_configured():
            callable_trigger = self._trigger if trigger else None
            if callable_trigger is not None:
                threading.Thread(
                    target=self._run_trigger, args=(callable_trigger,), daemon=True
                ).start()
                triggered = True
                notes.append("已触发一轮强制分析")
            else:
                notes.append("未注入分析触发器（仅重载配置）")
        else:
            notes.append("LLM 仍未配置完整，暂不触发分析")

        with self._lock:
            self._status = "watching"
            self._last_reload_at = timeutil.now_iso()
            self._reloaded_keys = hot
            self._note = "；".join(notes)
        logger.info(f"[配置监听] {self.snapshot()['note']}")
        return self.snapshot()

    def _run_trigger(self, callable_trigger: Callable[[], Any]) -> None:
        try:
            callable_trigger()
        except Exception as exc:  # noqa: BLE001 —— 分析失败只记录，等下轮调度
            logger.error(f"[配置监听] 触发分析失败：{type(exc).__name__}: {exc}")

    # ------------------------------------------------------------------ #
    # 后台线程
    # ------------------------------------------------------------------ #
    def _loop(self) -> None:
        while not self._stop.wait(POLL_SECONDS):
            self.check_once()

    def start(self, *, trigger: Optional[Callable[[], Any]] = None) -> dict:
        if not settings.CONFIG_WATCH:
            with self._lock:
                self._status = "disabled"
                self._note = "CONFIG_WATCH=false：未启动配置监听"
            return self.snapshot()
        if not settings.SCHEDULER_ENABLED:
            with self._lock:
                self._status = "disabled"
                self._note = (
                    "SCHEDULER_ENABLED=false（测试/外部调度模式）：未启动配置监听线程"
                )
            return self.snapshot()

        self._trigger = trigger
        self.prime()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="goldmind-config-watch"
        )
        self._thread.start()
        return self.snapshot()


watcher = ConfigWatch()


def start_watcher(engine) -> dict:
    """lifespan 入口：启动监听并注入「LLM 就绪后强制补一轮分析」。"""
    from app import bootstrap

    return watcher.start(trigger=lambda: bootstrap.warm_analyses(engine, force=True))


def check_once(*, trigger: bool = True) -> dict:
    return watcher.check_once(trigger=trigger)


def snapshot() -> dict:
    return watcher.snapshot()