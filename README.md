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
  <a href="#-贡献">贡献</a> •
  <a href="#-联系作者">联系作者</a>
</p>

---

## ⚡ 项目概述

**GoldMind** 是一个黄金市场分析看板：自动采集金价与美元指数，用大语言模型基于最近的新闻生成多空因子、机构观点、投资建议与市场总结，最后以单页看板呈现。

当前由**小米 MiMo**（`mimo-v2.6-flash`）单模型驱动，所有 LLM 客户端统一经 `backend/app/services/llm_provider.py` 构造。

> 你只需：打开页面  
> GoldMind 将返回：当天金价、美元指数，以及基于最近 24 小时新闻生成的多空分析与策略建议

> 📌 产品边界与已知限制见 [`docs/00-产品方向.md`](docs/00-产品方向.md)。**该文档中标记为「目标」的能力尚未实现，请勿当作已有功能。**

### 🎯 实现说明（请以代码为准）

以下四点是对早期文档中技术描述的更正 —— 早期描述与实际实现不符：

**关于「多智能体」**  
分析由 4 个**独立的单轮 LLM 调用**完成，不是 Agent 协作：每个分析服务把上下文拼进 prompt，调用一次 `llm.invoke(prompt)`，再解析返回的 JSON。没有工具调用循环、没有 Agent 间通信。`backend/app/agents/` 包目前**没有任何地方实例化**。

**关于「实时搜索」**  
设计上通过 MiMo 的 `web_search` 工具检索机构研报与新闻。但当前使用的 Token Plan `tp-` key 调用该工具一律返回 `HTTP 400`（实测，见 `backend/scripts/smoke_mimo.py`），因此搜索不可用时回退到数据库与 RSS 新闻，并且**不会**编造机构目标价。

**关于「RAG」**  
没有向量库、没有 embedding、没有检索步骤。历史价格与新闻是直接拼进 prompt 的上下文。

**关于「ReAct」**  
未实现，没有 Thought / Action / Observation 循环。

### 🧩 实际的分析链路

```
行情采集 ──► MySQL ──┐
RSS 新闻 ──► MySQL ──┼──► 拼装 prompt ──► llm.invoke() ──► 解析 JSON ──► 缓存 ──► 前端看板
                     │
                     └──► （可选）MiMo web_search，不可用时跳过
```

| 分析服务 | 输入 | 输出 |
|---|---|---|
| 看涨因子 | 最近 24h 新闻 + 金价 | 5 个看涨因子 |
| 看跌因子 | 最近 24h 新闻 + 金价 | 5 个看跌因子 |
| 机构观点 | 最近 24h 新闻 +（搜索） | 四大机构目标价与理由 |
| 投资建议 | 市场状态 + 多空因子 + 机构观点 | 保守/均衡/机会三档策略 |
| 市场总结 | 上述全部 | 核心逻辑、风险、综合判断 |

---

## 🌟 我们的愿景

**GoldMind** 致力于通过社区共同努力，打造一个**真实可用的 AI Agent 国际黄金市场数据分析与价格预测平台**。

我们希望通过技术创新：
- 📉 **减少信息差** - 让每位投资者都能获取专业级的市场分析
- 🛡️ **增强风险抵抗能力** - 提供多维度的风险评估和预警
- 💡 **切实可行的投资建议** - 基于数据和逻辑，给出可操作的投资策略

> 🤝 **期望您的加入！** 无论是代码贡献、功能建议还是使用反馈，都将成为推动项目前进的重要力量。

如果该项目对您有所帮助或启发，您的一个 ⭐ **Star** 是对我们最好的肯定！

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
# 小米 MiMo - 推理与联网搜索统一使用同一个 key
# 获取地址: https://platform.xiaomimimo.com/
# 注意：Token Plan 条款限定仅可用于编程工具，用于本项目后端属于条款外用法，
# 详见 docs/00-产品方向.md 第四节。
MIMO_API_KEY=your_mimo_api_key_here
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.6-flash
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
# 小米 MiMo - 推理与联网搜索统一使用同一个 key
# 获取地址: https://platform.xiaomimimo.com/
# 注意：Token Plan 条款限定仅可用于编程工具，用于本项目后端属于条款外用法，
# 详见 docs/00-产品方向.md 第四节。
MIMO_API_KEY=your_mimo_api_key_here
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.6-flash
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

## 🧪 常用命令

**闸门命令的唯一真源。** 改完代码必须全部跑绿（规矩见 [`AGENTS.md`](AGENTS.md)）。

### 后端

```bash
cd backend

# 安装依赖（首次）
pip install -r requirements.txt -r requirements-dev.txt

# 测试 —— 全档闸门
python -m pytest

# 只跑某一层
python -m pytest tests/unit
python -m pytest tests/integration

# 静态检查：全量语法
python -m compileall -q app
```

### 前端

```bash
cd app

# 安装依赖
npm ci

# 构建 + 类型检查 —— 全档闸门
npm run build

# 静态检查
npm run lint

# 本地开发
npm run dev
```

### 端到端冒烟（真实调用 LLM）

```bash
cd backend
python scripts/smoke_mimo.py
```

> ⚠️ 需要 `backend/.env` 已配置 `MIMO_API_KEY`，且会真实消耗额度。

### 排障

- **httpx 报 `Invalid port: ':1]'` 或 `Missing dependencies for SOCKS support`**
  —— 本机设置了系统代理（`ALL_PROXY` / `HTTP_PROXY` 等），或 `NO_PROXY` 里含
  `[::1]`，httpx 无法解析这些值。跑测试前先清掉：

  ```powershell
  $env:ALL_PROXY=''; $env:HTTP_PROXY=''; $env:HTTPS_PROXY=''; $env:NO_PROXY=''
  ```

- **测试报 `no such table`** —— 测试用的是内存 SQLite，正常不该出现；
  若出现，检查是否绕过了 `backend/tests/conftest.py` 的夹具。

---

## 🗺️ 文档地图

「改什么 → 读哪份」的唯一映射表。

| 文档 | 讲什么 | 什么时候读 |
|---|---|---|
| [`AGENTS.md`](AGENTS.md) | 怎么干活：规矩、闸门、流程 | 动手前必读 |
| [`docs/00-产品方向.md`](docs/00-产品方向.md) | 产品要做什么；**现状 vs 目标** | 改需求、加功能前 |
| [`README.md`](README.md) | 目录、命令、配置（本文件） | 找命令 / 配置时 |
| [`docs/10-密钥与隐私.md`](docs/10-密钥与隐私.md) | 密钥规则与历史泄漏处理 | 动配置 / 密钥前 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 架构设计 | 动系统结构前 |
| [`docs/API.md`](docs/API.md) | 接口规范 | 改接口前 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 贡献流程 | 提 PR 前 |

> ⚠️ `docs/ARCHITECTURE.md` 与 `docs/API.md` 是早期版本，**尚未与当前实现对齐**
> （例如它们仍描述 Redis、认证中间件、`/api/analysis/*` 前缀等不存在的内容）。
> 以代码与 `docs/00-产品方向.md` 为准；这两份文档待后续校正。

---

## 🔄 工作流程

1. **数据采集**：腾讯财经实时金价、新浪财经 ICE 美元指数；历史数据回填支持新浪 / 东方财富 / Yahoo 三源；新闻经 RSS 抓取
2. **持久化**：金价、美元指数、新闻写入 MySQL
3. **分析**：5 个分析服务各自拼装 prompt → 调用一次 MiMo → 解析 JSON
4. **缓存**：结果写入内存 + JSON 文件两级缓存（TTL 2 小时），供重启与多进程共享
5. **展示**：前端每 10 秒轮询行情接口，分析结果按需拉取

---

## 🤖 分析服务说明

早期文档把这 5 个服务描述为「LangChain Agent」，与实际实现不符。它们是**独立的单轮
LLM 调用**：彼此不通信、不共享状态，仅通过缓存与数据库间接关联。所有客户端统一经
`backend/app/services/llm_provider.py` 构造。

| 服务 | 代码位置 | 输入 | 输出 |
|---|---|---|---|
| 看涨因子 | `app/services/bullish_factor_service.py` | 最近 24h 新闻 + 金价 | 5 个看涨因子 + 总结 |
| 看跌因子 | `app/services/bearish_factor_service.py` | 最近 24h 新闻 + 金价 | 5 个看跌因子 + 总结 |
| 机构观点 | `app/services/institution_prediction_service.py` | 最近 24h 新闻 + 联网搜索 | 四大机构目标价与理由 |
| 投资建议 | `app/services/investment_advice_service.py` | 市场状态 + 多空因子 + 机构观点 | 三档策略 + 风险提示 |
| 市场总结 | `app/services/market_summary_service.py` | 上述全部 | 核心逻辑 + 风险 + 综合判断 |

**模型**：`mimo-v2.6-flash`，可用 `MIMO_MODEL` 覆盖。

**降级行为**：任一服务在数据源或联网搜索不可用时，返回明确的「不可用」状态并回退到
数据库 / RSS 内容，**不会**编造数据。前端在拿不到真实分析时会显示提示，而不是把
示例数据当成分析结果。

**历史遗留**：`backend/app/agents/` 下的 `BaseAgent` / `MarketAnalyzerAgent` /
`NewsAnalyzerAgent` 目前没有任何地方实例化。

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

- [小米 MiMo](https://platform.xiaomimimo.com/) - 提供大语言模型与联网搜索能力
- [FastAPI](https://fastapi.tiangolo.com/) - 高性能Web框架
- [React](https://react.dev/) - 前端UI框架

---

## 📧 联系作者

如果您有任何问题、建议或合作意向，欢迎通过以下方式联系我们：

- 🐛 **问题与建议**：请在 [GitHub Issues](https://github.com/JasonBuildAI/GoldMind/issues) 提出

---

<p align="center">
  <sub>Built with ❤️ by <a href="https://github.com/JasonBuildAI">JasonBuildAI</a></sub>
</p>
