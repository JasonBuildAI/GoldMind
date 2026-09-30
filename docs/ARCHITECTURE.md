# GoldMind 架构

本文描述**当前实现**。产品要做什么见 [`00-产品方向.md`](./00-产品方向.md)，
命令与配置见 [`../README.md`](../README.md)，接口规范见 [`API.md`](./API.md)。

> 本文档曾是一份 765 行的「企业级架构白皮书」，其中大量内容（Redis、消息总线、
> WebSocket、K8s/Istio、WAF、认证中间件、RAG 引擎）在本项目中**并不存在**。
> 现按实现重写；**同一事实只保留一个权威来源**，能力清单以 `00-产品方向.md` 为准。

---

## 一、组件

```
┌──────────────┐   /api/**   ┌──────────────┐            ┌──────────────┐
│  浏览器      │ ──────────► │  FastAPI     │ ─────────► │  MySQL 8     │
│  React 19    │             │  (uvicorn)   │            │  或 SQLite   │
└──────────────┘             └──────┬───────┘            └──────────────┘
                                    │
                                    │ llm_provider（唯一出口）
                                    ▼
                             ┌──────────────┐
                             │  小米 MiMo   │
                             │ OpenAI 兼容  │
                             └──────────────┘
```

前端**始终使用相对路径** `/api/**`：

- 开发期由 `vite.config.ts` 的 `server.proxy` 转发到 `localhost:8000`
- 生产期由 `app/nginx.conf` 的 `location /api/` 转发到 `backend:8000`

因此浏览器不产生跨域请求，CORS 只需覆盖本地开发地址。

---

## 二、目录

```
GoldMind/
├── AGENTS.md              怎么干活：规矩、闸门、流程
├── README.md              目录、命令、配置（唯一真源）
├── docs/
│   ├── 00-产品方向.md      产品要做什么；现状 vs 目标
│   ├── 10-密钥与隐私.md    密钥规则与历史泄漏处理
│   ├── ARCHITECTURE.md    本文件
│   └── API.md             接口规范
├── app/                   前端
│   ├── src/sections/      页面区块（7 个）
│   ├── src/services/api.ts  唯一的 HTTP 出口
│   ├── src/contexts/      行情数据的 Provider 与轮询
│   ├── src/components/ui/  仅保留 tabs.tsx
│   └── e2e/               Playwright 端到端测试
└── backend/
    ├── app/
    │   ├── main.py        应用入口、限流、CORS
    │   ├── config.py      全部配置项（pydantic-settings）
    │   ├── database.py    引擎与会话（MySQL / SQLite 双支持）
    │   ├── models/        7 张表的 ORM 定义
    │   ├── routers/       4 个路由模块
    │   ├── services/      业务逻辑（见下）
    │   ├── agents/        历史遗留，无任何地方实例化
    │   └── utils/         rate_limit 等
    ├── scripts/           smoke_mimo / dev_mock_llm / dev_seed_sqlite
    └── tests/             unit / integration / e2e
```

---

## 三、分析流水线

**这不是多 Agent 系统。** 五个服务各自独立完成一次单轮 LLM 调用，彼此不通信：

```
MySQL(gold_news, gold_prices)
        │
        ▼
  拼装 prompt ──► llm.invoke() ──► 解析 JSON ──► 两级缓存 ──► HTTP 响应
        ▲
        └── 可选：MiMo web_search（当前凭证不可用，见下）
```

| 服务 | 文件 | 输出 |
|---|---|---|
| 看涨因子 | `services/bullish_factor_service.py` | 5 个因子 + 总结 |
| 看跌因子 | `services/bearish_factor_service.py` | 5 个因子 + 总结 |
| 机构观点 | `services/institution_prediction_service.py` | 四大机构目标价与理由 |
| 投资建议 | `services/investment_advice_service.py` | 三档策略 + 风险提示 |
| 市场总结 | `services/market_summary_service.py` | 核心逻辑 + 风险 + 综合判断 |

### 缓存未命中时的行为

`GET .../xxx-ai` 在缓存为空时**不会**调用模型：它返回内置默认内容并触发一次后台分析，
响应里带 `metadata.status = "analyzing"`。真正调用模型的是 `POST .../refresh`
或后台任务。前端据此用一行提示区分「真实分析」与「默认内容」。

---

## 四、LLM 接入

所有客户端必须经 `app/services/llm_provider.py` 构造，这是**唯一出口**。
换供应商、端点、模型只改 `config.py` 或 `.env`。

关键设计：

- **显式传入 httpx 客户端**（`http_client` + `http_async_client`，`trust_env` 由
  `MIMO_TRUST_ENV` 控制）。宿主若设置了 SOCKS 代理或 `NO_PROXY` 里含 `[::1]`，
  httpx 会在**构造阶段**抛异常；而 `ChatOpenAI` 会同时准备同步与异步两个客户端，
  只给同步的那个仍会去建默认异步客户端并读环境。异常会被上层吞掉并回退到默认值，
  表现为「页面上有分析内容，其实一次模型都没调用」。
- **`web_search` 工具当前不可用**：Token Plan 的 `tp-` key 调用它一律返回
  HTTP 400（实测见 `scripts/smoke_mimo.py`）。搜索不可用时回退到数据库与 RSS，
  **不编造数据**。

---

## 五、缓存

两级，实现在 `services/cache_manager.py`：

| 级别 | 位置 | 说明 |
|---|---|---|
| 内存 | 进程内 dict | 最快；多进程不共享 |
| 文件 | `CACHE_DIR/*.json` | 原子写入（临时文件 + rename）；重启后仍可命中 |

TTL 默认 2 小时。`CACHE_DIR` 可配置（默认 `backend/cache`），测试用独立目录。
缓存文件**不入库**（`.gitignore` 忽略）。

---

## 六、数据模型

| 表 | 用途 |
|---|---|
| `gold_prices` | 金价 OHLC，`date` 唯一 |
| `dollar_index` | 美元指数，`date` 唯一 |
| `gold_news` | 新闻；`published_at` 有索引 |
| `market_factors` | 多空因子（`type` 区分） |
| `institution_views` | 机构观点 |
| `predictions` | **当前没有任何代码写入**，接口恒返回空 |
| `update_logs` | **当前没有任何代码写入** |

引擎同时支持 MySQL 与 SQLite：SQLite 需要 `check_same_thread=False`，
内存库还需 `StaticPool`，否则每个连接看到的是各自独立的空库。

---

## 七、配置

全部配置项集中在 `app/config.py`，可直接用环境变量覆盖。常用项：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | MySQL 本地 | 也可指向 SQLite |
| `MIMO_API_KEY` / `MIMO_BASE_URL` / `MIMO_MODEL` | — / Token Plan 端点 / `mimo-v2.6-flash` | LLM 接入 |
| `MIMO_TRUST_ENV` | `false` | 是否读取宿主代理环境变量 |
| `CACHE_DIR` | `backend/cache` | 文件缓存目录 |
| `NEWS_RSS_SOURCES` | 内置四个源 | 格式 `名称\|URL,名称\|URL` |
| `CORS_ALLOW_ORIGINS` | 本地开发地址 | 不要填 `*` |
| `RATE_LIMIT_PER_MINUTE` | `60` | 普通接口每 IP 上限 |
| `RATE_LIMIT_AI_PER_MINUTE` | `6` | 会调用 LLM 的接口上限 |
| `SCHEDULER_ENABLED` | `true` | 定时任务总开关 |

---

## 八、定时任务

`app/scheduler.py`，APScheduler，时区 `Asia/Shanghai`：

| 任务 | 默认 cron | 说明 |
|---|---|---|
| 更新金价 | `30 6 * * *` | 每日 06:30，周末跳过 |
| 更新美元指数 | 同金价 | |
| 更新新闻 | 偶数整点 | RSS 抓取 |
| 更新 AI 分析 | 偶数整点 | 依次跑 4 个分析服务 |

---

## 九、请求保护

`app/main.py` 的中间件，实现见 `app/utils/rate_limit.py`：

- **限流**：按客户端 IP 的滑动窗口；普通接口与「会调用 LLM」的接口分开计数，
  后者上限更严。`/health` 不限流。过期键会被清理，内存不会无界增长。
- **CORS**：显式来源列表；若来源里出现 `*`，中间件会强制关闭凭证。

> 本项目**没有鉴权**。若要公开部署，请在反向代理层加访问控制，
> 否则任何人都能触发会消耗 LLM 额度的 `/refresh` 接口。

---

## 十、部署

`docker-compose.yml` 起三个容器：`mysql` / `backend` / `frontend`(nginx)。

- 后端入口脚本会等待数据库就绪，再跑 `init_db.py`，然后启动 uvicorn
- 前端由 nginx 提供构建产物，`/api/` 与 `/health` 都反代到后端
- LLM 凭证经 `backend/.env` 注入（`MIMO_*`）

- MySQL 首次启动时会执行 `backend/schema.sql`（只读挂载为
  `/docker-entrypoint-initdb.d/01-schema.sql`）；该脚本自带 `CREATE DATABASE`
  与 `USE`，且全部是 `IF NOT EXISTS`，可重复执行

---

## 十一、明确不存在的能力

以下内容在早期文档中出现过，但代码里没有：

Redis、消息总线、WebSocket 推送、K8s / Istio、WAF、CSRF Token、
认证/鉴权中间件、日志追踪中间件、RAG（向量库 / embedding / 检索）、
ReAct 推理循环、多 Agent 协作、TF-IDF / NER、预测准确率追踪。

`app/agents/` 包（`BaseAgent` / `MarketAnalyzerAgent` / `NewsAnalyzerAgent`）
没有任何地方实例化，属历史遗留。
