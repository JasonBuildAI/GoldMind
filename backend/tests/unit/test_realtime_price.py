"""统一实时金价入口的测试。

合并前有两套实现（gold_service 走腾讯、gold_price_service 走新浪+东财），
各自带一份缓存。腾讯那条路把 open/high/low 的索引取错了，东财用的代码已失效，
而两边的降级互不可见 —— 腾讯挂了 /stats 就只能退回数据库旧数据。

这些测试用真实响应结构做夹具，不访问网络。
"""
from __future__ import annotations

import pytest

from app.services import realtime_price


class _FakeResponse:
    def __init__(self, *, text: str = "", payload=None, status_code: int = 200) -> None:
        self.text = text
        self._payload = payload
        self.status_code = status_code
        self.encoding = None

    def json(self):
        return self._payload


# 真实抓取的样本（腾讯与新浪的 hf_ 字段布局完全一致）
TENCENT_BODY = (
    'v_hf_GC="4229.70,1.20,4229.30,4229.60,4233.20,4197.60,15:38:05,'
    '4179.70,4216.20,0,2,2,2026-09-30,纽约黄金";'
)
SINA_BODY = (
    'var hq_str_hf_GC="4229.244,,4228.600,4228.900,4233.200,4197.600,15:38:20,'
    '4179.700,4216.200,0,3,2,2026-09-30,纽约黄金,0";'
)
EASTMONEY_PAYLOAD = {
    "data": {
        "f43": 419803,   # 最新价，放大 100 倍
        "f44": 420135,   # 最高
        "f45": 416580,   # 最低
        "f46": 418410,   # 开盘
        "f57": "XAU",
        "f58": "黄金/美元",
        "f60": 418245,   # 昨收
    }
}


def _patch(monkeypatch, *, tencent=..., sina=..., eastmoney=...):
    """按 URL 分发响应；传 None 表示该源抛异常（模拟不可用）。"""
    import requests

    def fake_get(url, **kwargs):
        if "gtimg" in url:
            source = tencent
        elif "sinajs" in url:
            source = sina
        elif "eastmoney" in url:
            source = eastmoney
        else:
            raise AssertionError(f"未预期的 URL: {url}")

        if source is ... or source is None:
            raise requests.ConnectionError("source unavailable")
        return source

    monkeypatch.setattr(realtime_price.requests, "get", fake_get)


# --------------------------------------------------------------------------- #
# 各数据源
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_tencent_uses_the_correct_field_positions(monkeypatch):
    """回归：原实现把 open/high/low 读成 [2]/[3]/[4]，真实位置是 [8]/[4]/[5]。

    [2]/[3] 是买价/卖价一类的报价，拿它们当开盘与最高价会得到错值，
    而且会算出「最高价低于最低价」。
    """
    _patch(monkeypatch, tencent=_FakeResponse(text=TENCENT_BODY))

    row = realtime_price.fetch_from_tencent()

    assert row["price"] == 4229.70
    assert row["open"] == 4216.20, "[8] 才是开盘价，不是 [2]"
    assert row["high"] == 4233.20, "[4] 才是最高价，不是 [3]"
    assert row["low"] == 4197.60, "[5] 才是最低价，不是 [4]"
    assert row["previous_close"] == 4179.70
    assert row["date"] == "2026-09-30"
    assert row["source"] == "tencent"


@pytest.mark.unit
def test_sina_parses_the_same_layout(monkeypatch):
    _patch(monkeypatch, sina=_FakeResponse(text=SINA_BODY))

    row = realtime_price.fetch_from_sina()

    assert row["price"] == 4229.24
    assert row["open"] == 4216.20
    assert row["high"] == 4233.20
    assert row["low"] == 4197.60
    assert row["source"] == "sina"


@pytest.mark.unit
def test_eastmoney_uses_122_xau_and_scales_by_100(monkeypatch):
    """回归：原实现用 103.XAUUSD，该代码返回 data=null。"""
    _patch(monkeypatch, eastmoney=_FakeResponse(payload=EASTMONEY_PAYLOAD))

    row = realtime_price.fetch_from_eastmoney()

    assert row["price"] == 4198.03
    assert row["high"] == 4201.35
    assert row["low"] == 4165.80
    assert row["open"] == 4184.10
    assert row["previous_close"] == 4182.45
    assert row["source"] == "eastmoney"


@pytest.mark.unit
@pytest.mark.parametrize("source", ["tencent", "sina", "eastmoney"])
def test_every_source_returns_a_self_consistent_row(monkeypatch, source):
    """每个源的高/低都必须包住开盘与收盘，否则就是把字段读错了。"""
    responses = {
        "tencent": dict(tencent=_FakeResponse(text=TENCENT_BODY)),
        "sina": dict(sina=_FakeResponse(text=SINA_BODY)),
        "eastmoney": dict(eastmoney=_FakeResponse(payload=EASTMONEY_PAYLOAD)),
    }
    _patch(monkeypatch, **responses[source])

    row = realtime_price._FETCHERS[source]()

    assert row["high"] >= max(row["open"], row["price"]), f"{source}: 最高价不合理"
    assert row["low"] <= min(row["open"], row["price"]), f"{source}: 最低价不合理"
    assert row["change"] == pytest.approx(row["price"] - row["previous_close"], abs=0.02)


@pytest.mark.unit
def test_eastmoney_null_data_is_not_a_crash(monkeypatch):
    _patch(monkeypatch, eastmoney=_FakeResponse(payload={"rc": 100, "data": None}))

    assert realtime_price.fetch_from_eastmoney() is None


@pytest.mark.unit
def test_malformed_hq_payload_is_rejected(monkeypatch):
    _patch(monkeypatch, tencent=_FakeResponse(text='v_hf_GC="1,2,3";'))

    assert realtime_price.fetch_from_tencent() is None


# --------------------------------------------------------------------------- #
# 多源编排
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_prefers_tencent_when_it_works(monkeypatch):
    _patch(
        monkeypatch,
        tencent=_FakeResponse(text=TENCENT_BODY),
        sina=_FakeResponse(text=SINA_BODY),
    )

    row = realtime_price.get_realtime_gold_price(use_cache=False)

    assert row["source"] == "tencent"


@pytest.mark.unit
def test_falls_back_to_sina_when_tencent_fails(monkeypatch):
    """回归：原先腾讯一挂就直接退回数据库，而新浪当时是可用的。"""
    _patch(monkeypatch, tencent=None, sina=_FakeResponse(text=SINA_BODY))

    row = realtime_price.get_realtime_gold_price(use_cache=False)

    assert row["source"] == "sina"


@pytest.mark.unit
def test_falls_back_to_eastmoney_when_the_first_two_fail(monkeypatch):
    _patch(monkeypatch, tencent=None, sina=None,
           eastmoney=_FakeResponse(payload=EASTMONEY_PAYLOAD))

    row = realtime_price.get_realtime_gold_price(use_cache=False)

    assert row["source"] == "eastmoney"


@pytest.mark.unit
def test_returns_none_when_every_source_fails(monkeypatch):
    _patch(monkeypatch, tencent=None, sina=None, eastmoney=None)

    assert realtime_price.get_realtime_gold_price(use_cache=False) is None


# --------------------------------------------------------------------------- #
# 缓存
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_second_call_is_served_from_cache(monkeypatch):
    calls: list[str] = []
    import requests

    def counting_get(url, **kwargs):
        calls.append(url)
        return _FakeResponse(text=TENCENT_BODY)

    monkeypatch.setattr(realtime_price.requests, "get", counting_get)

    first = realtime_price.get_realtime_gold_price()
    second = realtime_price.get_realtime_gold_price()

    assert first["price"] == second["price"]
    assert len(calls) == 1, "第二次应当命中缓存，不再打上游"


@pytest.mark.unit
def test_use_cache_false_bypasses_the_cache(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        realtime_price.requests,
        "get",
        lambda url, **kw: (calls.append(url), _FakeResponse(text=TENCENT_BODY))[1],
    )

    realtime_price.get_realtime_gold_price()
    realtime_price.get_realtime_gold_price(use_cache=False)

    assert len(calls) == 2
