"""`/dollar-realtime` 必须有缓存。

原实现**完全没有缓存**：每次调用都新建 `requests.Session()` 去上游取一次。
而前端每 10 秒轮询一次这个接口（`GoldDataContext` 里的 `setInterval`）——

    一个浏览器标签页 = 每分钟 6 次外部请求
    三个标签页       = 每分钟 18 次，而且不限速地持续下去

实时金价那条路径本来就有 30 秒缓存（`realtime_price.CACHE_TTL_SECONDS`），
美元指数这条漏了。加上之后，外部请求变成**每个实例每 30 秒一次**，
与标签页数量无关。
"""
import pytest

from app.services.cache_manager import REALTIME_PRICE_CACHE_TTL
from app.services.gold_service import GoldService

# 新浪 DINIW 的响应格式：
# 时间,最新价,买价,卖价,成交量,开盘价,最高价,最低价,昨收,名称,日期
PAYLOAD = (
    'var hq_str_DINIW="15:30:00,101.23,101.20,101.26,0,'
    "101.38,101.47,101.17,101.23,美元指数,2026-09-30\";"
)


class _FakeResponse:
    status_code = 200
    text = PAYLOAD


@pytest.fixture
def counting_session(monkeypatch):
    """替换 requests.Session，记录出网次数。"""
    import requests

    calls: list[str] = []

    class _Session:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            return _FakeResponse()

        def close(self):
            pass

    monkeypatch.setattr(requests, "Session", _Session)
    return calls


@pytest.mark.unit
def test_repeated_calls_hit_the_upstream_once(counting_session):
    """20 次调用只应出网 1 次。"""
    service = GoldService(None)

    results = [service.get_realtime_dollar_index() for _ in range(20)]

    assert len(counting_session) == 1, f"20 次调用出网 {len(counting_session)} 次"
    assert all(results), "缓存命中时也必须返回数据"


@pytest.mark.unit
def test_cached_value_is_the_parsed_quote(counting_session):
    """缓存里存的必须是解析好的结构，不是原始文本。"""
    service = GoldService(None)

    first = service.get_realtime_dollar_index()
    second = service.get_realtime_dollar_index()

    assert first["price"] == 101.23
    assert first["date"] == "2026-09-30"
    assert second == first


@pytest.mark.unit
def test_use_cache_false_bypasses_the_cache(counting_session):
    """强制刷新要真的重新取。"""
    service = GoldService(None)

    service.get_realtime_dollar_index()
    service.get_realtime_dollar_index(use_cache=False)

    assert len(counting_session) == 2


@pytest.mark.unit
def test_ttl_is_the_realtime_one_not_the_analysis_one():
    """行情缓存用 30 秒那档，不该用分析结果的 2 小时。"""
    assert REALTIME_PRICE_CACHE_TTL <= 300


@pytest.mark.unit
def test_failures_are_not_cached(counting_session, monkeypatch):
    """取不到时不要缓存失败 —— 否则上游恢复后要等 TTL 才重新尝试。"""
    import requests

    calls: list[str] = []

    class _FailingSession:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            raise requests.ConnectionError("upstream down")

        def close(self):
            pass

    monkeypatch.setattr(requests, "Session", _FailingSession)
    service = GoldService(None)

    for _ in range(3):
        assert service.get_realtime_dollar_index() is None

    assert len(calls) == 3, "失败被缓存了，上游恢复后要等 TTL 才会重试"
