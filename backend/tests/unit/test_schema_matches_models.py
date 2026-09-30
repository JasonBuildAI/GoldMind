"""`schema.sql` 必须与 SQLAlchemy 模型一致。

`schema.sql` 有两条使用路径：Docker 把它挂进 `/docker-entrypoint-initdb.d/`，
`init_db.py` 读取并逐条执行 —— 也就是**文档化的安装路径**。而应用本身用的是模型。
两边对枚举列的取值约定必须一致。

## 不一致的后果为什么特别隐蔽

`Column(Enum(SomeEnum))` 存的是**枚举名**（`POSITIVE`），不是枚举值（`positive`）。
而 MySQL 的 ENUM 比较**不区分大小写**，所以把 `'POSITIVE'` 插进
`ENUM('positive', ...)` 不会报错 —— 它会成功，并被规范成小写存下来。

于是变成「写得进去、读不出来」：写的时候一切正常，读的时候 SQLAlchemy 按枚举名
查 `'positive'`，查不到，直接抛

    LookupError: 'neutral' is not among the defined enum values

`/api/gold/news`、`/api/gold/factors` 因此全部 500，而且报错点离原因很远。

这个测试在**不需要 MySQL** 的前提下把两者钉在一起。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import Enum as SAEnum

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SQL = REPO_ROOT / "backend" / "schema.sql"

CREATE_TABLE = re.compile(
    r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\n\)\s*ENGINE=",
    re.DOTALL | re.IGNORECASE,
)
ENUM_COLUMN = re.compile(r"^\s*(\w+)\s+ENUM\s*\(([^)]*)\)", re.IGNORECASE | re.MULTILINE)


def _schema_enums() -> dict[tuple[str, str], list[str]]:
    """从 schema.sql 里取出 {(表, 列): [枚举取值]}。"""
    text = SCHEMA_SQL.read_text(encoding="utf-8")
    found: dict[tuple[str, str], list[str]] = {}

    for table, body in CREATE_TABLE.findall(text):
        for column, raw_values in ENUM_COLUMN.findall(body):
            values = [v.strip().strip("'\"").strip() for v in raw_values.split(",")]
            found[(table.lower(), column.lower())] = [v for v in values if v]

    return found


def _sql_without_comments() -> str:
    """去掉 `--` 行注释后的 SQL。

    注释里会提到 "CREATE DATABASE" 之类的字样（比如解释为什么不写它），
    直接对全文做子串判断会误报。
    """
    lines = []
    for line in SCHEMA_SQL.read_text(encoding="utf-8").splitlines():
        stripped = line.split("--", 1)[0]
        if stripped.strip():
            lines.append(stripped)
    return "\n".join(lines)


@pytest.fixture(scope="module")
def schema_enums() -> dict[tuple[str, str], list[str]]:
    enums = _schema_enums()
    assert enums, "没能从 schema.sql 里解析出任何 ENUM 列，解析逻辑大概失效了"
    return enums


@pytest.mark.unit
def test_schema_declares_the_expected_enum_columns(schema_enums):
    """先确认解析到的是预期的那几列，避免解析器静默失效后测试变成空转。"""
    expected = {
        ("gold_news", "sentiment"),
        ("market_factors", "type"),
        ("market_factors", "impact"),
        ("institution_views", "rating"),
    }
    assert expected <= set(schema_enums), f"schema.sql 里缺少这些枚举列：{expected - set(schema_enums)}"


@pytest.mark.unit
def test_schema_enums_match_model_storage_values(schema_enums):
    """枚举列在 schema.sql 里的取值，必须与模型实际存储的取值一致。"""
    import app.models  # noqa: F401  确保所有模型注册到 metadata
    from app.database import Base

    mismatches: list[str] = []

    for (table, column), schema_values in sorted(schema_enums.items()):
        sa_table = Base.metadata.tables.get(table)
        if sa_table is None:
            mismatches.append(f"{table}.{column}: 模型里没有这张表")
            continue

        sa_column = sa_table.columns.get(column)
        if sa_column is None:
            mismatches.append(f"{table}.{column}: 模型里没有这一列")
            continue

        col_type = sa_column.type
        if not isinstance(col_type, SAEnum):
            # 模型这一列不是枚举（比如 institution_views.rating 是 String），
            # schema.sql 里的 ENUM 只是额外约束，不做取值比对。
            continue

        enum_class = col_type.enum_class
        if enum_class is None:
            # 用字符串列表声明的 Enum，取值就是列表本身
            expected = list(col_type.enums)
        else:
            # 关键点：SQLAlchemy 存的是枚举**名**，不是值
            expected = [member.name for member in enum_class]

        if set(schema_values) != set(expected):
            mismatches.append(
                f"{table}.{column}: schema.sql={schema_values} 模型存的={expected}"
            )

    assert not mismatches, (
        "schema.sql 与模型的枚举取值不一致。\n"
        "MySQL 的 ENUM 比较不区分大小写，所以不一致不会在写入时报错，\n"
        "而是写进去被规范成另一种写法、读的时候抛 LookupError（写得进去读不出来）。\n"
        + "\n".join(f"  {m}" for m in mismatches)
    )


@pytest.mark.unit
def test_schema_does_not_hardcode_a_database_name():
    """schema.sql 不该写死库名。

    它被 `init_db.py` 读取执行，而那个脚本已经先连到了目标库上。
    文件里写 `CREATE DATABASE` / `USE gold_analysis` 会绕开调用方选好的库，
    把表建到另一个库里 —— 而且不会有任何报错。
    Docker 路径也不需要它 —— 官方 mysql 镜像会用 `MYSQL_DATABASE` 选好库。
    """
    text = _sql_without_comments().upper()

    assert "CREATE DATABASE" not in text, "schema.sql 不该自己建库"
    assert not re.search(r"^\s*USE\s+", text, re.MULTILINE), "schema.sql 不该写 USE 选库"


@pytest.mark.unit
def test_schema_covers_every_model_table(schema_enums):
    """schema.sql 建的表要覆盖模型里的每一张表，否则 Docker 路径会缺表。"""
    import app.models  # noqa: F401
    from app.database import Base

    text = SCHEMA_SQL.read_text(encoding="utf-8")
    declared = {t.lower() for t, _ in CREATE_TABLE.findall(text)}
    model_tables = {name.lower() for name in Base.metadata.tables}

    missing = model_tables - declared
    assert not missing, f"schema.sql 缺少这些表：{sorted(missing)}"

# --------------------------------------------------------------------------- #
# 索引
# --------------------------------------------------------------------------- #
@pytest.mark.unit
def test_news_url_index_exists_on_both_sides():
    """去重按 url 查，索引必须两边都有 —— 否则是一边全表扫描、一边有索引。

    MySQL 下 utf8mb4 的 500 字符索引超长，所以两边都用前缀长度 191。
    """
    import re

    from app.database import Base

    # 模型侧
    table = Base.metadata.tables["gold_news"]
    model_indexes = {idx.name for idx in table.indexes}
    assert "ix_gold_news_url" in model_indexes, (
        f"模型里没有 url 索引，现有：{sorted(model_indexes)}"
    )

    # schema 侧
    schema = (Path(__file__).resolve().parents[2] / "schema.sql").read_text(encoding="utf-8")
    match = re.search(r"CREATE TABLE IF NOT EXISTS gold_news \((.*?)\) ENGINE", schema, re.S)
    assert match, "schema.sql 里找不到 gold_news 的建表语句"
    body = match.group(1)
    assert "ix_gold_news_url" in body, "schema.sql 里没有 url 索引"
    assert re.search(r"ix_gold_news_url\s*\(url\(191\)\)", body), (
        "schema.sql 的 url 索引应当用前缀长度 191（utf8mb4 下 500 字符超长）"
    )
