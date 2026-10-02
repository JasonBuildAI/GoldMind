#!/usr/bin/env python
"""零人工冷启动验收（2.0.2 核心判据，真实源 + 真实 LLM 版本）。

做什么：在一个**全新目录**里起一个真实服务 —— 只给它一份 `backend/.env`
（LLM 配置来自项目 `.env`，其余走默认），此后不再执行任何命令，验证：

1. 启动引导自行完成（建表 / 迁移 / 回填 / 首轮分析），`/health.bootstrap` 报 done；
2. 七个板块 + 研究页都有内容（空态即失败）；
3. 重启一次仍然幂等：没有重复回填；没有**无理由**的重复计费 ——
   重启后五个分析都留有成功指纹，且新增调用数不超过「输入确实变了」的分析数
   带来的重试余量（输入没变时新增调用数必须为 0）。新闻在两轮之间新到一条，
   对应分析的输入确实变了，重新分析是正确行为而不是重复计费。

用法（在 backend 目录下）：

    python scripts/accept_bootstrap.py --dir ../.acceptance/coldstart --port 8099
    python scripts/accept_bootstrap.py --base-url http://127.0.0.1:8099   # 只做内容检查

退出码：0 = 全部通过；1 = 有检查失败（报告照实列出）；2 = 环境/启动失败。
报告写入 ``<dir>/accept_bootstrap.json``。
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent

def _items(value) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        return list(value.values())
    return []


def _accuracy_ok(body: dict) -> bool:
    """回测端点的**诚实形状**检查。

    冷启动当天，quant-v7 的前向窗口刚重启（窗口内仅 1 注），还没有到期样本；
    sample_size=0 是如实状态而不是空态，前提是每个尺度都给出 sample_size、
    且零样本时给出原因。有样本时按常规判定。
    """
    latest = body.get("latest") or []
    if not body.get("model_version") or not latest:
        return False
    for item in latest:
        if "sample_size" not in (item or {}):
            return False
        if not item.get("sample_size") and not item.get("reason"):
            return False
    return True


PROBES = [
    ("行情", "/api/gold/latest", lambda body: bool(body.get("price"))),
    ("行情", "/api/gold/prices/daily?days=30", lambda body: len(_items(body)) > 0),
    ("今日结论", "/api/gold/market-summary-ai", lambda body: bool(
        body.get("comprehensive_judgment") or body.get("core_view")
    )),
    ("多空", "/api/gold/bullish-factors-ai", lambda body: bool(body.get("bullish_factors"))),
    ("多空", "/api/gold/bearish-factors-ai", lambda body: bool(body.get("bearish_factors"))),
    ("消息", "/api/gold/news/digest", lambda body: bool(body.get("has_data")) and bool(body.get("windows"))),
    ("机构", "/api/gold/institutions", lambda body: len(_items(body)) > 0),
    ("机构", "/api/gold/institution-predictions-ai", lambda body: bool(body.get("institutions"))),
    ("策略", "/api/gold/investment-advice-ai", lambda body: bool(
        body.get("market_assessment") or body.get("strategies")
    )),
    ("量化", "/api/gold/quant/factors", lambda body: body.get("available_factors", 0) > 0),
    ("量化", "/api/gold/quant/predictions", lambda body: any(
        item.get("status") == "ok" for item in (body.get("predictions") or [])
    )),
    ("量化", "/api/gold/quant/accuracy", _accuracy_ok),
    ("量化", "/api/gold/quant/monitor", lambda body: bool(body.get("rows"))),
    ("研究", "/api/gold/quant/research", lambda body: bool(body.get("horizons") or body.get("verdict"))),
    ("数据与方法", "/api/gold/sources/status", lambda body: bool(body.get("sources"))),
]


def _get(url: str, timeout: float = 60.0) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "goldmind-acceptance"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            return error.code, json.loads(error.read().decode("utf-8"))
        except Exception:
            return error.code, {}
    except Exception as error:
        return 0, {"error": f"{type(error).__name__}: {error}"}


def _wait_health(base_url: str, timeout_s: float, poll_s: float = 10.0) -> dict:
    deadline = time.time() + timeout_s
    last: dict = {}
    while time.time() < deadline:
        status, body = _get(f"{base_url}/health", timeout=30)
        if status == 200:
            last = body
            bootstrap = body.get("bootstrap") or {}
            if bootstrap.get("status") in ("done", "failed", "disabled"):
                return body
        time.sleep(poll_s)
    return last or {"error": "等待 /health 超时"}


def _llm_calls(cache_dir: Path) -> int:
    path = cache_dir / "llm_gate.json"
    if not path.exists():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    total = 0
    for value in (data.get("calls") or {}).values() if isinstance(data.get("calls"), dict) else []:
        total += int(value or 0)
    if isinstance(data.get("calls"), int):
        total = data["calls"]
    return total


EXPECTED_ANALYSIS_KEYS = (
    "bullish_factors",
    "bearish_factors",
    "institution_predictions",
    "market_summary",
    "investment_advice",
)


def _gate_fingerprints(cache_dir: Path) -> dict:
    """`llm_gate.json` 里每个分析键最后成功产出时的输入指纹。"""
    path = cache_dir / "llm_gate.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return {
        key: (value or {}).get("fingerprint")
        for key, value in (data.get("fingerprints") or {}).items()
    }


def _factor_rows(db_path: Path) -> int:
    if not db_path.exists():
        return 0
    connection = sqlite3.connect(str(db_path))
    try:
        try:
            return int(connection.execute("SELECT COUNT(*) FROM factor_observations").fetchone()[0])
        except sqlite3.Error:
            return 0
    finally:
        connection.close()


def _launch(dir_path: Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{(dir_path / 'accept.db').as_posix()}"
    env["CACHE_DIR"] = str(dir_path / "cache")
    env["PYTHONIOENCODING"] = "utf-8"
    log = open(dir_path / "server.log", "a", encoding="utf-8")
    log.write(f"\n===== launch {datetime.now(timezone.utc).isoformat()} =====\n")
    log.flush()
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(BACKEND_DIR),
        env=env,
        stdout=log,
        stderr=subprocess.STDOUT,
    )


def _stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=15)


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="零人工冷启动验收（真实源 + 真实 LLM）")
    parser.add_argument("--dir", type=Path, default=Path("../.acceptance/coldstart"))
    parser.add_argument("--port", type=int, default=8099)
    parser.add_argument("--timeout-min", type=float, default=40.0)
    parser.add_argument("--base-url", default=None, help="只对已有服务做内容检查，不启动/重启")
    args = parser.parse_args(argv)

    dir_path = Path(args.dir).resolve()
    report: dict = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "dir": str(dir_path),
        "port": args.port,
        "checks": [],
        "failures": [],
    }

    if args.base_url:
        base_url = args.base_url.rstrip("/")
    else:
        dir_path.mkdir(parents=True, exist_ok=True)
        db_path = dir_path / "accept.db"
        process = _launch(dir_path, args.port)
        base_url = f"http://127.0.0.1:{args.port}"
        started = time.time()
        first_health = _wait_health(base_url, args.timeout_min * 60)
        report["first_boot"] = first_health.get("bootstrap")
        report["first_boot_seconds"] = round(time.time() - started, 1)
        if (first_health.get("bootstrap") or {}).get("status") != "done":
            report["failures"].append(f"首轮引导未完成：{first_health.get('bootstrap')}")
            _stop(process)
            (dir_path / "accept_bootstrap.json").write_text(
                json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return 1
        calls_after_first = _llm_calls(dir_path / "cache")
        fingerprint_after_first = _gate_fingerprints(dir_path / "cache")
        rows_after_first = _factor_rows(db_path)
        report["llm_calls_after_first_boot"] = calls_after_first
        report["factor_rows_after_first_boot"] = rows_after_first
        report["gate_fingerprints_after_first_boot"] = fingerprint_after_first

        for label, path, predicate in PROBES:
            status, body = _get(base_url + path)
            ok = status == 200 and bool(predicate(body))
            report["checks"].append({"label": label, "path": path, "status": status, "ok": ok})
            if not ok:
                report["failures"].append(f"{label} {path} 空态或不可用（HTTP {status}）")

        _stop(process)
        process = _launch(dir_path, args.port)
        try:
            second_health = _wait_health(base_url, 600)
        finally:
            _stop(process)
        report["second_boot"] = second_health.get("bootstrap")
        calls_after_second = _llm_calls(dir_path / "cache")
        fingerprint_after_second = _gate_fingerprints(dir_path / "cache")
        rows_after_second = _factor_rows(db_path)
        report["llm_calls_after_second_boot"] = calls_after_second
        report["factor_rows_after_second_boot"] = rows_after_second
        report["gate_fingerprints_after_second_boot"] = fingerprint_after_second
        changed_keys = sorted(
            key
            for key in EXPECTED_ANALYSIS_KEYS
            if fingerprint_after_second.get(key) != fingerprint_after_first.get(key)
        )
        missing_keys = sorted(
            key for key in EXPECTED_ANALYSIS_KEYS if not fingerprint_after_second.get(key)
        )
        report["analysis_keys_with_changed_inputs"] = changed_keys
        report["analysis_keys_without_success"] = missing_keys
        if (second_health.get("bootstrap") or {}).get("status") != "done":
            report["failures"].append(f"重启后引导未完成：{second_health.get('bootstrap')}")
        if missing_keys:
            report["failures"].append(f"重启后这些分析没有成功指纹：{missing_keys}")
        delta_calls = calls_after_second - calls_after_first
        # 输入变了的分析重新分析是正确行为；每次重新分析最多一次主调用 +
        # 一次重试（截断 / 风控）。输入没变时新增调用必须为 0。
        allowed = 2 * len(changed_keys)
        if delta_calls < 0:
            report["failures"].append(
                f"重启后调用数反而减少（状态文件被动过？）：{calls_after_first} -> {calls_after_second}"
            )
        elif delta_calls > allowed:
            report["failures"].append(
                f"重启发生无理由的重复计费：{calls_after_first} -> {calls_after_second}"
                f"（输入变化键 {changed_keys or '无'}，最多允许 +{allowed}）"
            )
        if rows_after_second != rows_after_first:
            report["failures"].append(
                f"重启发生重复回填：{rows_after_first} -> {rows_after_second}"
            )
    if args.base_url:
        for label, path, predicate in PROBES:
            status, body = _get(base_url + path)
            ok = status == 200 and bool(predicate(body))
            report["checks"].append({"label": label, "path": path, "status": status, "ok": ok})
            if not ok:
                report["failures"].append(f"{label} {path} 空态或不可用（HTTP {status}）")

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    target = Path(args.dir).resolve() / "accept_bootstrap.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    passed = not report["failures"]
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}, ensure_ascii=False, indent=2))
    print(f"检查 {sum(1 for c in report['checks'] if c['ok'])}/{len(report['checks'])} 通过；报告：{target}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())