"""README 里写的 `python scripts/*.py --flag` 必须真的存在。

回归：README 曾写着 `python scripts/quant_lab.py --refresh`，而 `--refresh` 这个参数
从来不存在（真实参数是 `--out / --horizons / --group / --from-db / --as-of /
--holdout-start`）—— 照着文档敲命令会直接报错。`AGENTS.md` 要求「文档里的路径、命令、
名字必须真实存在」，这里把「命令」也变成可执行检查：

1. 命令里的脚本文件必须存在；
2. 每个 `--flag` 必须出现在该脚本 `--help` 的输出里（真跑一次 argparse，不靠人肉）；
3. 中英两份 README 一起查 —— 只守中文等于只守一半。
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND = REPO_ROOT / "backend"
READMES = ("README.md", "README_EN.md")

CODE_FENCE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)
# 匹配：python[ -X utf8] <script>，脚本可能是 scripts/xxx.py / init_db.py / seed_data.py
PYTHON_CALL = re.compile(
    r"(?:python(?:\.exe)?(?:\s+-X\s+utf8)?|\.venv\\Scripts\\python\.exe)\s+"
    r"((?:scripts[\\/])?[\w.-]+\.py)\b(.*)$"
)
FLAG = re.compile(r"(?<![\w-])(--[a-z][a-z0-9-]*)")


def _readme_commands() -> list[tuple[str, str, str]]:
    """返回 (readme, script, flags 行) 三元组。"""
    calls = []
    for rel in READMES:
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        for block in CODE_FENCE.findall(text):
            for raw in block.splitlines():
                line = raw.split(" #", 1)[0].strip().rstrip("\\").strip()
                if not line or line.startswith("#"):
                    continue
                match = PYTHON_CALL.search(line)
                if not match:
                    continue
                script = match.group(1).replace("\\", "/")
                calls.append((rel, script, match.group(2)))
    return calls


@lru_cache(maxsize=None)
def _help_text(script: str) -> str:
    env = dict(os.environ)
    for key in ("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"):
        env[key] = ""
    result = subprocess.run(
        [sys.executable, script, "--help"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        # README 里的入口脚本会把 stdout 重配成 UTF-8（GBK 控制台契约），
        # 这里若按 Windows 本地编码解码会拿到 None 的 stdout。
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
        env=env,
    )
    assert result.returncode == 0, (
        f"`{script} --help` 跑不通（退出码 {result.returncode}），README 却让读者这么敲：\n"
        f"{result.stderr[-1500:]}"
    )
    return result.stdout + result.stderr


@pytest.mark.unit
def test_readme_script_files_exist():
    calls = _readme_commands()
    assert calls, "没从 README 里解析出任何 python 脚本命令，解析逻辑失效了"
    missing = sorted({script for _, script, _ in calls if not (BACKEND / script).exists()})
    assert not missing, "README 引用了不存在的脚本：" + "、".join(missing)


@pytest.mark.unit
def test_every_readme_script_flag_exists():
    offenders = []
    checked = 0
    for rel, script, rest in _readme_commands():
        for flag in FLAG.findall(rest):
            checked += 1
            if flag not in _help_text(script):
                offenders.append(f"{rel}: python {script} {flag}")
    assert checked >= 10, f"只解析出 {checked} 个参数，解析逻辑可能失效了"
    assert not offenders, (
        "README 里的这些参数在对应脚本的 argparse 里不存在（照着敲会报错）：\n"
        + "\n".join(f"  {item}" for item in offenders)
    )
