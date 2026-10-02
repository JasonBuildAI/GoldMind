"""入口脚本的 GBK 控制台守卫。

默认中文 Windows 控制台是 GBK；脚本里只要有一个 emoji / 勾叉被 print 出去，
就会抛 UnicodeEncodeError（不是显示乱码，是直接崩掉）。改动一次的代价很小：
在 main() 开头把 stdout/stderr 切到 UTF-8。这里把这个约定变成可执行的检查，
免得下一个新脚本又踩一遍。
"""
from __future__ import annotations

from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENTRY_DIRS = (BACKEND_DIR, BACKEND_DIR / "scripts")


def _is_gbk_encodable(char: str) -> bool:
    try:
        char.encode("gbk")
    except UnicodeEncodeError:
        return False
    return True


@pytest.mark.unit
def test_entry_scripts_with_non_gbk_output_configure_the_console():
    offenders: list[str] = []
    scanned = 0
    for directory in ENTRY_DIRS:
        for path in sorted(directory.glob("*.py")):
            if path.name == "__init__.py":
                continue
            scanned += 1
            text = path.read_text(encoding="utf-8")
            if any(not _is_gbk_encodable(ch) for ch in text) and "reconfigure" not in text:
                offenders.append(str(path.relative_to(BACKEND_DIR)))

    assert scanned >= 10, f"只扫描到 {scanned} 个入口脚本，扫描逻辑可能失效"
    assert not offenders, (
        "这些入口脚本含非 GBK 字符（emoji/勾叉）却没有 reconfigure 控制台编码，"
        "在默认中文 Windows 控制台（GBK）上会抛 UnicodeEncodeError：\n"
        + "\n".join(offenders)
    )
