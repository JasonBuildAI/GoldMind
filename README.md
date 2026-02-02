<p align="center">
  <img src="docs\images\6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>基于多智能体协作的下一代黄金市场智能分析引擎</strong><br>
  <em>A Next-Generation Multi-Agent Gold Market Intelligence Analysis Engine</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Docker-部署就绪-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/version-v1.0.0-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <a href="./README_EN.md">English</a> | <strong>中文文档</strong>
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> •
  <a href="#-项目概述">项目概述</a> •
  <a href="#-agent原理">Agent原理</a> •
  <a href="#-系统展示">系统展示</a> •
  <a href="#-工作流程">工作流程</a> •
  <a href="#-贡献">贡献</a>
</p>

---

## ⚡ 项目概述

**GoldMind** 是一个基于 **LangChain Multi-Agent 架构** 的黄金市场智能分析平台，融合 **ReAct 推理框架**、**RAG（检索增强生成）** 与 **多模型协作** 技术，为投资者提供深度市场洞察。

系统基于 **GLM-4-Plus**（智谱AI）与 **DeepSeek-V3** 双引擎驱动，通过专用 Agent 分工协作：**Market Analysis Agent** 负责技术面量化分析，**News Intelligence Agent** 基于实时搜索进行舆情解析，**Institution Research Agent** 追踪主流机构观点，**Investment Advisory Agent** 融合多源信息生成策略建议。各 Agent 通过结构化输出实现结果融合，形成对黄金市场的全景认知。

> 你只需：关注黄金市场动态，系统自动采集数据并分析  
> GoldMind 将返回：融合价格走势、市场情绪、机构观点的综合分析报告

### 🎯 核心技术架构

**🚀 LangChain Multi-Agent 框架**  
基于 LangChain 构建的模块化 Agent 系统，每个 Agent 封装独立的分析逻辑与工具链。通过 `BaseAgent` 抽象基类统一 LLM 调用接口，支持 DeepSeek 与智谱AI 双模型后端灵活切换。Agent 间通过结构化数据传递实现协作，避免单点失效，提升系统鲁棒性。

**🌐 GLM-4-Plus 实时搜索增强**  
集成智谱AI **GLM-4-Plus** 模型的 **Web Search** 能力，实现对机构研报、财经新闻、市场动态的实时检索与理解。相比传统静态数据源，系统能够捕捉最新市场变化，为分析提供时效性信息支撑。

**🧠 DeepSeek 深度推理与多 Agent 融合**  
采用 **DeepSeek-V3** 作为核心推理引擎，结合其强大的长文本理解与逻辑推理能力，对多 Agent 输出进行融合分析。通过设计特定的融合 Prompt，将技术面、基本面、情绪面、机构观点四维信息整合，生成具备逻辑一致性的投资判断。

**📊 ReAct 推理 + RAG 检索增强**  
在 Agent 内部实现 **ReAct（Reasoning + Acting）** 推理模式：Thought（分析当前状态）→ Action（调用工具获取数据）→ Observation（整合观察结果）→ Final Answer（输出结论）。结合 RAG 技术从本地数据库检索历史价格、新闻舆情等上下文信息，增强 LLM 的事实性与准确性。

---

## 🌟 我们的愿景

**GoldMind** 致力于通过社区共同努力，打造一个**真实可用的 AI Agent 国际黄金市场数据分析与价格预测平台**。

我们希望通过技术创新：
- 📉 **减少信息差** - 让每位投资者都能获取专业级的市场分析
- 🛡️ **增强风险抵抗能力** - 提供多维度的风险评估和预警
- 💡 **切实可行的投资建议** - 基于数据和逻辑，给出可操作的投资策略

> 🤝 **期望您的加入！** 无论是代码贡献、功能建议还是使用反馈，都将成为推动项目前进的重要力量。

---

## 📸 系统展示

### 首页仪表盘
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/dashboard.jpeg" alt="Dashboard" width="800">
</p>

### 实时价格走势
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/price-chart.jpeg" alt="Price Chart" width="800">
</p>

### 多空因素分析
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-up.jpeg" alt="Bullish Factors" width="400">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-down.jpeg" alt="Bearish Factors" width="400">
</p>

### 机构观点
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/institutional-views.jpeg" alt="Institutional Views" width="800">
</p>

### 投资建议
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/investment-advice.jpeg" alt="Investment Advice" width="800">
</p>

### 市场总结
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/market-summary.jpeg" alt="Market Summary" width="800">
</p>

---

## 🚀 快速开始

### 前置要求

| 工具 | 版本要求 | 说明 | 安装检查 |
|------|----------|------|----------|
| Node.js | 18+ | 前端运行环境，包含 npm | `node -v` |
| Python | 3.11 - 3.12 | 后端运行环境 | `python --version` |
| MySQL | 8.0+ | 数据存储 | `mysql --version` |

### 方式一：本地开发（推荐）

#### 1. 配置环境变量

```bash
# 复制示例配置文件
cd backend
cp .env.example .env

# 编辑 .env 文件，填入必要的 API 密钥
```

**必需的环境变量：**

```bash
# ============================================
# 数据库配置
# ============================================
# MySQL数据库连接URL
DATABASE_URL=mysql+pymysql://root:your_password@localhost:3306/gold_analysis

# ============================================
# AI API 密钥配置
# ============================================
# 智谱AI (Zhipu AI) - 用于实时搜索、新闻分析、机构预测
# 获取地址: https://open.bigmodel.cn/
ZHIPU_API_KEY=your_zhipu_api_key_here

# DeepSeek - 用于深度推理、投资建议生成
# 获取地址: https://www.deepseek.com/
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

#### 2. 安装依赖

**后端依赖：**

```bash
cd backend

# 创建虚拟环境（推荐）
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

**前端依赖：**

```bash
cd app

# 安装依赖
npm install
```

#### 3. 初始化数据库

```bash
cd backend

# 确保MySQL服务已启动

# 初始化数据库（自动创建数据库、数据表，并填充2025年至今的历史数据）
python init_db.py
```

**数据初始化说明：**

`init_db.py` 会自动完成以下操作：
1. 创建数据库 `gold_analysis`（如果不存在）
2. 创建所有数据表结构
3. **自动获取并填充历史数据**（2025年1月1日至今）
   - 黄金价格数据：开盘价、最高价、最低价、收盘价
   - 美元指数数据：开盘价、最高价、最低价、收盘价

**数据源优先级（国内优先）：**
- 黄金数据：新浪财经 → 东方财富 → Yahoo Finance
- 美元指数：新浪财经 → 东方财富 → Yahoo Finance

> 💡 **提示**：脚本会自动尝试多个数据源，确保国内用户也能成功获取数据。如果所有数据源都失败，您可以稍后再运行 `python seed_data.py` 重试。

**跳过数据填充（仅创建表结构）：**
```bash
SKIP_SEED=1 python init_db.py
```

**手动填充数据：**
```bash
# 如果初始化时跳过数据填充，或需要更新数据
python seed_data.py
```

#### 4. 启动服务

**同时启动前后端（在项目根目录执行）：**

```bash
# Windows PowerShell
.\start_all.ps1

# 或者分别启动
```

**单独启动：**

```bash
# 后端（在 backend 目录）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端（在 app 目录）
npm run dev
```

**服务地址：**
- 前端: http://localhost:5173
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

### 方式二：Docker部署

#### 前置要求

| 工具 | 版本要求 | 说明 | 安装检查 |
|------|----------|------|----------|
| Docker | 20.10+ | 容器化平台 | `docker --version` |
| Docker Compose | 2.0+ | 多容器编排 | `docker compose version` |

> ⚠️ **网络要求**：需要能够访问 Docker Hub 下载镜像。国内用户可能需要配置 VPN/代理。

#### 1. 配置环境变量

```bash
# 复制示例配置文件
cp backend/.env.example backend/.env

# 编辑 .env 文件，填入必要的 API 密钥
```

**必需的环境变量：**

```bash
# ============================================
# 数据库配置（Docker内部使用）
# ============================================
MYSQL_ROOT_PASSWORD=your_secure_password
DATABASE_URL=mysql+pymysql://root:your_secure_password@mysql:3306/gold_analysis

# ============================================
# AI API 密钥配置
# ============================================
# 智谱AI (Zhipu AI) - 用于实时搜索、新闻分析、机构预测
# 获取地址: https://open.bigmodel.cn/
ZHIPU_API_KEY=your_zhipu_api_key_here

# DeepSeek - 用于深度推理、投资建议生成
# 获取地址: https://www.deepseek.com/
DEEPSEEK_API_KEY=your_deepseek_api_key_here
```

> 💡 **注意**：`docker-compose.yml` 已配置自动加载 `backend/.env` 文件，无需手动设置环境变量。

#### 2. 启动服务

```bash
# 构建并启动所有服务（前端 + 后端 + 数据库）
docker-compose up -d --build

# 查看服务状态
docker-compose ps

# 查看日志（观察数据初始化进度）
docker-compose logs -f backend
```

**国内用户网络配置（如无法下载镜像）：**

如果使用 Clash/V2Ray 等代理工具：

1. 开启系统代理或 TUN 模式
2. 在 Docker Desktop → Settings → Resources → Proxies 中配置：
   - HTTP Proxy: `http://127.0.0.1:7890`
   - HTTPS Proxy: `http://127.0.0.1:7890`
3. Apply & Restart
4. 重试 `docker-compose up -d --build`

> ⚠️ 如果网络问题无法解决，建议使用**本地开发方式**（方式一）。

**首次启动说明：**

Docker 部署会自动完成以下初始化：
1. ✅ 创建 MySQL 数据库和数据表
2. ✅ **自动获取并填充历史数据**（2025年至今的黄金和美元指数数据）
3. ✅ 启动后端服务

数据获取过程可能需要 1-3 分钟，请观察日志等待初始化完成。

#### 3. 访问应用

**服务地址：**
- 前端: http://localhost
- 后端API: http://localhost:8000
- API文档: http://localhost:8000/docs

> 💡 **提示**：首次访问时，如果看到 "数据加载中"，说明后端仍在初始化数据，请稍等片刻刷新页面。

#### 4. 常用命令

```bash
# 停止服务
docker-compose down

# 停止并删除数据卷（清空数据库）
docker-compose down -v

# 重启服务
docker-compose restart

# 进入后端容器
docker exec -it goldmind_backend /bin/bash

# 进入数据库容器
docker exec -it goldmind_mysql mysql -uroot -p
```

---

## 🔄 工作流程

1. **数据采集层**：实时金价API抓取 & 新闻舆情Web搜索 & 机构研报智能检索
2. **多Agent并行分析**：Market Analysis Agent技术面量化 & News Intelligence Agent情绪解析 & Institution Research Agent观点追踪
3. **ReAct推理决策**：各Agent基于RAG检索历史数据 → Thought分析 → Action工具调用 → Observation整合 → Final Answer输出
4. **结果融合引擎**：DeepSeek-V3接收四维结构化数据 → 多源信息交叉验证 → 逻辑一致性校验 → 生成综合投资判断
5. **智能报告生成**：Investment Advisory Agent整合所有分析结果 → 生成策略建议与风险提示 → 结构化JSON响应前端可视化

---

## 🤖 Agent原理

### 📈 市场分析 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + 智谱AI GLM-4-Plus |
| **大模型** | 智谱AI GLM-4-Plus (支持实时搜索) |
| **架构** | ReAct推理架构 + 实时搜索插件 |
| **功能逻辑** | 基于24小时新闻与市场数据，智能提取看涨/看空因子 |
| **数据来源** | 智谱AI实时搜索 + 腾讯财经API + MySQL历史数据 |

---

### 🏛️ 机构预测 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + 智谱AI GLM-4-Plus |
| **大模型** | 智谱AI GLM-4-Plus (支持实时搜索) |
| **架构** | 专用Agent架构 + Web Search实时检索插件 |
| **功能逻辑** | 实时抓取高盛、瑞银、摩根士丹利、花旗等主流机构最新黄金预测观点，提取目标价位与逻辑依据 |
| **数据来源** | 智谱AI实时搜索 + 机构官方研报 + 权威财经新闻 |

---

### � 新闻分析 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + 智谱AI GLM-4-Plus |
| **大模型** | 智谱AI GLM-4-Plus (支持实时搜索) |
| **架构** | 实时搜索 + 情感分析 + 多空因子提取 |
| **功能逻辑** | 24小时滚动抓取黄金市场相关新闻，分析情感倾向，智能提取看涨/看空因子及其市场影响权重 |
| **数据来源** | 智谱AI实时搜索 + 新浪财经 + 腾讯财经 + 金十数据 |

---

### 💡 投资建议 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + DeepSeek-V3 + RAG |
| **大模型** | DeepSeek-V3 (671B参数) |
| **架构** | RAG检索增强生成 + 多源分析结果融合 |
| **功能逻辑** | 综合分析市场分析Agent、机构预测Agent、新闻分析Agent的输出结果，生成个性化投资策略与风险提示 |
| **数据来源** | 市场分析Agent结构化输出 + 机构预测Agent观点汇总 + 新闻分析Agent情绪数据 |

---

### 🧠 综合分析 Agent

| 属性 | 详情 |
|------|------|
| **技术栈** | LangChain + DeepSeek-V3 + 多Agent协作 |
| **大模型** | DeepSeek-V3 (671B参数) |
| **架构** | 多Agent结果融合 + 深度推理生成 + 结构化输出 |
| **功能逻辑** | 整合所有Agent分析结果，进行交叉验证与逻辑一致性校验，生成全面市场认知与投资判断，输出包含技术面、基本面、情绪面、机构观点的四维综合分析报告 |
| **数据来源** | 市场分析Agent + 机构预测Agent + 新闻分析Agent + 投资建议Agent |

---

## 🤝 贡献

我们欢迎所有形式的贡献！请查看我们的[贡献指南](./CONTRIBUTING.md)了解如何参与项目。

### 贡献者

<a href="https://github.com/JasonBuildAI/GoldMind/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=JasonBuildAI/GoldMind" alt="Contributors" />
</a>

---

## 📄 许可证

本项目采用 [MIT 许可证](./LICENSE) 开源。

---

## 🙏 致谢

- [DeepSeek](https://deepseek.com/) - 提供AI模型支持
- [智谱AI](https://www.zhipuai.cn/) - 提供大语言模型API
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能Web框架
- [React](https://react.dev/) - 前端UI框架

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/JasonBuildAI">JasonBuildAI</a></sub>
</p>
