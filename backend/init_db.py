"""数据库初始化脚本

功能:
    1. 创建数据库（如果不存在）
    2. 创建数据表结构（执行 schema.sql）
    3. 自动填充初始数据（从公开API获取2025年至今的黄金和美元指数数据）

使用方式:
    cd backend
    python init_db.py

环境变量:
    库连接以 **DATABASE_URL 为唯一真源**（与后端应用一致），
    例如 mysql+pymysql://root:pw@localhost:3306/gold_analysis。
    没有配 DATABASE_URL 时，退回下面这套旧约定：
        DB_HOST: 数据库主机 (默认: localhost)
        DB_PORT: 数据库端口 (默认: 3306)
        DB_USER: 数据库用户名 (默认: root)
        DB_PASSWORD: 数据库密码 (默认: root123)
        DB_NAME: 数据库名称 (默认: gold_analysis)
    SKIP_SEED: 设置为1跳过数据填充 (默认: 0)

    （曾经这两套配置各说各话：应用读 DATABASE_URL、本脚本读 DB_*，
      不一致时会把表建到另一个库上，且没有任何报错。）
"""

import os
import sys
import subprocess

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import mysql_connection_params  # noqa: E402

# 带库名的连接参数（用于建表、灌数据）
DB_PARAMS = mysql_connection_params(include_database=True)
DB_NAME = DB_PARAMS["database"]
SKIP_SEED = os.getenv('SKIP_SEED', '0') == '1'


def create_database_and_tables():
    """创建数据库和数据表"""
    import pymysql

    # 先不带库名连上去，把库建出来
    conn = pymysql.connect(**mysql_connection_params(include_database=False))

    print("✅ MySQL 连接成功!")

    cursor = conn.cursor()

    # 检查数据库是否存在
    cursor.execute("SHOW DATABASES LIKE %s", (DB_NAME,))
    result = cursor.fetchone()

    if result:
        print(f"✅ 数据库 '{DB_NAME}' 已存在")
    else:
        # 库名不能参数化（DDL 标识符），这里用反引号包住并拒绝可疑字符
        if not DB_NAME.replace("_", "").isalnum():
            raise ValueError(f"库名 {DB_NAME!r} 含非字母数字字符，拒绝执行")
        cursor.execute(
            f"CREATE DATABASE `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        print(f"✅ 数据库 '{DB_NAME}' 创建成功!")

    cursor.close()
    conn.close()

    # 读取并执行 schema.sql
    print("\n📋 创建数据表...")
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'schema.sql')
    with open(schema_path, 'r', encoding='utf-8') as f:
        sql = f.read()

    # schema.sql 不自带 CREATE DATABASE / USE（写死库名会让配置失效），
    # 这里靠上面的 database= 参数选库。
    conn = pymysql.connect(**DB_PARAMS)

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


def seed_database():
    """填充初始数据"""
    print("\n" + "=" * 60)
    print("🌱 开始填充初始数据...")
    print("=" * 60)
    
    try:
        # 检查 seed_data.py 是否存在
        if not os.path.exists('seed_data.py'):
            print("❌ 错误: seed_data.py 不存在")
            return False
        
        # 运行 seed_data.py
        result = subprocess.run(
            [sys.executable, 'seed_data.py'],
            capture_output=False,
            text=True
        )
        
        return result.returncode == 0
        
    except Exception as e:
        print(f"❌ 填充数据失败: {e}")
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("🚀 数据库初始化")
    print("=" * 60)
    print(f"数据库: {DB_PARAMS['host']}:{DB_PARAMS['port']}/{DB_NAME}")
    print("-" * 60)
    
    try:
        # 1. 创建数据库和表
        create_database_and_tables()
        
        # 2. 填充初始数据（除非跳过）
        if not SKIP_SEED:
            success = seed_database()
            if not success:
                print("\n⚠️  数据填充失败，但数据库结构已创建")
                print("您可以稍后手动运行: python seed_data.py")
        else:
            print("\n⏭️  跳过数据填充 (SKIP_SEED=1)")
        
        print("\n" + "=" * 60)
        print("🎉 数据库初始化完成!")
        print("=" * 60)
        print("\n现在您可以启动后端服务了:")
        print("  python -m uvicorn app.main:app --reload")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
