"""消息板块中文翻译：批量、幂等、校验与降级。

这一层最怕两种坏法，两条都在这里被钉住：

1. **编内容**。模型输出被直接信任 → 原文没有的机构 / 数字进了页面，而页面看起来
   与真实译文一模一样。所以解析是**确定性校验**：id 必须落在本批输入集合内，
   中文标题必须非空，不合格的条目整条丢弃、绝不写库。
2. **重复付费**。已经翻好的条目又被送进 prompt —— 每小时一次抓取，一天就是
   24 次白花。所以「已翻译」的判定单独测，并且断言第二次的 prompt 里
   根本不出现已翻条目的标题。
"""
from __future__ import annotations

import json
from datetime import timedelta
from typing import Any, Optional

import pytest

from app.config import settings
from app.models.news_digest import NewsDigestItem
from app.services import llm_gate, news_translation
from app.services.news_translation import (
    BRIEF_ZH_MAX_CHARS,
    TITLE_ZH_MAX_CHARS,
    TRANSLATION_PROMPT,
    build_translation_prompt,
    parse_translation_payload,
)
from app.utils import timeutil

MODEL = "test-model"  # 与 conftest 里的 LLM_MODEL 一致


def _add(
    db,
    *,
    title: str,
    summary: str = "Bullion demand surges across Asia.",
    hours_ago: float = 1.0,
    source: str = "Reuters",
    tier: int = 1,
    title_zh: Optional[str] = None,
    model: Optional[str] = None,
) -> NewsDigestItem:
    now = timeutil.now_naive()
    row = NewsDigestItem(
        title=title,
        summary=summary,
        source=source,
        source_key=source.lower(),
        authority_tier=tier,
        url=f"https://example.invalid/{abs(hash(title))}",
        published_at=now - timedelta(hours=hours_ago),
        fetched_at=now,
        title_zh=title_zh,
        translation_model=model,
    )
    db.add(row)
    db.commit()
    return row


def _payload(*pairs: tuple[int, str, str]) -> str:
    return json.dumps(
        {
            "items": [
                {"id": item_id, "title_zh": title_zh, "brief_zh": brief_zh}
                for item_id, title_zh, brief_zh in pairs
            ]
        },
        ensure_ascii=False,
    )


# --------------------------------------------------------------------------- #
# 提示词：硬约束必须真的写在 prompt 里
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_prompt_forbids_adding_facts_the_source_does_not_have():
    """红线 1 的落地：提示词必须明说「只使用给出的原文信息」。

    变异验证：删掉这一行，本用例必须红 —— 否则「不许编造」只是文档里的一句话。
    """
    assert "只使用给出的原文信息" in TRANSLATION_PROMPT
    # 数字 / 机构 / 背景这三类是历史上真实编造过的东西，逐类点名
    for forbidden in ("数字", "机构名", "背景"):
        assert forbidden in TRANSLATION_PROMPT, f"提示词没有点名禁止添加{forbidden}"


@pytest.mark.unit
def test_prompt_requires_json_only_and_echoes_ids():
    assert '"items"' in TRANSLATION_PROMPT
    assert "id 必须原样返回" in TRANSLATION_PROMPT


@pytest.mark.unit
def test_build_prompt_lists_every_item_with_its_id_and_truncates_the_summary():
    prompt = build_translation_prompt(
        [
            {
                "id": 7,
                "source": "Reuters",
                "tier_label": "一级信源",
                "title": "Gold hits record high",
                "summary": "x" * 5000,
            },
            {
                "id": 9,
                "source": "Kitco News",
                "tier_label": "二级信源",
                "title": "Gold steadies",
                "summary": "",
            },
        ]
    )

    assert "[7] 来源：Reuters（一级信源）" in prompt
    assert "[9] 来源：Kitco News（二级信源）" in prompt
    assert "Gold hits record high" in prompt
    # 摘要截断：不能把整篇塞进一次调用
    assert "x" * (news_translation.PROMPT_SUMMARY_CHARS + 1) not in prompt
    # 没有摘要的条目要如实标出来，不能凭标题编导语
    assert "（来源未提供摘要）" in prompt


# --------------------------------------------------------------------------- #
# 解析：确定性校验，不信任模型
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_parse_accepts_a_valid_payload():
    parsed = parse_translation_payload(
        _payload((1, "金价创纪录", "受央行购金推动。"), (2, "金价持稳", "等待非农。")),
        [1, 2],
    )

    assert parsed == {
        1: {"title_zh": "金价创纪录", "brief_zh": "受央行购金推动。"},
        2: {"title_zh": "金价持稳", "brief_zh": "等待非农。"},
    }


@pytest.mark.unit
def test_parse_drops_ids_outside_the_batch():
    """模型偶尔会把上一批的 id 抄回来 —— 写库就会张冠李戴。"""
    parsed = parse_translation_payload(_payload((1, "甲", "a"), (99, "乙", "b")), [1])

    assert set(parsed) == {1}


@pytest.mark.unit
def test_parse_drops_items_without_a_chinese_title():
    """没有中文标题的「译文」没有意义：整条丢弃，不留一个空壳。"""
    parsed = parse_translation_payload(_payload((1, "", "只有导语"), (2, "   ", "空格")), [1, 2])

    assert parsed == {}


@pytest.mark.unit
def test_parse_keeps_title_when_the_source_had_no_summary():
    parsed = parse_translation_payload(_payload((1, "金价创纪录", "")), [1])

    # 空导语存 None（NULL 的含义才是「没有」），而不是空字符串
    assert parsed == {1: {"title_zh": "金价创纪录", "brief_zh": None}}


@pytest.mark.unit
def test_parse_truncates_overlong_translations():
    parsed = parse_translation_payload(
        _payload((1, "标" * 500, "导" * 900)), [1]
    )

    assert len(parsed[1]["title_zh"]) == TITLE_ZH_MAX_CHARS
    assert len(parsed[1]["brief_zh"]) == BRIEF_ZH_MAX_CHARS


@pytest.mark.unit
@pytest.mark.parametrize(
    "content",
    [
        "",
        "这不是 JSON",
        "```json\n{\"items\": [{\"id\": 1, \"title_zh\":",  # 被输出上限截断
        '{"items": "不是数组"}',
        '{"other": []}',
    ],
)
def test_parse_returns_empty_instead_of_guessing(content):
    assert parse_translation_payload(content, [1]) == {}


# --------------------------------------------------------------------------- #
# 批量翻译：写库、幂等、换模型重翻
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_translate_pending_writes_chinese_and_reports(db_session, fake_llm):
    first = _add(db_session, title="Gold hits record high")
    second = _add(db_session, title="Gold steadies", hours_ago=2)
    fake_llm.responses.append(
        _payload((first.id, "金价创纪录", "央行购金推动。"), (second.id, "金价持稳", "等待数据。"))
    )

    report = news_translation.translate_pending(db_session)

    assert report.requested == 2 and report.translated == 2 and report.failed == 0
    assert report.reason is None
    db_session.expire_all()
    rows = {row.id: row for row in db_session.query(NewsDigestItem).all()}
    assert rows[first.id].title_zh == "金价创纪录"
    assert rows[first.id].brief_zh == "央行购金推动。"
    assert rows[first.id].translation_model == MODEL
    assert rows[first.id].translated_at is not None
    # 英文原文一个字都没动
    assert rows[first.id].title == "Gold hits record high"


@pytest.mark.unit
def test_translate_pending_is_idempotent_and_does_not_repay(db_session, fake_llm):
    row = _add(db_session, title="Gold hits record high")
    fake_llm.responses.append(_payload((row.id, "金价创纪录", "导语")))

    first_report = news_translation.translate_pending(db_session)
    assert first_report.translated == 1

    second_report = news_translation.translate_pending(db_session)

    assert second_report.requested == 0 and second_report.translated == 0
    # 只调用过一次模型；第二次连 prompt 都没拼
    assert len(fake_llm.calls) == 1
    assert "Gold hits record high" in fake_llm.calls[0]
    # 已翻好的条目不得出现在任何后续 prompt 里
    assert all("Gold hits record high" not in call for call in fake_llm.calls[1:])


@pytest.mark.unit
def test_translate_pending_retranslates_when_the_model_changed(db_session, fake_llm):
    """换了模型，旧译文是另一份产物 —— 必须重翻，不能当成已完成。"""
    row = _add(db_session, title="Gold hits record high", title_zh="旧模型的译文", model="old-model")
    fake_llm.responses.append(_payload((row.id, "新模型的译文", "导语")))

    report = news_translation.translate_pending(db_session)

    assert report.requested == 1 and report.translated == 1
    db_session.expire_all()
    refreshed = db_session.get(NewsDigestItem, row.id)
    assert refreshed.title_zh == "新模型的译文"
    assert refreshed.translation_model == MODEL


@pytest.mark.unit
def test_translate_pending_takes_the_newest_items_first(db_session, fake_llm):
    old = _add(db_session, title="Old news", hours_ago=100)
    new = _add(db_session, title="Fresh news", hours_ago=1)

    rows = news_translation.NewsTranslationService(db_session).pending_rows(limit=1, model=MODEL)

    assert [row.id for row in rows] == [new.id], "最新优先：页面上先看到的先有中文"
    assert old.id not in [row.id for row in rows]


@pytest.mark.unit
def test_translate_pending_skips_items_outside_the_window(db_session):
    _add(db_session, title="Ancient news", hours_ago=24 * 40)

    rows = news_translation.NewsTranslationService(db_session).pending_rows(limit=10, model=MODEL)

    assert rows == []


# --------------------------------------------------------------------------- #
# 降级：每种「翻不了」都要有自己的原因，且绝不写库
# --------------------------------------------------------------------------- #
def _assert_nothing_written(db_session, row) -> None:
    db_session.expire_all()
    assert db_session.get(NewsDigestItem, row.id).title_zh is None


@pytest.mark.unit
def test_disabled_switch_reports_its_own_reason(db_session, fake_llm, monkeypatch):
    monkeypatch.setattr(settings, "NEWS_TRANSLATE_ENABLED", False)
    row = _add(db_session, title="Gold hits record high")

    report = news_translation.translate_pending(db_session)

    assert report.translated == 0
    assert "NEWS_TRANSLATE_ENABLED" in (report.reason or "")
    assert fake_llm.calls == [], "关掉开关后一次模型调用都不许有"
    _assert_nothing_written(db_session, row)


@pytest.mark.unit
def test_unconfigured_llm_reports_its_own_reason(db_session, monkeypatch):
    monkeypatch.setattr(news_translation.llm_provider, "is_configured", lambda: False)
    row = _add(db_session, title="Gold hits record high")

    report = news_translation.translate_pending(db_session)

    assert report.translated == 0
    assert "LLM 未配置" in (report.reason or "")
    _assert_nothing_written(db_session, row)


@pytest.mark.unit
def test_budget_exhausted_reports_its_own_reason(db_session, monkeypatch):
    row = _add(db_session, title="Gold hits record high")

    def _exhausted() -> None:
        raise llm_gate.LLMBudgetExceeded("当日 LLM 调用预算已用尽（200/200）")

    monkeypatch.setattr(news_translation.llm_gate.gate, "ensure_budget", _exhausted)

    report = news_translation.translate_pending(db_session)

    assert report.translated == 0
    assert "预算" in (report.reason or "")
    _assert_nothing_written(db_session, row)


@pytest.mark.unit
def test_llm_error_never_propagates(db_session, monkeypatch):
    """翻译失败不许抛异常 —— 抓取与启动引导都调用它，那是两件事。"""
    row = _add(db_session, title="Gold hits record high")

    def _boom(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("端点挂了")

    monkeypatch.setattr(news_translation.llm_provider, "invoke_with_retries", _boom)

    report = news_translation.translate_pending(db_session)

    assert report.translated == 0
    assert "翻译调用失败" in (report.reason or "")
    _assert_nothing_written(db_session, row)


@pytest.mark.unit
def test_unparsable_output_writes_nothing_and_says_so(db_session, fake_llm):
    row = _add(db_session, title="Gold hits record high")
    fake_llm.responses.append("对不起，我不能翻译。")

    report = news_translation.translate_pending(db_session)

    assert report.requested == 1 and report.translated == 0 and report.failed == 1
    assert "无法解析" in (report.reason or "")
    _assert_nothing_written(db_session, row)


@pytest.mark.unit
def test_partial_success_reports_the_count(db_session, fake_llm):
    """模型只回了一半：写进去一半，另一半如实计失败并说明。"""
    first = _add(db_session, title="Gold hits record high")
    second = _add(db_session, title="Gold steadies", hours_ago=2)
    fake_llm.responses.append(_payload((first.id, "金价创纪录", "导语")))

    report = news_translation.translate_pending(db_session)

    assert report.translated == 1 and report.failed == 1
    assert report.failed_ids == [second.id]
    assert "1 条没有拿到可用译文" in (report.reason or "")
    _assert_nothing_written(db_session, second)


# --------------------------------------------------------------------------- #
# 状态（GET 响应用，不发起任何调用）
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_translation_status_reports_pending_without_calling_the_model(db_session, fake_llm):
    _add(db_session, title="Gold hits record high")

    status = news_translation.translation_status(db_session)

    assert status["enabled"] is True
    assert status["model"] == MODEL
    assert status["pending"] == 1
    assert fake_llm.calls == [], "GET 路径不许调用模型"


@pytest.mark.unit
def test_translation_status_is_quiet_when_everything_is_translated(db_session):
    _add(db_session, title="Gold hits record high", title_zh="金价创纪录", model=MODEL)

    status = news_translation.translation_status(db_session)

    assert status["pending"] == 0
    assert status["reason"] is None, "没有待翻译条目时不该给一句套话当理由"


@pytest.mark.unit
def test_translation_status_explains_why_it_cannot_translate(db_session, monkeypatch):
    _add(db_session, title="Gold hits record high")
    monkeypatch.setattr(news_translation.llm_provider, "is_configured", lambda: False)

    status = news_translation.translation_status(db_session)

    # 「待翻译」照数（这条确实还没有中文），只是翻不了 —— 原因必须给出来
    assert status["pending"] == 1
    assert "LLM 未配置" in (status["reason"] or "")


@pytest.mark.unit
def test_translation_status_surfaces_the_last_failure(db_session, fake_llm):
    _add(db_session, title="Gold hits record high")
    fake_llm.responses.append("这不是 JSON")
    news_translation.translate_pending(db_session)

    status = news_translation.translation_status(db_session)

    assert status["pending"] == 1
    assert "无法解析" in (status["reason"] or ""), "上一次失败的原因要能传到页面上"


@pytest.mark.unit
def test_last_report_is_cached_for_the_page(db_session, fake_llm):
    _add(db_session, title="Gold hits record high")
    fake_llm.responses.append("这不是 JSON")

    news_translation.translate_pending(db_session)

    cached = news_translation.last_translation_report()
    assert cached is not None
    assert cached["requested"] == 1 and cached["translated"] == 0
