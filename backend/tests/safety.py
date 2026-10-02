"""测试套件的数据安全护栏。

2026-10-02 的真实事故：一次把 `GOLDMIND_TEST_DATABASE_URL` 指向开发库
`gold_analysis` 的 MySQL 方言 pytest 运行，在会话结束时执行 `drop_all`，
把 9 张业务表全部删掉（binlog 里能看到完整的
`use gold_analysis; DROP TABLE ...` 序列），只剩一张非模型表 `update_logs`——
接口整片 500，行情/量化/AI 区块全部「暂不可用」。

测试套件按设计会 `drop_all` / 逐表 `DELETE`，**只应该对它自己建出来的库做这件事**。
这个护栏保证：非 SQLite 的测试库，名字里必须含 `test`，否则宁可不跑。
"""
from __future__ import annotations

from typing import Optional


class UnsafeTestDatabaseError(RuntimeError):
    """测试库看起来不像测试库 —— 拒绝运行，避免删掉真实数据。"""


def is_safe_test_database(url: Optional[str]) -> bool:
    """测试套件连上去就删的库，必须是「它自己建得出来」的库。

    - 未配置（None / 空串）：调用方会退回默认的**内存** SQLite —— 安全；
    - SQLite 内存库：安全（自建自删，进程结束即消失）；
    - SQLite **文件**库：文件名必须含 `test`。`backend/goldmind.db` 是项目的
      真实单文件数据库，不能因为「它是 SQLite」就被当成可删对象；
    - 其它方言（MySQL 等）：库名必须含 `test`；
    - URL 解析失败按不安全处理：宁可拒跑，也不赌一个看不懂的 URL。
    """
    if not url:
        return True

    from sqlalchemy.engine import make_url

    try:
        parsed = make_url(url)
    except Exception:
        return False

    name = parsed.database or ""
    if parsed.get_backend_name().startswith("sqlite"):
        if not name or name == ":memory:" or ":memory:" in url:
            return True

    # 只认最后一段名字（库名 / 文件名）。整条路径里出现 "latest" 之类的
    # 子串不算数 —— 那会把一个真实数据文件放行成「测试库」。
    candidate = name.replace("\\", "/").rsplit("/", 1)[-1]
    return "test" in candidate.lower()


def assert_safe_test_database(url: Optional[str]) -> None:
    """不安全的库直接抛错；错误信息只带**库名**，绝不回显凭据。"""
    if is_safe_test_database(url):
        return

    from sqlalchemy.engine import make_url

    name = "<无法解析>"
    if url:
        try:
            name = make_url(url).database or "<未指定库名>"
        except Exception:
            name = "<无法解析>"

    raise UnsafeTestDatabaseError(
        f"测试套件会 DROP 所有表，而 DATABASE_URL 指向的库 {name!r} 名字里不含 "
        "\"test\"。\n"
        "为避免删掉真实数据，本次运行已拒绝继续。\n"
        "请把它指向独立的测试库（名字含 test，例如 goldmind_test），"
        "或留空以使用默认的内存 SQLite（sqlite://）：\n"
        '  GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" '
        "python -m pytest"
    )
