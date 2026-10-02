"""`news_digest_items.url` 必须是 TEXT，不能是 VARCHAR(500)。

2026-10-02 的真实故障：Google News 的文章链接实测最长 517 字符，超过
`VARCHAR(500)`。MySQL 严校验、整批 INSERT 回滚（`Data too long for column 'url'`）；
SQLite 不强制 VARCHAR 长度 —— 测试全绿，只有真实部署一条都落不进去。

这里把「改回 VARCHAR(500)」变成不需要 MySQL 就会红的守卫：一条查模型的 MySQL
方言 DDL，一条查 `schema.sql`（Docker 初始化与 `init_db.py` 的文档化安装路径）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy.dialects import mysql
from sqlalchemy.schema import CreateTable

from app.models.news_digest import NewsDigestItem

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_SQL = REPO_ROOT / "backend" / "schema.sql"


def _schema_table_body(table: str) -> str:
    text = SCHEMA_SQL.read_text(encoding="utf-8")
    match = re.search(
        r"CREATE TABLE IF NOT EXISTS\s+" + table + r"\s*\((.*?)\n\)\s*ENGINE=",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    assert match, f"schema.sql 里找不到表 {table}"
    return match.group(1)


def _column_line(body: str, column: str) -> str:
    for line in body.splitlines():
        if re.match(rf"\s*{column}\s+\w", line):
            return line.strip()
    raise AssertionError(f"表定义里找不到列 {column}")


@pytest.mark.unit
def test_url_column_compiles_to_text_on_mysql():
    """MySQL 方言下 url 必须编译为 TEXT —— 真实部署按这个 DDL 校验长度。"""
    ddl = str(CreateTable(NewsDigestItem.__table__).compile(dialect=mysql.dialect()))
    url_line = _column_line(ddl, "url")
    assert "TEXT" in url_line.upper(), url_line
    assert "VARCHAR" not in url_line.upper(), url_line


@pytest.mark.unit
def test_schema_sql_declares_url_as_text():
    """`schema.sql` 是 Docker 初始化与 init_db.py 的路径，必须与模型一致。"""
    url_line = _column_line(_schema_table_body("news_digest_items"), "url")
    assert url_line.split()[1].upper() == "TEXT", url_line
