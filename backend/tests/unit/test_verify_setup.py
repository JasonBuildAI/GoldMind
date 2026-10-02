"""`scripts/verify_setup.py` 的守卫：能过、坏配置会红、失败带修复命令、且真的只读。

测试在临时工作目录里启动子进程，这样 `python-dotenv` 找不到仓库里的
`backend/.env` —— 用例永不依赖、也不会读取任何真实密钥。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_DIR = REPO_ROOT / "backend"
SCRIPT = BACKEND_DIR / "scripts" / "verify_setup.py"


def _run(workdir: Path, **overrides: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("LLM_", "DATABASE_URL", "CACHE_DIR", "SCHEDULER_"))}
    env.update(overrides)
    return subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


@pytest.mark.unit
def test_verify_setup_passes_with_default_sqlite_and_no_llm(tmp_path):
    """SQLite 默认配置 + 未填 LLM：必需项全过（LLM 只是提示，不是失败）。"""
    result = _run(
        tmp_path,
        DATABASE_URL=f"sqlite:///{(tmp_path / 'goldmind.db').as_posix()}",
        CACHE_DIR=str(tmp_path / "cache"),
        SCHEDULER_TIMEZONE="Asia/Shanghai",
        # 显式置空（而不是删除）：进程环境里「存在且为空」的值优先于
        # backend/.env 里的真实配置，用例才不会依赖开发机的密钥。
        LLM_API_KEY="",
        LLM_BASE_URL="",
        LLM_MODEL="",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "[fail]" not in result.stdout
    assert "[ok] Python 版本" in result.stdout
    assert "[warn] LLM 配置" in result.stdout
    assert result.stdout.count("[ok]") >= 5, "解析到的通过项太少，检查逻辑可能失效"


@pytest.mark.unit
def test_verify_setup_is_read_only(tmp_path):
    """自检不得建库、建目录或写文件。"""
    workdir = tmp_path / "work"
    workdir.mkdir()
    result = _run(
        workdir,
        DATABASE_URL=f"sqlite:///{(workdir / 'goldmind.db').as_posix()}",
        CACHE_DIR=str(workdir / "cache"),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert not (workdir / "goldmind.db").exists(), "自检不应创建数据库文件"
    assert not (workdir / "cache").exists(), "自检不应创建缓存目录"
    assert list(workdir.iterdir()) == []


@pytest.mark.unit
def test_verify_setup_fails_on_unwritable_cache_dir(tmp_path):
    """把 CACHE_DIR 指到一个「文件」下面：必须红，并给出可执行的修复命令。"""
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory", encoding="utf-8")

    result = _run(
        tmp_path,
        DATABASE_URL=f"sqlite:///{(tmp_path / 'goldmind.db').as_posix()}",
        CACHE_DIR=str(blocker / "cache"),
    )

    assert result.returncode == 1, result.stdout
    assert "[fail] 缓存目录" in result.stdout
    assert "CACHE_DIR" in result.stdout


@pytest.mark.unit
def test_verify_setup_fails_on_unknown_timezone(tmp_path):
    """时区是红线：写错必须红，并提示正确的 IANA 写法。"""
    result = _run(
        tmp_path,
        DATABASE_URL=f"sqlite:///{(tmp_path / 'goldmind.db').as_posix()}",
        CACHE_DIR=str(tmp_path / "cache"),
        SCHEDULER_TIMEZONE="Nowhere/Invalid",
    )

    assert result.returncode == 1, result.stdout
    assert "[fail] 时区口径" in result.stdout
    assert "Asia/Shanghai" in result.stdout


@pytest.mark.unit
def test_verify_setup_fails_on_unknown_database_dialect(tmp_path):
    """不认识的方言必须红，而不是悄悄当成 SQLite。"""
    result = _run(
        tmp_path,
        DATABASE_URL="oracle://user:secret@localhost:1521/gold",
        CACHE_DIR=str(tmp_path / "cache"),
    )

    assert result.returncode == 1, result.stdout
    assert "无法识别的 DATABASE_URL" in result.stdout
    assert "secret" not in result.stdout, "自检输出不得回显连接串里的密码"
