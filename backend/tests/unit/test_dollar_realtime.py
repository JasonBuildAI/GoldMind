"""实时美元指数解析的测试。

变异测试发现的缺口：`test_scheduler_jobs.py` 里的用例把
`GoldService.get_realtime_dollar_index` 整个替换掉了，所以它验证的是「任务会
使用解析器给出的 OHLC」，而**没有任何测试验证解析器真的解析出了 OHLC**。
把解析器里的 `_field(5)` 改回 `prev_close`，整套测试依然全绿。

这里用真实响应结构补上这一段。
"""
from __future__ import annotations

import pytest

from app.services import gold_service

# 真实抓取的新浪响应：0时间 1最新 2买 3卖 4量 5开 6高 7低 8昨收 9名称 10日期
DINIW_BODY = (
    'var hq_str_DINIW="15:56:00,101.2993,101.2993,101.3820,2700,'
    '101.3838,101.4673,101.1973,101.2993,美元指数,2026-09-30";'
)


class _FakeResponse:
    def __init__(self, *, text: str = "", status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class _FakeSession:
    def __init__(self, response: _FakeResponse) -> None:
        self._response = response
        self.closed = False
        self.requested_url: str | None = None

    def get(self, url, **kwargs):
        self.requested_url = url
        return self._response

    def close(self) -> None:
        self.closed = True


def _patch(monkeypatch, response: _FakeResponse) -> _FakeSession:
    session = _FakeSession(response)
    monkeypatch.setattr(gold_service.requests, "Session", lambda: session)
    return session


@pytest.mark.unit
def test_dollar_parser_returns_the_real_ohlc(monkeypatch, db_session):
    """回归：原实现只取 [1] 最新价与 [8] 昨收，把真实开高低丢掉了。

    丢掉之后，定时任务只能用「昨收当开盘、max/min 当高低」硬凑，
    把编出来的数据写进数据库。
    """
    _patch(monkeypatch, _FakeResponse(text=DINIW_BODY))

    result = gold_service.GoldService(db_session).get_realtime_dollar_index()

    assert result is not None
    assert result["price"] == 101.30
    assert result["previous_close"] == 101.30
    assert result["open"] == 101.38, "[5] 是开盘价"
    assert result["high"] == 101.47, "[6] 是最高价"
    assert result["low"] == 101.20, "[7] 是最低价"
    assert result["date"] == "2026-09-30"


@pytest.mark.unit
def test_dollar_parser_ohlc_is_self_consistent(monkeypatch, db_session):
    """最高/最低必须包住开盘与最新价 —— 取错字段就必然违反。"""
    _patch(monkeypatch, _FakeResponse(text=DINIW_BODY))

    result = gold_service.GoldService(db_session).get_realtime_dollar_index()

    assert result["high"] >= max(result["open"], result["price"])
    assert result["low"] <= min(result["open"], result["price"])


@pytest.mark.unit
def test_dollar_parser_requests_the_diniw_endpoint(monkeypatch, db_session):
    session = _patch(monkeypatch, _FakeResponse(text=DINIW_BODY))

    gold_service.GoldService(db_session).get_realtime_dollar_index()

    assert session.requested_url == "https://hq.sinajs.cn/list=DINIW"
    assert session.closed, "用完必须关闭 session"


@pytest.mark.unit
def test_dollar_parser_handles_an_empty_payload(monkeypatch, db_session):
    """接口偶尔会回空串，不能崩。"""
    _patch(monkeypatch, _FakeResponse(text='var hq_str_DINIW="";'))

    assert gold_service.GoldService(db_session).get_realtime_dollar_index() is None


@pytest.mark.unit
def test_dollar_parser_handles_http_error(monkeypatch, db_session):
    _patch(monkeypatch, _FakeResponse(status_code=500))

    assert gold_service.GoldService(db_session).get_realtime_dollar_index() is None


@pytest.mark.unit
def test_dollar_parser_rejects_a_zero_price(monkeypatch, db_session):
    """价格解析不出来时应当返回 None，而不是把 0 当成有效价格写库。"""
    body = 'var hq_str_DINIW="15:56:00,0,0,0,0,0,0,0,0,美元指数,2026-09-30";'
    _patch(monkeypatch, _FakeResponse(text=body))

    assert gold_service.GoldService(db_session).get_realtime_dollar_index() is None
