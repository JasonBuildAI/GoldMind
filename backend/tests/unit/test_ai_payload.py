"""``last_updated`` 契约兜底（``app.services.ai_payload``）的单元测试。

真实故障（2026-10-02）：缓存里存的是 LLM 原始输出的转写；模型没吐
``last_updated`` 时，缓存命中路径把这份载荷原样交给响应模型 —— 整个接口 500。
兜底规则：这个时间只能由服务端产生 —— 优先取载荷自己记的生成时间，
没有才用当前时刻。
"""
from __future__ import annotations

from app.services import ai_payload


def test_existing_value_is_kept_and_coerced_to_string():
    payload = {"last_updated": 1759392000}

    result = ai_payload.ensure_last_updated(payload)

    assert result["last_updated"] == "1759392000"


def test_missing_value_prefers_the_payloads_own_generated_at(monkeypatch):
    """载荷自己记的生成时间优先于「现在」—— 缓存命中时不该谎报成刚刚生成。"""
    monkeypatch.setattr(ai_payload.timeutil, "now_str", lambda: "CLOCK-NOW")
    payload = {"metadata": {"generated_at": "2026-10-01T21:00:00+08:00"}}

    result = ai_payload.ensure_last_updated(payload)

    assert result["last_updated"] == "2026-10-01T21:00:00+08:00"


def test_missing_everything_falls_back_to_the_server_clock(monkeypatch):
    monkeypatch.setattr(ai_payload.timeutil, "now_str", lambda: "2026-10-02 14:00:00")

    result = ai_payload.ensure_last_updated({"bullish_factors": []})

    assert result["last_updated"] == "2026-10-02 14:00:00"


def test_empty_string_counts_as_missing(monkeypatch):
    """模型可能吐一个空串 —— 空串不是时间，按缺失处理。"""
    monkeypatch.setattr(ai_payload.timeutil, "now_str", lambda: "2026-10-02 14:00:00")

    result = ai_payload.ensure_last_updated({"last_updated": ""})

    assert result["last_updated"] == "2026-10-02 14:00:00"


def test_non_dict_payloads_pass_through():
    """这一层只负责契约字段，不替调用方判断载荷是否可用。"""
    assert ai_payload.ensure_last_updated(None) is None
    assert ai_payload.ensure_last_updated(["not", "a", "dict"]) == ["not", "a", "dict"]


def test_decorator_covers_every_return_path(monkeypatch):
    monkeypatch.setattr(ai_payload.timeutil, "now_str", lambda: "2026-10-02 14:00:00")

    @ai_payload.with_last_updated
    def returns_early(flag: bool) -> dict:
        if flag:
            return {"analysis_summary": "缓存命中"}
        return {"analysis_summary": "占位"}

    assert returns_early(True)["last_updated"] == "2026-10-02 14:00:00"
    assert returns_early(False)["last_updated"] == "2026-10-02 14:00:00"


def test_decorator_keeps_the_wrapped_signature():
    @ai_payload.with_last_updated
    def sample(use_cache: bool = True) -> dict:
        return {}

    assert sample.__name__ == "sample"
    assert sample(use_cache=False)["last_updated"]
