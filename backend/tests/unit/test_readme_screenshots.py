"""README 的截图一节必须与截图脚本、磁盘上的图三方对得上。

为什么要有这份守卫：图是脚本生成、README 是手写的，两边只靠人记性对齐 —— 换版式时很容易
留下「README 指着一张不存在的图」或「脚本多拍一张没人看」的半坏状态，而在 GitHub 上它只
表现为一个碎图图标，谁也不会报错。这里把三件事变成可执行检查：

1. README / README_EN 引用的每张截图都真实存在；
2. 每个引用都写在**表格行**里 —— 截图一节是表格化的，散落的 `<img>` 是漏改的信号；
3. 两语言引用的集合 == `capture_screenshots.mjs` 里 SHOTS 的 name 集合 == 目录里的实际文件，
   再多一张、再少一张都会红。中英两份一起查：只守中文等于只守一半。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
READMES = ("README.md", "README_EN.md")
SHOT_DIR = REPO_ROOT / "docs" / "images" / "screenshots"
SCRIPT = REPO_ROOT / "app" / "scripts" / "capture_screenshots.mjs"

REFERENCE = re.compile(r"docs/images/screenshots/([A-Za-z0-9_.-]+\.png)")
SHOT_NAME = re.compile(r"\bname:\s*'([a-z0-9-]+)'")


def _references(rel: str) -> list[tuple[int, str, str]]:
    """返回 (行号, 文件名, 整行) 三元组。"""
    text = (REPO_ROOT / rel).read_text(encoding="utf-8")
    return [
        (number, name, line)
        for number, line in enumerate(text.splitlines(), start=1)
        for name in REFERENCE.findall(line)
    ]


def _script_shots() -> set[str]:
    names = SHOT_NAME.findall(SCRIPT.read_text(encoding="utf-8"))
    assert len(names) >= 15, f"只解析出 {len(names)} 个截图名，解析逻辑可能失效了"
    return set(names)


def _versions(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


@pytest.mark.unit
def test_every_readme_reference_points_at_a_real_file():
    references = _references("README.md")
    assert len(references) >= 15, f"README 只解析出 {len(references)} 个截图引用，解析逻辑失效了"
    missing = [
        f"{rel}:{number} → {name}"
        for rel in READMES
        for number, name, _ in _references(rel)
        if not (SHOT_DIR / name).exists()
    ]
    assert not missing, "README 引用的截图文件不存在（GitHub 上就是一张碎图）：\n" + "\n".join(
        f"  {item}" for item in missing
    )


@pytest.mark.unit
def test_every_readme_reference_sits_in_a_table_row():
    strays = [
        f"{rel}:{number}（{name}）"
        for rel in READMES
        for number, name, line in _references(rel)
        if not line.lstrip().startswith("|")
    ]
    assert not strays, (
        "截图引用不在表格行里（截图一节是表格化的，散落的 <img> 是漏改的信号）：\n"
        + "\n".join(f"  {item}" for item in strays)
    )


@pytest.mark.unit
def test_readme_references_match_the_capture_script():
    shots = _script_shots()
    for rel in READMES:
        referenced = {name[: -len(".png")] for _, name, _ in _references(rel)}
        assert referenced == shots, (
            f"{rel} 的截图集合与 capture_screenshots.mjs 的 SHOTS 不一致：\n"
            f"  README 多出来：{sorted(referenced - shots)}\n"
            f"  README 缺：{sorted(shots - referenced)}"
        )


@pytest.mark.unit
def test_no_orphan_screenshots_on_disk():
    on_disk = {path.name[: -len(".png")] for path in SHOT_DIR.glob("*.png")}
    shots = _script_shots()
    assert on_disk == shots, (
        "docs/images/screenshots 里的文件与截图脚本对不上：\n"
        f"  目录里多出来：{sorted(on_disk - shots)}\n"
        f"  目录里缺：{sorted(shots - on_disk)}"
    )


@pytest.mark.unit
def test_readmes_state_the_right_shot_count():
    count = len(_script_shots())
    zh, en = _versions("README.md"), _versions("README_EN.md")
    assert f"以下 {count} 张截图" in zh, f"README 的截图导语没写「以下 {count} 张截图」——数字对不上"
    assert f"All {count} screenshots" in en, (
        f"README_EN 的截图导语没写「All {count} screenshots」——数字对不上"
    )
