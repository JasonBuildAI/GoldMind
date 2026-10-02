"""AI 分析端点的集成测试。

专门钉住两个曾经让「投资建议」链路静默失真的 bug：

1. 路由从 `bullish_result` 里读 `"factors"`，而服务返回的键是
   `"bullish_factors"` —— 多空因子永远是空列表，LLM 拿不到任何因子。
2. 拼给 LLM 的市场描述读 `ytd_change` / `volatility_range`，而
   `GoldService.get_statistics()` 返回的是 `ytd_return` / `volatility`
   —— 每次分析都被告知「涨幅 +0.00%，波动区间 0.00%」。
"""
import pytest

from app.services.cache_manager import CacheManager
from app.services.gold_service import GoldService
from app.services.investment_advice_service import InvestmentAdviceService
from app.services.market_summary_service import MarketSummaryService

STATS = {
    "current_price": 2710.80,
    "start_price": 2600.0,
    "ytd_return": 4.26,
    "max_price": 2750.0,
    "min_price": 2580.0,
    "max_date": "2025-06-01",
    "min_date": "2025-01-02",
    "volatility": 6.59,
    "market_status": "上涨",
    "market_status_desc": "趋势向好",
    "updated_at": "2026-02-03T10:00:00",
    "data_source": "测试",
}

BULLISH_TITLE = "测试看涨因子标题"
BEARISH_TITLE = "测试看跌因子标题"


def _seed_factor_caches():
    """把已知因子写进缓存，让服务走缓存路径返回可预期的内容。"""
    CacheManager("bullish_factors", ttl=7200).set(
        {
            "bullish_factors": [
                {"id": "fed-policy", "title": BULLISH_TITLE, "subtitle": "s",
                 "description": "d", "details": ["a"], "impact": "high"}
            ],
            "analysis_summary": "summary",
            "last_updated": "2026-02-03 10:00:00",
        }
    )
    CacheManager("bearish_factors", ttl=7200).set(
        {
            "bearish_factors": [
                {"id": "dollar-strength", "title": BEARISH_TITLE, "subtitle": "s",
                 "description": "d", "details": ["a"], "impact": "medium"}
            ],
            "analysis_summary": "summary",
            "last_updated": "2026-02-03 10:00:00",
        }
    )


@pytest.fixture
def stub_stats(monkeypatch):
    """让 get_statistics 返回可预期的固定值，避免依赖出网。"""

    def _install(value=STATS):
        monkeypatch.setattr(GoldService, "get_statistics", lambda self: value)

    return _install


@pytest.fixture
def capture_advice(monkeypatch):
    """截获投资建议服务收到的参数。"""
    captured: dict = {}

    def _fake(self, **kwargs):
        captured.update(kwargs)
        # 必须返回符合契约的完整结构：响应模型现在会校验顶层键，少一个就 500。
        # 这些 fixture 原先只返回两个字段 —— 因为当时 response_model 是
        # Dict[str, Any]，什么都不校验。
        return {
            "market_assessment": {},
            "strategies": [],
            "core_principles": [],
            "risk_warning": "测试用风险提示",
            "disclaimer": "测试用免责声明",
            "metadata": {"status": "analyzing"},
        }

    monkeypatch.setattr(InvestmentAdviceService, "get_investment_advice", _fake)
    return captured


@pytest.fixture
def capture_summary(monkeypatch):
    """截获市场总结服务收到的参数。"""
    captured: dict = {}

    def _fake(self, **kwargs):
        captured.update(kwargs)
        # 同上：市场总结的响应模型也校验顶层键
        return {
            "core_bullish_logic": [],
            "main_risks": [],
            "market_consensus": [],
            "institution_targets": [],
            "comprehensive_judgment": {},
            "core_view": "测试",
            "investment_recommendation": "测试",
            "confidence_level": "中",
            "time_horizon": "中长期",
            "metadata": {"status": "analyzing"},
        }

    monkeypatch.setattr(MarketSummaryService, "get_market_summary", _fake)
    return captured


# --------------------------------------------------------------------------- #
# 投资建议：多空因子必须真的传下去
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_investment_advice_receives_bullish_and_bearish_factors(
    client, stub_stats, capture_advice
):
    """回归：因子不能是空列表（旧代码读错了键名）。"""
    _seed_factor_caches()
    stub_stats()

    resp = client.get("/api/gold/investment-advice-ai")

    assert resp.status_code == 200
    assert [f["title"] for f in capture_advice["bullish_factors"]] == [BULLISH_TITLE]
    assert [f["title"] for f in capture_advice["bearish_factors"]] == [BEARISH_TITLE]


@pytest.mark.integration
def test_investment_advice_market_status_uses_real_stat_keys(
    client, stub_stats, capture_advice
):
    """回归：市场描述必须带真实涨幅/波动，而不是恒为 0。"""
    _seed_factor_caches()
    stub_stats()

    client.get("/api/gold/investment-advice-ai")

    market_status = capture_advice["market_status"]
    assert "4.26%" in market_status
    assert "6.59%" in market_status
    assert "0.00%" not in market_status


@pytest.mark.integration
def test_investment_advice_refresh_also_receives_factors(
    client, stub_stats, capture_advice, monkeypatch
):
    """POST 刷新端点走的是另一段代码，同样要传对因子。

    这里必须**显式替掉**两个因子服务：刷新路径用的是 `use_cache=False`，
    会真的去跑分析；而测试环境不出网、也没有真 LLM。

    注意这条测试此前是**靠编造的兜底内容通过的** —— LLM 失败时
    `_get_default_factors()` 会返回一组写死的因子，于是「因子传下去了」
    看起来成立。第 22 轮把那份兜底清空之后它才暴露出来。
    """
    from app.services.bearish_factor_service import BearishFactorService
    from app.services.bullish_factor_service import BullishFactorService

    monkeypatch.setattr(
        BullishFactorService,
        "get_bullish_factors",
        lambda self, use_cache=True: {
            "bullish_factors": [{"id": "fed-policy", "title": BULLISH_TITLE, "impact": "high"}],
            "analysis_summary": "s",
        },
    )
    monkeypatch.setattr(
        BearishFactorService,
        "get_bearish_factors",
        lambda self, use_cache=True: {
            "bearish_factors": [{"id": "dollar-strength", "title": BEARISH_TITLE, "impact": "medium"}],
            "analysis_summary": "s",
        },
    )
    stub_stats()

    resp = client.post("/api/gold/investment-advice-ai/refresh")

    assert resp.status_code == 200
    assert capture_advice["bullish_factors"], "刷新端点也必须传看涨因子"
    assert capture_advice["bearish_factors"], "刷新端点也必须传看跌因子"


@pytest.mark.integration
def test_investment_advice_survives_missing_statistics(
    client, stub_stats, capture_advice
):
    """回归：无行情数据时 get_statistics() 返回 None，不能让接口 500。"""
    _seed_factor_caches()
    stub_stats(value=None)

    resp = client.get("/api/gold/investment-advice-ai")

    assert resp.status_code == 200
    assert capture_advice["market_status"]  # 兜底字符串仍然可用


# --------------------------------------------------------------------------- #
# 市场总结：同样两个断言
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_market_summary_receives_factors(client, stub_stats, capture_summary):
    _seed_factor_caches()
    stub_stats()

    resp = client.get("/api/gold/market-summary-ai")

    assert resp.status_code == 200
    assert [f["title"] for f in capture_summary["bullish_factors"]] == [BULLISH_TITLE]
    assert [f["title"] for f in capture_summary["bearish_factors"]] == [BEARISH_TITLE]


@pytest.mark.integration
def test_market_summary_market_status_uses_real_stat_keys(
    client, stub_stats, capture_summary
):
    _seed_factor_caches()
    stub_stats()

    client.get("/api/gold/market-summary-ai")

    assert "4.26%" in capture_summary["market_status"]
    assert "0.00%" not in capture_summary["market_status"]


@pytest.mark.integration
def test_market_summary_survives_missing_statistics(
    client, stub_stats, capture_summary
):
    _seed_factor_caches()
    stub_stats(value=None)

    assert client.get("/api/gold/market-summary-ai").status_code == 200


# --------------------------------------------------------------------------- #
# 路由契约
# --------------------------------------------------------------------------- #
@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    [
        "/api/gold/bullish-factors-ai",
        "/api/gold/bearish-factors-ai",
        "/api/gold/institution-predictions-ai",
        "/api/gold/market-summary-ai",
    ],
)
def test_ai_endpoints_return_200_without_any_data(client, path, stub_stats):
    """空库时这些端点也必须可用（返回默认/兜底内容，而不是 5xx）。"""
    stub_stats(value=None)

    assert client.get(path).status_code == 200


@pytest.mark.integration
def test_institution_list_tolerates_placeholder_rows(client, db_session):
    """占位行（target_price=None）不得让 `/institutions` 整体 500。

    实测（2026-10-02）：当天没有可核实目标价时，库里的四条占位行让这个
    「读已入库观点」的端点直接 500 —— 一个诚实的结果反而打挂了接口。
    """
    from app.models.analysis import InstitutionView

    db_session.add(
        InstitutionView(
            institution_name="高盛 (Goldman Sachs)",
            logo="GS",
            rating="neutral",
            target_price=None,
            timeframe=None,
            reasoning="暂无最新预测",
            key_points=[],
            source="legacy",
        )
    )
    db_session.commit()

    response = client.get("/api/gold/institutions")

    assert response.status_code == 200, response.text
    rows = response.json()
    assert rows and rows[0]["target_price"] is None
    assert rows[0]["reasoning"] == "暂无最新预测"
