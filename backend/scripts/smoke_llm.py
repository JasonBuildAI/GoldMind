#!/usr/bin/env python3
"""LLM 接入探测脚本 —— 纯标准库，零依赖。

适用于任何 **OpenAI 兼容端点**（OpenAI / DeepSeek / 通义 / Kimi / Ollama /
小米 MiMo …），不绑定具体供应商。

用途：在改动 GoldMind 的 LLM 调用点之前，先实测确认 4 件事：

    P0  鉴权方式（api-key 头 vs Authorization: Bearer）
    P1  推理请求该用 max_tokens 还是 max_completion_tokens
    P2  对照组（与 P1 二选一）
    P3  （可选）端点能否调用 MiMo 插件式 web_search 联网搜索
    P4  中文 JSON 结构化输出是否稳定可解析

为什么用标准库：本机到 PyPI 的网络被代理阻断，装不上 openai/langchain，
所以只有零依赖脚本才能真正跑起来验证。

用法：
    1. 把 key / 端点 / 模型写入 backend/.env：
           LLM_API_KEY=sk-xxxxx
           LLM_BASE_URL=https://api.deepseek.com/v1
           LLM_MODEL=deepseek-chat
    2. cd backend && python scripts/smoke_llm.py

    P3 默认跳过 —— 只有 backend/.env 里 LLM_SEARCH_ENABLED=true 时才探测
    （联网搜索是 MiMo 插件式的专属能力，不是通用 OpenAI 能力）。

脚本不会打印完整密钥。退出码 0 表示 P1~P4 全部通过。
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

TIMEOUT = 120

BACKEND_DIR = Path(__file__).resolve().parent.parent
RESULT_FILE = Path(__file__).resolve().parent / "smoke_llm_result.json"


# --------------------------------------------------------------------------- #
# 基础设施
# --------------------------------------------------------------------------- #
def setup_console() -> None:
    """让 Windows 控制台按 UTF-8 输出。

    默认代码页是 GBK，直接 print emoji 会抛 UnicodeEncodeError 而不是显示乱码，
    所以必须在任何输出之前把 stdout/stderr 切到 UTF-8（并保留替换字符兜底）。
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:
            pass


def load_env_file(path: Path) -> None:
    """极简 .env 解析器（不覆盖已存在的真实环境变量）。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def mask(secret: str) -> str:
    """只暴露前缀，用于确认 key 类型（tp-/ttp-/sk-）而不泄露内容。"""
    if not secret:
        return "<empty>"
    prefix = secret.split("-", 1)[0] + "-"
    return f"{prefix}***（长度 {len(secret)}）"


def request_chat(
    base_url: str,
    payload: dict,
    api_key: str,
    auth_style: str = "api-key",
    timeout: int = TIMEOUT,
) -> tuple[int, object]:
    """POST {base_url}/chat/completions，返回 (status_code, 已解析响应或错误文本)。"""
    url = base_url.rstrip("/") + "/chat/completions"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if auth_style == "api-key":
        headers["api-key"] = api_key
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw
    except Exception as exc:  # 网络层失败
        return 0, f"{type(exc).__name__}: {exc}"


def extract_text(resp: object) -> str:
    """从 chat completion 响应里取出正文。"""
    if not isinstance(resp, dict):
        return ""
    choices = resp.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return message.get("content") or ""


def brief_error(status: int, resp: object) -> str:
    """把错误压成一行，方便贴日志。"""
    if isinstance(resp, dict):
        err = resp.get("error")
        if isinstance(err, dict):
            code = err.get("code") or err.get("type") or ""
            msg = err.get("message") or ""
            # 端点常把真正的原因放在 `param` 里（例如 web_search 的
            # "web search tool found in the request body, but
            # webSearchEnabled is false"），只看 message 会得到无用的
            # "Param Incorrect"。
            param = err.get("param") or ""
            detail = f"{msg} · {param}" if param else msg
            return f"HTTP {status} · {code} · {detail}"[:300]
        if err:
            return f"HTTP {status} · {err}"[:300]
        return f"HTTP {status} · {json.dumps(resp, ensure_ascii=False)[:250]}"
    return f"HTTP {status} · {str(resp)[:250]}"


def base_payload(model: str, prompt: str) -> dict:
    return {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "stream": False,
    }


# --------------------------------------------------------------------------- #
# 探测项
# --------------------------------------------------------------------------- #
def probe_auth(base_url: str, model: str, api_key: str, results: dict) -> tuple[str, bool]:
    """P0：确定可用的鉴权方式。返回 (auth_style, ok)。"""
    payload = base_payload(model, "回复两个字：收到")
    payload["max_tokens"] = 32

    for style in ("api-key", "bearer"):
        status, resp = request_chat(base_url, payload, api_key, style)
        ok = status == 200
        print(f"  P0 鉴权 [{style:<7}] → {'✅ 可用' if ok else '❌ ' + brief_error(status, resp)}")
        results[f"P0_auth_{style}"] = {"ok": ok, "status": status}
        if ok:
            return style, True
    return "api-key", False


def probe_max_tokens(base_url: str, model: str, api_key: str, auth: str, results: dict) -> bool:
    """P1/P2：max_tokens 与 max_completion_tokens 哪个被接受。"""
    all_ok = False
    for field in ("max_tokens", "max_completion_tokens"):
        payload = base_payload(model, "用一句话说明黄金为什么被视为避险资产。")
        payload[field] = 128
        status, resp = request_chat(base_url, payload, api_key, auth)
        text = extract_text(resp)
        ok = status == 200 and bool(text)
        print(f"  P1 参数 [{field:<22}] → {'✅ 接受' if ok else '❌ ' + brief_error(status, resp)}")
        if ok:
            print(f"       返回 {len(text)} 字：{text[:60].replace(chr(10), ' ')}...")
        results[f"P1_{field}"] = {"ok": ok, "status": status}
        all_ok = all_ok or ok
    return all_ok


def probe_web_search(base_url: str, model: str, api_key: str, auth: str, results: dict) -> bool:
    """P3：该端点能否调用 MiMo 插件式 web_search（仅 LLM_SEARCH_ENABLED=true 时执行）。

    端点若返回 HTTP 400 `web search tool found in the request body, but
    webSearchEnabled is false`，那是**账号侧的插件开关**没开（控制台开通），
    逐变体二分也绕不过去；此时应保持 LLM_SEARCH_ENABLED=false，走数据库/RSS 回退。
    """
    print("  P3 联网搜索 —— 逐变体二分：")
    variants: list[tuple[str, dict, dict]] = [
        ("最小工具定义", {"type": "web_search"}, {}),
        ("+ force_search", {"type": "web_search", "force_search": True}, {}),
        ("+ max_keyword", {"type": "web_search", "force_search": True, "max_keyword": 2}, {}),
        (
            "+ limit/user_location",
            {
                "type": "web_search",
                "force_search": True,
                "max_keyword": 2,
                "limit": 2,
                "user_location": {"type": "approximate", "country": "China"},
            },
            {},
        ),
        (
            "文档示例 + thinking=disabled",
            {
                "type": "web_search",
                "force_search": True,
                "max_keyword": 2,
                "limit": 2,
                "user_location": {"type": "approximate", "country": "China"},
            },
            {"thinking": {"type": "disabled"}},
        ),
    ]

    working: str | None = None
    detail: list[dict] = []
    for name, tool, extra in variants:
        payload = base_payload(model, "搜索一下当前国际金价的最新报价，并给出来源。")
        payload["max_completion_tokens"] = 512
        payload["tools"] = [tool]
        payload.update(extra)

        status, resp = request_chat(base_url, payload, api_key, auth)
        text = extract_text(resp)
        ok = status == 200 and bool(text)
        note = "" if ok else brief_error(status, resp)
        print(f"      [{'OK  ' if ok else 'FAIL'}] {name:<30} {note}")
        detail.append({"variant": name, "ok": ok, "status": status})

        if ok and working is None:
            working = name
            print(f"             返回 {len(text)} 字：{text[:70].replace(chr(10), ' ')}...")
            if isinstance(resp, dict):
                extra_keys = [
                    k
                    for k in resp
                    if k not in ("id", "object", "created", "model", "choices", "usage")
                ]
                if extra_keys:
                    print(f"             额外字段（可能是搜索来源）：{extra_keys}")
                results["P3_extra_fields"] = extra_keys

    results["P3_web_search"] = {
        "ok": working is not None,
        "working_variant": working,
        "variants": detail,
    }

    if working:
        print(f"  P3 结论 → ✅ 可用（有效变体：{working}）")
    else:
        print("  P3 结论 → ❌ 全部变体均失败。最可能的原因：")
        print("             · 账号未开通联网搜索插件（报错：webSearchEnabled is false）")
        print("             · 或该端点本身不支持 MiMo 插件式 web_search 工具")
        print("             → 保持 LLM_SEARCH_ENABLED=false，搜索链路走数据库/RSS 回退")
    return working is not None


def probe_json_output(base_url: str, model: str, api_key: str, auth: str, results: dict) -> bool:
    """P4：中文 JSON 结构化输出稳定性 —— 现有代码靠正则抠 {...}，所以必须可解析。"""
    prompt = (
        "你是黄金市场分析师。请严格按以下 JSON 格式返回，不要输出任何其他文字：\n"
        '{"bullish_factors":[{"id":"fed-policy","title":"因素标题",'
        '"subtitle":"副标题","description":"描述","details":["要点1","要点2"],"impact":"high"}],'
        '"analysis_summary":"总结"}\n'
        "请给出 2 个看涨因子。"
    )
    payload = base_payload(model, prompt)
    payload["max_completion_tokens"] = 1500

    status, resp = request_chat(base_url, payload, api_key, auth)
    text = extract_text(resp)
    if status != 200 or not text:
        print(f"  P4 中文JSON → ❌ {brief_error(status, resp)}")
        results["P4_json_output"] = {"ok": False, "status": status}
        return False

    # 完全复刻 GoldMind 现有的解析策略：先直接 parse，失败再抠花括号
    parsed, strategy = None, ""
    try:
        parsed = json.loads(text)
        strategy = "直接解析"
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}") + 1
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start:end])
                strategy = "正则抠取 {...}"
            except json.JSONDecodeError:
                pass

    ok = isinstance(parsed, dict) and bool(parsed.get("bullish_factors"))
    if ok:
        n = len(parsed.get("bullish_factors") or [])
        print(f"  P4 中文JSON → ✅ 可解析（{strategy}），拿到 {n} 个因子")
    else:
        print(f"  P4 中文JSON → ❌ 解析失败（前 120 字：{text[:120]!r}）")
    results["P4_json_output"] = {"ok": ok, "status": status, "strategy": strategy}
    return ok


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main() -> int:
    setup_console()
    load_env_file(BACKEND_DIR / ".env")

    api_key = os.environ.get("LLM_API_KEY", "").strip()
    base_url = os.environ.get("LLM_BASE_URL", "").strip()
    model = os.environ.get("LLM_MODEL", "").strip()
    search_enabled = os.environ.get("LLM_SEARCH_ENABLED", "false").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    print("=" * 68)
    print("LLM 接入探测（OpenAI 兼容端点）")
    print("=" * 68)
    print(f"  BASE_URL : {base_url}")
    print(f"  MODEL    : {model}")
    print(f"  API_KEY  : {mask(api_key)}")
    print(f"  联网搜索 : {'探测' if search_enabled else '跳过（LLM_SEARCH_ENABLED 未开启）'}")

    if not api_key:
        print("\n❌ 未找到 LLM_API_KEY。")
        print(f"   请写入 {BACKEND_DIR / '.env'}：LLM_API_KEY=你的key")
        return 2
    if not base_url or not model:
        print("\n❌ 缺少 LLM_BASE_URL 或 LLM_MODEL（三项齐备才算已配置）。")
        print(f"   请写入 {BACKEND_DIR / '.env'}：LLM_BASE_URL=... / LLM_MODEL=...")
        return 2

    print("-" * 68)
    results: dict = {"base_url": base_url, "model": model, "key_prefix": mask(api_key)}

    auth, auth_ok = probe_auth(base_url, model, api_key, results)
    if not auth_ok:
        print("\n❌ 鉴权失败，后续探测无法进行。请检查 key 是否有效、是否已过期。")
        RESULT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    results["auth_style"] = auth
    print("-" * 68)
    max_tokens_ok = probe_max_tokens(base_url, model, api_key, auth, results)
    print("-" * 68)
    if search_enabled:
        search_ok = probe_web_search(base_url, model, api_key, auth, results)
    else:
        search_ok = True
        results["P3_web_search"] = {"ok": None, "skipped": "LLM_SEARCH_ENABLED=false"}
        print("  P3 联网搜索 → ⏭ 跳过（LLM_SEARCH_ENABLED 未开启，分析走数据库/RSS 回退）")
    print("-" * 68)
    json_ok = probe_json_output(base_url, model, api_key, auth, results)

    print("=" * 68)
    print("结论")
    print("=" * 68)
    print(f"  P1 采样参数   : {'可用' if max_tokens_ok else '全部失败'}")
    if search_enabled:
        print(f"  P3 联网搜索   : {'可用' if search_ok else '不可用 → 保持开关关闭，走数据库/RSS 回退'}")
    else:
        print("  P3 联网搜索   : 跳过（LLM_SEARCH_ENABLED 未开启）")
    print(f"  P4 中文 JSON  : {'稳定可解析' if json_ok else '不可解析 → 需改用结构化输出或加强容错'}")
    print(f"\n  详细结果已写入：{RESULT_FILE}")

    RESULT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    passed = max_tokens_ok and search_ok and json_ok
    print(f"\n{'✅ 全部通过，可以开始替换调用点' if passed else '⚠️  有探测项未通过，请先看上面结论再决定是否继续'}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
