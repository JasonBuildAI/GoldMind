"""前后端之间的**查询参数契约**。

第 19 轮发现：前端一直在传 `?days=30`，而端点**从未声明** `days` ——
FastAPI 会静默忽略未声明的查询参数，于是那个参数从来没有生效过，
调用方以为拿到 30 天，实际拿到最多 100 个点（跨 385 天）。

同一处理函数里此前还修过 `limit`（声明了、校验了、从未使用）。
两次都是「参数的契约两端各写各的」，而且**两边都不报错** ——
类型系统管不到 URL 字符串，FastAPI 也不检查多余参数。

这条测试把契约钉住，两个方向都查：

    A. 前端传的每个参数，端点必须声明（否则会被静默忽略）
    B. 端点声明的每个参数，函数体里必须真的用到（否则是装饰）

判据是「有没有一条测试证明它真的生效」—— 这条守卫只能保证**名字对得上**，
「生效」由各端点自己的行为测试负责（如 `test_correlation_days_actually_filters`）。
"""
import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BACKEND = REPO / "backend" / "app"
FRONTEND = REPO / "app" / "src"

# 带普通默认值的简单类型也是查询参数（`refresh: bool = False`）；
# 这些是 FastAPI 的依赖注入，不是查询参数。
_NOT_QUERY = {"Depends", "Path", "Body", "Header", "Cookie", "File", "Form"}


def _route_prefixes() -> dict[str, str]:
    """从 main.py 的 include_router 读出每个 router 模块的前缀。"""
    src = (BACKEND / "main.py").read_text(encoding="utf-8")
    prefixes: dict[str, str] = {}
    for m in re.finditer(
        r"app\.include_router\(\s*(\w+)\.router\s*,\s*prefix\s*=\s*['\"]([^'\"]+)['\"]", src
    ):
        prefixes[m.group(1)] = m.group(2)
    return prefixes


def _declared_params() -> dict[str, set[str]]:
    """{路由路径: 声明的查询参数集合}"""
    prefixes = _route_prefixes()
    declared: dict[str, set[str]] = {}

    for path in (BACKEND / "routers").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        prefix = prefixes.get(path.stem, "")

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route = None
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, "attr", "") in (
                    "get", "post", "put", "delete", "patch",
                ):
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        route = prefix + dec.args[0].value
            if not route:
                continue

            all_args = list(node.args.args) + list(node.args.kwonlyargs)
            defaults: list[ast.AST | None] = list(node.args.defaults) + list(
                node.args.kw_defaults
            )
            offset = len(all_args) - len(defaults)
            by_name: dict[str, ast.AST | None] = {}
            for i, d in enumerate(defaults):
                by_name[all_args[offset + i].arg] = d

            params: set[str] = set()
            for name in (a.arg for a in all_args):
                d = by_name.get(name)
                if d is None:
                    continue
                if isinstance(d, ast.Call):
                    fn = getattr(d.func, "id", "") or getattr(d.func, "attr", "")
                    if fn == "Query":
                        params.add(name)
                    continue
                # `None` 也是查询参数（`start_date: Optional[str] = None`）。
                # `Depends(...)` 是 Call，上面已经排除了。
                if isinstance(d, ast.Constant):
                    params.add(name)
            if params:
                declared[route] = params

    return declared


def _sent_params() -> dict[str, set[str]]:
    """{路由路径: 前端实际会传的参数集合}"""
    sent: dict[str, set[str]] = {}

    for path in FRONTEND.rglob("*.ts*"):
        if ".test." in path.name:
            continue
        src = path.read_text(encoding="utf-8")

        # 字面量查询串：`/api/gold/x?a=1&b=2`
        for m in re.finditer(r"`(/api/gold/[^`?]*)\?([^`]*)`", src):
            route, qs = m.group(1), m.group(2)
            names = {p.split("=")[0].strip() for p in qs.split("&") if "=" in p}
            if "${" in qs:
                names.discard("")
            sent.setdefault(route, set()).update(n for n in names if n)

        # 模板拼接：`/api/gold/x?${params}`
        for m in re.finditer(r"`(/api/gold/[^`]*?)\?\$\{", src):
            sent.setdefault(m.group(1), set()).update(
                n for n in _appended_params(src) if n
            )

    return sent


def _appended_params(src: str) -> set[str]:
    """从 `params.append('name', ...)` 里取出参数名。"""
    return {m.group(1) for m in re.finditer(r"params\.append\(\s*['\"]([a-z_]+)['\"]", src)}


# --------------------------------------------------------------------------- #
# A. 前端传的，后端必须声明
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_every_frontend_param_is_declared_by_the_endpoint():
    declared = _declared_params()
    sent = _sent_params()

    problems = []
    for route, names in sorted(sent.items()):
        ok = declared.get(route, set())
        missing = names - ok
        if missing:
            problems.append(f"{route}: 前端传 {sorted(missing)}，端点只声明 {sorted(ok) or '（无）'}")

    assert not problems, (
        "前端传了端点没有声明的查询参数 —— FastAPI 会静默忽略它们：\n  "
        + "\n  ".join(problems)
    )


# --------------------------------------------------------------------------- #
# B. 后端声明的，必须真的用到
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_every_declared_param_is_used_in_the_body():
    """声明了却不用的参数是装饰 —— 调用方以为它能改变行为。"""
    unused = []
    prefixes = _route_prefixes()

    for path in (BACKEND / "routers").glob("*.py"):
        src = path.read_text(encoding="utf-8")
        tree = ast.parse(src)
        prefix = prefixes.get(path.stem, "")

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            route = None
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call) and getattr(dec.func, "attr", "") in (
                    "get", "post", "put", "delete", "patch",
                ):
                    if dec.args and isinstance(dec.args[0], ast.Constant):
                        route = prefix + dec.args[0].value
            if not route:
                continue

            all_args = list(node.args.args) + list(node.args.kwonlyargs)
            defaults: list[ast.AST | None] = list(node.args.defaults) + list(
                node.args.kw_defaults
            )
            offset = len(all_args) - len(defaults)
            by_name: dict[str, ast.AST | None] = {}
            for i, d in enumerate(defaults):
                by_name[all_args[offset + i].arg] = d

            query_names = set()
            for name in (a.arg for a in all_args):
                d = by_name.get(name)
                if d is None:
                    continue
                if isinstance(d, ast.Call):
                    if (getattr(d.func, "id", "") or getattr(d.func, "attr", "")) == "Query":
                        query_names.add(name)
                    continue
                if isinstance(d, ast.Constant):
                    query_names.add(name)

            # 函数体（去掉签名）里是否出现过这个名字
            body = "\n".join(
                src.splitlines()[node.body[0].lineno - 1 : node.end_lineno]
            )
            for name in sorted(query_names):
                if not re.search(rf"(?<![\w.]){re.escape(name)}(?![\w])", body):
                    unused.append(f"{path.name} {route} 声明了 {name} 却没用")

    assert not unused, "这些参数声明了但函数体没用：\n  " + "\n  ".join(unused)


# --------------------------------------------------------------------------- #
# 守卫自身
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_the_audit_actually_finds_params():
    """守卫要真的扫到东西 —— 空集合上断言 `not problems` 是假绿。"""
    declared = _declared_params()
    sent = _sent_params()

    assert len(declared) >= 5, f"只解析出 {len(declared)} 个带参数的路由，解析八成坏了"
    assert len(sent) >= 5, f"只解析出 {len(sent)} 个带参数的前端调用，解析八成坏了"
    # 至少要有几个已知的参数被扫到
    assert "refresh" in declared.get("/api/gold/bullish-factors-ai", set())
    assert "days" in declared.get("/api/gold/prices/correlation", set())
    assert "start_date" in _appended_params(
        (FRONTEND / "services" / "api.ts").read_text(encoding="utf-8")
    )
