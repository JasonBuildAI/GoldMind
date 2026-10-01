"""数据库初始化脚本

功能:
    1. 创建数据表结构
    2. 自动填充初始数据（从公开 API 获取 2025 年至今的黄金和美元指数数据）

数据库由 **DATABASE_URL 唯一决定**（与后端应用、seed_data.py 同一处真源）:
    - 默认 SQLite：backend/goldmind.db，零安装、单文件。
      不需要 MySQL、不需要 Docker，任何人都能在自己电脑上复现整个系统。
    - 需要 MySQL 时，在 backend/.env 里显式写：
      DATABASE_URL=mysql+pymysql://user:password@localhost:3306/gold_analysis
      （MySQL 路径会先建库，再执行 schema.sql。）

使用方式:
    cd backend
    python init_db.py
    SKIP_SEED=1 python init_db.py    # 只建表，不抓历史数据（也不联网）
"""

import os
import sys
import subprocess
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402

SKIP_SEED = os.getenv('SKIP_SEED', '0') == '1'


def database_url() -> str:
    """当前 DATABASE_URL（唯一真源）。"""
    return settings.DATABASE_URL.get_secret_value()


def describe_target() -> str:
    """日志里显示的库标识；**不含凭据**。"""
    from app.database import engine

    url = engine.url
    if url.get_backend_name() == "sqlite":
        return f"SQLite {url.database}"
    return f"{url.get_backend_name()} {url.host}:{url.port}/{url.database}"


def create_sqlite_tables() -> None:
    """SQLite：用 SQLAlchemy 模型建表（MySQL 的 DDL 在 SQLite 上跑不了）。"""
    import app.models  # noqa: F401  注册全部模型
    from app.database import Base, engine

    Base.metadata.create_all(bind=engine)
    print(f"✅ SQLite 表结构就绪: {engine.url.database}")


def create_mysql_database_and_tables() -> None:
    """MySQL：先建库，再逐条执行 schema.sql（保持原有安装路径不变）。"""
    import pymysql

    from app.database import mysql_connection_params

    params = mysql_connection_params(include_database=True)
    db_name = params["database"]

    # 先不带库名连上去，把库建出来
    conn = pymysql.connect(**mysql_connection_params(include_database=False))
    print("✅ MySQL 连接成功!")

    cursor = conn.cursor()
    cursor.execute("SHOW DATABASES LIKE %s", (db_name,))
    if cursor.fetchone():
        print(f"✅ 数据库 '{db_name}' 已存在")
    else:
        # 库名不能参数化（DDL 标识符），这里用反引号包住并拒绝可疑字符
        if not db_name.replace("_", "").isalnum():
            raise ValueError(f"库名 {db_name!r} 含非字母数字字符，拒绝执行")
        cursor.execute(
            f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        print(f"✅ 数据库 '{db_name}' 创建成功!")
    cursor.close()
    conn.close()

    # 读取并执行 schema.sql（schema.sql 不自带 CREATE DATABASE / USE，
    # 写死库名会让配置失效；这里靠上面的 database= 参数选库。）
    print("\n📋 创建数据表...")
    sql = (BACKEND_DIR / "schema.sql").read_text(encoding="utf-8")

    conn = pymysql.connect(**params)
    cursor = conn.cursor()

    # 执行SQL脚本（先去掉 -- 行注释，避免注释里的分号或关键字干扰）
    cleaned = "\n".join(line.split('--', 1)[0] for line in sql.splitlines())
    for statement in cleaned.split(';'):
        statement = statement.strip()
        if not statement:
            continue
        try:
            cursor.execute(statement)
        except Exception as e:
            if 'already exists' not in str(e).lower():
                print(f"⚠️  注意: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    print("✅ 所有数据表创建成功!")


def create_tables() -> None:
    """按 DATABASE_URL 选择建表路径。"""
    if database_url().startswith("mysql"):
        create_mysql_database_and_tables()
    else:
        create_sqlite_tables()


def seed_database() -> bool:
    """跑一遍 seed_data.py（抓真实历史数据）。"""
    print("\n" + "=" * 60)
    print("🌱 开始填充初始数据...")
    print("=" * 60)

    script = BACKEND_DIR / "seed_data.py"
    if not script.exists():
        print(f"❌ 错误: 找不到 {script}")
        return False

    try:
        result = subprocess.run([sys.executable, str(script)], cwd=str(BACKEND_DIR))
        return result.returncode == 0
    except Exception as e:
        print(f"❌ 填充数据失败: {e}")
        return False


def main() -> int:
    """主函数"""
    print("=" * 60)
    print("🚀 数据库初始化")
    print("=" * 60)

    try:
        create_tables()
        print(f"数据库: {describe_target()}")
        print("-" * 60)

        if SKIP_SEED:
            print("\n⏭️  跳过数据填充 (SKIP_SEED=1)")
        elif not seed_database():
            print("\n⚠️  数据填充失败，但数据库结构已就绪")
            print("您可以稍后手动运行: python seed_data.py")

        print("\n" + "=" * 60)
        print("🎉 数据库初始化完成!")
        print("=" * 60)
        print("\n现在您可以启动后端服务了:")
        print("  python -m uvicorn app.main:app --reload")
        return 0

    except Exception as e:
        print(f"\n❌ 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
