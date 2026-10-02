"""`.env` 热监听（2.0.2）：LLM 配置变化无需重启，自动重载 + 补一轮分析。

变异验证（commit body 有记录）：
- 去掉「配置变化后触发分析」→ 触发用例必红；
- 去掉客户端 / 指纹重置 → 副作用用例必红；
- 把非 LLM 变化也热应用 → 需重启用例必红；
- 删除 LLM 键时不置空 → 删除用例必红。
"""
from __future__ import annotations

import time

import pytest
from pydantic import SecretStr

from app import config_watch
from app.config import settings


def _configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr("test-key"))
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://example.invalid/v1")
    monkeypatch.setattr(settings, "LLM_MODEL", "model-old")


def _wait_for(events: list, value: str, timeout: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while value not in events and time.time() < deadline:
        time.sleep(0.02)
    return value in events


@pytest.mark.unit
def test_llm_change_reloads_settings_resets_state_and_triggers(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("LLM_MODEL=model-old\n", encoding="utf-8")
    _configured(monkeypatch)
    watcher = config_watch.ConfigWatch(env_path=env)
    watcher.prime()

    events: list[str] = []
    monkeypatch.setattr(
        "app.services.llm_provider.reset_clients", lambda: events.append("reset")
    )
    monkeypatch.setattr(
        "app.services.llm_gate.reset_fingerprints", lambda: events.append("fingerprints")
    )
    watcher._trigger = lambda: events.append("analysis")

    env.write_text("LLM_MODEL=model-new\n", encoding="utf-8")
    snapshot = watcher.check_once()

    assert settings.LLM_MODEL == "model-new", "配置必须就地热生效（无需重启）"
    assert snapshot["status"] == "watching"
    assert snapshot["last_reload_at"] is not None
    assert "LLM_MODEL" in snapshot["reloaded_keys"]
    assert "已热重载" in snapshot["note"]
    assert _wait_for(events, "analysis"), "配置变化后必须自动补一轮分析"
    assert events == ["reset", "fingerprints", "analysis"], "顺序：先清旧状态，再分析"


@pytest.mark.unit
def test_non_llm_change_is_reported_as_restart_only(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("NEWS_RSS_SOURCES=source-a\n", encoding="utf-8")
    monkeypatch.setattr(settings, "NEWS_RSS_SOURCES", "source-a")
    watcher = config_watch.ConfigWatch(env_path=env)
    watcher.prime()

    events: list[str] = []
    watcher._trigger = lambda: events.append("analysis")
    env.write_text("NEWS_RSS_SOURCES=source-b\n", encoding="utf-8")
    snapshot = watcher.check_once()

    assert settings.NEWS_RSS_SOURCES == "source-a", "非 LLM 配置不得中途热应用"
    assert "需重启" in snapshot["note"]
    assert snapshot["last_reload_at"] is None
    assert events == []


@pytest.mark.unit
def test_deleted_llm_key_is_cleared(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("LLM_MODEL=model-x\n", encoding="utf-8")
    monkeypatch.setattr(settings, "LLM_MODEL", "model-x")
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr(""))
    watcher = config_watch.ConfigWatch(env_path=env)
    watcher.prime()
    watcher._trigger = lambda: None

    env.write_text("", encoding="utf-8")
    watcher.check_once()

    assert settings.LLM_MODEL == "", "删掉的键不能靠 os.environ 里的旧值复活"


@pytest.mark.unit
def test_incomplete_llm_config_reloads_but_does_not_trigger(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("LLM_MODEL=model-old\n", encoding="utf-8")
    monkeypatch.setattr(settings, "LLM_API_KEY", SecretStr(""))
    monkeypatch.setattr(settings, "LLM_BASE_URL", "")
    monkeypatch.setattr(settings, "LLM_MODEL", "model-old")
    watcher = config_watch.ConfigWatch(env_path=env)
    watcher.prime()

    events: list[str] = []
    watcher._trigger = lambda: events.append("analysis")
    env.write_text("LLM_MODEL=model-new\n", encoding="utf-8")
    snapshot = watcher.check_once()

    assert settings.LLM_MODEL == "model-new"
    assert "未配置完整" in snapshot["note"]
    assert events == []


@pytest.mark.unit
def test_watcher_respects_disabled_setting(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_WATCH", False)
    watcher = config_watch.ConfigWatch(env_path=tmp_path / ".env")

    snapshot = watcher.start(trigger=lambda: None)

    assert snapshot["enabled"] is False
    assert snapshot["status"] == "disabled"
    assert "CONFIG_WATCH" in snapshot["note"]
    assert watcher._thread is None


@pytest.mark.unit
def test_watcher_disabled_when_scheduler_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "CONFIG_WATCH", True)
    monkeypatch.setattr(settings, "SCHEDULER_ENABLED", False)
    watcher = config_watch.ConfigWatch(env_path=tmp_path / ".env")

    snapshot = watcher.start(trigger=lambda: None)

    assert snapshot["enabled"] is True
    assert snapshot["status"] == "disabled"
    assert "SCHEDULER_ENABLED" in snapshot["note"]
    assert watcher._thread is None


@pytest.mark.integration
def test_health_exposes_config_watch(client):
    body = client.get("/health").json()

    assert "config_watch" in body, "/health 必须报告配置监听状态"
    watch = body["config_watch"]
    assert watch["enabled"] is True
    assert watch["status"] == "disabled"
    assert "SCHEDULER_ENABLED" in watch["note"]
    assert watch["env_file"] == ".env"
