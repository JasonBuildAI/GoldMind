"""日志配置的测试。

回归点：`.env.example` 里一直写着 `LOG_LEVEL`，但此前**没有任何代码读它** ——
设成 WARNING 也照样输出 INFO。loguru 的默认 handler 固定在 DEBUG 级别。
"""
from __future__ import annotations

import pytest
from loguru import logger


def _handler_levels() -> list[int]:
    return [h.levelno for h in logger._core.handlers.values()]


@pytest.mark.unit
def test_logging_is_configured_with_a_single_handler():
    """导入 app.main 即完成配置；默认 handler 必须已被移除。"""
    import app.main  # noqa: F401  导入触发 _configure_logging

    assert len(_handler_levels()) == 1, "应当只剩一个 stderr handler"


@pytest.mark.unit
def test_default_level_is_info():
    import app.main  # noqa: F401

    assert _handler_levels() == [20], "默认应为 INFO"


@pytest.mark.unit
@pytest.mark.parametrize(
    "level,expected",
    [("DEBUG", 10), ("INFO", 20), ("WARNING", 30), ("ERROR", 40)],
)
def test_log_level_setting_is_honoured(monkeypatch, level, expected):
    import app.main as main

    monkeypatch.setattr(main.settings, "LOG_LEVEL", level)
    main._configure_logging()

    assert _handler_levels() == [expected], f"LOG_LEVEL={level} 未生效"


@pytest.mark.unit
def test_lowercase_level_is_accepted(monkeypatch):
    import app.main as main

    monkeypatch.setattr(main.settings, "LOG_LEVEL", "warning")
    main._configure_logging()

    assert _handler_levels() == [30]


@pytest.mark.unit
def test_configuration_is_idempotent(monkeypatch):
    """重复配置不应叠加 handler（否则日志会重复输出）。"""
    import app.main as main

    for _ in range(3):
        main._configure_logging()

    assert len(_handler_levels()) == 1
