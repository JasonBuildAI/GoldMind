"""机构评级的归一化。

背景：`institution_views.rating` 在模型里是 `String`，取值约束却只在数据库
（`ENUM('bullish','bearish','neutral')`）。提示词里写了「rating只能是：
bullish, bearish, neutral」，但 LLM 并不总听话 —— 一旦返回「看涨」之类的值，
插入会直接报数据库错误，而 `save_to_database` 是一次 commit，
**一个字段不合规会让整批机构观点都存不进去**。

归一化把这种情况兜住：写进数据库的值永远落在三种之内。
"""
from __future__ import annotations

import pytest

from app.services.institution_prediction_service import VALID_RATINGS, normalize_rating


@pytest.mark.unit
def test_valid_ratings_pass_through():
    for rating in VALID_RATINGS:
        assert normalize_rating(rating) == rating


@pytest.mark.unit
def test_uppercase_is_normalised():
    """MySQL 的 ENUM 比较不区分大小写，但归一化后语义更明确。"""
    assert normalize_rating("BULLISH") == "bullish"
    assert normalize_rating("Bearish") == "bearish"
    assert normalize_rating("  NEUTRAL  ") == "neutral"


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("bull", "bullish"),
        ("buy", "bullish"),
        ("positive", "bullish"),
        ("看涨", "bullish"),
        ("看多", "bullish"),
        ("bear", "bearish"),
        ("sell", "bearish"),
        ("negative", "bearish"),
        ("看跌", "bearish"),
        ("看空", "bearish"),
        ("hold", "neutral"),
        ("中性", "neutral"),
        ("观望", "neutral"),
    ],
)
def test_aliases_map_to_the_three_allowed_values(raw, expected):
    assert normalize_rating(raw) == expected


@pytest.mark.unit
@pytest.mark.parametrize("raw", [None, "", "   ", "看多黄金", "strong buy", "???", 42, [], {}])
def test_unknown_values_fall_back_to_neutral(raw):
    """认不出的值不能让写入失败 —— 退回 neutral 并记警告。"""
    assert normalize_rating(raw) == "neutral"


@pytest.mark.unit
def test_output_is_always_one_of_the_allowed_values():
    """核心不变量：无论输入什么，输出都必须能通过数据库的 ENUM 约束。"""
    samples = [
        None, "", "bullish", "BEARISH", "看涨", "看跌", "neutral",
        "strong buy", "持有", 0, 1, [], {}, "随机文本", "BULL", "SELL",
    ]
    for sample in samples:
        assert normalize_rating(sample) in VALID_RATINGS, f"{sample!r} 归一化后不合规"


@pytest.mark.integration
def test_save_to_database_survives_a_noncompliant_rating(db_session):
    """回归：一个不合规的 rating 不能让整批机构观点都存不进去。"""
    from app.models.analysis import InstitutionView
    from app.services.institution_prediction_service import InstitutionPredictionAnalyzer

    InstitutionPredictionAnalyzer().save_to_database(db_session, {
        "institutions": [
            {"name": "合规机构", "rating": "bullish", "target_price": 3000},
            {"name": "乱来机构", "rating": "看多黄金", "target_price": 3100},
            {"name": "缺字段机构", "target_price": 3200},
        ]
    })

    rows = {r.institution_name: r for r in db_session.query(InstitutionView).all()}

    assert set(rows) == {"合规机构", "乱来机构", "缺字段机构"}, "整批都应当写入"
    assert rows["合规机构"].rating == "bullish"
    assert rows["乱来机构"].rating == "neutral", "认不出的评级应退回 neutral"
    assert rows["缺字段机构"].rating == "neutral"


@pytest.mark.integration
def test_saved_ratings_are_all_readable(db_session):
    """写进去的值必须能读回来（这正是枚举大小写不一致会踩的坑）。"""
    from app.models.analysis import InstitutionView
    from app.services.institution_prediction_service import InstitutionPredictionAnalyzer

    InstitutionPredictionAnalyzer().save_to_database(db_session, {
        "institutions": [
            {"name": "A", "rating": "BULLISH", "target_price": 1},
            {"name": "B", "rating": "看跌", "target_price": 2},
        ]
    })

    ratings = {r.rating for r in db_session.query(InstitutionView).all()}
    assert ratings <= set(VALID_RATINGS)
