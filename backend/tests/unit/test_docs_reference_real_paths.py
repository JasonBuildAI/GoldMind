"""文档里引用的路径与命令必须真实存在。

`AGENTS.md` 硬性要求第 3 条写着「文档里的路径、命令、名字必须真实存在，先验证再写」。
这条规矩此前只能靠人肉遵守 —— 实际也确实漏过：`AGENTS.md` 曾引用
`docs/0X-*.md` 这个并不存在的命名约定，以及一个不存在的 `.env.example` 位置。

这里把它变成可执行的检查。检查范围刻意只覆盖**仓库内**的引用：
外部 URL 会随网络与第三方变化，纳入检查只会带来不稳定。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# 形如仓库内路径的反引号片段（`docs/xxx`、`backend/xxx`、`.env`…）
INLINE_PATH = re.compile(
    r"`((?:docs/|backend/|app/|\.env|README|AGENTS)[^`\s]*)`"
)

# 刻意豁免：这两项都**不是**路径声明，文中也说明了它们是什么。
PATH_EXEMPTIONS = {
    # 约定名（「密钥只进 .env」），真实文件是 backend/.env
    ".env",
    # 文中已明确写「本项目还没有 docs/specs/ 目录」
    "docs/specs/",
}

# markdown 链接目标里指向仓库内的相对路径
MD_LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)\)")


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _inline_paths(text: str) -> set[str]:
    return {
        token
        for token in INLINE_PATH.findall(text)
        if token not in PATH_EXEMPTIONS
    }


def _gitignored(rel: str) -> bool:
    """该路径是否被 .gitignore 覆盖。

    被忽略的文件（最典型的是 `backend/.env`）在**新克隆里天然不存在**，
    引用它并不算死链 —— CI 里就是这种情况。反之，没被忽略又不存在的路径
    必须报出来。
    """
    result = subprocess.run(
        ["git", "check-ignore", "-q", rel],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _repo_links(text: str) -> set[str]:
    """只取相对路径的链接目标；http(s)、mailto、锚点都不算。"""
    targets = set()
    for target in MD_LINK.findall(text):
        if target.startswith(("http://", "https://", "mailto:", "#", "//")):
            continue
        targets.add(target)
    return targets


# --------------------------------------------------------------------------- #
# AGENTS.md
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_agents_md_inline_paths_exist():
    """AGENTS.md 里反引号引用的仓库内路径都必须真实存在。"""
    missing = [
        token
        for token in sorted(_inline_paths(_read("AGENTS.md")))
        if not (REPO_ROOT / token).exists() and not _gitignored(token)
    ]

    assert not missing, (
        "AGENTS.md 引用了不存在的路径。改文档时请先验证路径真的存在。\n"
        + "\n".join(f"  {m}" for m in missing)
    )


@pytest.mark.unit
def test_agents_md_names_only_real_skills():
    """AGENTS.md 的流程表里点名的 skill 必须真的存在。

    通用模板里写的是 `superpowers:brainstorming` / `grill-me` 这类名字，
    在本环境里并不存在。改写时换成了真实名字，这个测试防止再写回不存在的。
    """
    text = _read("AGENTS.md")

    # 流程表「默认方法」列里出现的反引号名字
    table_rows = [line for line in text.splitlines() if line.startswith("| ") and "`" in line]
    named = set()
    for row in table_rows:
        cells = row.split("|")
        if len(cells) >= 5:
            named.update(re.findall(r"`([a-z][a-z0-9-]+)`", cells[4]))

    # 这些是流程本身的名字，不是 skill
    not_skills = {"plan", "spec"}

    known = {
        "grilling",
        "brainstorming",
        "writing-plans",
        "test-driven-development",
        "systematic-debugging",
        "subagent-driven-development",
        "executing-plans",
        "verification-before-completion",
        "requesting-code-review",
        "using-superpowers",
    }

    unknown = named - known - not_skills
    assert not unknown, f"AGENTS.md 点名了不存在的 skill：{sorted(unknown)}"
    assert named & known, "流程表里一个真实 skill 都没提到，解析大概失效了"


# --------------------------------------------------------------------------- #
# README.md
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_readme_relative_links_exist():
    """README 里的仓库内链接不能是死链。"""
    missing = []
    for rel in ("README.md", "README_EN.md"):
        for target in sorted(_repo_links(_read(rel))):
            if not (REPO_ROOT / target).exists():
                missing.append(f"{rel} -> {target}")

    assert not missing, "文档里有死链：\n" + "\n".join(f"  {m}" for m in missing)


@pytest.mark.unit
def test_readme_gate_commands_match_package_scripts():
    """README「常用命令」里写的 npm 命令，必须真的在 package.json 里。"""
    scripts = json.loads((REPO_ROOT / "app" / "package.json").read_text(encoding="utf-8"))["scripts"]

    readme = _read("README.md")
    referenced = set(re.findall(r"npm run ([a-zA-Z0-9:_-]+)", readme))
    referenced |= set(re.findall(r"npm (test|ci)\b", readme)) - {"ci"}

    missing = sorted(name for name in referenced if name not in scripts)

    assert not missing, (
        "README 里写了不存在的 npm 命令：\n"
        + "\n".join(f"  npm run {m}" for m in missing)
    )
    assert referenced, "没从 README 里解析出任何 npm 命令，解析大概失效了"


@pytest.mark.unit
def test_readme_gate_section_exists_and_points_at_agents_md():
    """AGENTS.md 说「命令的唯一真源在 README 的常用命令章节」—— 那一节必须真的在。"""
    readme = _read("README.md")

    assert "常用命令" in readme, "README 里找不到「常用命令」章节"
    assert "AGENTS.md" in readme, "README 没有指回 AGENTS.md"


# --------------------------------------------------------------------------- #
# 页内锚点
# --------------------------------------------------------------------------- #
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
# 页内锚点有两种写法：markdown 的 `](#anchor)` 与 HTML 的 `href="#anchor"`
ANCHOR_LINK = re.compile(r'(?:\]\(#|href="#)([^)"]+)')


def _slug(heading: str) -> str:
    """按 GitHub 的规则把标题转成锚点。

    规则：转小写 -> 去掉非「字母/数字/下划线/空格/连字符」的字符（表情符号就这样没了，
    中日韩字符属于 \\w 会保留）-> 空格换成连字符。
    """
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def _headings(text: str) -> set[str]:
    return {_slug(h) for h in HEADING.findall(text)}


@pytest.mark.unit
@pytest.mark.parametrize("rel", ["README.md", "README_EN.md"])
def test_readme_in_page_anchors_resolve(rel):
    """README 顶部导航里的 `#锚点` 必须指向真实存在的标题。

    回归：README 的导航里有 `#-agent原理`，但那一节早就被删了（早期文档把单轮
    调用描述成多智能体，改写时删掉了整节），留下一个点了没反应的死链。
    """
    text = _read(rel)
    slugs = _headings(text)

    dead = sorted({a for a in ANCHOR_LINK.findall(text) if a.lower() not in slugs})

    assert not dead, f"{rel} 里有指向不存在标题的锚点：{dead}"


@pytest.mark.unit
def test_anchor_parser_is_not_silently_empty():
    """确保解析器本身有效，否则上面的断言会变成空转。"""
    text = _read("README.md")

    assert len(_headings(text)) > 5
    assert ANCHOR_LINK.findall(text), "没从 README 里解析出任何页内锚点，解析逻辑失效了"
