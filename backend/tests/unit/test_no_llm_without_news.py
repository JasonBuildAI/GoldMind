"""没有任何新闻时，不得调用 LLM。

红线第 1 条（`AGENTS.md` / `docs/00-产品方向.md` 第四节）：

> 数据源或联网搜索不可用时，返回「不可用」并说明原因，**不得**让模型凭印象生成
> 机构目标价、央行购金量、金价点位等具体数字后当作事实展示。

这条红线在提示词里被违反过三次，每次载体不同：

| 载体 | 形态 | 何时修的 |
|---|---|---|
| 写死的兜底常量 | 一个具体的「默认值」 | 第 2 轮 |
| 提示词里的「合理推断」 | 让模型自己编 | 第 21 轮 |
| **无新闻时的邀请语** | 「暂无最新新闻数据，**将基于当前市场状况进行分析**」 | 第 22 轮 |

第三种最隐蔽：它不产生默认值，也不说「编造」，只是**请模型用记忆去补**。
产物与真实分析长得一模一样。

现在的行为：24 小时内一点新闻都没有时**直接返回空 + 状态，不调 LLM** ——
既守住红线，也省下一次没有依据的付费调用。
"""
from datetime import timedelta

import pytest

from app.models.news import GoldNews
from app.utils import timeutil


@pytest.fixture
def no_news(db_session):
    """确保 24 小时内没有任何新闻。"""
    db_session.query(GoldNews).delete()
    db_session.commit()
    return db_session


@pytest.fixture
def no_web_news(monkeypatch):
    """联网抓新闻也返回空。"""
    import app.services.bearish_factor_service as bearish
    import app.services.bullish_factor_service as bullish
    import app.services.institution_prediction_service as institution

    for module in (bullish, bearish, institution):
        for cls_name in dir(module):
            cls = getattr(module, cls_name)
            if isinstance(cls, type) and hasattr(cls, "fetch_news_from_web"):
                monkeypatch.setattr(cls, "fetch_news_from_web", lambda self: [], raising=False)


@pytest.mark.integration
def test_bullish_does_not_call_the_llm_without_news(no_news, no_web_news, fake_llm):
    from app.services.bullish_factor_service import BullishFactorAnalyzer

    result = BullishFactorAnalyzer()._analyze_with_traditional_llm(no_news)

    assert fake_llm.calls == [], "没有新闻却调用了 LLM —— 那是让它凭记忆编"
    assert result["bullish_factors"] == []


@pytest.mark.integration
def test_bearish_does_not_call_the_llm_without_news(no_news, no_web_news, fake_llm):
    from app.services.bearish_factor_service import BearishFactorAnalyzer

    result = BearishFactorAnalyzer()._analyze_with_traditional_llm(no_news)

    assert fake_llm.calls == [], "没有新闻却调用了 LLM"
    assert result["bearish_factors"] == []


@pytest.mark.integration
def test_institution_does_not_call_the_llm_without_news(no_news, no_web_news, fake_llm):
    from app.services.institution_prediction_service import InstitutionPredictionAnalyzer

    result = InstitutionPredictionAnalyzer()._analyze_with_traditional_llm(no_news)

    assert fake_llm.calls == [], "没有新闻却调用了 LLM"
    assert result["institutions"] == []


@pytest.mark.integration
def test_news_from_the_database_is_still_used(db_session, fake_llm):
    """有新闻时必须照常分析 —— 上面几条不能把正常路径也堵死。"""
    from app.services.bullish_factor_service import BullishFactorAnalyzer

    db_session.query(GoldNews).delete()
    db_session.add(
        GoldNews(
            title="美联储暗示降息",
            content="正文",
            url="https://e.invalid/1",
            source="测试源",
            published_at=timeutil.now_naive() - timedelta(hours=2),
        )
    )
    db_session.commit()

    BullishFactorAnalyzer()._analyze_with_traditional_llm(db_session)

    assert fake_llm.calls, "有新闻却没调用 LLM —— 分析链路被堵死了"


@pytest.mark.integration
def test_no_invitation_to_use_the_models_own_knowledge(
    db_session, seed_news, monkeypatch
):
    """提示词里不得再出现「基于当前市场状况进行分析」这类邀请。

    用 `seed_news` 夹具而不是手工插一条：手工插「刚刚发布」的新闻在
    MySQL 上会因为秒级截断与查询边界擦边（SQLite 上则恰好能过），
    夹具插的是几小时前的，稳定落在窗口内。
    """
    from app.services.bullish_factor_service import BullishFactorAnalyzer

    seed_news(count=3, hours_ago=2)

    captured: list[str] = []

    class _Spy:
        def invoke(self, prompt):
            captured.append(prompt)
            raise RuntimeError("stop here")

    analyzer = BullishFactorAnalyzer()
    monkeypatch.setattr(type(analyzer), "llm", property(lambda self: _Spy()))
    monkeypatch.setattr(type(analyzer), "fetch_news_from_web", lambda self: [])

    try:
        analyzer._analyze_with_traditional_llm(db_session)
    except Exception:
        pass

    assert captured, "没有捕获到提示词 —— 说明分析没走到 LLM"
    assert "基于当前市场状况" not in captured[0]
