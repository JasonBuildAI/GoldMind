"""结构性守卫：时间只能从 `app.utils.timeutil` 取。

这是被三次真实故障逼出来的（见 `AGENTS.md` 红线 5 与
`docs/ARCHITECTURE.md` 第七节）：

1. 定时任务用 `datetime.now().date()` 取「今天」—— cron 按东八区触发、
   容器默认 UTC，同一份行情在 Docker 里被记到**前一天**；
2. RSS 的 `published_parsed` 是 UTC，直接当本地时间存 ——
   「最近 24 小时」的窗口实际覆盖到约 **32 小时**；
3. 前端用 `toISOString()` 取「今天」—— 东八区 00:00-08:00 之间给出昨天，
   实时美元指数静默不更新。

根因是同一个：**没有写下来的时区约定**，于是每处代码各自假设。
约定写下来之后，这条测试负责让它不被下一次改动悄悄破坏。
"""
import re
from pathlib import Path

import pytest

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# 时区入口本身（它就是干这个的），以及只在注释/文档里提到的地方
ALLOWED_FILES = {"utils/timeutil.py", "scheduler.py"}

# 会算错「今天是哪天」的写法
FORBIDDEN = (
    # 裸的 datetime.now()：取的是服务器本地时间。
    # **这条是后补的** —— 上一版只查 .date()/.strftime()/.isoformat()，
    # 于是 `datetime.now() - timedelta(hours=24)` 这种**算术**用法整片漏掉，
    # 而它正是「最近24小时」窗口多算 8 小时的原因。
    re.compile(r"datetime\.now\(\s*\)"),
    re.compile(r"datetime\.now\(\)\.date\(\)"),
    re.compile(r"datetime\.now\(\)\.strftime\("),
    re.compile(r"datetime\.now\(\)\.isoformat\("),
    re.compile(r"datetime\.utcnow\(\)"),
    re.compile(r"date\.today\(\)"),
)


def _python_files():
    for path in APP_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _code_line_numbers(source: str) -> set[int]:
    """返回**真正含有代码**的行号。

    注释与文档里提到 `datetime.now().date()` 是在**解释**这个坑，不该被判成违规。
    但「跳过含字符串的行」是错的 —— 几乎每行都有字符串字面量
    （`datetime.now().strftime("%Y-%m-%d")` 里的 `"%Y-%m-%d"` 就是），
    那样会把真正的违规行也一起跳过，守卫形同虚设（实测踩过这个坑）。

    所以用 tokenize：只有注释 / 字符串 / 缩进 / 换行的行不算代码行。
    """
    import io
    import tokenize

    code_lines: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (
                tokenize.COMMENT,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.ENDMARKER,
                tokenize.STRING,
            ):
                continue
            code_lines.add(tok.start[0])
    except (tokenize.TokenError, IndentationError):
        # 解析不了就保守处理：当成「全是代码」，宁可多报不可漏报
        return set(range(1, len(source.splitlines()) + 1))
    return code_lines


@pytest.mark.unit
def test_no_bare_local_time_calls():
    """业务代码里不得直接取服务器本地时间。"""
    offenders = []
    for path in _python_files():
        rel = path.relative_to(APP_DIR).as_posix()
        if rel in ALLOWED_FILES:
            continue
        source = path.read_text(encoding="utf-8")
        code_lines = _code_line_numbers(source)
        for lineno, line in enumerate(source.splitlines(), start=1):
            if lineno not in code_lines:
                continue
            for pattern in FORBIDDEN:
                if pattern.search(line):
                    offenders.append(f"{rel}:{lineno}: {line.strip()}")

    assert not offenders, (
        "这些地方直接取了服务器本地时间，应改用 app.utils.timeutil：\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.unit
def test_scheduler_delegates_to_timeutil(monkeypatch):
    """`scheduler_now()` 必须复用 timeutil，而不是另有一份实现。

    两份实现 = 第二个真源，迟早漂开。
    """
    from app import scheduler as sched
    from app.utils import timeutil

    called = []
    monkeypatch.setattr(timeutil, "now", lambda: called.append(True) or "sentinel")

    result = sched.scheduler_now()

    assert called, "scheduler_now 没有走 timeutil.now()"
    assert result == "sentinel"


@pytest.mark.unit
def test_timeutil_uses_the_configured_timezone():
    """timeutil 的返回值必须带配置时区的偏移。"""
    from app.config import settings
    from app.utils import timeutil

    assert str(timeutil.now().tzinfo) == settings.SCHEDULER_TIMEZONE
    assert timeutil.now_naive().tzinfo is None
    assert timeutil.today() == timeutil.now().date()


@pytest.mark.unit
def test_from_utc_naive_shifts_by_the_offset():
    """UTC 的 naive 时间换算后应当带上时区偏移。"""
    from datetime import datetime, timedelta

    from app.config import settings
    from app.utils import timeutil

    moment = datetime(2026, 9, 30, 12, 0, 0)
    result = timeutil.from_utc_naive(moment)

    from zoneinfo import ZoneInfo

    offset = datetime.now(ZoneInfo(settings.SCHEDULER_TIMEZONE)).utcoffset()
    assert result == moment + offset
    assert timeutil.from_utc_naive(None) is None


@pytest.mark.unit
def test_guard_actually_detects_a_violation(tmp_path, monkeypatch):
    """守卫自身要有效：塞一个违规文件进去，必须被抓到。

    （前几轮吃过亏：测试和被测代码用同一个错误公式，两边「错得一样」，
    测试永远绿。所以守卫本身也要有判别力测试。）
    """
    import importlib

    module = importlib.import_module("tests.unit.test_timezone_discipline")

    fake_app = tmp_path / "app"
    (fake_app / "services").mkdir(parents=True)
    (fake_app / "services" / "bad.py").write_text(
        "from datetime import datetime\n"
        "def f():\n"
        '    """文档里提一句 datetime.now().date() 不该算违规。"""\n'
        "    return datetime.now().date()\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "APP_DIR", fake_app)
    monkeypatch.setattr(module, "ALLOWED_FILES", set())

    with pytest.raises(AssertionError) as excinfo:
        module.test_no_bare_local_time_calls()

    # 只应命中真正的代码那一行，不该命中 docstring
    assert "bad.py:4" in str(excinfo.value)
    assert "bad.py:3" not in str(excinfo.value)
