"""测试库护栏（``tests/safety.py``）的守卫测试。

2026-10-02 的真实事故：一次 ``GOLDMIND_TEST_DATABASE_URL`` 指向开发库
``gold_analysis`` 的 MySQL 方言 pytest，在会话结束时 ``drop_all`` 把 9 张
业务表删光，接口整片 500。护栏的立场是「宁可拒跑，也不删真实数据」：

* 合法库（内存 SQLite、名字含 test 的库）必须放行；
* 真实库名必须被拒 —— 把 ``is_safe_test_database`` 改成恒 True 时本文件必须变红；
* 拒跑信息只带库名，绝不回显凭据。
"""
from __future__ import annotations

import pytest

from tests.safety import (
    UnsafeTestDatabaseError,
    assert_safe_test_database,
    is_safe_test_database,
)

# 这些 URL 代表「测试套件自己建得出来」的库，必须放行
SAFE_URLS = [
    None,  # 未配置 —— 调用方退回默认的内存 SQLite
    "",  # 配了但为空，同上
    "sqlite://",  # 内存 SQLite（会话级默认）
    "sqlite:///:memory:",  # 显式内存
    "sqlite:///./test.db",  # 文件库，但文件名含 test
    "mysql+pymysql://root:pw@localhost:3306/goldmind_test",
    "postgresql://user:pw@localhost:5432/goldmind_test",
]

# 这些 URL 一旦被执行，真实数据就没了 —— 必须拒
UNSAFE_URLS = [
    "mysql+pymysql://root:pw@localhost:3306/gold_analysis",  # 事故现场
    "mysql+pymysql://root:pw@localhost:3306/goldmind",
    "sqlite:///./goldmind.db",  # 项目的真实单文件库
    "sqlite:///D:/App/AgentProjects/GoldMind/backend/goldmind.db",
    "not a url at all",  # 解析失败：fail-closed，不赌
]


@pytest.mark.parametrize("url", SAFE_URLS)
def test_safe_database_is_allowed(url: str | None) -> None:
    assert is_safe_test_database(url) is True


@pytest.mark.parametrize("url", UNSAFE_URLS)
def test_real_database_is_rejected(url: str) -> None:
    assert is_safe_test_database(url) is False


@pytest.mark.parametrize("url", UNSAFE_URLS)
def test_assert_raises_before_touching_anything(url: str) -> None:
    with pytest.raises(UnsafeTestDatabaseError):
        assert_safe_test_database(url)


def test_refusal_message_names_the_database_but_never_the_password() -> None:
    url = "mysql+pymysql://root:supersecret@localhost:3306/gold_analysis"

    with pytest.raises(UnsafeTestDatabaseError) as excinfo:
        assert_safe_test_database(url)

    message = str(excinfo.value)
    assert "gold_analysis" in message  # 说清拒的是哪个库，便于当场改命令
    assert "supersecret" not in message  # 凭据绝不回显
