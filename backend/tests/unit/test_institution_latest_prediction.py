"""机构观点的「最近一次可核实预测」语义。

2026-10-01 06:01 的真实故障：一次没有找到新研报的抓取，把四家机构的真实
目标价（5400 / 5000 / 6300 / 6000）全部覆盖成了「暂无」。本文件的每一条
守卫都对应那次故障的一个成因：

- 别名行与规范行分裂（`Goldman Sachs` 有真实数据、`高盛 (Goldman Sachs)` 被清空）；
- 空 target_price 直接落库覆盖；
- 读路径要求「2 小时内更新」，否则视为无数据；
- 扫描窗口只有 24 小时，窗口内早些时候发布的研报被排除。

每条守卫都做过变异验证（把被测行为改坏，确认它会红）。
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from app.models.analysis import InstitutionView
from app.models.news import GoldNews
from app.services.institution_prediction_service import (
    CANONICAL_NAMES,
    InstitutionPredictionAnalyzer,
    InstitutionPredictionService,
    canonical_name,
    match_institution,
    parse_as_of_date,
)
from app.utils import timeutil


def _seed_view(db_session, name: str, *, price=5400.0, as_of=None, source="legacy"):
    db_session.add(
        InstitutionView(
            institution_name=name,
            logo="GS",
            rating="bullish",
            target_price=price,
            timeframe="2026年底",
            reasoning="真实预测",
            key_points=["要点"],
            as_of_date=as_of,
            source=source,
        )
    )
    db_session.commit()


def _news(title: str, days_ago: float = 0, content: str = "", seconds_ago: float = 0):
    item = GoldNews(title=title, content=content, source="测试源")
    item.published_at = (
        timeutil.now_naive() - timedelta(days=days_ago) - timedelta(seconds=seconds_ago)
    )
    return item


# --------------------------------------------------------------------------- #
# 机构注册表
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize(
    "alias,expected_key",
    [
        ("高盛", "goldman"),
        ("高盛集团", "goldman"),
        ("Goldman Sachs", "goldman"),
        ("goldman", "goldman"),
        ("GS", "goldman"),
        ("瑞银", "ubs"),
        ("UBS", "ubs"),
        ("摩根士丹利", "morgan_stanley"),
        ("Morgan Stanley", "morgan_stanley"),
        ("MS", "morgan_stanley"),
        ("花旗", "citi"),
        ("花旗银行", "citi"),
        ("Citi", "citi"),
        ("Citigroup", "citi"),
    ],
)
def test_aliases_map_to_the_registry(alias, expected_key):
    inst = match_institution(alias)
    assert inst is not None, f"{alias!r} 应当能匹配到注册表"
    assert inst.key == expected_key


@pytest.mark.unit
def test_canonical_names_match_the_registry():
    for name in CANONICAL_NAMES:
        assert canonical_name(name) == name


@pytest.mark.unit
def test_unknown_institutions_do_not_match():
    assert match_institution("摩根大通 (JPMorgan Chase)") is None
    assert match_institution("") is None
    assert canonical_name("某银行") is None


# --------------------------------------------------------------------------- #
# as_of 解析与回退链
# --------------------------------------------------------------------------- #
@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-02-08", "2026-02-08"),
        ("2026/02/08", "2026-02-08"),
        ("2026-02-08T10:00:00", "2026-02-08"),
        ("2026年02月08日", "2026-02-08"),
    ],
)
def test_parse_as_of_accepts_day_precision(raw, expected):
    assert parse_as_of_date(raw).isoformat() == expected


@pytest.mark.unit
@pytest.mark.parametrize("raw", ["", "  ", "不是日期", "2026-02", "2026-02-30", "2099-01-01", "1989-12-31"])
def test_parse_as_of_rejects_junk_and_future_dates(raw):
    assert parse_as_of_date(raw) is None


@pytest.mark.integration
def test_as_of_falls_back_to_the_latest_news_date(db_session):
    analyzer = InstitutionPredictionAnalyzer()
    db_session.add(
        GoldNews(
            title="高盛发布黄金研报",
            content="目标价",
            source="测试源",
            url="https://example.invalid/1",
            published_at=timeutil.now_naive() - timedelta(days=3),
        )
    )
    db_session.commit()

    analyzer.save_to_database(
        db_session,
        {
            "data_source": "news_scan",
            "institutions": [
                {"name": "高盛", "rating": "bullish", "target_price": 5400, "as_of": "不是日期"}
            ],
        },
    )

    row = (
        db_session.query(InstitutionView)
        .filter(InstitutionView.institution_name == CANONICAL_NAMES[0])
        .one()
    )
    assert row.as_of_date == timeutil.today() - timedelta(days=3)


@pytest.mark.integration
def test_as_of_falls_back_to_today_without_any_news(db_session):
    analyzer = InstitutionPredictionAnalyzer()
    analyzer.save_to_database(
        db_session,
        {
            "data_source": "news_scan",
            "institutions": [
                {"name": "高盛", "rating": "bullish", "target_price": 5400, "as_of": ""}
            ],
        },
    )

    row = (
        db_session.query(InstitutionView)
        .filter(InstitutionView.institution_name == CANONICAL_NAMES[0])
        .one()
    )
    assert row.as_of_date == timeutil.today()


@pytest.mark.integration
def test_llm_as_of_wins_when_it_is_valid(db_session):
    analyzer = InstitutionPredictionAnalyzer()
    analyzer.save_to_database(
        db_session,
        {
            "data_source": "web_search",
            "institutions": [
                {"name": "高盛", "rating": "bullish", "target_price": 5400, "as_of": "2026-02-08"}
            ],
        },
    )

    row = (
        db_session.query(InstitutionView)
        .filter(InstitutionView.institution_name == CANONICAL_NAMES[0])
        .one()
    )
    assert row.as_of_date.isoformat() == "2026-02-08"
    assert row.source == "web_search"


# --------------------------------------------------------------------------- #
# 写入：空目标价绝不覆盖真实数据
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_empty_target_price_never_overwrites_a_real_prediction(db_session):
    today = timeutil.today()
    original_date = today - timedelta(days=5)
    _seed_view(db_session, CANONICAL_NAMES[0], price=5400.0, as_of=original_date, source="news_scan")

    written = InstitutionPredictionAnalyzer().save_to_database(
        db_session,
        {
            "data_source": "news_scan",
            "institutions": [
                {
                    "name": "高盛 (Goldman Sachs)",
                    "rating": "neutral",
                    "target_price": None,
                    "reasoning": "暂无最新预测",
                    "as_of": "",
                }
            ],
        },
    )

    assert written == 0, "没有真实目标价就不该计成写入"
    row = (
        db_session.query(InstitutionView)
        .filter(InstitutionView.institution_name == CANONICAL_NAMES[0])
        .one()
    )
    assert row.target_price == 5400.0, "真实目标价被空值覆盖 —— 这正是 2026-10-01 的故障"
    assert row.reasoning == "真实预测"
    assert row.as_of_date == original_date
    assert row.source == "news_scan"


@pytest.mark.integration
def test_analysis_without_any_institution_keeps_every_real_row(db_session):
    _seed_view(db_session, CANONICAL_NAMES[0], price=5400.0, as_of=timeutil.today())
    _seed_view(db_session, CANONICAL_NAMES[1], price=5000.0, as_of=timeutil.today())

    InstitutionPredictionAnalyzer().save_to_database(
        db_session, {"data_source": "news_scan", "institutions": []}
    )

    rows = db_session.query(InstitutionView).all()
    prices = {r.institution_name: r.target_price for r in rows}
    assert prices[CANONICAL_NAMES[0]] == 5400.0
    assert prices[CANONICAL_NAMES[1]] == 5000.0
    # 没有提及的两家只写占位行（没有任何数字），绝不凭空补一个目标价
    assert len(rows) == 4
    assert prices[CANONICAL_NAMES[2]] is None
    assert prices[CANONICAL_NAMES[3]] is None


@pytest.mark.integration
def test_save_writes_alias_names_into_canonical_rows(db_session):
    analyzer = InstitutionPredictionAnalyzer()
    written = analyzer.save_to_database(
        db_session,
        {
            "data_source": "web_search",
            "institutions": [
                {"name": "Goldman Sachs", "rating": "bullish", "target_price": "5,400",
                 "timeframe": "2026年底", "reasoning": "x", "key_points": [], "as_of": "2026-02-08"}
            ],
        },
    )

    assert written == 1
    rows = {r.institution_name: r for r in db_session.query(InstitutionView).all()}
    assert set(rows) == set(CANONICAL_NAMES), "四家规范行都应当存在（其余为占位行）"
    assert rows[CANONICAL_NAMES[0]].target_price == 5400.0
    assert rows[CANONICAL_NAMES[0]].as_of_date.isoformat() == "2026-02-08"
    assert rows[CANONICAL_NAMES[1]].target_price is None, "找不到的机构只能写占位行"


# --------------------------------------------------------------------------- #
# 读取：直接组装规范行 + stale_days，空缓存不得遮蔽数据库
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_read_assembles_canonical_rows_with_stale_days(db_session):
    today = timeutil.today()
    _seed_view(db_session, CANONICAL_NAMES[0], price=5400.0, as_of=today - timedelta(days=235))
    # 历史遗留的别名行有「更新」的假数据 —— 读取必须忽略它
    _seed_view(db_session, "Goldman Sachs", price=1.0, as_of=today, source="legacy")
    _seed_view(db_session, CANONICAL_NAMES[1], price=5000.0, as_of=today - timedelta(days=45))

    result = InstitutionPredictionService(db_session).get_institution_predictions()

    names = [item["name"] for item in result["institutions"]]
    assert names == [CANONICAL_NAMES[0], CANONICAL_NAMES[1]], "必须按注册表顺序，且忽略别名行"

    goldman = result["institutions"][0]
    assert goldman["target_price"] == 5400.0
    assert goldman["stale_days"] == 235
    assert goldman["as_of_date"] == (today - timedelta(days=235)).isoformat()
    assert goldman["source"] == "legacy"

    ubs = result["institutions"][1]
    assert ubs["stale_days"] == 45

    assert "未出现新的机构目标价" in result["analysis_summary"]
    assert "最近 30 天" in result["analysis_summary"]


@pytest.mark.integration
def test_an_empty_cached_result_does_not_shadow_the_database(db_session):
    """回归：旧代码把「什么都没找到」的抓取结果也写进缓存，页面再也回不到真实数据。

    两种形态都要挡住：空列表，以及 2026-10-01 06:01 实际写下的
    「四条 null 占位」缓存 —— 后者看起来非空，但没有一条真实目标价。
    """
    _seed_view(db_session, CANONICAL_NAMES[0], price=5400.0, as_of=timeutil.today())

    service = InstitutionPredictionService(db_session)
    service.cache.set({"institutions": [], "analysis_summary": "", "last_updated": ""})

    result = service.get_institution_predictions()

    assert [item["name"] for item in result["institutions"]] == [CANONICAL_NAMES[0]]
    assert result["institutions"][0]["target_price"] == 5400.0

    # 06:01 的缓存形态：四条占位行 + 旧口径摘要
    service.cache.set(
        {
            "institutions": [
                {"name": name, "rating": "neutral", "target_price": None}
                for name in CANONICAL_NAMES
            ],
            "analysis_summary": "过去24小时内检索的新闻中未包含任何机构预测",
            "last_updated": "2026-10-01 06:01:42",
        }
    )

    result = service.get_institution_predictions()

    assert result["institutions"][0]["target_price"] == 5400.0, "占位缓存不得遮蔽真实数据"
    assert "24 小时" not in (result["analysis_summary"] or "")


@pytest.mark.integration
def test_summary_is_rebuilt_from_structured_rows_not_the_model(db_session):
    """回归：汇总不得与结构化行矛盾（实测缓存里「瑞银看涨」而 UBS 行是 neutral）。

    摘要只能由行确定性拼装 —— 输出里只有计数，没有任何方向判断。
    """
    _seed_view(db_session, CANONICAL_NAMES[0], price=5400.0, as_of=timeutil.today(), source="news_scan")
    service = InstitutionPredictionService(db_session)

    result = service._assemble_from_database(metadata={})

    summary = result["analysis_summary"]
    assert "最近 30 天" in summary
    assert "最近 30 天内有 1 家机构的目标价可核实" in summary
    assert "1 家" in summary
    assert "看涨" not in summary and "看跌" not in summary


@pytest.mark.integration
def test_cached_llm_summary_is_replaced_by_the_structured_rebuild(db_session):
    """File 缓存里可能还留着「模型概括」时代的旧摘要；读缓存时也要按行重算。"""
    service = InstitutionPredictionService(db_session)
    service.cache.set(
        {
            "institutions": [
                {"name": CANONICAL_NAMES[1], "rating": "neutral", "target_price": 5000.0, "stale_days": 3},
            ],
            "analysis_summary": "瑞银看涨，目标价上调",
            "last_updated": "2026-10-02 06:00:00",
        }
    )

    result = service.get_institution_predictions()

    assert "瑞银看涨" not in (result["analysis_summary"] or "")
    assert "1 家" in result["analysis_summary"]


@pytest.mark.integration
def test_placeholder_only_rows_say_there_is_no_number_to_show(db_session):
    from app.models.analysis import InstitutionView as View

    db_session.add(
        View(
            institution_name=CANONICAL_NAMES[0], logo="GS", rating="neutral",
            target_price=None, timeframe="", reasoning="暂无最新预测", key_points=[],
            as_of_date=None, source="news_scan",
        )
    )
    db_session.commit()

    result = InstitutionPredictionService(db_session).get_institution_predictions()

    assert result["institutions"][0]["target_price"] is None
    assert result["institutions"][0]["stale_days"] is None
    assert "没有找到任何可核实的机构目标价" in result["analysis_summary"]


# --------------------------------------------------------------------------- #
# 窗口与关键词预选
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_selection_keeps_recent_and_keyword_hits():
    analyzer = InstitutionPredictionAnalyzer()
    recent = [_news(f"行情快讯 {i}", seconds_ago=i) for i in range(20)]
    older_irrelevant = [_news(f"无关旧闻 {i}", days_ago=5) for i in range(10)]
    older_hit = _news("高盛上调黄金目标价至5400美元", days_ago=5)

    selected = analyzer._select_news_for_institutions(recent + older_irrelevant + [older_hit])

    assert selected[:15] == recent[:15], "最近的 15 条必须原样保留"
    assert older_hit in selected, "命中机构名的较早研报不能被最近一批挤掉"
    assert not any(item in selected for item in older_irrelevant), "无关旧闻不该占用预算"
    assert len(selected) == 16


@pytest.mark.unit
def test_selection_caps_the_keyword_bucket():
    analyzer = InstitutionPredictionAnalyzer()
    recent = [_news(f"行情快讯 {i}") for i in range(15)]
    hits = [_news(f"花旗看涨黄金目标价 {i}", days_ago=5) for i in range(40)]

    selected = analyzer._select_news_for_institutions(recent + hits)

    assert len(selected) == 30, "最多 15 条最近 + 15 条关键词命中"


@pytest.mark.integration
def test_lookback_window_comes_from_settings(db_session, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "INSTITUTION_NEWS_LOOKBACK_DAYS", 7)
    now = timeutil.now_naive()
    db_session.add_all(
        [
            GoldNews(title="窗口内", content="", source="测试源", url="https://e.invalid/a",
                     published_at=now - timedelta(days=3)),
            GoldNews(title="窗口外", content="", source="测试源", url="https://e.invalid/b",
                     published_at=now - timedelta(days=10)),
        ]
    )
    db_session.commit()

    titles = {item.title for item in InstitutionPredictionAnalyzer().fetch_recent_news(db_session)}
    assert titles == {"窗口内"}


@pytest.mark.integration
def test_prompt_states_the_configured_window(db_session, seed_news, fake_llm, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "INSTITUTION_NEWS_LOOKBACK_DAYS", 7)
    seed_news(count=2, hours_ago=2)

    InstitutionPredictionAnalyzer()._analyze_with_traditional_llm(db_session)

    assert fake_llm.calls, "有新闻却没走到 LLM"
    assert "最近 7 天" in fake_llm.calls[0], "提示词必须写明当前扫描窗口"
