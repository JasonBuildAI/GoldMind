<p align="center">
  <img src="docs\images\6779ac1d5f10d9ad61b395a725e21bbd.png" alt="GoldMind Logo" width="600">
</p>

<h1 align="center">🥇 GoldMind</h1>

<p align="center">
  <strong>面向国际黄金市场的 AI 数据分析引擎</strong><br>
  <em>An AI Data Analysis Engine for the International Gold Market</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Docker-部署就绪-2496ED?style=flat-square&logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/version-v1.0.0-brightgreen?style=flat-square" alt="Version">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/React-19-61DAFB?style=flat-square&logo=react" alt="React">
</p>

<p align="center">
  <a href="./README_EN.md">English</a> | <strong>中文文档</strong>
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> •
  <a href="#-项目概述">项目概述</a> •
  <a href="#-实际的分析链路">分析链路</a> •
  <a href="#-系统展示">系统展示</a> •
  <a href="#-工作流程">工作流程</a> •
  <a href="#-贡献">贡献</a> •
  <a href="#-联系作者">联系作者</a>
</p>

---

## ⚡ 项目概述

**GoldMind** 是一个黄金市场分析看板：自动采集金价与美元指数，用大语言模型基于最近的新闻生成多空对照、机构观点、投资策略与市场总结，并以量化引擎基于四类影响因素（货币政策与利率 / 避险与信用 / 供需结构 / 市场与技术面）预测 1 / 5 / 20 / 60 / 250 个交易日（日内～一周、1～3 个月、6～18 个月）的方向、目标价与情景（全部出自同一份校准分布，未校准的因子偏向单列一行），以一张单页的**浅色研究简报**呈现 —— 六节（行情 / 多空对照 / 机构观点 / 投资策略 / 量化预测 / 总结）全部左对齐，无渐变、无阴影、无卡片套件；数字表格化，红涨绿跌，且方向同时给符号与文字。

当前由**小米 MiMo**（`mimo-v2.6-flash`）单模型驱动，所有 LLM 客户端统一经 `backend/app/services/llm_provider.py` 构造。

> 你只需：打开页面  
> GoldMind 将返回：当天金价、美元指数，以及基于最近 24 小时新闻生成的多空分析与策略建议

> 📌 产品边界与已知限制见 [`docs/00-产品方向.md`](docs/00-产品方向.md)。**该文档中标记为「目标」的能力尚未实现，请勿当作已有功能。**

### 🎯 实现说明（请以代码为准）

以下四点是对早期文档中技术描述的更正 —— 早期描述与实际实现不符：

**关于「多智能体」**  
分析由 4 个**独立的单轮 LLM 调用**完成，不是 Agent 协作：每个分析服务把上下文拼进 prompt，调用一次 `llm.invoke(prompt)`，再解析返回的 JSON。没有工具调用循环、没有 Agent 间通信。早期文档提到的 `backend/app/agents/` 包**从未被实例化，已删除**。

**关于「实时搜索」**  
设计上通过 MiMo 的 `web_search` 工具检索机构研报与新闻。但当前使用的 Token Plan `tp-` key 调用该工具一律返回 `HTTP 400`（实测，见 `backend/scripts/smoke_mimo.py`），因此搜索不可用时回退到数据库与 RSS 新闻，并且**不会**编造机构目标价。

**关于「RAG」**  
没有向量库、没有 embedding、没有检索步骤。历史价格与新闻是直接拼进 prompt 的上下文。

**关于「ReAct」**  
未实现，没有 Thought / Action / Observation 循环。

**关于「某一节显示暂不可用」**
分析模型是推理模型，`max_tokens=4096` 同时覆盖思考与正文。投资策略要求三档策略的完整
JSON，输出逼近上限时会被截断、解析失败，于是按红线返回空内容 —— 页面如实显示
「投资策略暂不可用」，而不是摆一份编造的策略。看涨 / 看跌因子偶发为空时同理，点
「重新分析」重试即可。

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
| 机构观点 | 最近 30 天新闻 +（搜索） | 四家机构最近一次可核实的预测（含日期与来源） |
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

### 报头与行情
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/dashboard.jpeg" alt="报头与行情" width="800">
</p>

### 走势与关键数据
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/price-chart.jpeg" alt="走势图与关键数据" width="800">
</p>

### 多空对照
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-up.jpeg" alt="看涨因素" width="400">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/news-analysis-down.jpeg" alt="看跌因素" width="400">
</p>

### 机构观点
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/institutional-views.jpeg" alt="机构观点" width="800">
</p>

> 本机部署的 MiMo key 未开通联网搜索（调用返回 `HTTP 400`）；此时回退到新闻窗口，
> 提取每家机构**最近一次可核实**的预测并标注预测日期。一条都找不到才显示「暂无」，
> 而且空目标价不会覆盖库里已有的真实记录。

### 投资策略
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/investment-advice.jpeg" alt="投资策略" width="800">
</p>

> 上图为分析尚未落库时的状态：模型输出被 token 上限截断时，这一节如实说明「暂不可用」，
> 而不是摆一份内置策略。

### 总结
<p align="center">
  <img src="https://raw.githubusercontent.com/JasonBuildAI/GoldMind/main/docs/images/screenshots/market-summary.jpeg" alt="市场总结" width="800">
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

# 这一项是**唯一真源**：后端应用、init_db.py、seed_data.py、scripts/*.py 都从这里取。
# 不要再单独配 DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME —— 两套配置一旦不一致，
# 建表灌数据的库和应用读写的库就不是同一个，而且不会有任何报错。
# （那两个脚本只在 DATABASE_URL 缺失时才退回 DB_*。）

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

> **版本是钉死的**（`==`，不是 `>=`），钉的是测试实际跑过的版本。
> 松散范围意味着 `pip install` 随时可能拉到带破坏性变更的新大版本，
> 而问题要到部署时才暴露。前端同理 —— `package-lock.json` 已入库，
> 用 `npm ci` 而不是 `npm install`。

**前端依赖：**

```bash
cd app

# 安装依赖（用 ci 而不是 install：严格按 lockfile，可重现）
npm ci
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
# 复制示例配置文件（后端应用自己的变量，比如 MIMO_API_KEY）
cp backend/.env.example backend/.env

# 编辑 backend/.env，填入必要的 API 密钥
```

**Docker 部署的变量分两处，别放错：**

```bash
# ============================================
# ① 项目根目录的 .env —— 供 docker-compose 做变量插值
# ============================================
# compose 里的 ${MYSQL_ROOT_PASSWORD:-goldmind123} 只认**宿主环境**和
# **项目根目录的 .env**，不认 `env_file:` 指定的 backend/.env。
# 放错地方的结果是 MySQL 用默认密码、后端却按你写的密码去连，连不上。
MYSQL_ROOT_PASSWORD=your_secure_password

# ============================================
# ② backend/.env —— 供容器内的应用读取
# ============================================
# 小米 MiMo - 推理与联网搜索统一使用同一个 key
# 获取地址: https://platform.xiaomimimo.com/
# 注意：Token Plan 条款限定仅可用于编程工具，用于本项目后端属于条款外用法，
# 详见 docs/00-产品方向.md 第四节。
MIMO_API_KEY=your_mimo_api_key_here
MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
MIMO_MODEL=mimo-v2.6-flash
```

> 💡 `docker-compose.yml` 会加载 `backend/.env` 作为容器环境（`env_file:`），
> 并在 `environment:` 里覆盖数据库连接与 `DEBUG` / `LOG_LEVEL`。
> **`DATABASE_URL` 不必写进 `backend/.env`** —— compose 会用
> `${MYSQL_ROOT_PASSWORD}` 拼好并覆盖它，写在那里也不会生效。
>
> 注意 `environment:` 的优先级高于 `env_file:`，所以那里**不要**写
> `- MIMO_API_KEY=${MIMO_API_KEY}`：项目根目录没有该变量时它会插值成空串，
> 反过来把 `backend/.env` 里配好的 key 覆盖掉。

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

> 💡 **提示**：首次访问时，页面显示「正在读取…」或「正在分析中」，说明后端仍在初始化数据
> 或首次分析尚未完成，请稍等片刻刷新页面。

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
python -m pytest tests/unit          # 单元：不依赖数据库与网络
python -m pytest tests/integration   # 集成：内存 SQLite + 假 LLM
python -m pytest tests/e2e           # 端到端：按真实使用顺序串起整条链路

# 换 MySQL 方言再跑一遍（改数据库相关代码后建议做）
# 生产用 MySQL，而 SQLite 与它在枚举存储、JSON 列、字符串比较大小写上都有差异 ——
# 「SQLite 全绿」不等于「MySQL 全绿」。必须指向**独立的测试库**：用例会清空所有表。
GOLDMIND_TEST_DATABASE_URL="mysql+pymysql://root:pw@localhost:3306/goldmind_test" \
    python -m pytest

# 静态检查：全量语法
python -m compileall -q app

# 数据库初始化（建库 + 建表 + 灌历史数据）
python init_db.py
SKIP_SEED=1 python init_db.py        # 只建库建表，不灌数据

# 修正旧库里的枚举列取值（幂等；只影响 schema.sql 早期版本建出来的库）
python scripts/fix_enum_columns.py --dry-run
python scripts/fix_enum_columns.py

# 量化因子引擎：老库升级到带 factor_observations / model_evaluations 的结构（幂等，只加不删）
python scripts/migrate_quant.py --dry-run    # 先看会做什么
python scripts/migrate_quant.py
# 回滚（删除两张新表与 predictions 的量化列，既有数据不动）
python scripts/migrate_quant.py --drop --yes

# 手动跑一轮因子抓取（首次回填 10 年；之后是增量）
python -c "from app.database import SessionLocal; from app.services.quant.sync import run_sync; db=SessionLocal(); print(run_sync(db, force=True).to_dict()); db.close()"
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

# 单元 + 集成测试（vitest + Testing Library）
npm test

# 浏览器端到端测试（Playwright）—— 需要先 npm run build
npm run test:e2e

# 本地开发
npm run dev
```

### 浏览器端到端测试

`npm run test:e2e` 会真的把三个服务拉起来，再由真实浏览器访问：

1. 假 LLM 服务（`backend/scripts/dev_mock_llm.py`，OpenAI 协议兼容，不消耗额度）
2. 真后端（uvicorn + SQLite，数据由 `backend/scripts/dev_seed_sqlite.py` 准备）
3. 构建产物（`vite preview`，经代理把 `/api` 转发给后端）

它复用本机已安装的 Chrome，**不下载** Playwright 自带浏览器。若你的 Python
不在 `PATH` 上，用 `E2E_PYTHON` 指定解释器：

```powershell
$env:E2E_PYTHON = "path\to\python.exe"
cd app
npm run build
npm run test:e2e
```

> 端到端测试用独立的数据库与缓存目录（`backend/e2e.db`、`backend/e2e-cache/`），
> 不会碰你的开发数据；两者都已被 `.gitignore` 忽略。

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

- **`git push` 报 `schannel: failed to receive handshake, SSL/TLS connection failed`**
  —— Windows 上 git 默认用系统的 schannel 做 TLS，某些网络环境（尤其是走了本地
  代理时）握手会失败，而 `curl` 访问同一地址却是通的。换成 OpenSSL 后端即可：

  ```bash
  git -c http.sslBackend=openssl push origin main
  # 想长期生效：git config --global http.sslBackend openssl
  ```

---

## 🗺️ 文档地图

「改什么 → 读哪份」的唯一映射表。

| 文档 | 讲什么 | 什么时候读 |
|---|---|---|
| [`AGENTS.md`](AGENTS.md) | 怎么干活：规矩、闸门、流程 | 动手前必读 |
| [`docs/00-产品方向.md`](docs/00-产品方向.md) | 产品要做什么；**现状 vs 目标** | 改需求、加功能前 |
| [`README.md`](README.md) | 目录、命令、配置（本文件） | 找命令 / 配置时 |
| [`docs/10-密钥与隐私.md`](docs/10-密钥与隐私.md) | 密钥规则与历史泄漏处理 | 动配置 / 密钥前 |
| [`docs/20-前端设计规范.md`](docs/20-前端设计规范.md) | 前端视觉语言：令牌、排版、组件、界面文案规则 | 改前端界面前 |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | 架构设计 | 动系统结构前 |
| [`docs/API.md`](docs/API.md) | 接口规范 | 改接口前 |
| [`docs/specs/`](docs/specs/) | 各轮改动的 spec 与 plan（过程记录，不是第二权威） | 追溯某轮决定时 |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | 贡献流程 | 提 PR 前 |

> ⚠️ `docs/API.md` 是早期版本，**尚未与当前实现对齐**：它仍以 `/api/analysis/*`
> 作为前缀（实际全部挂在 `/api/gold` 下），响应示例里的字段名也与代码不符
> （例如 `/gold/stats` 实际返回 `ytd_return` / `volatility`，文档写的是
> `ytd_change` / `volatility_range`）。改接口前请以代码为准，该文档待校正。

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
| 机构观点 | `app/services/institution_prediction_service.py` | 最近 30 天新闻 + 联网搜索 | 四家机构最近一次可核实的预测（含日期与来源） |
| 投资建议 | `app/services/investment_advice_service.py` | 市场状态 + 多空因子 + 机构观点 | 三档策略 + 风险提示 |
| 市场总结 | `app/services/market_summary_service.py` | 上述全部 | 核心逻辑 + 风险 + 综合判断 |

**模型**：`mimo-v2.6-flash`，可用 `MIMO_MODEL` 覆盖。

**降级行为**：任一服务在数据源或联网搜索不可用时，返回明确的「不可用」状态并回退到
数据库 / RSS 内容，**不会**编造数据。

前端在拿不到数据时**显示「暂不可用」并说明原因**，不摆任何内置的数字或结论。
这条以前只是写在文档里：各 section 其实各自带了一份写死的兜底数据
（金价 2823、机构目标价 5400/5000/4500/2700、14 个点的价格序列……），
接口一失败就把它们当成真实内容渲染出来。那些常量已全部删除，
并由测试钉住「失败时不得出现内置文案」。

**已删除**：早期存在的 `backend/app/agents/` 包（`BaseAgent` /
`MarketAnalyzerAgent` / `NewsAnalyzerAgent`）从未被任何地方实例化，已移除。

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
