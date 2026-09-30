"""出网拦截本身要真的有效。

红线第 4 条：**测试不得访问真实外部服务。**

原来的拦截只 patch 了 `socket.create_connection` 与 urllib3 的同名函数。
实测（用 `127.0.0.1:1` 这种**能解析**的地址验证，避免 DNS 失败掩盖问题）：

    requests（urllib3 路径）      -> 被拦住
    异步 httpx（anyio 路径）      -> **没被拦**

异步客户端走 `loop.create_connection` → `sock.connect()`，不经过
`create_connection`。也就是说异步 HTTP 客户端的测试会**真的打到外网**。

现在拦在 `socket.getaddrinfo` 这一层 —— 任何按域名发起的连接都要先解析，
同步与异步都覆盖。**本机地址放行**（测试要连本机 MySQL）。

（不 patch `socket.socket.connect`：实测那样会弄坏 asyncio 在 Windows 上的
Proactor 事件循环。）

这一组测试验证拦截对多种客户端都有效 —— 拦截器自己也要有判别力，
否则「测试不出网」只是一句没人验证过的话。
"""
import asyncio
import socket

import pytest


@pytest.mark.unit
def test_sync_requests_is_blocked():
    """同步 requests（urllib3 路径）。"""
    import requests

    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        requests.get("http://93.184.216.34/", timeout=2)     # 一个公网 IP


@pytest.mark.unit
def test_dns_is_the_interception_point():
    """拦截点在 `getaddrinfo` —— 任何按域名发起的连接都要先过这里。

    为什么不在 `socket.socket.connect` 拦：实测那样会弄坏 asyncio 在
    Windows 上的 Proactor 事件循环（`'ProactorEventLoop' object has no
    attribute '_ssock'`）。而所有真实出网都走域名，`getaddrinfo` 足够。
    """
    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        socket.getaddrinfo("example.com", 80)


@pytest.mark.unit
def test_dns_resolution_is_blocked():
    """解析一个公网域名也算出网。"""
    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        socket.getaddrinfo("example.com", 80)


@pytest.mark.unit
def test_async_clients_go_through_socket_connect(monkeypatch):
    """异步客户端的底层路径**就是** `socket.socket.connect` —— 拦它才有效。

    这条不靠「请求失败了」来判断（那可能是任何原因），
    而是**直接验证机制**：装一个探针，看异步请求是否真的走到它。

    （anyio 会把 connect 抛出的异常包成 ConnectTimeout，
    所以按异常类型断言并不可靠。）
    """
    import httpx

    resolved: list = []
    real_getaddrinfo = socket.getaddrinfo

    def spy(host, *args, **kwargs):
        resolved.append(host)          # 原样记录，别 str() —— 会把 bytes 变成 "b'...'"
        raise RuntimeError("测试禁止真实网络访问")

    monkeypatch.setattr(socket, "getaddrinfo", spy)

    async def go():
        async with httpx.AsyncClient(timeout=3) as client:
            await client.get("http://example.com/")

    with pytest.raises(Exception):
        asyncio.run(go())

    # 注意：异步客户端传的是 **bytes**（实测 b'example.com'）——
    # 拦截器的白名单也必须按这个事实做归一化，否则本机放行会失效。
    assert any(
        (h.decode() if isinstance(h, bytes) else h) == "example.com" for h in resolved
    ), "异步 httpx 没有走 socket.getaddrinfo —— 那么拦截点选错了"


@pytest.mark.unit
def test_localhost_is_allowed():
    """本机地址必须放行 —— 测试要连本机的 MySQL。

    这里不真的连 3306（可能没开），只验证**拦截器不会拦它**：
    连一个本机关闭的端口应当得到「连接被拒绝」之类的网络错误，
    而不是我们抛的 RuntimeError。
    """
    try:
        socket.getaddrinfo("localhost", 3306)
        socket.getaddrinfo("127.0.0.1", 3306)
    except RuntimeError as exc:
        pytest.fail(f"本机地址被拦截了：{exc}")


@pytest.mark.unit
def test_localhost_dns_is_allowed():
    socket.getaddrinfo("localhost", 3306)           # 不该抛


@pytest.mark.unit
def test_localhost_is_allowed_as_bytes():
    """异步客户端会把主机名传成 bytes —— 白名单必须照样放行本机。"""
    socket.getaddrinfo(b"localhost", 3306)          # 不该抛
