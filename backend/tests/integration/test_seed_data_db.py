"""seed_data 落库路径的测试（真实 SQLite，不连 MySQL）。

`seed_data.py` 现在通过 SQLAlchemy 会话写库，SQLite 与 MySQL 共用同一套代码。
这些用例替代了旧的「假游标 + %s 占位符」断言 —— 那种断言只能证明 SQL 字符串
拼得对，证明不了数据真的写得进去、读得出来。
"""
from __future__ import annotations

from datetime import date

import pytest

import seed_data
from app.models.gold_price import DollarIndex, GoldPrice

GOLD_ROWS = [
    {"date": date(2025, 1, 2), "open_price": 2600.0, "high_price": 2610.0,
     "low_price": 2590.0, "close_price": 2605.0, "volume": 100},
    {"date": date(2025, 1, 3), "open_price": 2605.0, "high_price": 2620.0,
     "low_price": 2600.0, "close_price": 2615.0, "volume": 120},
]


@pytest.mark.integration
def test_save_gold_prices_round_trips(db_session):
    inserted = seed_data.save_gold_prices(db_session, GOLD_ROWS)

    assert inserted == 2
    rows = db_session.query(GoldPrice).order_by(GoldPrice.date).all()
    assert [r.date for r in rows] == [date(2025, 1, 2), date(2025, 1, 3)]
    assert rows[0].close_price == 2605.0
    assert rows[0].volume == 100


@pytest.mark.integration
def test_save_gold_prices_computes_change_percent(db_session):
    seed_data.save_gold_prices(db_session, GOLD_ROWS[:1])

    row = db_session.query(GoldPrice).one()
    # (2605 - 2600) / 2600 * 100
    assert row.change_percent == pytest.approx(0.19, abs=0.01)


@pytest.mark.integration
def test_save_gold_prices_skips_existing_dates(db_session, capsys):
    """重跑必须是「安静地跳过」。

    只断言 inserted == 0 是不够的：唯一约束同样会拦下重复行，把「预检查跳过」
    换成「靠约束报错」后测试依然会绿。这里同时要求输出里没有逐行警告 ——
    真实场景是重跑一次 seed，不能刷屏几百条失败日志。
    """
    seed_data.save_gold_prices(db_session, GOLD_ROWS)
    capsys.readouterr()  # 清掉第一遍的输出

    inserted = seed_data.save_gold_prices(db_session, GOLD_ROWS)
    out = capsys.readouterr().out

    assert inserted == 0, "已存在的日期应当跳过"
    assert "跳过 2 条" in out
    assert "警告" not in out, "已存在的日期应当走预检查，而不是靠唯一约束报错"
    assert db_session.query(GoldPrice).count() == 2


@pytest.mark.integration
def test_save_gold_prices_survives_a_bad_row(db_session):
    """单行缺字段不能让整批都写不进去。"""
    bad = [{"date": date(2025, 1, 2)}, GOLD_ROWS[1]]

    inserted = seed_data.save_gold_prices(db_session, bad)

    assert inserted == 1
    assert [r.date for r in db_session.query(GoldPrice).all()] == [date(2025, 1, 3)]


@pytest.mark.integration
def test_save_dollar_index_round_trips_and_skips_duplicates(db_session):
    rows = [{"date": date(2025, 1, 2), "open_price": 108.0, "high_price": 108.5,
             "low_price": 107.5, "close_price": 108.2}]

    assert seed_data.save_dollar_index(db_session, rows) == 1
    assert seed_data.save_dollar_index(db_session, rows) == 0

    row = db_session.query(DollarIndex).one()
    assert row.close_price == 108.2
