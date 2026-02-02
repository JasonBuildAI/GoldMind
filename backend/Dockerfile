FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 确保入口脚本可执行
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000

# 使用入口脚本启动
ENTRYPOINT ["./docker-entrypoint.sh"]
