"""枚举取值的解析工具。

## 为什么需要它

本项目的枚举列都写成 `Column(Enum(X))`，而 SQLAlchemy 对 `enum.Enum` 默认存的是
**枚举名**（`BULLISH` / `POSITIVE`），不是枚举值（`bullish` / `positive`）。
接口对外则一律用小写值：schema 里是 `FactorTypeEnum.BULLISH = "bullish"`，
响应体里也是 `"bullish"`。

于是把接口收到的小写串直接丢给过滤条件，会一条都匹配不到 ——
**接口自己的输出不能当作输入用**：

    GET /api/gold/factors?factor_type=bullish   ->  0 条（库里存的是 BULLISH）
    GET /api/gold/news?sentiment=positive       ->  0 条（库里存的是 POSITIVE）

这个工具把两种写法都收下来，统一解析成枚举成员。
"""
from __future__ import annotations

from enum import Enum
from typing import Optional, Type, TypeVar

E = TypeVar("E", bound=Enum)


def resolve_enum(enum_cls: Type[E], value: object) -> Optional[E]:
    """把值解析成 `enum_cls` 的成员；认不出来返回 None。

    接受：枚举成员本身、枚举名（任意大小写）、枚举值（任意大小写）。

    注意不要直接 `str(value)`：schema 里的枚举多是 `str` 子类，
    Python 3.11 下 `str(SomeStrEnum.MEMBER)` 得到的是 `"SomeStrEnum.MEMBER"`，
    而不是它的小写值。所以这里取 `.value`。
    """
    if isinstance(value, enum_cls):
        return value

    raw = getattr(value, "value", value)
    text = str(raw).strip().lower()

    for member in enum_cls:
        if member.value == text or member.name.lower() == text:
            return member
    return None
