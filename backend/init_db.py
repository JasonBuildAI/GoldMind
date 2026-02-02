"""数据库初始化脚本"""
import pymysql
import sys

# 连接MySQL
try:
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='root123',
        port=3306,
        charset='utf8mb4'
    )
    print("✅ MySQL 连接成功!")
    
    cursor = conn.cursor()
    
    # 检查数据库是否存在
    cursor.execute("SHOW DATABASES LIKE 'gold_analysis'")
    result = cursor.fetchone()
    
    if result:
        print("✅ 数据库 'gold_analysis' 已存在")
    else:
        # 创建数据库
        cursor.execute("CREATE DATABASE gold_analysis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        print("✅ 数据库 'gold_analysis' 创建成功!")
    
    cursor.close()
    conn.close()
    
    # 读取并执行 schema.sql
    print("\n📋 创建数据表...")
    with open('schema.sql', 'r', encoding='utf-8') as f:
        sql = f.read()
    
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='root123',
        database='gold_analysis',
        port=3306,
        charset='utf8mb4'
    )
    
    cursor = conn.cursor()
    
    # 执行SQL脚本
    for statement in sql.split(';'):
        statement = statement.strip()
        if statement:
            try:
                cursor.execute(statement)
            except Exception as e:
                if 'already exists' not in str(e).lower():
                    print(f"⚠️  注意: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("✅ 所有数据表创建成功!")
    print("\n🎉 数据库初始化完成!")
    
except Exception as e:
    print(f"❌ 错误: {e}")
    sys.exit(1)
