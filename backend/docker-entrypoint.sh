#!/bin/bash
# Docker容器入口脚本
# 功能：等待数据库就绪 → 运行数据初始化 → 启动后端服务

set -e

echo "=========================================="
echo "🚀 GoldMind 后端服务启动"
echo "=========================================="

# 数据库连接信息
DB_HOST="${DB_HOST:-mysql}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-goldmind123}"
DB_NAME="${DB_NAME:-gold_analysis}"

echo "📡 等待数据库连接..."
echo "  主机: $DB_HOST:$DB_PORT"

# 等待MySQL就绪
until python -c "
import pymysql
try:
    conn = pymysql.connect(
        host='$DB_HOST',
        port=$DB_PORT,
        user='$DB_USER',
        password='$DB_PASSWORD',
        charset='utf8mb4'
    )
    conn.close()
    exit(0)
except Exception as e:
    print(f'等待中: {e}')
    exit(1)
" 2>/dev/null; do
    echo "  ⏳ 数据库尚未就绪，等待5秒后重试..."
    sleep 5
done

echo "✅ 数据库连接成功"

# 运行数据库初始化（创建表结构 + 填充数据）
echo ""
echo "📊 初始化数据库..."
cd /app
python init_db.py

if [ $? -eq 0 ]; then
    echo "✅ 数据库初始化完成"
else
    echo "⚠️  数据库初始化出现问题，但将继续启动服务"
fi

echo ""
echo "=========================================="
echo "🎯 启动后端服务"
echo "=========================================="

# 启动后端服务
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
