"""seed_data 数据源解析的测试。

这些数据源**曾经全部失效**，而且没有任何测试覆盖，所以问题长期无人发现：
  - 新浪：请求缺少服务名（服务端回 "Invalid service name"），
    且解析用的是数组下标，与真实的「对象数组」格式不符
  - 东方财富：黄金用了无效代码 113.AU0；并且把 klines 的
    high/low 两个字段读反了（最高价 < 最低价）
  - 美元指数的新浪接口对 DINIW 返回 null

这里用真实响应结构做夹具，不访问网络，把上述格式与字段顺序钉住。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

import seed_data


class _FakeResponse:
    def __init__(self, *, text: str = "", payload=None, status_code: int = 200) -> None:
        self.text = text
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _patch_get(monkeypatch: pytest.MonkeyPatch, response: _FakeResponse) -> None:
    monkeypatch.setattr(seed_data.requests, "get", lambda *a, **k: response)


# --------------------------------------------------------------------------- #
# 新浪：外盘期货 JSONP
# --------------------------------------------------------------------------- #
def _sina_gold_body(rows: list[dict]) -> str:
    """复刻真实响应：数组外还套了一层括号。"""
    return f"/*<script>location.href='//sina.com';</script>*/ var _GC=({json.dumps(rows)});"


SINA_ROWS = [
    {"date": "2024-12-31", "open": "2600.0", "high": "2620.0", "low": "2590.0",
     "close": "2610.0", "volume": "0"},
    {"date": "2025-01-02", "open": "2641.0", "high": "2674.2", "low": "2636.1",
     "close": "2671.2", "volume": "138480"},
]


@pytest.mark.unit
def test_sina_gold_parses_object_array(monkeypatch):
    _patch_get(monkeypatch, _FakeResponse(text=_sina_gold_body(SINA_ROWS)))

    result = seed_data.fetch_gold_from_sina()

    assert result is not None
    # 早于 START_DATE 的行会被过滤
    assert [r["date"] for r in result] == [date(2025, 1, 2)]
    row = result[0]
    assert row["open_price"] == 2641.0
    assert row["high_price"] == 2674.2
    assert row["low_price"] == 2636.1
    assert row["close_price"] == 2671.2
    assert row["volume"] == 138480


@pytest.mark.unit
def test_sina_gold_keeps_high_above_low(monkeypatch):
    _patch_get(monkeypatch, _FakeResponse(text=_sina_gold_body(SINA_ROWS)))

    row = seed_data.fetch_gold_from_sina()[0]

    assert row["high_price"] > row["low_price"]
    assert row["high_price"] >= max(row["open_price"], row["close_price"])
    assert row["low_price"] <= min(row["open_price"], row["close_price"])


@pytest.mark.unit
def test_sina_gold_requires_the_wrapping_parentheses(monkeypatch):
    """响应格式是 `var _GC=([...])`，少一层括号就应当解析失败并返回 None。"""
    body = 'var _GC=[{"date": "2025-01-02", "open": "1", "high": "2", "low": "0", "close": "1"}]'
    _patch_get(monkeypatch, _FakeResponse(text=body))

    assert seed_data.fetch_gold_from_sina() is None


@pytest.mark.unit
def test_sina_gold_returns_none_on_http_error(monkeypatch):
    _patch_get(monkeypatch, _FakeResponse(status_code=500))

    assert seed_data.fetch_gold_from_sina() is None


# --------------------------------------------------------------------------- #
# 实际发出的请求
# --------------------------------------------------------------------------- #
# 上面那些用例只 mock 了响应，不校验 URL 与参数。后果是：把 URL 或 secid 改成
# 失效值，测试照样全绿。下面这些补上 —— 这几个值恰恰就是当初出错的地方。
@pytest.mark.unit
def test_sina_gold_requests_the_service_path(monkeypatch):
    """回归：原实现漏了服务名，服务端直接回 "Invalid service name"。"""
    seen: dict = {}

    def capture_get(url, **kwargs):
        seen["url"] = url
        seen["params"] = kwargs.get("params")
        return _FakeResponse(text=_sina_gold_body(SINA_ROWS))

    monkeypatch.setattr(seed_data.requests, "get", capture_get)

    seed_data.fetch_gold_from_sina()

    assert "GlobalFuturesService.getGlobalFuturesDailyKLine" in seen["url"], (
        "服务名必须在路径里，不能只传 query 参数"
    )
    assert "var%20_GC=" in seen["url"], "JSONP 变量名必须在路径里"
    assert seen["params"] == {"symbol": "GC"}


@pytest.mark.unit
def test_eastmoney_gold_requests_the_working_secid(monkeypatch):
    """回归：原实现用 113.AU0，服务端返回 data=null。"""
    seen: dict = {}

    def capture_get(url, **kwargs):
        seen.update(kwargs.get("params") or {})
        return _FakeResponse(payload=_eastmoney_payload(EM_KLINES))

    monkeypatch.setattr(seed_data.requests, "get", capture_get)

    seed_data.fetch_gold_from_eastmoney()

    assert seen["secid"] == "101.GC00Y"


@pytest.mark.unit
def test_eastmoney_dollar_requests_the_working_secid(monkeypatch):
    """回归：原实现用 100.DINIW，服务端返回 data=null。"""
    seen: dict = {}

    def capture_get(url, **kwargs):
        seen.update(kwargs.get("params") or {})
        return _FakeResponse(
            payload=_eastmoney_payload(["2025-01-01,108.48,108.45,108.49,108.42,0,0.00"])
        )

    monkeypatch.setattr(seed_data.requests, "get", capture_get)

    seed_data.fetch_dollar_from_eastmoney()

    assert seen["secid"] == "100.UDI"


# --------------------------------------------------------------------------- #
# 东方财富：klines 字段顺序
# --------------------------------------------------------------------------- #
def _eastmoney_payload(klines: list[str]) -> dict:
    return {"rc": 0, "data": {"code": "GC00Y", "name": "COMEX黄金", "klines": klines}}


# 真实格式：date,open,close,HIGH,LOW,volume,amount
EM_KLINES = [
    "2025-01-02,2641.0,2671.2,2674.2,2636.1,138480,0.0",
    "2025-01-03,2671.1,2652.7,2681.0,2649.7,115489,0.0",
]


@pytest.mark.unit
def test_eastmoney_gold_maps_high_before_low(monkeypatch):
    """回归：原实现把 parts[3] 当 low、parts[4] 当 high，两个字段写反了。"""
    _patch_get(monkeypatch, _FakeResponse(payload=_eastmoney_payload(EM_KLINES)))

    result = seed_data.fetch_gold_from_eastmoney()

    assert result is not None
    row = result[0]
    assert row["open_price"] == 2641.0
    assert row["close_price"] == 2671.2
    assert row["high_price"] == 2674.2, "parts[3] 是最高价"
    assert row["low_price"] == 2636.1, "parts[4] 是最低价"
    assert row["volume"] == 138480


@pytest.mark.unit
def test_eastmoney_rows_are_self_consistent(monkeypatch):
    """每一行的最高/最低都必须包住开盘与收盘 —— 读反了就必然违反。"""
    _patch_get(monkeypatch, _FakeResponse(payload=_eastmoney_payload(EM_KLINES)))

    for row in seed_data.fetch_gold_from_eastmoney():
        assert row["high_price"] >= max(row["open_price"], row["close_price"])
        assert row["low_price"] <= min(row["open_price"], row["close_price"])


@pytest.mark.unit
def test_eastmoney_gold_returns_none_when_data_is_null(monkeypatch):
    """无效 secid 的响应就是 data=null，必须优雅失败而不是抛异常。"""
    _patch_get(monkeypatch, _FakeResponse(payload={"rc": 100, "data": None}))

    assert seed_data.fetch_gold_from_eastmoney() is None


@pytest.mark.unit
def test_eastmoney_dollar_maps_high_before_low(monkeypatch):
    klines = ["2025-01-01,108.48,108.45,108.49,108.42,0,0.00"]
    _patch_get(monkeypatch, _FakeResponse(payload=_eastmoney_payload(klines)))

    row = seed_data.fetch_dollar_from_eastmoney()[0]

    assert row["open_price"] == 108.48
    assert row["close_price"] == 108.45
    assert row["high_price"] == 108.49
    assert row["low_price"] == 108.42


@pytest.mark.unit
def test_eastmoney_skips_rows_before_start_date(monkeypatch):
    klines = [
        "2024-12-31,2600.0,2610.0,2620.0,2590.0,1000,0.0",
        "2025-01-02,2641.0,2671.2,2674.2,2636.1,138480,0.0",
    ]
    _patch_get(monkeypatch, _FakeResponse(payload=_eastmoney_payload(klines)))

    result = seed_data.fetch_gold_from_eastmoney()

    assert [r["date"] for r in result] == [date(2025, 1, 2)]


# --------------------------------------------------------------------------- #
# 编排
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_gold_history_falls_back_to_the_next_source(monkeypatch):
    """第一个源失败时必须继续尝试下一个，而不是直接放弃。"""
    monkeypatch.setattr(seed_data, "fetch_gold_from_sina", lambda: None)
    monkeypatch.setattr(
        seed_data,
        "fetch_gold_from_eastmoney",
        lambda: [{"date": date(2025, 1, 2), "open_price": 1.0, "high_price": 2.0,
                  "low_price": 0.5, "close_price": 1.5, "volume": 0}],
    )

    result = seed_data.fetch_gold_history()

    assert len(result) == 1


@pytest.mark.unit
def test_gold_history_raises_when_every_source_fails(monkeypatch):
    """全部失败时必须显式报错，不能返回空列表让调用方以为成功了。"""
    monkeypatch.setattr(seed_data, "fetch_gold_from_sina", lambda: None)
    monkeypatch.setattr(seed_data, "fetch_gold_from_eastmoney", lambda: None)
    monkeypatch.setattr(seed_data, "fetch_gold_from_yahoo", lambda: None)

    with pytest.raises(seed_data.DataSourceError):
        seed_data.fetch_gold_history()


@pytest.mark.unit
def test_dollar_history_no_longer_uses_the_dead_sina_source():
    """新浪那条路已移除：它对该符号固定返回 null。"""
    assert not hasattr(seed_data, "fetch_dollar_from_sina")


# --------------------------------------------------------------------------- #
# 落库（初始化路径的最后一步）
# --------------------------------------------------------------------------- #
class _FakeCursor:
    """记录执行过的 SQL；SELECT 按给定的已存在日期返回命中。"""

    def __init__(self, existing_dates: set | None = None) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self._existing = existing_dates or set()
        self._last_select: object = None

    def execute(self, sql: str, params=None) -> None:
        self.executed.append((sql, params))
        if sql.strip().upper().startswith("SELECT"):
            self._last_select = params[0] if params else None

    def fetchone(self):
        return (1,) if self._last_select in self._existing else None

    def close(self) -> None:
        pass

    @property
    def inserts(self) -> list[tuple[str, tuple]]:
        return [(s, p) for s, p in self.executed if s.strip().upper().startswith("INSERT")]


class _FakeConn:
    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.commits = 0

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def commit(self) -> None:
        self.commits += 1


GOLD_ROWS = [
    {"date": date(2025, 1, 2), "open_price": 2600.0, "high_price": 2610.0,
     "low_price": 2590.0, "close_price": 2605.0, "volume": 100},
    {"date": date(2025, 1, 3), "open_price": 2605.0, "high_price": 2620.0,
     "low_price": 2600.0, "close_price": 2615.0, "volume": 120},
]


@pytest.mark.unit
def test_save_gold_prices_columns_match_placeholders():
    """列数与占位符数量必须一致，否则 MySQL 会直接报错。"""
    cursor = _FakeCursor()
    seed_data.save_gold_prices(_FakeConn(cursor), GOLD_ROWS)

    assert len(cursor.inserts) == 2
    for sql, params in cursor.inserts:
        columns = sql.split("(", 1)[1].split(")", 1)[0]
        column_count = len([c for c in columns.split(",") if c.strip()])
        values_clause = sql.split("VALUES", 1)[1]
        placeholder_count = values_clause.count("%s")
        assert column_count == placeholder_count == len(params), (
            f"列 {column_count} 个、占位符 {placeholder_count} 个、参数 {len(params)} 个"
        )


@pytest.mark.unit
def test_save_gold_prices_computes_change_percent():
    cursor = _FakeCursor()
    seed_data.save_gold_prices(_FakeConn(cursor), GOLD_ROWS[:1])

    _, params = cursor.inserts[0]
    # (2605 - 2600) / 2600 * 100
    assert params[-1] == pytest.approx(0.19, abs=0.01)


@pytest.mark.unit
def test_save_gold_prices_skips_existing_dates():
    cursor = _FakeCursor(existing_dates={date(2025, 1, 2)})
    conn = _FakeConn(cursor)

    inserted = seed_data.save_gold_prices(conn, GOLD_ROWS)

    assert inserted == 1, "已存在的日期应当跳过"
    assert len(cursor.inserts) == 1
    assert conn.commits == 1


@pytest.mark.unit
def test_save_gold_prices_survives_a_bad_row():
    """单行失败不能中断整批。"""
    cursor = _FakeCursor()
    bad = [{"date": date(2025, 1, 2)}, GOLD_ROWS[1]]  # 第一行缺字段

    inserted = seed_data.save_gold_prices(_FakeConn(cursor), bad)

    assert inserted == 1


@pytest.mark.unit
def test_save_dollar_index_columns_match_placeholders():
    cursor = _FakeCursor()
    rows = [
        {"date": date(2025, 1, 2), "open_price": 108.0, "high_price": 108.5,
         "low_price": 107.5, "close_price": 108.2}
    ]

    seed_data.save_dollar_index(_FakeConn(cursor), rows)

    assert len(cursor.inserts) == 1
    sql, params = cursor.inserts[0]
    columns = sql.split("(", 1)[1].split(")", 1)[0]
    column_count = len([c for c in columns.split(",") if c.strip()])
    assert column_count == sql.split("VALUES", 1)[1].count("%s") == len(params) == 5
