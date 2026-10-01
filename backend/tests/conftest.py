"""pytest 全局夹具与测试环境准备。

四条铁律：

1. **在导入 app 之前**把 `DATABASE_URL` 指向内存 SQLite —— 测试绝不依赖 MySQL。
2. **关闭调度器** —— 测试期间不得触发后台 LLM 任务。
3. **清理代理环境变量** —— 本机若设置了 SOCKS 代理，或 `NO_PROXY` 里含 `[::1]`
   （httpx 无法解析该写法），构造 httpx 客户端时会直接抛异常，与业务代码无关。
4. **测试永不发起真实外部请求** —— LLM 与出网调用全部被替换。
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# --------------------------------------------------------------------------- #
# 必须在导入任何 app.* 之前执行
# --------------------------------------------------------------------------- #
for _var in (
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
    "HTTPS_PROXY",
    "https_proxy",
    "NO_PROXY",
    "no_proxy",
):
    os.environ.pop(_var, None)

# 默认用内存 SQLite：快、隔离、不依赖外部服务。
#
# 但生产用的是 MySQL，而两者在**枚举存储、JSON 列、字符串比较大小写、
# 事务与约束行为**上都有差异 —— 「SQLite 全绿」不等于「MySQL 全绿」。
# 所以留一个开关，可以拿同一套用例去跑另一个方言：
#
#   GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" \
#       python -m pytest
#
# 注意必须指向**独立的测试库**：用例会清空所有表。
os.environ["DATABASE_URL"] = os.environ.get("GOLDMIND_TEST_DATABASE_URL", "sqlite://")
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ.setdefault("LLM_API_KEY", "test-key-not-real")
os.environ.setdefault("LLM_BASE_URL", "https://example.invalid/v1")
os.environ.setdefault("LLM_MODEL", "test-model")
os.environ.setdefault("LLM_PROVIDER", "test")
# LLM_SEARCH_ENABLED 故意不设置：默认关闭，测试不得访问真实外部服务。

import pytest  # noqa: E402


# --------------------------------------------------------------------------- #
# 假 LLM：测试永不调用真实 API
# --------------------------------------------------------------------------- #
class FakeMessage:
    """模拟 langchain 的 AIMessage —— 业务代码只用到 `.content`。"""

    def __init__(self, content: str) -> None:
        self.content = content


class FakeLLM:
    """记录收到的 prompt，并按顺序返回预设响应。"""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses: list[str] = list(responses or [])
        self.calls: list[str] = []
        self.last_kwargs: dict[str, Any] = {}

    def invoke(self, prompt: str) -> FakeMessage:
        self.calls.append(prompt)
        content = self.responses.pop(0) if self.responses else "{}"
        return FakeMessage(content)


class _FakeChatOpenAIFactory:
    """替代 `langchain_openai.ChatOpenAI`：吞掉构造参数，返回共享的 FakeLLM。"""

    def __init__(self, llm: FakeLLM) -> None:
        self._llm = llm

    def __call__(self, **kwargs: Any) -> FakeLLM:
        self._llm.last_kwargs = kwargs
        return self._llm


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> FakeLLM:
    """替换 llm_provider 的底层客户端类。

    只 patch 工厂内部的 `_chat_openai_class` 一个点，因此所有经由
    `get_chat_llm()` 取实例的服务都会自动拿到假实现。
    """
    llm = FakeLLM()
    monkeypatch.setattr(
        "app.services.llm_provider._chat_openai_class",
        lambda: _FakeChatOpenAIFactory(llm),
    )
    return llm


# --------------------------------------------------------------------------- #
# 出网兜底
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _block_outbound_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """兜底：任何**对外**连接直接失败；本机地址放行。

    只 patch `socket.create_connection` 与 urllib3 是**不够的**：
    异步 httpx 走 anyio → `loop.create_connection` → `sock.connect()`，
    不经过它，测试会**真的打到外网**。

    拦截点选 `socket.getaddrinfo`：任何按域名发起的连接都要先解析，覆盖同步
    与异步两条路径，又不像 patch `socket.socket.connect` 那样弄坏 asyncio 在
    Windows 上的 Proactor 事件循环（实测：patch `connect` 后 asyncio 会报
    `'ProactorEventLoop' object has no attribute '_ssock'`）。

    2026-10-02 的实测发现还有两个漏洞，于是补成四层：

    1. **代理**。本机配置着 `HTTP_PROXY=127.0.0.1:7897` 这类代理；httpx 与
       requests 的 `trust_env` 会连这个**本机**代理，而代理会替你把请求转发
       出去 —— 回环地址在「放行本机」规则里，DNS 与连接层一次都不触发，
       实测异步 httpx 拿到过真实 HTTP 200。所以先整体清掉代理：环境变量、
       `urllib.request.getproxies`、以及所有已加载模块里按值导入的那份副本
       （`from urllib.request import getproxies` 是按值导入，只改源模块拦不住）。
    2. **IP 字面量**。任何直接用 IP 的连接都不经过解析，`getaddrinfo` 拦不住。
    3. **客户端层**。httpx / openai SDK 都经由 `httpcore`：拦它的连接类与
       连接池的 `handle_request` / `handle_async_request`（异步是 `async def`，
       必须用协程包装），域名与 IP 字面量、同步与异步一起覆盖，且不碰 socket。
    4. **urllib3 的签名**与 `socket.create_connection` 不同（多出
       `socket_options` 等参数）—— 包装 urllib3 时必须调用 urllib3 自己的原
       函数，否则连本机请求都会 TypeError。

    本机（回环）地址一律放行 —— 测试要连本机服务。
    """
    import inspect
    import socket
    import sys

    _ALLOWED_HOSTS = {"127.0.0.1", "::1", "localhost", "", None}

    def _blocked(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            "测试禁止真实网络访问：请 mock 掉发起该请求的服务方法"
        )

    def _normalized(host: Any) -> Any:
        # host 可能是 bytes（异步客户端就这么传，实测是 b'example.com'）——
        # 不归一化的话，本机白名单会因为类型不同而失效。
        if isinstance(host, bytes):
            try:
                return host.decode("ascii")
            except UnicodeDecodeError:
                return host
        return host

    def _is_allowed(host: Any) -> bool:
        return _normalized(host) in _ALLOWED_HOSTS

    def _host_of(address: Any) -> Any:
        return address[0] if isinstance(address, tuple) and address else address

    # 0) 代理：环境变量 + 注册表兜底一起清掉。已导入模块里的副本也要换 ——
    #    `from urllib.request import getproxies` 会在模块命名空间里留一份旧引用。
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(key, raising=False)

    def _no_proxies(*args: Any, **kwargs: Any) -> dict:
        return {}

    import urllib.request

    monkeypatch.setattr(urllib.request, "getproxies", _no_proxies)

    for module in list(sys.modules.values()):
        name = getattr(module, "__name__", "")
        if name.split(".")[0] not in {"requests", "httpx", "urllib3", "openai"}:
            continue
        if hasattr(module, "getproxies"):
            monkeypatch.setattr(module, "getproxies", _no_proxies, raising=False)

    # 1) DNS：解析非本机域名即视为出网
    _real_getaddrinfo = socket.getaddrinfo

    def _guarded_getaddrinfo(host: Any, *args: Any, **kwargs: Any) -> Any:
        if not _is_allowed(host):
            _blocked()
        return _real_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", _guarded_getaddrinfo)

    # 2) socket 层的高层入口：给出更直白的报错，并挡住直接给 IP 的调用。
    _real_create_connection = socket.create_connection

    def _guarded_create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        if not _is_allowed(_host_of(address)):
            _blocked()
        return _real_create_connection(address, *args, **kwargs)

    monkeypatch.setattr(socket, "create_connection", _guarded_create_connection)

    try:
        import urllib3.util.connection as urllib3_connection
    except ImportError:  # urllib3 不在时无需处理
        pass
    else:
        _real_urllib3_create_connection = urllib3_connection.create_connection

        def _guarded_urllib3_create_connection(
            address: Any, *args: Any, **kwargs: Any
        ) -> Any:
            if not _is_allowed(_host_of(address)):
                _blocked()
            return _real_urllib3_create_connection(address, *args, **kwargs)

        monkeypatch.setattr(
            urllib3_connection, "create_connection", _guarded_urllib3_create_connection
        )

    # 3) 客户端层：httpx / openai SDK 都经 httpcore。同步方法叫 handle_request，
    #    异步方法叫 handle_async_request 且是 async def。连接类与连接池类都拦
    #    （池负责代理路径，连接类负责真正的建连），带上标记属性便于测试核验。
    try:
        import httpcore
    except ImportError:  # httpx 不在时无需处理
        return

    def _guard_request(request: Any) -> None:
        url = getattr(request, "url", None)
        if not _is_allowed(getattr(url, "host", None)):
            _blocked()

    def _guard_sync(original: Any) -> Any:
        def guarded(self: Any, request: Any) -> Any:
            _guard_request(request)
            return original(self, request)

        guarded.__goldmind_outbound_guard__ = True
        return guarded

    def _guard_async(original: Any) -> Any:
        async def guarded(self: Any, request: Any) -> Any:
            _guard_request(request)
            return await original(self, request)

        guarded.__goldmind_outbound_guard__ = True
        return guarded

    for attr_name in dir(httpcore):
        connection_class = getattr(httpcore, attr_name)
        if not inspect.isclass(connection_class):
            continue
        for method_name in ("handle_request", "handle_async_request"):
            original = vars(connection_class).get(method_name)
            if original is None:
                continue
            if getattr(original, "__goldmind_outbound_guard__", False):
                continue  # 已经包过就不再包（同一个类可能以多个别名出现）
            guard = _guard_async if inspect.iscoroutinefunction(original) else _guard_sync
            monkeypatch.setattr(connection_class, method_name, guard(original))

# --------------------------------------------------------------------------- #
# 数据库
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="session", autouse=True)
def _prepare_database():
    """建表（此时 engine 已指向内存 SQLite）。"""
    import app.models  # noqa: F401  确保所有模型注册到 metadata
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables(_prepare_database):
    """每个用例前清空所有表，保证用例之间互不影响。"""
    from app.database import Base, engine

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(table.delete())
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limiters(monkeypatch: pytest.MonkeyPatch) -> None:
    """每个用例都换一套全新的限流器。

    限流器是模块级单例。若不重置，用例之间会共享计数：整套测试累计的请求数
    足以让靠后的用例意外收到 429，限流相关的断言也会不可靠。
    """
    import app.main as main
    from app.utils.rate_limit import SlidingWindowRateLimiter

    monkeypatch.setattr(
        main,
        "_general_limiter",
        SlidingWindowRateLimiter(main.settings.RATE_LIMIT_PER_MINUTE),
    )
    monkeypatch.setattr(
        main,
        "_ai_limiter",
        SlidingWindowRateLimiter(main.settings.RATE_LIMIT_AI_PER_MINUTE),
    )


@pytest.fixture(autouse=True)
def _disable_background_analysis(request, monkeypatch: pytest.MonkeyPatch) -> None:
    """禁止各分析服务在测试中触发后台线程分析。

    这些线程会新建数据库会话、发起真实 LLM 调用，而且可能活过用例本身
    （表现为「no such table」之类来自已销毁引擎的噪声）。测试必须同步、确定。

    需要验证真实触发逻辑的用例可以打 `@pytest.mark.real_background` 跳过本夹具。
    """
    if request.node.get_closest_marker("real_background"):
        return

    import app.services.bearish_factor_service as bearish
    import app.services.bullish_factor_service as bullish
    import app.services.institution_prediction_service as institution
    import app.services.investment_advice_service as advice
    import app.services.market_summary_service as summary

    modules = (bullish, bearish, institution, advice, summary)
    patched = 0
    for module in modules:
        for name in dir(module):
            candidate = getattr(module, name)
            if isinstance(candidate, type) and hasattr(candidate, "_trigger_background_analysis"):
                # 签名不统一：有的服务无参，有的服务接上下文参数，所以必须吃掉任意参数。
                monkeypatch.setattr(
                    candidate,
                    "_trigger_background_analysis",
                    lambda self, *args, **kwargs: None,
                )
                patched += 1
    assert patched >= 5, f"预期至少 patch 5 个服务，实际 {patched}"


@pytest.fixture(autouse=True)
def _isolate_cache_dir(tmp_path, monkeypatch):
    """把文件缓存重定向到临时目录。

    否则测试会读写仓库里的 `backend/cache/*.json`：既让测试结果依赖仓库内容，
    也可能把仓库文件改坏。同时清空进程内内存缓存，避免用例串味。

    注意：文件缓存现在只有 CacheManager 一个实现（gold_service 与
    gold_price_service 各自那份已合并到 realtime_price），所以只需要改它一处。
    """
    import app.services.bearish_factor_service as bearish_factor_service
    import app.services.cache_manager as cache_manager

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    monkeypatch.setattr(cache_manager, "CACHE_DIR", cache_dir)

    cache_manager._memory_cache.clear()
    bearish_factor_service._cache.clear()
    yield
    cache_manager._memory_cache.clear()
    bearish_factor_service._cache.clear()


@pytest.fixture
def db_session(_prepare_database):
    """一个数据库会话；用例结束回滚并关闭。"""
    from app.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(_prepare_database):
    """FastAPI 测试客户端（会触发 lifespan：建表 + 调度器按配置跳过）。"""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------- #
# 造数据助手
# --------------------------------------------------------------------------- #
@pytest.fixture
def seed_gold_prices(db_session):
    """插入**截至今天**的连续金价与美元指数，用于统计/相关性测试。

    日期是**相对今天**的，不是钉死在 2025-01-02。原因：接口里有
    「最近 N 天」这类时间窗（如 `/prices/correlation?days=`），
    固定日期会让夹具数据整个落在窗口外 —— 于是窗口逻辑在测试里
    **完全测不到**，而且一旦真去按窗口裁，测试就红。
    """
    from app.utils import timeutil

    def _seed(days: int = 10, start: float = 2600.0, step: float = 10.0):
        from app.models.gold_price import DollarIndex, GoldPrice

        # 最后一天就是今天，往前铺 days 天
        base = timeutil.today() - timedelta(days=days - 1)
        for i in range(days):
            day = base + timedelta(days=i)
            price = start + step * i
            db_session.add(
                GoldPrice(
                    date=day,
                    open_price=price,
                    high_price=price + 5,
                    low_price=price - 5,
                    close_price=price,
                    volume=1000 + i,
                    change_percent=0.5,
                )
            )
            db_session.add(
                DollarIndex(
                    date=day,
                    open_price=108.0 - i * 0.1,
                    high_price=108.2 - i * 0.1,
                    low_price=107.8 - i * 0.1,
                    close_price=108.0 - i * 0.1,
                )
            )
        db_session.commit()
        return days

    return _seed


@pytest.fixture
def seed_news(db_session):
    """插入最近若干小时的新闻。"""

    def _seed(count: int = 3, hours_ago: int = 1):
        from app.models.news import GoldNews, SentimentType
        from app.utils import timeutil

        # 用与代码同一个时钟（项目时区），别用 datetime.now()
        now = timeutil.now_naive()
        for i in range(count):
            db_session.add(
                GoldNews(
                    title=f"测试新闻 {i}",
                    content=f"测试内容 {i}",
                    source="单元测试",
                    url=f"https://example.invalid/news/{i}",
                    published_at=now - timedelta(hours=hours_ago + i),
                    sentiment=SentimentType.NEUTRAL,
                )
            )
        db_session.commit()
        return count

    return _seed


@pytest.fixture
def seed_quant_panel(db_session):
    """写入一整块量化因子面板（含基准金价），不访问任何网络。

    与真实数据同样的形状：日频因子每天更新，周度（CFTC）、月度（央行储备）、
    单点快照（GLD 份额）与短期语料（地缘）按各自的稀疏度写入 ——
    这样新鲜度判定、前向填充与「可用因子不足」的降级路径才是真的被测到。
    """
    from app.services.quant import storage
    from app.services.quant.definitions import BENCHMARK_KEY, FACTORS
    from app.services.quant.definitions import factor_by_key
    from app.utils import timeutil

    def _seed(days: int = 850, *, step: int = 1):
        import numpy as np
        import pandas as pd

        end = pd.Timestamp(timeutil.today())
        calendar = pd.date_range(end=end, periods=days, freq="B")
        rng = np.random.default_rng(2026)

        written = {}
        for position, definition in enumerate(FACTORS):
            values = np.cumsum(rng.normal(0.0, 0.5, len(calendar))) + 100.0 + position * 5.0
            series = pd.Series(values, index=calendar, name=definition.key)
            written[definition.key] = series

        written["cftc_positioning"] = written["cftc_positioning"].iloc[::5]
        written["central_bank"] = written["central_bank"].iloc[::21]
        written["etf_shares"] = written["etf_shares"].iloc[-1:]
        written["geopolitical"] = written["geopolitical"].iloc[-70:]

        for key, series in written.items():
            source = factor_by_key[key].source if key in factor_by_key else "测试夹具"
            storage.upsert_series(db_session, key, series, source=source, commit=False)

        close = pd.Series(
            2000.0 * np.exp(np.cumsum(rng.normal(0.0, 0.008, len(calendar)))),
            index=calendar,
            name=BENCHMARK_KEY,
        )
        storage.upsert_series(db_session, BENCHMARK_KEY, close, source="测试夹具（GC=F 收盘）", commit=False)
        db_session.commit()
        return written, close

    return _seed
