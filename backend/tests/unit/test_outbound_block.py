"""出网拦截本身要真的有效。

红线第 4 条：**测试不得访问真实外部服务。**

拦截器自己也要有判别力，否则「测试不出网」只是一句没人验证过的话。
2026-10-02 的实测把守卫推进成了四层（实现见 conftest 的
`_block_outbound_network`）：

    requests（IP 字面量）         -> 被拦住
    异步 httpx（域名）            -> 之前**拦不住**，现在由 httpcore 层拦住
    异步 httpx（走本机代理）       -> 之前真的发出去了（实测拿到过 HTTP 200）

四层分别是：代理清零、DNS、socket/urllib3 连接层、httpcore 客户端层。
本机（回环）地址一律放行 —— 测试要连本机服务。
"""
import asyncio
import http.server
import os
import socket
import threading

import pytest


def _local_server() -> tuple[http.server.HTTPServer, int]:
    """起一个只回 ok 的本机 HTTP 服务，用来验证守卫不误伤回环。"""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler 规定的接口名
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):  # 静音：测试输出里不需要访问日志
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_port


@pytest.mark.unit
def test_sync_requests_is_blocked():
    """同步 requests（urllib3 路径），给的是 IP 字面量 —— 连 DNS 都不需要。"""
    import requests

    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        requests.get("http://93.184.216.34/", timeout=2)


@pytest.mark.unit
def test_async_httpx_is_blocked():
    """异步 httpx 必须被拦住 —— 这正是 2026-10-02 之前漏掉的那条。"""
    import httpx

    async def go():
        async with httpx.AsyncClient(timeout=3) as client:
            await client.get("http://example.com/")

    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        asyncio.run(go())


@pytest.mark.unit
def test_async_httpx_with_ip_literal_is_blocked():
    """IP 字面量不走 DNS，只有客户端层拦得住 —— 少这一层就会真的发出去。"""
    import httpx

    async def go():
        async with httpx.AsyncClient(timeout=3) as client:
            await client.get("http://93.184.216.34/")

    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        asyncio.run(go())


@pytest.mark.unit
def test_async_httpx_goes_through_the_httpcore_guard(monkeypatch):
    """异步 httpx 的拦截点必须落在 httpcore 上。

    只断言「请求失败了」不够 —— 那可能是任何原因。这里把守卫包一层探针：
    请求必须真的走到 httpcore，并由守卫抛出我们自己的错误。
    （探针挂在连接池层：httpx 的 AsyncHTTPTransport 正是调它。）
    """
    import httpcore
    import httpx

    installed = httpcore.AsyncConnectionPool.handle_async_request  # 夹具装上的守卫
    seen: list = []

    async def spy(self, request):
        seen.append(request.url.host)  # bytes，原样记录，别 str()
        return await installed(self, request)  # 委派给守卫 —— 应当抛错

    def dns_must_not_be_reached(*args, **kwargs):
        raise AssertionError(
            "请求走到了 DNS —— 说明拦截不是发生在 httpcore 层，这条测试就白写了"
        )

    monkeypatch.setattr(httpcore.AsyncConnectionPool, "handle_async_request", spy)
    monkeypatch.setattr(socket, "getaddrinfo", dns_must_not_be_reached)

    async def go():
        async with httpx.AsyncClient(timeout=3) as client:
            await client.get("http://example.com/")

    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        asyncio.run(go())

    assert any(
        (h.decode() if isinstance(h, bytes) else h) == "example.com" for h in seen
    ), "异步 httpx 没有经过 httpcore —— 那么守卫装错了地方"


@pytest.mark.unit
def test_httpcore_guard_is_installed_on_pool_and_connection_layers():
    """同步 / 异步、池 / 连接四个关键层都要有守卫。

    行为测试只能证明「请求被拦」，证明不了拦它的到底是哪一层；这里直接
    检查守卫标记，防止某次重构后只剩一层、甚至哪里都没装。
    """
    import httpcore

    for cls, method in (
        (httpcore.AsyncConnectionPool, "handle_async_request"),
        (httpcore.AsyncHTTPConnection, "handle_async_request"),
        (httpcore.ConnectionPool, "handle_request"),
        (httpcore.HTTPConnection, "handle_request"),
    ):
        guarded = getattr(cls, method)
        assert getattr(guarded, "__goldmind_outbound_guard__", False), (
            f"{cls.__name__}.{method} 没有被出网守卫包住"
        )


@pytest.mark.unit
def test_system_proxy_is_neutralized():
    """代理必须清零：本机代理会替测试把请求转发到真实外网。"""
    import urllib.request

    assert urllib.request.getproxies() == {}
    for key in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        assert key not in os.environ, f"{key} 还留在测试环境里"

    import requests.utils

    assert requests.utils.getproxies() == {}, "requests 拿到的代理副本没被清掉"

    import httpx._utils

    assert httpx._utils.getproxies() == {}, "httpx 拿到的代理副本没被清掉"


@pytest.mark.unit
def test_dns_is_the_interception_point():
    """拦截点之一是 getaddrinfo —— 任何按域名发起的连接都要先过这里。"""
    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        socket.getaddrinfo("example.com", 80)


@pytest.mark.unit
def test_async_dns_is_blocked_too():
    """异步路径传的是 bytes 域名 —— 归一化没做对的话这条会漏。"""

    async def go():
        return await asyncio.get_running_loop().getaddrinfo("example.com", 80)

    with pytest.raises(RuntimeError, match="禁止真实网络访问"):
        asyncio.run(go())


@pytest.mark.unit
def test_localhost_is_allowed():
    """本机地址必须放行 —— 测试要连本机服务。

    这里不真的连 3306（可能没开），只验证拦截器不会拦它。
    """
    try:
        socket.getaddrinfo("localhost", 3306)
        socket.getaddrinfo("127.0.0.1", 3306)
    except RuntimeError as exc:
        pytest.fail(f"本机地址被拦截了：{exc}")


@pytest.mark.unit
def test_localhost_dns_is_allowed():
    socket.getaddrinfo("localhost", 3306)  # 不该抛


@pytest.mark.unit
def test_localhost_is_allowed_as_bytes():
    """异步客户端会把主机名传成 bytes —— 白名单必须照样放行本机。"""
    socket.getaddrinfo(b"localhost", 3306)  # 不该抛


@pytest.mark.unit
def test_local_server_is_still_reachable():
    """守卫不能把回环一起挡死：本机 HTTP 服务必须还能连。

    同步与异步各验一次 —— 两条路径的拦截实现不同，只验一条会漏。
    """
    import httpx
    import requests

    server, port = _local_server()
    try:
        url = f"http://127.0.0.1:{port}/"
        assert requests.get(url, timeout=5).text == "ok"

        async def go():
            async with httpx.AsyncClient(timeout=5) as client:
                return (await client.get(url)).text

        assert asyncio.run(go()) == "ok"
    finally:
        server.shutdown()
        server.server_close()