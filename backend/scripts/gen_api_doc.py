#!/usr/bin/env python3
"""从 FastAPI 路由表生成 `docs/API.md`。

**为什么要生成而不是手写**：手写的接口文档已经与实现严重脱节 ——
前缀写成 `/api/analysis/*`（实际全在 `/api/gold` 下）、
`/gold/stats` 的字段名写成 `ytd_change`/`volatility_range`
（实际返回 `ytd_return`/`volatility`）、限流规则也与代码不符。
手写文档会持续漂移；从路由表生成则不会。

`backend/tests/integration/test_api_doc.py` 会校验文档与路由一致，
因此「改了接口却没更新文档」会直接让闸门变红。

用法：
    cd backend && python scripts/gen_api_doc.py          # 写入 docs/API.md
    cd backend && python scripts/gen_api_doc.py --check   # 只校验是否最新（退出码 1 表示过期）
"""
from __future__ import annotations

import argparse
import inspect
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
DOC_PATH = REPO_ROOT / "docs" / "API.md"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# 只收录这些前缀下的路由；FastAPI 自带的 /docs /openapi.json 等另行说明
PUBLIC_PREFIXES = ("/api/", "/health", "/")


def _collect_routes() -> list[dict]:
    """从应用里取出公开路由，按路径与方法排序，保证输出稳定。"""
    from app.main import app

    rows: list[dict] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        # 只保留公开 API 与健康检查；跳过 FastAPI 内置文档路由
        if path.startswith("/api/") or path in ("/", "/health"):
            endpoint = getattr(route, "endpoint", None)
            # 优先用路由上的 summary；没有就取处理函数 docstring 的第一行
            doc = ""
            if endpoint is not None:
                doc = (inspect.getdoc(endpoint) or "").strip().split("\n")[0].strip()
            summary = (getattr(route, "summary", None) or doc or "").strip()

            for method in sorted(m for m in methods if m not in ("HEAD", "OPTIONS")):
                rows.append(
                    {
                        "method": method,
                        "path": path,
                        "name": getattr(route, "name", ""),
                        "summary": summary,
                    }
                )
    rows.sort(key=lambda r: (r["path"], r["method"]))
    return rows


def _is_expensive(path: str) -> bool:
    return path.endswith("/refresh")


def _is_llm_backed(path: str) -> bool:
    """会真实调用 LLM 的刷新端点（与 app/main.py 的 _is_ai_path 同一判据）。"""
    return path.endswith("/refresh") and "-ai" in path


def render() -> str:
    rows = _collect_routes()
    by_prefix: dict[str, list[dict]] = {}
    for row in rows:
        # 用第二段做分组（/api/gold/... -> gold）
        parts = [p for p in row["path"].split("/") if p]
        group = parts[1] if len(parts) > 1 and parts[0] == "api" else "其他"
        by_prefix.setdefault(group, []).append(row)

    lines: list[str] = [
        "# GoldMind API",
        "",
        "> 🤖 **本文件由 `backend/scripts/gen_api_doc.py` 从 FastAPI 路由表生成，请勿手工编辑。**",
        "> 改接口后运行 `cd backend && python scripts/gen_api_doc.py` 重新生成；",
        "> `backend/tests/integration/test_api_doc.py` 会校验两者一致。",
        "",
        "运行中的服务还提供交互式文档：`http://localhost:8000/docs`（Swagger UI）",
        "与 `http://localhost:8000/openapi.json`（OpenAPI 规范）。",
        "",
        "---",
        "",
        "## 通用约定",
        "",
        "- **前缀**：所有业务接口都在 `/api/gold` 下（不是 `/api/analysis` 或 `/api/news`）",
        "- **鉴权**：无。若要公开部署，请在反向代理层加访问控制",
        "- **限流**：按客户端 IP 的滑动窗口。普通接口默认 60 次/分钟；",
        "  路径以 `/refresh` 结尾的接口按「重操作」限流，默认仅 6 次/分钟",
        "  （AI 分析刷新会真实调用 LLM，量化刷新会出网抓取全部数据源）。",
        "  `/health` 不限流。超限返回 `429`，响应体含 `retry_after`（秒）",
        "- **CORS**：仅允许 `CORS_ALLOW_ORIGINS` 中列出的来源",
        "- **错误格式**：FastAPI 默认的 `{\"detail\": ...}`；限流为 `{\"error\", \"retry_after\"}`",
        "",
        "---",
        "",
        "## 接口一览",
        "",
    ]

    for group in sorted(by_prefix):
        lines.append(f"### {group}")
        lines.append("")
        lines.append("| 方法 | 路径 | 说明 |")
        lines.append("|---|---|---|")
        for row in by_prefix[group]:
            note = row["summary"] or row["name"]
            if _is_expensive(row["path"]):
                note += (
                    "（**会调用 LLM**，限流更严）"
                    if _is_llm_backed(row["path"])
                    else "（**重操作**，限流更严）"
                )
            lines.append(f"| `{row['method']}` | `{row['path']}` | {note} |")
        lines.append("")

    lines += [
        "---",
        "",
        "## 响应字段以代码为准",
        "",
        "各接口的响应模型定义在 `backend/app/schemas/`，字段名请以那里为准。",
        "举例：`GET /api/gold/stats` 返回的是 `ytd_return` 与 `volatility`，",
        "而不是早期文档里写的 `ytd_change` 与 `volatility_range`。",
        "",
        "前端对应的类型定义在 `app/src/services/api.ts`，两侧必须保持一致。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只校验文档是否最新")
    args = parser.parse_args()

    content = render()

    if args.check:
        current = DOC_PATH.read_text(encoding="utf-8") if DOC_PATH.exists() else ""
        if current != content:
            print("docs/API.md 已过期，请运行：cd backend && python scripts/gen_api_doc.py")
            return 1
        print("docs/API.md 与路由表一致")
        return 0

    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(content, encoding="utf-8")
    print(f"已生成 {DOC_PATH}（{len(content.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
