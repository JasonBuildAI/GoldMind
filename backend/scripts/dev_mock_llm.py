#!/usr/bin/env python3
"""本地假的 OpenAI 兼容服务 —— 仅供端到端测试使用。

作用：让 Playwright 的端到端测试能跑通**完整后端链路**（含真实的 HTTP 调用、
JSON 解析、缓存写入），而不消耗任何真实 LLM 额度，也不需要网络。

实现方式：按 prompt 里要求的 JSON 结构返回对应样例，与
`backend/tests/e2e/test_full_flow.py` 的分发逻辑保持一致。

用法：
    python scripts/dev_mock_llm.py --port 8099

然后让后端指向它：
    MIMO_BASE_URL=http://127.0.0.1:8099/v1

注意：这是**测试替身**，不要用于任何真实场景。
"""
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# --------------------------------------------------------------------------- #
# 各分析服务的期望输出结构
# --------------------------------------------------------------------------- #
BULLISH = {
    "bullish_factors": [
        {
            "id": "fed-policy",
            "title": "端到端看涨因子",
            "subtitle": "副标题",
            "description": "描述",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "high",
        }
    ],
    "analysis_summary": "看涨总结",
    "last_updated": "2026-02-03 10:00:00",
}

BEARISH = {
    "bearish_factors": [
        {
            "id": "dollar-strength",
            "title": "端到端看跌因子",
            "subtitle": "副标题",
            "description": "描述",
            "details": ["要点1", "要点2", "要点3", "要点4"],
            "impact": "medium",
        }
    ],
    "analysis_summary": "看跌总结",
    "last_updated": "2026-02-03 10:00:00",
}

INSTITUTIONS = {
    "institutions": [
        {
            "name": "高盛 (Goldman Sachs)",
            "logo": "GS",
            "rating": "bullish",
            "target_price": 5400,
            "timeframe": "2026年底",
            "reasoning": "端到端机构理由",
            "key_points": ["a", "b", "c", "d"],
        }
    ],
    "analysis_summary": "机构汇总",
    "last_updated": "2026-02-03 10:00:00",
}

ADVICE = {
    "market_assessment": {
        "current_position": "中位",
        "risk_level": "medium",
        "recommended_approach": "分批建仓",
        "key_considerations": ["考虑1", "考虑2", "考虑3"],
    },
    "strategies": [
        {
            "type": "conservative",
            "title": "保守策略",
            "description": "描述",
            "allocation": "5%",
            "timeframe": "长期",
            "risk_level": "low",
            "entry_strategy": {
                "current_price_assessment": "偏高",
                "recommended_entry_range": "$2500-2600",
                "entry_timing": "等待回调",
                "position_building": "分三批",
            },
            "exit_strategy": {
                "profit_target": "$2900",
                "stop_loss": "-10%",
                "rebalancing_trigger": "年末",
            },
            "pros": ["稳"],
            "cons": ["收益低"],
            "suitable_for": ["新手"],
            "execution_steps": ["步骤1", "步骤2"],
        }
    ],
    "core_principles": [{"title": "风险管理", "description": "描述"}],
    "risk_warning": "端到端风险提示",
    "disclaimer": "端到端免责声明",
}

SUMMARY = {
    "core_bullish_logic": ["端到端核心看涨逻辑"],
    "main_risks": ["端到端主要风险"],
    "market_consensus": ["端到端市场共识"],
    "institution_targets": [
        {"institution": "高盛", "target": 5400, "probability": "高", "timeframe": "2026年底"}
    ],
    "current_price": 2690.0,
    "comprehensive_judgment": {
        "bullish_summary": "偏多",
        "bearish_summary": "偏空",
        "neutral_summary": "中性",
    },
    "core_view": "端到端核心观点",
    "investment_recommendation": "端到端投资建议",
    "confidence_level": "中",
    "time_horizon": "中期",
}

DISPATCH = [
    ("market_assessment", ADVICE),
    ("core_bullish_logic", SUMMARY),
    ("institutions", INSTITUTIONS),
    ("bearish_factors", BEARISH),
    ("bullish_factors", BULLISH),
]


def pick(prompt: str) -> dict:
    for needle, payload in DISPATCH:
        if needle in prompt:
            return payload
    return {}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args) -> None:  # 保持测试输出干净
        pass

    def do_GET(self) -> None:  # noqa: N802
        """健康检查端点。

        只为让 Playwright 的 webServer 就绪探测能通过 —— 它会对配置的 url
        发 GET，而本服务实际只处理 POST。
        """
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8", "replace")

        try:
            body = json.loads(raw)
        except json.JSONDecodeError:
            body = {}

        messages = body.get("messages") or []
        prompt = " ".join(str(m.get("content", "")) for m in messages)
        payload = pick(prompt)

        response = {
            "id": "mock-1",
            "object": "chat.completion",
            "created": 0,
            "model": body.get("model", "mock"),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        }

        data = json.dumps(response, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8099)
    args = parser.parse_args()

    # 必须用多线程版本：页面首次加载会在缓存未命中时并发触发多个后台分析，
    # 单线程 HTTPServer 会让这些请求互相阻塞，表现为「Connection error」。
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    print(f"[mock-llm] listening on http://127.0.0.1:{args.port}/v1", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
