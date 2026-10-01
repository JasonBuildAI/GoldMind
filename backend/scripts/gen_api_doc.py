#!/usr/bin/env python3
"""从 FastAPI 路由表生成 `docs/API.md`（中文）与 `docs/en/api.md`（英文）。

**为什么要生成而不是手写**：手写的接口文档已经与实现严重脱节 ——
前缀写成 `/api/analysis/*`（实际全在 `/api/gold` 下）、
`/gold/stats` 的字段名写成 `ytd_change`/`volatility_range`
（实际返回 `ytd_return`/`volatility`）、限流规则也与代码不符。
手写文档会持续漂移；从路由表生成则不会。

**为什么两份一起生成**：英文版若靠人工翻译，第一天就会与中文版分叉。
两份共用同一次 `_collect_routes()`，只有标题、说明与 summary 走各自的表 ——
英文 summary 查 `SUMMARY_EN`，查不到就回退路由名，而不是留空。

`backend/tests/integration/test_api_doc.py` 会校验两份文档与路由一致，
因此「改了接口却没更新文档」会直接让闸门变红。

用法：
    cd backend && python scripts/gen_api_doc.py          # 写入两份文档
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
DOC_PATH_EN = REPO_ROOT / "docs" / "en" / "api.md"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


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


# 英文 summary 表：键是 `"METHOD path"`。缺条目时回退路由名（不是留空），
# 因此新增接口不会让英文版出现空白说明 —— 但补上译文仍然是你的事。
SUMMARY_EN: dict[str, str] = {
    "GET /api/gold/bearish-factors-ai": "AI-generated bearish factors (fast, cached response)",
    "POST /api/gold/bearish-factors-ai/refresh": "Refresh the bearish-factor analysis.",
    "GET /api/gold/bullish-factors-ai": "AI-generated bullish factors (fast, cached response)",
    "POST /api/gold/bullish-factors-ai/refresh": "Refresh the bullish-factor analysis.",
    "GET /api/gold/dollar-realtime": (
        "Realtime dollar index (source: Sina Finance ICE DINIW; 30-second cache)."
    ),
    "GET /api/gold/factors": "Stored market factors, optionally filtered by type.",
    "GET /api/gold/factors/bearish": (
        "Bearish factors read straight from the database (no AI call)."
    ),
    "GET /api/gold/factors/bullish": (
        "Bullish factors read straight from the database (no AI call)."
    ),
    "GET /api/gold/institution-predictions-ai": (
        "AI analysis of institution views: each bank's latest verifiable gold target, "
        "with its prediction date and source."
    ),
    "POST /api/gold/institution-predictions-ai/refresh": (
        "Refresh the institution-view analysis."
    ),
    "GET /api/gold/institutions": "Stored institution views.",
    "GET /api/gold/investment-advice-ai": "AI-generated investment advice.",
    "POST /api/gold/investment-advice-ai/refresh": (
        "Refresh the investment-advice analysis."
    ),
    "GET /api/gold/latest": "Latest gold price row in the database.",
    "GET /api/gold/market-summary-ai": "AI-generated gold market summary.",
    "POST /api/gold/market-summary-ai/refresh": "Refresh the market summary.",
    "GET /api/gold/news": (
        "News list, filterable by source and sentiment (no pagination; first `limit` rows only)."
    ),
    "GET /api/gold/news/sentiment/summary": (
        "News sentiment distribution. Note: rows are always stored as NEUTRAL — this project "
        "does no sentiment analysis, so this is always all-neutral; the field exists only to "
        "keep the response shape stable."
    ),
    "GET /api/gold/news/{news_id}": "Single news item.",
    "GET /api/gold/predictions": (
        "Stored price predictions. The table holds real rows: the quant engine "
        "(services/quant) writes one per refresh."
    ),
    "GET /api/gold/predictions/latest": "Latest stored price prediction.",
    "GET /api/gold/prices/correlation": "Gold vs. dollar index correlation.",
    "GET /api/gold/prices/daily": "Daily gold price series.",
    "GET /api/gold/quant/accuracy": (
        "Walk-forward hit rate, side by side with the always-long / momentum / coin-flip baselines."
    ),
    "GET /api/gold/quant/factors": (
        "Current snapshot of the four driver categories: value, direction, contribution, "
        "source and data-as-of date."
    ),
    "GET /api/gold/quant/monitor": (
        "Monitoring dashboard: one row per indicator (frequency, source, current value, "
        "signal, data as of)."
    ),
    "GET /api/gold/quant/predictions": (
        "Quant forecast: direction, upside probability, target price and per-factor contributions."
    ),
    "POST /api/gold/quant/refresh": (
        "Fetch factors, recompute predictions and append one backtest run now "
        "(takes tens of seconds)."
    ),
    "GET /api/gold/quant/research": (
        "Research page: skill overview, reliability bins, coverage, regime scores, "
        "factor breakdown and the pre-registered verdict."
    ),
    "GET /api/gold/stats": (
        "Gold price statistics since 2025 (current price, return, volatility range, ...)."
    ),
    "GET /": "Service information and documentation entry points.",
    "GET /health": "Enhanced health check covering every critical dependency.",
}


def _is_expensive(path: str) -> bool:
    return path.endswith("/refresh")


def _is_llm_backed(path: str) -> bool:
    """会真实调用 LLM 的刷新端点（与 app/main.py 的 _is_ai_path 同一判据）。"""
    return path.endswith("/refresh") and "-ai" in path


LABELS = {
    "zh": {
        "title": "# GoldMind API",
        "banner": [
            "> 🤖 **本文件由 `backend/scripts/gen_api_doc.py` 从 FastAPI 路由表生成，请勿手工编辑。**",
            "> 改接口后运行 `cd backend && python scripts/gen_api_doc.py` 重新生成；",
            "> `backend/tests/integration/test_api_doc.py` 会校验两份语言版本都与路由表一致。",
        ],
        "switch": "> 🌐 [中文](./API.md) | [English](./en/api.md)",
        "interactive": [
            "运行中的服务还提供交互式文档：`http://localhost:8000/docs`（Swagger UI）",
            "与 `http://localhost:8000/openapi.json`（OpenAPI 规范）。",
        ],
        "conventions_title": "## 通用约定",
        "conventions": [
            "- **前缀**：所有业务接口都在 `/api/gold` 下（不是 `/api/analysis` 或 `/api/news`）",
            "- **鉴权**：无。若要公开部署，请在反向代理层加访问控制",
            "- **限流**：按客户端 IP 的滑动窗口。普通接口默认 60 次/分钟；",
            "  路径以 `/refresh` 结尾的接口按「重操作」限流，默认仅 6 次/分钟",
            "  （AI 分析刷新会真实调用 LLM，量化刷新会出网抓取全部数据源）。",
            "  `/health` 不限流。超限返回 `429`，响应体含 `retry_after`（秒）",
            "- **CORS**：仅允许 `CORS_ALLOW_ORIGINS` 中列出的来源",
            "- **错误格式**：FastAPI 默认的 `{\"detail\": ...}`；限流为 `{\"error\", \"retry_after\"}`",
        ],
        "list_title": "## 接口一览",
        "table_head": "| 方法 | 路径 | 说明 |",
        "fields_title": "## 响应字段以代码为准",
        "fields": [
            "各接口的响应模型定义在 `backend/app/schemas/`，字段名请以那里为准。",
            "举例：`GET /api/gold/stats` 返回的是 `ytd_return` 与 `volatility`，",
            "而不是早期文档里写的 `ytd_change` 与 `volatility_range`。",
            "",
            "前端对应的类型定义在 `app/src/services/api.ts`，两侧必须保持一致。",
        ],
        "llm": "（**会调用 LLM**，限流更严）",
        "heavy": "（**重操作**，限流更严）",
        "group_other": "其他",
    },
    "en": {
        "title": "# GoldMind API",
        "banner": [
            "> 🤖 **Generated from the FastAPI route table by `backend/scripts/gen_api_doc.py` — do not edit by hand.**",
            "> After changing an endpoint run `cd backend && python scripts/gen_api_doc.py`;",
            "> `backend/tests/integration/test_api_doc.py` checks that both language versions match the routes.",
        ],
        "switch": "> 🌐 [中文](../API.md) | [English](./api.md)",
        "interactive": [
            "The running service also serves interactive documentation at `http://localhost:8000/docs`",
            "(Swagger UI) and `http://localhost:8000/openapi.json` (the OpenAPI schema).",
        ],
        "conventions_title": "## Conventions",
        "conventions": [
            "- **Prefix**: every business endpoint lives under `/api/gold` (not `/api/analysis` or `/api/news`)",
            "- **Auth**: none. Add access control at the reverse proxy before exposing this publicly",
            "- **Rate limiting**: sliding window per client IP. Regular endpoints default to 60/min;",
            "  paths ending in `/refresh` count as heavy operations and default to 6/min",
            "  (AI analysis refreshes really call the LLM; the quant refresh fetches every data source).",
            "  `/health` is not limited. Over the limit returns `429` with `retry_after` (seconds)",
            "- **CORS**: only the origins listed in `CORS_ALLOW_ORIGINS`",
            "- **Errors**: FastAPI's `{\"detail\": ...}`; rate limiting returns `{\"error\", \"retry_after\"}`",
        ],
        "list_title": "## Endpoints",
        "table_head": "| Method | Path | Description |",
        "fields_title": "## Response fields follow the code",
        "fields": [
            "Response models live in `backend/app/schemas/`; field names follow that source.",
            "For example `GET /api/gold/stats` returns `ytd_return` and `volatility`, not the",
            "`ytd_change` / `volatility_range` an early hand-written doc claimed.",
            "",
            "The matching frontend types live in `app/src/services/api.ts`; the two must agree.",
        ],
        "llm": "(**calls the LLM**, stricter rate limit)",
        "heavy": "(**heavy operation**, stricter rate limit)",
        "group_other": "other",
    },
}


def _note_for(row: dict, lang: str) -> str:
    """一行的说明：中文取 docstring，英文查 SUMMARY_EN，缺条目回退路由名。"""
    labels = LABELS[lang]
    if lang == "zh":
        note = row["summary"] or row["name"]
    else:
        note = SUMMARY_EN.get(f"{row['method']} {row['path']}") or row["name"]
    if _is_expensive(row["path"]):
        note += " " + (labels["llm"] if _is_llm_backed(row["path"]) else labels["heavy"])
    return note


def render(lang: str = "zh") -> str:
    labels = LABELS[lang]
    rows = _collect_routes()
    by_prefix: dict[str, list[dict]] = {}
    for row in rows:
        # 用第二段做分组（/api/gold/... -> gold）
        parts = [p for p in row["path"].split("/") if p]
        group = parts[1] if len(parts) > 1 and parts[0] == "api" else labels["group_other"]
        by_prefix.setdefault(group, []).append(row)

    lines: list[str] = [labels["title"], "", labels["switch"], ""]
    lines += labels["banner"]
    lines += [""] + labels["interactive"] + ["", "---", "", labels["conventions_title"], ""]
    lines += labels["conventions"]
    lines += ["", "---", "", labels["list_title"], ""]

    for group in sorted(by_prefix):
        lines.append(f"### {group}")
        lines.append("")
        lines.append(labels["table_head"])
        lines.append("|---|---|---|")
        for row in by_prefix[group]:
            lines.append(f"| `{row['method']}` | `{row['path']}` | {_note_for(row, lang)} |")
        lines.append("")

    lines += ["---", "", labels["fields_title"], ""] + labels["fields"] + [""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只校验文档是否最新")
    args = parser.parse_args()

    targets = ((DOC_PATH, render("zh")), (DOC_PATH_EN, render("en")))

    if args.check:
        stale = [
            str(path.relative_to(REPO_ROOT))
            for path, content in targets
            if (path.read_text(encoding="utf-8") if path.exists() else "") != content
        ]
        if stale:
            print("以下接口文档已过期，请运行：cd backend && python scripts/gen_api_doc.py")
            for name in stale:
                print(f"  - {name}")
            return 1
        print("docs/API.md 与 docs/en/api.md 均与路由表一致")
        return 0

    for path, content in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"已生成 {path.relative_to(REPO_ROOT)}（{len(content.splitlines())} 行）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
