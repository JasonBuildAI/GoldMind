"""枚举列在**查询**里必须与枚举成员比较，不能与小写字符串比较。

这是第 2 轮那个 bug 的查询版。当时修的是 **schema**（ENUM 写成了小写，
而 ORM 存的是枚举**名**），这次是**查询**：

    db.query(MarketFactor).filter(MarketFactor.type == "bullish")

列类型是 `Enum(FactorType)`，SQLAlchemy 存的是 `BULLISH`：

    MySQL  —— ENUM 比较不区分大小写，碰巧能匹配，所以线上看不出来；
    SQLite —— 存的是 VARCHAR，比较区分大小写，**一条都匹配不到**。

实测：`/factors/bullish` 在 SQLite 下恒返回 `[]`，在 MySQL 下正常。
测试套件跑的是 SQLite，所以这类问题**只会在测试里显形**，而当时没有测试覆盖它。
"""
import re
from pathlib import Path

import pytest

from app.database import Base
from app.models.analysis import FactorType, ImpactLevel, MarketFactor
from app.models.news import SentimentType

APP_DIR = Path(__file__).resolve().parents[2] / "app"

# 模型里所有 Enum 列：(表名, 列名)
ENUM_COLUMNS = {
    ("market_factors", "type"),
    ("market_factors", "impact"),
    ("gold_news", "sentiment"),
}


def _python_files():
    for path in APP_DIR.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        yield path


def _code_line_numbers(source: str) -> set[int]:
    """只返回真正含代码的行（跳过纯注释/字符串行）。"""
    import io
    import tokenize

    lines: set[int] = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type in (
                tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE,
                tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER, tokenize.STRING,
            ):
                continue
            lines.add(tok.start[0])
    except (tokenize.TokenError, IndentationError):
        return set(range(1, len(source.splitlines()) + 1))
    return lines


# --------------------------------------------------------------------------- #
# 结构性守卫
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_no_enum_column_compared_to_a_string_literal():
    """`<Model>.<enum列> == "小写字符串"` 一律不允许。"""
    offenders = []
    for path in _python_files():
        source = path.read_text(encoding="utf-8")
        code_lines = _code_line_numbers(source)
        for lineno, line in enumerate(source.splitlines(), start=1):
            if lineno not in code_lines:
                continue
            for model, column in (
                ("MarketFactor", "type"),
                ("MarketFactor", "impact"),
                ("GoldNews", "sentiment"),
                ("InstitutionView", "rating"),
            ):
                pattern = rf"{model}\.{column}\s*==\s*[\"']"
                if re.search(pattern, line):
                    offenders.append(
                        f"{path.relative_to(APP_DIR).as_posix()}:{lineno}: {line.strip()}"
                    )

    assert not offenders, (
        "这些地方把枚举列与字符串字面量比较了，应改用枚举成员：\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.unit
def test_the_guard_actually_detects_a_violation(tmp_path, monkeypatch):
    """守卫自身要有判别力（本会话已经吃过三次假绿测试的亏）。"""
    import importlib

    module = importlib.import_module("tests.unit.test_enum_query_discipline")

    fake = tmp_path / "app"
    (fake / "routers").mkdir(parents=True)
    (fake / "routers" / "bad.py").write_text(
        "def f(db):\n"
        '    """文档里写一句 MarketFactor.type == "bullish" 不该算违规。"""\n'
        '    return db.query(MarketFactor).filter(MarketFactor.type == "bullish")\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "APP_DIR", fake)

    with pytest.raises(AssertionError) as excinfo:
        module.test_no_enum_column_compared_to_a_string_literal()

    assert "bad.py:3" in str(excinfo.value)
    assert "bad.py:2" not in str(excinfo.value), "文档行不该被判违规"


@pytest.mark.unit
def test_the_enum_columns_are_still_what_we_think():
    """守卫依赖这份列清单；模型改了它也要跟着变。"""
    actual = set()
    for table_name, table in Base.metadata.tables.items():
        for column in table.columns:
            if isinstance(column.type, type(column.type)) and column.type.__class__.__name__ == "Enum":
                actual.add((table_name, column.name))
            elif hasattr(column.type, "enum_class") and column.type.enum_class is not None:
                actual.add((table_name, column.name))

    assert ENUM_COLUMNS.issubset(actual), (
        f"守卫清单里的列在模型里找不到了：{ENUM_COLUMNS - actual}"
    )


# --------------------------------------------------------------------------- #
# 功能性：接口本身
# --------------------------------------------------------------------------- #
@pytest.mark.integration
def test_factor_endpoints_return_the_matching_type(client, db_session):
    """回归：`/factors/bullish` 曾恒返回 []。

    这条测试在 SQLite 下会红 —— 而线上跑 MySQL 时它是绿的，
    正是「只在测试里显形」的那类问题。
    """
    db_session.add(
        MarketFactor(type=FactorType.BULLISH, title="看涨因子", impact=ImpactLevel.HIGH, details=[])
    )
    db_session.add(
        MarketFactor(type=FactorType.BEARISH, title="看跌因子", impact=ImpactLevel.LOW, details=[])
    )
    db_session.commit()

    all_factors = client.get("/api/gold/factors").json()
    bullish = client.get("/api/gold/factors/bullish").json()
    bearish = client.get("/api/gold/factors/bearish").json()

    assert len(all_factors) == 2
    assert [f["title"] for f in bullish] == ["看涨因子"], "bullish 接口没返回看涨因子"
    assert [f["title"] for f in bearish] == ["看跌因子"], "bearish 接口没返回看跌因子"


@pytest.mark.integration
def test_factor_type_filter_accepts_both_cases(client, db_session):
    """`/factors?factor_type=` 大小写都要能匹配（这个已经走 resolve_enum 了）。"""
    db_session.add(
        MarketFactor(type=FactorType.BULLISH, title="看涨因子", impact=ImpactLevel.HIGH, details=[])
    )
    db_session.commit()

    for value in ("bullish", "BULLISH", "Bullish"):
        body = client.get(f"/api/gold/factors?factor_type={value}").json()
        assert [f["title"] for f in body] == ["看涨因子"], f"factor_type={value} 没匹配到"


@pytest.mark.integration
def test_news_sentiment_filter_accepts_both_cases(client, db_session):
    """新闻情感过滤同样不该受大小写影响。

    2.0.2 修掉了这条测试的假绿：旧断言只数响应体的键，而 422 的
    `{"detail": [...]}` 恰好也是 1 个键 —— 大小写不敏感**从未被真正验证过**。
    现在先断言 200，再数列表长度。
    """
    from app.models.news import GoldNews

    db_session.add(
        GoldNews(title="中性新闻", content="x", url="https://e.invalid/1",
                 source="测试源", sentiment=SentimentType.NEUTRAL)
    )
    db_session.commit()

    for value in ("neutral", "NEUTRAL", "Neutral"):
        response = client.get(f"/api/gold/news?sentiment={value}")
        assert response.status_code == 200, f"sentiment={value} 被拒了：{response.text}"
        assert len(response.json()) == 1, f"sentiment={value} 没匹配到"
