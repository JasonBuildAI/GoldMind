#!/usr/bin/env python
"""配置级自检：只读，不连数据库、不发网络请求。

回答一个具体问题：**「这台机器上的 GoldMind 还缺什么才能跑起来？」**
每一项都给出结论与可执行的修复命令；只读，不改任何文件、不建表、不写库。

用法（在 backend 目录下）：

    python scripts/verify_setup.py

退出码：0 = 必需项全过；1 = 有必需项不满足（细节见输出）。
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent

OK = "[ok]"
WARN = "[warn]"
FAIL = "[fail]"

results: list[tuple[str, str, str]] = []


def record(level: str, name: str, detail: str, fix: str = "") -> None:
    results.append((level, name, detail + (f" -> 修复: {fix}" if fix and level == FAIL else "")))


def check_python() -> None:
    version = sys.version_info
    if (version.major, version.minor) in {(3, 11), (3, 12)}:
        record(OK, "Python 版本", f"{version.major}.{version.minor}.{version.micro}")
    else:
        record(
            FAIL,
            "Python 版本",
            f"当前 {version.major}.{version.minor}.{version.micro}，需要 3.11 或 3.12",
            "安装 Python 3.11/3.12 并重建虚拟环境: python -m venv .venv",
        )


REQUIRED_MODULES = {
    "fastapi": "fastapi",
    "sqlalchemy": "SQLAlchemy",
    "pydantic_settings": "pydantic-settings",
    "httpx": "httpx",
    "apscheduler": "APScheduler",
    "pandas": "pandas",
    "numpy": "numpy",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
}
OPTIONAL_MODULES = {
    "pymysql": "PyMySQL（只有走 MySQL 路径才需要）",
    "pytest": "pytest（只有跑测试才需要）",
}


def check_dependencies() -> None:
    missing = [pip for module, pip in REQUIRED_MODULES.items() if importlib.util.find_spec(module) is None]
    if missing:
        record(
            FAIL,
            "后端依赖",
            "缺少: " + ", ".join(missing),
            "pip install -r requirements.txt -r requirements-dev.txt",
        )
    else:
        record(OK, "后端依赖", f"{len(REQUIRED_MODULES)} 个必需包可导入")
    absent_optional = [label for module, label in OPTIONAL_MODULES.items() if importlib.util.find_spec(module) is None]
    if absent_optional:
        record(WARN, "可选依赖", "未安装: " + ", ".join(absent_optional))


def check_database() -> None:
    sys.path.insert(0, str(BACKEND_DIR))
    try:
        from app.config import settings  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - 只有配置本身损坏才会走到
        record(FAIL, "数据库配置", f"无法加载 app.config: {exc}", "检查 backend/.env 的写法")
        return

    url = settings.DATABASE_URL.get_secret_value()
    backend = url.split(":", 1)[0]
    if backend.startswith("sqlite"):
        raw = url.split("///", 1)[1]
        path = Path(raw) if raw and raw != ":memory:" else None
        if path is None:
            record(OK, "数据库配置", "SQLite 内存库")
        else:
            writable = path.parent.is_dir() and os.access(path.parent, os.W_OK)
            record(
                OK if writable else FAIL,
                "数据库配置",
                f"SQLite 单文件 {path}（{'已存在' if path.exists() else '尚未创建，init_db.py 会自动建'}，目录{'可写' if writable else '不可写'}）",
                "" if writable else f"检查目录权限，或把 DATABASE_URL 指到可写目录: {path.parent}",
            )
    elif backend.startswith("mysql"):
        driver_ok = importlib.util.find_spec("pymysql") is not None
        record(
            OK if driver_ok else FAIL,
            "数据库配置",
            f"MySQL（{url.split('@')[-1] if '@' in url else url}）",
            "" if driver_ok else "pip install PyMySQL；注意 MySQL 路径未随本仓库实测",
        )
    else:
        record(FAIL, "数据库配置", f"无法识别的 DATABASE_URL 方言: {backend}")

    env_file = BACKEND_DIR / ".env"
    record(
        OK if env_file.exists() else WARN,
        ".env 文件",
        f"{env_file} {'存在' if env_file.exists() else '不存在（默认配置仍可运行：SQLite + 未配置 LLM）'}",
        "cp backend/.env.example backend/.env",
    )


def check_llm() -> None:
    from app.config import settings  # noqa: PLC0415

    key = settings.LLM_API_KEY.get_secret_value().strip()
    placeholders = {"", "your_api_key_here", "sk-xxx", "changeme"}
    configured = key.lower() not in placeholders and bool(settings.LLM_BASE_URL.strip()) and bool(settings.LLM_MODEL.strip())
    if configured:
        record(OK, "LLM 配置", f"已配置（模型 {settings.LLM_MODEL}，端点 {settings.LLM_BASE_URL}）")
    else:
        record(
            WARN,
            "LLM 配置",
            "未配置 —— 应用可正常启动，五个分析区块会如实显示「暂不可用」",
            "在 backend/.env 填 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL 三项",
        )


def check_cache_dir() -> None:
    from app.config import settings  # noqa: PLC0415

    raw = settings.CACHE_DIR.strip() or str(BACKEND_DIR / "cache")
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / raw
    parent = path if path.exists() else path.parent
    writable = parent.is_dir() and os.access(parent, os.W_OK)
    record(
        OK if writable else FAIL,
        "缓存目录",
        f"{path}（{'可写' if writable else '父目录不存在或不可写'}）",
        "" if writable else f"mkdir -p {path.parent} 或把 CACHE_DIR 指到可写目录",
    )


def check_timezone() -> None:
    from app.config import settings  # noqa: PLC0415

    name = settings.SCHEDULER_TIMEZONE
    try:
        from zoneinfo import ZoneInfo  # noqa: PLC0415

        ZoneInfo(name)
        record(OK, "时区口径", f"SCHEDULER_TIMEZONE={name}")
    except Exception:
        record(FAIL, "时区口径", f"无法识别的时区: {name}", "改成 IANA 名称，如 Asia/Shanghai")


def check_optional_components() -> None:
    node_modules = REPO_ROOT / "app" / "node_modules"
    record(
        OK if node_modules.exists() else WARN,
        "前端依赖",
        f"app/node_modules {'已安装' if node_modules.exists() else '未安装'}",
        "cd app && npm ci",
    )
    compose = REPO_ROOT / "docker-compose.yml"
    record(
        OK if compose.exists() else WARN,
        "MySQL / Docker（可选路径）",
        f"{compose} {'存在（本仓库未实测，仅供需要的用户参考）' if compose.exists() else '不存在'}",
    )


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover
        pass
    print("GoldMind 配置级自检（只读；不连库、不出网）")
    print("=" * 60)
    check_python()
    check_dependencies()
    check_database()
    check_llm()
    check_cache_dir()
    check_timezone()
    check_optional_components()

    for level, name, detail in results:
        print(f"{level} {name}: {detail}")

    failures = [r for r in results if r[0] == FAIL]
    warnings = [r for r in results if r[0] == WARN]
    print("=" * 60)
    print(f"结果：{len(results) - len(failures) - len(warnings)} 项通过，{len(warnings)} 项提示，{len(failures)} 项失败")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
