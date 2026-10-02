# -*- coding: utf-8 -*-
"""价格口径守卫：口径名、中文标签与实时/收盘的折算（A9）。"""
import pytest

from app.services import price_basis


def test_every_known_basis_has_a_chinese_label():
    """三个口径都必须有中文标签 —— 界面只显示标签，缺了就会露出生 id。"""
    assert set(price_basis.LABELS) == {
        price_basis.REALTIME,
        price_basis.CLOSE,
        price_basis.QUANT,
    }
    for basis, label in price_basis.LABELS.items():
        assert label and label != basis


def test_unknown_basis_is_returned_as_is_instead_of_guessing():
    assert price_basis.label("made-up") == "made-up"


@pytest.mark.parametrize(
    "source,expected",
    [
        ("tencent", price_basis.REALTIME),
        ("sina", price_basis.REALTIME),
        ("eastmoney", price_basis.REALTIME),
        ("database", price_basis.CLOSE),
    ],
)
def test_realtime_quote_is_only_called_realtime_when_it_really_is(source, expected):
    """数据库兜底价必须标成日收盘：它来自 gold_prices 表，不是盘中报价。"""
    result = price_basis.realtime_basis(
        {"source": source, "source_name": "x", "price": 4000.0, "date": "2026-10-03"}
    )
    assert result["basis"] == expected
    assert result["basis_label"] == price_basis.LABELS[expected]
    assert result["as_of"] == "2026-10-03"


def test_missing_quote_yields_no_annotation_instead_of_a_fake_one():
    assert price_basis.realtime_basis(None) == {}
