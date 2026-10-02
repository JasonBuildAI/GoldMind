#!/bin/bash
# Docker容器入口脚本
# 功能：等待数据库就绪 → 直接启动后端服务

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

# 建表 / 自动迁移 / 历史回填 / 首轮分析全部由应用的启动引导完成
# （app/bootstrap.py，挂在 FastAPI lifespan 上）。入口脚本不再跑 init_db.py ——
# 人工脚本已降级为可选的运维工具；填好 .env 即完成配置。
echo "✅ 建表 / 迁移 / 回填 / 首轮分析由启动引导自动完成，进度见 /health 的 bootstrap 字段"

echo ""
echo "=========================================="
echo "🎯 启动后端服务"
echo "=========================================="

# 启动后端服务
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
