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

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ.setdefault("MIMO_API_KEY", "test-key-not-real")
os.environ.setdefault("MIMO_BASE_URL", "https://example.invalid/v1")
os.environ.setdefault("MIMO_MODEL", "mimo-v2.6-flash")

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
    """兜底：任何真实出网连接直接失败。

    必须同时 patch 两处，只拦一处是无效的：

    - ``socket.create_connection`` —— httpx / httpcore 走这里；
    - ``urllib3.util.connection.create_connection`` —— requests 走这里。
      urllib3 在导入时就把该函数绑定进了自己的模块命名空间，
      所以仅 patch ``socket`` 拦不住 requests（曾因此让测试打到真实行情接口）。
    """
    import socket

    def _blocked(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError(
            "测试禁止真实网络访问：请 mock 掉发起该请求的服务方法"
        )

    monkeypatch.setattr(socket, "create_connection", _blocked)

    try:
        import urllib3.util.connection as urllib3_connection

        monkeypatch.setattr(urllib3_connection, "create_connection", _blocked)
    except ImportError:  # urllib3 不在时无需处理
        pass


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
def _disable_background_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    """禁止各分析服务在测试中触发后台线程分析。

    这些线程会新建数据库会话、发起真实 LLM 调用，而且可能活过用例本身
    （表现为「no such table」之类来自已销毁引擎的噪声）。测试必须同步、确定。
    """
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

    否则测试会读写仓库里提交的 `backend/cache/*.json`：既让测试结果依赖
    仓库内容，也可能把仓库文件改坏。同时清空进程内内存缓存，避免用例串味。
    """
    import app.services.bearish_factor_service as bearish_factor_service
    import app.services.cache_manager as cache_manager
    import app.services.gold_service as gold_service

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    monkeypatch.setattr(cache_manager, "CACHE_DIR", cache_dir)
    monkeypatch.setattr(gold_service, "CACHE_DIR", cache_dir)

    cache_manager._memory_cache.clear()
    gold_service._price_cache.clear()
    bearish_factor_service._cache.clear()
    yield
    cache_manager._memory_cache.clear()
    gold_service._price_cache.clear()
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
    """插入 2025-01-02 起的连续金价与美元指数，用于统计/相关性测试。"""

    def _seed(days: int = 10, start: float = 2600.0, step: float = 10.0):
        from app.models.gold_price import DollarIndex, GoldPrice

        base = date(2025, 1, 2)
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

        now = datetime.now()
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
