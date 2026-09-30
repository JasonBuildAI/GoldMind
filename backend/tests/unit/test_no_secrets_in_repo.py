"""防止密钥与个人信息再次进入版本控制的守卫测试。

这些断言直接跑 `git ls-files`，检查的是**真正会被提交的内容**，而不是工作区里
那些已被 `.gitignore` 排除的临时文件（`backend/.env`、`backend/cache/` 等）。

它守不住**历史** —— 历史里的泄漏只能靠重写来消除，步骤见
`docs/10-密钥与隐私.md`；这个文件保证的是「从此往后不再新增」。

刻意不做的事：不检查工作区里的未跟踪文件。那些文件本来就不该被提交，
把它们纳入检查只会让 `backend/.env` 这种正常的本地配置导致测试变红。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

# 密钥形状。要求足够长，避免把文档里的 `sk-xxx` 占位符也算进来。
SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI 风格密钥"),
    (r"tp-[A-Za-z0-9]{20,}", "Token Plan 密钥"),
    (r"ghp_[A-Za-z0-9]{20,}", "GitHub personal access token"),
    (r"github_pat_[A-Za-z0-9_]{20,}", "GitHub fine-grained token"),
    (r"AKIA[0-9A-Z]{16}", "AWS Access Key ID"),
    (r"AIza[0-9A-Za-z_\-]{30,}", "Google API key"),
    (r"xox[baprs]-[A-Za-z0-9-]{10,}", "Slack token"),
]

# 个人邮箱。占位符域名与 noreply 地址不算。
PERSONAL_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@(gmail|qq|163|126|outlook|hotmail|foxmail|sina)\.com",
    re.IGNORECASE,
)
EMAIL_ALLOWLIST = (
    "example.com",
    "noreply",
    "users.noreply.github.com",
)

# 只对文档类文件做「QQ 号」检查。
#
# 不能直接匹配「一串数字」：文档里的年份、价格、代码编号都是数字，会大量误报。
# 而且 QQ 号本身没有固定长度（5～11 位都有），跟手机号规则也不一样。
# 所以只在**联系方式上下文**里检查 —— 「QQ」「QQ号」「QQ邮箱」后面跟的数字。
DOC_SUFFIXES = (".md",)
QQ_IN_CONTACT_CONTEXT = re.compile(
    r"(?:QQ|qq)\s*(?:号码?|邮箱|mail)?\s*[:：]?\s*(\d{5,11})"
)


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    ).stdout


@pytest.fixture(scope="module")
def tracked_files() -> list[Path]:
    names = [n for n in _git("ls-files").splitlines() if n.strip()]
    assert names, "git ls-files 返回空 —— 这个仓库状态不对"
    return [REPO_ROOT / n for n in names]


def _read_text(path: Path) -> str | None:
    """读文本；二进制文件返回 None。"""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _scan(tracked_files: list[Path], pattern: re.Pattern[str]) -> list[str]:
    hits: list[str] = []
    for path in tracked_files:
        if not path.is_file():
            continue
        text = _read_text(path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                rel = path.relative_to(REPO_ROOT).as_posix()
                hits.append(f"{rel}:{lineno}: {line.strip()[:120]}")
    return hits


# --------------------------------------------------------------------------- #
# 密钥
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize("pattern,label", SECRET_PATTERNS, ids=[p[1] for p in SECRET_PATTERNS])
def test_no_secret_shaped_strings_in_tracked_files(tracked_files, pattern, label):
    hits = _scan(tracked_files, re.compile(pattern))

    assert not hits, (
        f"受版本控制的文件里出现疑似{label}。\n"
        f"密钥只能放在 .env（已被 .gitignore 忽略）与部署环境里。\n"
        + "\n".join(hits)
    )


# --------------------------------------------------------------------------- #
# 个人信息
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_no_personal_email_in_tracked_files(tracked_files):
    hits = [
        hit
        for hit in _scan(tracked_files, PERSONAL_EMAIL)
        if not any(allowed in hit for allowed in EMAIL_ALLOWLIST)
    ]

    assert not hits, (
        "受版本控制的文件里出现个人邮箱。联系方式请引导到 GitHub Issues。\n"
        + "\n".join(hits)
    )


@pytest.mark.unit
def test_no_qq_number_in_docs(tracked_files):
    """文档里不该出现 QQ 号 —— 那是联系方式，不是数据。"""
    docs = [p for p in tracked_files if p.suffix in DOC_SUFFIXES and p.is_file()]
    hits = _scan(docs, QQ_IN_CONTACT_CONTEXT)

    assert not hits, (
        "文档里出现疑似 QQ 号。联系方式请引导到 GitHub Issues。\n" + "\n".join(hits)
    )


# --------------------------------------------------------------------------- #
# 配置文件
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_env_is_not_tracked(tracked_files):
    """`backend/.env` 保存着真实密钥，绝不能进版本控制。"""
    tracked = {p.relative_to(REPO_ROOT).as_posix() for p in tracked_files}

    assert "backend/.env" not in tracked
    assert ".env" not in tracked


@pytest.mark.unit
def test_env_example_holds_only_placeholders(tracked_files):
    """`.env.example` 会入库，里面只能是占位符。"""
    example = REPO_ROOT / "backend" / ".env.example"
    assert example.is_file(), "缺少 backend/.env.example"

    text = example.read_text(encoding="utf-8")

    for pattern, label in SECRET_PATTERNS:
        assert not re.search(pattern, text), f".env.example 里出现疑似{label}"


@pytest.mark.unit
def test_gitignore_covers_the_sensitive_paths():
    """`.env`、本地数据库、缓存目录都必须被忽略。"""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    entries = {
        line.strip()
        for line in gitignore.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    for required in (".env", "*.db", "backend/cache/", "node_modules/"):
        assert required in entries, f".gitignore 缺少 {required}"


@pytest.mark.unit
def test_ignored_sensitive_files_really_are_ignored():
    """`.gitignore` 里写了不算数，要真的生效。"""
    for rel in ("backend/.env", "backend/e2e.db", "backend/cache"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel],
            cwd=REPO_ROOT,
            capture_output=True,
        )
        # 0 = 被忽略；1 = 没被忽略；128 = 出错
        assert result.returncode == 0, f"{rel} 没有被 .gitignore 忽略"
