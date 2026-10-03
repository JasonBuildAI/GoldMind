# GoldMind 架构

> 🌐 **中文** | [English](./en/architecture.md)

本文描述**当前实现**。产品要做什么见 [`00-产品方向.md`](./00-产品方向.md)，
命令与配置见 [`../README.md`](../README.md)，接口规范见 [`API.md`](./API.md)。

> 本文档曾是一份 765 行的「企业级架构白皮书」，其中大量内容（Redis、消息总线、
> WebSocket、K8s/Istio、WAF、认证中间件、RAG 引擎）在本项目中**并不存在**。
> 现按实现重写；**同一事实只保留一个权威来源**，能力清单以 `00-产品方向.md` 为准。

---

## 一、组件

```
┌──────────────┐   /api/**   ┌──────────────┐            ┌────────────────┐
│  浏览器      │ ──────────► │  FastAPI     │ ─────────► │ SQLite（默认） │
│  Vue 3       │             │  (uvicorn)   │            │ 或 MySQL（可选）│
└──────────────┘             └──────┬───────┘            └────────────────┘
                                    │
                                    │ llm_provider（唯一出口）
                                    ▼
                             ┌──────────────┐
                             │ 任意 OpenAI  │
                             │   兼容端点   │
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
├── app/                   前端（Vue 3 + Pinia + Vite；视觉与文案规则见 docs/20-前端设计规范.md）
│   ├── src/views/dashboard/  看板七节：今日结论 / 行情 / 驱动 / 消息 / 量化预测 / 投资策略 / 数据与方法
│   ├── src/views/research/   研究页八节：裁决 / 前向留出期 / 覆盖度 / 诊断 / 分段 / 因子 / 基准 / 同步
│   ├── src/components/    节内原语（SectionBlock / StateBlock / DataTable / 报价 / 自绘 SVG 图表……）
│   ├── src/layout/        左侧栏（字标 / 导航 / 速览 / 新鲜度）与页脚
│   ├── src/styles/        设计令牌与基础排版
│   ├── src/services/api.ts  唯一的 HTTP 出口
│   ├── src/stores/        Pinia：行情轮询 / 数据新鲜度 / AI 配置
│   ├── src/entries/       两个入口：看板（index.html）与研究页（research.html）
│   └── e2e/               Playwright 端到端测试
└── backend/
    ├── app/
    │   ├── main.py        应用入口、限流、CORS
    │   ├── config.py      全部配置项（pydantic-settings）
    │   ├── database.py    引擎与会话（默认 SQLite；MySQL 可选）
    │   ├── models/        6 张表的 ORM 定义
    │   ├── routers/       4 个路由模块
    │   ├── services/      业务逻辑（见下）
        │   └── utils/         rate_limit 等
    ├── scripts/           smoke_llm / dev_mock_llm / dev_seed_sqlite
    └── tests/             unit / integration / e2e
```

---

## 三、分析流水线

**这不是多 Agent 系统。** 五个服务各自独立完成一次单轮 LLM 调用，彼此不通信：

```
SQLite(gold_news, news_digest_items, gold_prices)
        │
        ▼
  拼装 prompt ──► llm.invoke() ──► 解析 JSON ──► 两级缓存 ──► HTTP 响应
        ▲
        └── 可选：插件式 web_search（LLM_SEARCH_ENABLED，默认关）
```

新闻与价格上下文由 `services/analysis_input.py` 组装成同一份「分析输入包」
（`build_analysis_input`：`news_items` / `news_block` / `price` / 能力声明），
多空因子、机构观点、投资建议与市场总结消费同一入口；每个 prompt 里显式声明
「单轮调用、没有联网与工具、数据不足如实说」，避免模型拿记忆补数字。
模型返回的因子还要过 `services/factor_validation.py` 的确定性结构校验：最多 5 条、
按 id / 标题去重、id 必须在允许集合内、正文数字要能在参考新闻里找到（best-effort），
不合格的因子整条丢弃 —— 全丢光时降级为空结构，不把半份脏数据写进缓存与数据库。

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
  `LLM_TRUST_ENV` 控制）。宿主若设置了 SOCKS 代理或 `NO_PROXY` 里含 `[::1]`，
  httpx 会在**构造阶段**抛异常；而 `ChatOpenAI` 会同时准备同步与异步两个客户端，
  只给同步的那个仍会去建默认异步客户端并读环境。异常会被上层吞掉并回退到默认值，
  表现为「页面上有分析内容，其实一次模型都没调用」。
- **`web_search` 工具默认关闭**：它是 MiMo 插件式能力（不是通用 OpenAI 能力），
  需端点侧开通并用 `LLM_SEARCH_ENABLED=true` 显式开启；未开通时返回
  `HTTP 400 · web search tool found in the request body, but webSearchEnabled is false`
  （实测见 `scripts/smoke_llm.py`）。搜索不可用时回退到数据库与 RSS，**不编造数据**。
- **调用门控（`services/llm_gate.py`）**：两个阀门都为了同一件事 —— 付费调用只花在
  有信息增量的地方。
  1. **输入指纹**：把 prompt 里调用方明确声明的易变值（目前只有各服务拼进
     prompt 的 `current_time`）替换成占位符后做 sha256。指纹与上次**成功产出**
     时记录的一致且缓存仍在 → 直接复用缓存、不再调用模型。指纹只在解析成功后
     记录：失败路径下次仍要重试。`force=True`（`POST .../refresh` 的用户显式
     刷新）绕过该门控；调度器的 `refresh_analysis_sync` 默认受门控。
  2. **每日预算**：`config.LLM_DAILY_CALL_BUDGET`（默认 200，≤0 = 不设上限）。
     计数发生在 `llm_provider.retry_on_content_filter` 真正 `invoke` 之前，
     失败与风控重试同样计入；用尽后抛 `LLMBudgetExceeded`，各服务照常走
     「暂不可用」路径，**不会编内容**。

  状态落 `CACHE_DIR/llm_gate.json`（与 CacheManager 同目录，同样被 gitignore），
  日期口径走 `timeutil.today()`。多进程各写各读，因此预算是「大致上限」而不是
  计费系统 —— 真实账单以端点侧为准。守卫：`tests/unit/test_llm_gate.py`
  （5 个服务的关键对：`GATE_KEY == Service._ANALYSIS_KEY`）。

---

## 五、缓存

两级，实现在 `services/cache_manager.py`：

| 级别 | 位置 | 说明 |
|---|---|---|
| 内存 | 进程内 dict | 最快；多进程不共享 |
| 文件 | `CACHE_DIR/*.json` | 原子写入（临时文件 + rename）；重启后仍可命中 |

TTL 由两个常量定义（`services/cache_manager.py`）：

| 常量 | 值 | 用途 |
|---|---|---|
| `AI_ANALYSIS_CACHE_TTL` | 7200（2 小时） | 五份 AI 分析结果 |
| `REALTIME_PRICE_CACHE_TTL` | 30 | 实时行情（「取一次外部报价」的缓存） |

**分析缓存必须 >= 调度器的刷新间隔。** 缓存过期时，**一个用户请求会触发一次
按需的付费 LLM 分析**（见各服务的 `get_xxx(use_cache=True)`），而调度器本来就会
按 `UPDATE_AI_ANALYSIS_CRON` 刷新同一份结果：

```
TTL >= 刷新间隔  ->  过期时调度器几乎已写好新结果，不会多花钱
TTL <  刷新间隔  ->  每个周期白白多触发一次付费分析
```

机构预测原先单独写了 **3600**（1 小时），而调度器每 **2 小时**才刷新一次 ——
每个周期都多花一次分析。现在五个服务共用同一个常量，
`tests/unit/test_cache_ttl_vs_schedule.py` 会解析 cron 并守住这条关系。

`CACHE_DIR` 可配置（默认 `backend/cache`），测试用独立目录。
缓存文件**不入库**（`.gitignore` 忽略）。

---

## 六、数据模型

| 表 | 用途 |
|---|---|
| `gold_prices` | 金价 OHLC，`date` 唯一 |
| `dollar_index` | 美元指数，`date` 唯一 |
| `gold_news` | 新闻；`published_at` 有索引 |
| `news_digest_items` | 消息板块的高权威条目（与 `gold_news` 存储隔离）；`url` 为 `TEXT`（Google News 链接实测超 500 字符，`VARCHAR(500)` 在 MySQL 下整批落库失败，老库升级走 `scripts/migrate_news_digest_url.py`）、去重靠前缀索引 191、`published_at` 有索引 |
| `market_factors` | 多空因子（`type` 区分） |
| `institution_views` | 机构观点；`as_of_date` / `source` 记录每条预测最近一次被核实的日期与线索来源（`web_search` / `news_scan` / `legacy`），老库升级走 `scripts/migrate_institution_views.py`（只加列/补数据，不删行） |
| `predictions` | 量化引擎（`services/quant/service.py`）预测存档：每个 `(模型版本, 尺度, 截止日)` 一行 —— 同一天重算就地更新、跨天追加保留；含方向、周期、基准价、目标价、得分、期望收益、不确定度与模型版本 |
| `factor_observations` | 量化因子观测，`(factor_key, obs_date)` 唯一；只存成功观测，失败在同步报告里说明 |
| `factor_observation_revisions` | 因子观测的**追加式修订流水**：每次写入（首见或回修）留一行，带 `recorded_at`（项目时区）。有它才能按「当时可见的输入」重建面板（`storage.load_series_as_of`，研究台 `--as-of`），预注册裁决才可复现 |
| `model_evaluations` | 走查式回测结果（命中率 / 基准对照 / Brier / 逐因子指标），每次评估追加一行 |

> `update_logs` 已删除：没有任何写入方、读取方或接口，产品方向里也没把它列为目标，
> 属于纯死表。同理，`schema.sql` 与模型的一致性由
> `tests/unit/test_schema_matches_models.py` 守住 —— 这两份 schema 曾经对枚举列的
> 取值约定不一致，而 MySQL 的 ENUM 比较不区分大小写，导致「写得进去、读不出来」。

引擎默认使用 SQLite（单文件 `backend/goldmind.db`），同时支持 MySQL：SQLite 需要
`check_same_thread=False`，内存库还需 `StaticPool`，否则每个连接看到的是各自独立的空库。
`init_db.py` 在 SQLite 下用模型 `create_all` 建表，MySQL 下才先建库、再执行 `schema.sql`。

> 测试默认跑内存 SQLite；想验 MySQL 时用 `conftest.py` 的 `GOLDMIND_TEST_DATABASE_URL`
> 开关拿同一套用例再跑一遍（指向独立的测试库，用例会清空所有表）。两者在枚举存储、
> JSON 列与字符串比较大小写上都有差异。
>
> **硬护栏**（2026-10-02 事故后加）：该 URL 的库名必须含 `test`（SQLite 文件同理），
> 否则测试在导入期就拒跑并点名库名 —— 用例会 `drop_all`，而事故现场正是它被指向了
> 开发库 `gold_analysis`，一次会话删光 9 张业务表。实现见 `backend/tests/safety.py`。

---

## 七、配置

全部配置项集中在 `app/config.py`，可直接用环境变量覆盖。常用项：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/goldmind.db` | 默认单文件 SQLite，零安装；也可指向 MySQL（可选，未随本仓库实测） |
| `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL` | —（必须自填） | LLM 接入；任何 OpenAI 兼容端点，三项齐备才算已配置 |
| `LLM_MAX_TOKENS` | `8192` | 单次输出上限，模型思考与正文共用 |
| `LLM_SEARCH_ENABLED` | `false` | 插件式联网搜索开关（端点侧未开通时无效） |
| `LLM_TRUST_ENV` | `false` | 是否读取宿主代理环境变量 |
| `CACHE_DIR` | `backend/cache` | 文件缓存目录 |
| `NEWS_RSS_SOURCES` | 内置四个源 | 格式 `名称\|URL,名称\|URL` |
| `NEWS_DIGEST_SOURCES` | 内置 13 个高权威源 | 消息板块来源池，格式 `名称\|URL\|tier\|relevance`；留空用内置默认池 |
| `NEWS_TRANSLATE_ENABLED` | `true` | 消息板块中文翻译开关；关掉即完全不调用 LLM（页面显示英文 + 原因） |
| `NEWS_TRANSLATE_BATCH` | `30` | 一次批量翻译的条目上限（= 三个窗口可见条目上限）；未翻完的下一轮继续 |
| `CORS_ALLOW_ORIGINS` | 本地开发地址 | 不要填 `*` |
| `RATE_LIMIT_PER_MINUTE` | `60` | 普通接口每 IP 上限 |
| `RATE_LIMIT_AI_PER_MINUTE` | `6` | 会调用 LLM 的接口上限 |
| `SCHEDULER_ENABLED` | `true` | 定时任务总开关 |
| `SCHEDULER_TIMEZONE` | `Asia/Shanghai` | **全项目唯一的时区口径**，见下 |

### 时区口径

`SCHEDULER_TIMEZONE` 不只是 cron 的时区，它是**整个项目的时间口径**：

> 数据进入系统时立刻换算成它，离开系统时才转回去。

这条规则不是设计洁癖，是两次真实故障逼出来的 —— 两次都只在特定部署下才显形：

| 故障 | 表现 |
|---|---|
| 定时任务用 `datetime.now().date()` 取「今天」 | cron 按东八区触发，容器默认 UTC，同一份行情在 Docker 里被记到**前一天** |
| RSS 的 `published_parsed` 是 UTC，直接 `datetime(*parsed[:6])` 存库 | 库里存的是 UTC 墙上时间、读的却按本地时间算，**「最近24小时」的窗口实际覆盖约 32 小时** |

同一根因还有一处：前端用 `new Date().toISOString().split('T')[0]` 取「今天」，
那是 **UTC 日期** —— 东八区 00:00-08:00 之间它给出昨天，实时美元指数就静默不更新。

现成的入口（不要另造）：

| 需要什么 | 用什么 |
|---|---|
| 后端要「现在」/「今天」 | `app.scheduler.scheduler_now()` / `scheduler_today()` |
| 外部时间戳（RSS 的 UTC struct_time） | `app.services.news_service.to_local_naive()` |
| 数据源自报的交易日（字符串） | `app.scheduler.parse_source_date()` |
| 前端要判断「是不是今天」 | **不要自己算** —— 用后端给的交易日字段（如 `DollarRealtime.date`） |

禁止的写法：`datetime.now().date()` 取「今天」、`datetime.utcnow()`、
`new Date().toISOString()` 取日期。测试用固定时刻构造场景，不要依赖跑测试时的钟点 ——
本机是东八区，很多时区错误在这里**根本测不出来**。

### 价格口径与刷新时间（as-of）

同一个「金价」在页面上的口径并不相同，口径名与中文标签只在
`app/services/price_basis.py` 定义一次（`realtime` 实时报价 / `close` 日收盘 /
`quant_basis` 量化基准）。2026-10-03 起补上第二件事：**价格与它的刷新时间必须同源同刻下发**。

- 六处展示国际金价：侧边栏今日速览、行情节与报价块、今日结论「当前价格」、
  投资策略降级快照、量化预测「基准价」、公允价值「市场价」。
- 后端逐处给出该价格**自己的** as-of：
  `GET /api/gold/stats` 的 `price_as_of`（行情，来自报价自身）、
  `GET /api/analysis/market-summary-ai` 的 `price_as_of` / `price_basis` /
  `price_basis_label` / `price_source`（与 `current_price` 在**三个响应分支**
  用同一个 `_apply_price_meta` 写入 —— 只换数字留下旧时间比不给时间更误导）、
  投资策略降级快照的 `as_of` / `basis` / `basis_label` / `source`（窗口末的日收盘）、
  量化预测的 `as_of` 与 `price_basis`（`gold_close` 最后一点，接口本来就有）。
- **取不到金价时四个字段一起为 `null`**，页面写「金价刷新时间未知（后端未返回）」——
  不许用 `datetime.now()` 或前端时钟造一个「刚刚」。
- 前端措辞只在一个组件里定（`app/src/components/GoldPriceAsOf.vue`），六处引用它。
- 守卫：`backend/tests/unit/test_price_asof_exposure.py`（三个分支同字段、缺失时为 null、
  口径标签只从 `price_basis` 取）、`app/src/components/__tests__/GoldPriceAsOf.test.ts`。

---

### 查询参数的契约

前后端之间**没有任何机制保证参数名一致**：类型系统管不到 URL 字符串，
FastAPI 也会**静默忽略**未声明的查询参数。第 19 轮就是这样漏掉了一个：

```ts
`/api/gold/prices/correlation?days=${days}`   // 前端一直在传
```

```python
async def get_correlation_data(limit: int = Query(...), include_realtime: bool = Query(...))
#                                            ^ days 从未被声明
```

结果 `days=30` / `days=5` / `days=365` / 不传，返回的完全一样。
同一处理函数此前还修过 `limit`（声明了、校验了、从未使用）——
两次都是「参数的契约两端各写各的」，而且两边都不报错。

因此两条规矩：

| 方向 | 要求 | 谁守 |
|---|---|---|
| 前端传的 | 端点必须声明 | `tests/unit/test_api_params_contract.py` |
| 端点声明的 | 函数体必须真的用到 | 同上 |

这条守卫只保证**名字对得上**；「参数真的改变了行为」由各端点自己的行为测试负责
（如 `test_correlation_days_actually_filters`）。

---

## 八、定时任务

`app/scheduler.py`，APScheduler，时区 `Asia/Shanghai`：

| 任务 | 默认 cron | 说明 |
|---|---|---|
| 更新金价 | `30 6 * * *` | 每日 06:30，周末跳过 |
| 更新美元指数 | 同金价 | |
| 更新新闻 | 偶数整点 | RSS 抓取 |
| 更新消息精选 | `25 * * * *` | 消息板块全源抓取（高权威来源，评分不调用 LLM）＋ 一批中文翻译（一次 chat 调用，见第十二节） |
| 更新 AI 分析 | 偶数整点 | 依次跑 4 个分析服务 |
| 同步量化因子 | `15 */2 * * *` | 各源按自身节奏跳过未到期的抓取（`QUANT_ENABLED=false` 可整体关闭） |
| 重算量化预测 | `45 */2 * * *` | 重算 1 / 5 / 20 / 60 / 250 个交易日预测；回测按 24 小时节流 |

---

## 九、请求保护

`app/main.py` 的中间件，实现见 `app/utils/rate_limit.py`：

- **限流**：按客户端 IP 的滑动窗口；普通接口与「会调用 LLM」的接口分开计数，
  后者上限更严。`/health` 不限流。过期键会被清理，内存不会无界增长。
- **CORS**：显式来源列表；若来源里出现 `*`，中间件会强制关闭凭证。
- **失败传播**（2026-10-02 加固）：
  - 缺库/缺表（MySQL 1146/1049、SQLite `no such table`）统一翻译成
    **503 + `python init_db.py` 修复指引**，不再是裸 500；启动时做 schema 自检，
    缺表打 ERROR。其余 SQL 错误仍是 500，不被这句指引掩盖。
  - 前端对幂等 GET 的 **429 / 5xx / 网络错误**做指数退避（±25% 抖动）重试，最多 3 次
    尝试；429 优先按 `Retry-After`（其次 body `retry_after`）等待。`POST` 与
    `GET ...?refresh=true` 一律不重试 —— 它们可能触发一次付费 LLM 调用。
  - 同一 URL 的在飞 GET 合并成一个请求（StrictMode 双挂载、轮询与手动刷新撞车不再
    翻倍请求量）；看板轮询 30 秒一档、`document.hidden` 时暂停、恢复立即补一次。

> 本项目**没有通用鉴权**，只有一个可选的刷新门（2.0.2 第 20 条）：设
> `REFRESH_TOKEN` 后，七个 `POST .../refresh` 必须携带 `X-Refresh-Token` 请求头
> （实现 `app/utils/refresh_auth.py`，`secrets.compare_digest` 比较，缺/错一律
> 401 且在副作用之前拒绝）；不设则保持旧行为。其余接口仍应靠反向代理层加访问
> 控制 —— 这个门只保护「会花钱 / 会抓外网」的刷新入口。

---

## 十、部署

**文档化的复现路径是本地 SQLite**（见 `README.md`「快速开始」）：不装数据库、不装容器，
`python init_db.py` 自动创建 `backend/goldmind.db` 并建表。

仓库里仍保留可选的 MySQL / 容器资产，**未随本轮闸门实测**：

- `docker-compose.yml` 起三个容器：`mysql` / `backend` / `frontend`(nginx)；后端入口
  等待数据库就绪后跑 `init_db.py` 再启动 uvicorn，前端 nginx 把 `/api/` 与 `/health`
  反代到后端，LLM 凭证经 `backend/.env`（`LLM_*`）注入
- MySQL 首次启动会执行 `backend/schema.sql`（只读挂载为
  `/docker-entrypoint-initdb.d/01-schema.sql`）：脚本只含 `CREATE TABLE IF NOT EXISTS`，
  **不写 CREATE DATABASE / USE**（写死库名会让配置失效）；mysql 镜像会先在
  `MYSQL_DATABASE` 指定的库中选库再执行，因此可重复执行

> 改用本机 MySQL 时在 `backend/.env` 写 `DATABASE_URL`，再跑 `python init_db.py`
> （MySQL 路径先建库、再执行 `schema.sql`）。两条 MySQL 路径与 SQLite 默认路径的
> 行为差异（ENUM 存储、字符串比较大小写、事务语义）已知，上线前先用
> `GOLDMIND_TEST_DATABASE_URL` 跑一遍全档测试。

---

## 十一、量化预测引擎

`app/services/quant/`：把「影响国际金价的四类因素」（货币政策与利率 / 避险与信用 /
供需结构 / 市场与技术面）变成可回测的信号。因子清单、权重、方向先验与新鲜度上限
只在 `app/services/quant/definitions.py` 定义一处，接口按它输出 —— 文档不另抄一份。

| 环节 | 位置 | 要点 |
|---|---|---|
| 数据源 | `sources/*.py` | 全部免费、无需密钥（含财政部 DTS 的 TGA、纽约联储 RRP、CFTC 未平仓量、Yahoo 的 USDCNY）；HTTP 客户端可注入，测试永不真出网。**外部行情源（Yahoo）失败时**，金价基准与美元因子改用本地 `gold_prices` / `dollar_index` 表兜底（来源如实标注「本地行情表…兜底」），只换数据来路，不改因子集与权重 |
| 派生 | `derive.py` | 原始序列 → 因子值，单位与口径只在这一层固定 |
| 落库 | `storage.py` | `factor_observations`，唯一约束 `(factor_key, obs_date)`，幂等；每次首见或回修同时向 `factor_observation_revisions` 追加一行（值没变不追加） |
| 候选闸门 | `screen.py` + `scripts/screen_factors.py` | 新信息要进因子集必须过三道事先写死的检验：① 去均值后的 `z × h 日前瞻收益` 协方差做 Newey–West 单尾检验（滞后 h−1）且 p < α/整轮检验数、\|t\| ≥ 3；② ≥2 个尺度同号；③ 结论公布日之后的前向窗口确认。本模块**没有采纳权**：正向过线只能给「待前向确认」，反向显著（同一条 \|t\| 下限＋双侧 p）只登记成「反向假设」等闸门 ③，**不许当场翻号** |
| 同步 | `sync.py` | 按源节流（6h ~ 24h）、增量抓取、逐源降级并写入同步报告 |
| 信号 | `engine.py` | 滚动 z → 方向对齐 → 按尺度取权重（`definitions.horizon_weights`）合成 → 一份校准分布给出期望收益、不确定度、上行概率、目标价与区间 |
| 公允价 | `decompose.py` | 走查式扩展窗口 OLS（`log 金价 ~ 实际利率 + log 美元指数 + log 央行储备 + VIX`）把金价拆成 宏观锚＋需求溢价＋风险溢价＋情绪残差；偏离度 = 市场价 / 公允价 − 1 |
| 情景 | `scenarios.py` | 预测分布 N(μ, σ²) 的分位数 → Base [q25, q75]（50%）/ Bull 上 25% / Bear 下 25%；触发与失效条件由该尺度最重因子＋200 日均线生成 |
| 回测 | `backtest.py` | 走查式命中率（评校准后的方向）+ 三个基准 + 未校准得分方向单列成绩 + 80% 区间覆盖率（**并按预测时点的实现波动率分档**，见 `coverage_by_vol_regime`）+ 2022-01-01 前后分段 + 逐因子命中率与 IC + 分布级 CRPS（对「零漂移」基准的 `crps_skill_vs_flat` 技能分） |
| 监测 | `monitor.py` | 周更仪表盘逐行给频率 / 来源 / 值 / 信号 / 数据截至日；信号规则集中在 `_rule`，信息型行 `signal=null`，缺数据标「不可用 + 原因」 |
| 出口 | `service.py` | 调度任务与 `POST /api/gold/quant/refresh` 共用同一条链路 |
| 统计 | `stats.py` | 重叠样本的显著性工具箱：Newey–West HAC 标准误、圆周分块自助区间、HAC t / Diebold–Mariano、Brier 技能分与可靠性分桶（不引入 scipy） |
| 预注册 | `preregistered.py` | 候选清单、选择规则与通过线的**唯一实现**：先注册、后检验；看到留出期成绩后再改常量即破坏预注册 |
| M 族（研究） | `multivariate.py` | 研究台专用：walk-forward Ridge 直接对因子矩阵建模（只用 `j + h ≤ t` 的已实现样本对，均值 / 标准差也在同一段窗口内估计），与「先合成再一元回归」对照；**不进线上 service**，候选定义见研究台清单 M1/M2 |
| Regime 与基准口径（研究） | `regimes.py` | 第四轮预注册的状态切换候选（R1 实际利率周期 / R2 美元周期 / R3 央行购金时代，滚动窗口只回看、状态不成立记中性 0 分）与基准清单（生产 = GC=F 连续合约、**含展期**；对照 = GLD；不可达 = XAUUSD 现货 404、展期调整序列无免费来源）。**只进研究台**，读接口把基准口径与候选登记一并发布 |
| 研究台 | `scripts/quant_lab.py` | 预注册候选 × 尺度 × **四个样本期**（开发期 / 历史留出期 / 前向留出期 / 全样本）的全档评估（`--from-db` 读库 / `--out` 落盘 / `--horizons` 选尺度 / `--group` 选候选族 / `--as-of` 按时点重建面板 / `--holdout-start` 改历史留出期起点）。**裁决只认前向留出期**（`DECISION_PERIOD = "forward"`）：历史那一段已被前两轮看过，只作记录；窗口里独立下注不够时结论是「不可判定」而不是「未过线」。结论进「研究」页与研究台报告 |

三条不能破的口径：

1. **无前视**。滚动统计与回归样本全部 `shift` 到 t 之前；在黄金收盘之后才发布的
   数据源（财政部收益率曲线、纽约联储 EFFR、CFTC 持仓）由
   `sources/base.py::shift_to_next_trading_day` 整体右移一个工作日。
   守卫：`backend/tests/unit/quant/test_no_lookahead.py` —— 把 t 之后的数据改成
   垃圾值，t 时刻的信号必须逐位不变。
2. **不编造**。可用因子少于 3 个、价格序列缺失、单因子数据陈旧（超过该因子的
   更新周期）都返回「不可用 + 原因」；缺失因子按剩余权重归一，不会被当成 0。
3. **时间只走一个时区**。所有「现在」都用 `app.utils.timeutil`（调度器时区），
   与第七条同一口径。

预测只有一个分布出口（`engine.build_prediction_frame` + `engine.calibrate_distribution`）：
t 时刻的 μ = α + β·score（扩展窗口一元 OLS，样本对满足 s + h ≤ t），
且 **|μ| ≤ `EXPECTED_CAP_SIGMAS` × 同期已实现 h 日收益的扩展标准差**（OLS 在得分近乎恒定的
窗口里能把 β 推到 10⁴ 量级，2019-01-08 曾算出 60 日期望收益 +1261，封顶是硬要求）；
尺度 scale = std(e_s | s + h ≤ t)（**走查预测误差**的标准差，不是回归残差；已实现误差不足
60 组时退回「已实现 h 日收益的扩展标准差」，仍然只用过去的数据）；
F̂ = 最近 `CALIBRATION_WINDOW` 个 studentized 误差 `e_s/scale_s` 的**半衰期加权经验分布**，
名义错失率 α 由 ACI 在线递推（`α ← α + γ(α_target − miss)`）。两个细节都是实测逼出来的：

- **`miss` 判的是这一注发出时的那条区间**，不是当前这一行正在展示的区间。误差序列传进
  校准函数时已按实现时间右移 `horizon` 行，所以第 t 行的误差属于第 `t − horizon` 行发出的
  那一注（`calibrate_distribution(issued_lag=)`）。搞混的代价是长尺度覆盖率系统性偏低
  （开发期实测 20 日 0.767、60 日 0.726，修复后 0.791 / 0.744）；
- 校准样本怎么取有三档（`engine.CALIBRATION_MODES`，研究台候选 C0 / C1 / C2）：`row` 每行计
  一次（交付口径），`bet` 每 `horizon` 行才计一次，`bet_window` 在 `bet` 之上按日历等值加回
  回看窗 —— h 日前瞻误差在日频上重叠，同一次下注被数了 h 遍，保形推断的「样本可交换」
  前提就不成立了。三档的配套常数由 `engine.calibration_settings()` 一处给出，取样单位一变，
  γ / 半衰期 / 回看窗必须跟着变；交付用哪一档由 `engine.DEFAULT_CALIBRATION_MODE` 决定，
  候选定义与判据见 `docs/specs/2026-10-02-量化引擎第三轮预注册.md`。

四个出口全部取自这一张 F̂：

```
80% 区间 = μ + scale · [ F̂⁻¹(α/2),  F̂⁻¹(1−α/2) ]     ← 非对称，默认口径 interval="aci"
情景区间 = μ + scale · [ F̂⁻¹(0.25), F̂⁻¹(0.75)  ]      ← 与 80% 区间同批分位样本，按构造嵌套
上行概率 = 1 − F̂( −μ / scale )                        ← 不是 Φ(μ/σ)
展示尺度 = (区间上界 − 区间下界) / (2 × 1.2816)         ← 即 `uncertainty` 字段
```

`uncertainty` 只是「把区间宽度换算成正态尺度的显示值」：**非对称口径下区间中点不等于 μ**，
所以「μ ± 1.2816·uncertainty」只在对称口径（`normal` / `empirical`）下恰好等于展示的区间。
它**不参与**概率计算 —— 曾经拿它当 Φ 的分母，后果是每个概率都被压向 50%
（Brier 技能分全线为负的直接机制之一，2026-10-02 修）。
页面上的「方向」= sign(μ)。曾用分布中位数定方向，实测（真实 20 年面板）会让 60 日留出期
命中率从 83.3% 掉到 78.9%，因为走查误差的位置项系统性偏负、把三成喊单翻成看跌：
位置项用于给概率与区间定标度，不用于决策（理由记在 `engine.SignalSnapshot.direction`）。
因子合成的 score 是**未校准**的输入：只在因子表与「因子偏向（未校准）」的折叠详情里展示，
回测成绩也折进详情单列（`metrics.score_direction_accuracy`）。回归样本不足 60 组时
`expected_return` 为 NaN → 该尺度整体「不可用 + 原因」，不退回「预期不变」，
也不拿得分符号顶替方向。超过 `max_age_days` 的观测在 `engine.align_series` 里就变成 NaN，
因此「陈旧」同时意味着不参与合成、不计入回测的可用因子数。
经验分位校准后 80% 区间的实际覆盖率（**26 年面板，2026-10-02 引擎加固后重算**；
口径：`backtest.evaluate_periods` 的三列，`interval="aci"`）：

| 尺度 | 开发期命中 | 历史留出命中 | 永远看多（留出） | 差 | 开发期覆盖率 | 历史留出覆盖率 | 全样本覆盖率 |
|---|---|---|---|---|---|---|---|
| 1 日 | 52.5% | 54.6% | 56.4% | −1.7pp | 79.9% | 78.4% | 79.7% |
| 1 周 | 53.4% | 60.9% | 62.1% | −1.2pp | 80.0% | 77.9% | 79.7% |
| 1 月 | 54.6% | 68.1% | 68.1% | +0.0pp | 79.0% | 76.9% | 78.8% |
| 1 季 | 60.8% | 83.4% | 83.4% | +0.0pp | 74.5% | 65.3% | 73.5% |
| 1 年 | 71.8% | 100.0% | 100.0% | +0.0pp | 61.2% | 28.4% | 58.4% |

**这些数字会随口径变化，不许照抄**：改一次引擎就重跑一次
（`cd backend && python scripts/quant_lab.py`，或研究接口 `GET /api/gold/quant/research`）。
历史留出期的方向命中率与「永远看多」在 20 日及更长的尺度上逐日一致（差 +0.0pp），
Brier 技能分为负 —— 模型在留出期没有方向上的信息优势。1 年尺度是头号问题：
区间宽度校准补不回中心（μ）的偏差，覆盖率提高也不能换来方向上的改进
（留出期独立下注只有 3 次，见下）。2026-10-02 的预注册裁决：17 个候选 × 5 个尺度
无一过线，按规则**保留线上版本并标注「无统计优势」**（当时是 `quant-v4`；第二轮修好
ACI 判错区间之后升为 `quant-v5`，同日引擎加固再升为 `quant-v6`（对齐不再丢弃非交易日
观测、α 上界收到 0.5），2026-10-03 的 2.0.2 再把发布滞后写进因子表（`publication_lag_days`，
利率三因子 1 个工作日）并升为 `quant-v7` —— 上表是 v6 口径，v7 后待真实栈重算；
第三轮的 C2 候选同样按预注册判据淘汰 ——
裁决细节见 `docs/specs/2026-10-02-研究台报告.md` 与
`docs/specs/2026-10-02-量化引擎第三轮预注册.md`，规则实现见 `preregistered.py`）。
按这条结论，1 年尺度在 2.0.2 起**停发方向**：预测响应带 `direction_status: not_published`
与原因文本，方向字段置空，公允价值偏离与校准区间照常发布（策略表见
`definitions.NOT_PUBLISHED_DIRECTION_REASONS`，同处定义、不另抄）。

**自适应 α 的上界是 0.5，且必须 ≤ 0.5**：区间端点取分位 `α/2` 与 `1−α/2`，情景固定取
`QUARTILE_LOW` / `QUARTILE_HIGH`（0.25 / 0.75）；`α/2 > 0.25` 时区间下界会越过情景下界，
「情景 ⊂ 区间」按构造被破坏（26 年面板实测 h=250 曾有 1036 行违反）。
接口同时给出这一行的实际名义水平（`interval_alpha` / `interval_nominal`）与
分布来源（`distribution_mode`：`aci` 经验分布 / `normal` 兜底），以及期望收益是否被
护栏夹过（`expected_capped`）—— 名义 80% 只是起点，不给这几个数读者就会按名义值
去读一个名义值已经不成立的区间。

页面把覆盖率与「永远看多 / 动量」基准一起如实展示（见 docs/00-产品方向.md 第四节）。
守卫：`tests/unit/quant/test_engine.py`（方向 / 概率 / σ / 经验分位 / α 上界五条判据，
逐条做过变异验证）、`tests/unit/quant/test_backtest_metrics.py`。

四层分解的展示口径固定在 `decompose.py` 一处：需求与风险溢价按链式相乘
（风险溢价以「中枢＋需求溢价」为基数），使「中枢＋需求溢价＋风险溢价 = 公允价」
与「三块＋情绪残差 = 市场价」都按构造成立；t 时刻的回归系数只用 `s ≤ t−1` 的
已实现样本，已实现样本不足 120 组或缺任一回归量时返回「不可用 + 原因」。
守卫：`backend/tests/unit/quant/test_decompose.py`。

情景（`scenarios.py`）把同一份 μ/σ 变成 Base / Bull / Bear 与可核对的触发、失效条件；
σ 非正、基准价缺失或没有可用因子时返回「不可用 + 原因」，不阻塞预测主输出。
守卫：`backend/tests/unit/quant/test_scenarios.py`。

回测（`backtest.py`）在命中率之外报告 80% 名义区间的实际覆盖率
（`metrics.interval_coverage_80`）与以 2022-01-01 为界的 `metrics.regimes`
分段成绩；某段样本不足时只给样本数与原因，不凑数字。样本期切成四段，混用等于偷换证据：
`development`（`HOLDOUT_START = 2023-10-02` 之前，唯一可以调参的一段）、
`holdout`（历史留出期，已被前两轮裁决看过，只作记录）、
`forward`（前向留出期，`ACTIVE_HOLDOUT_START = 2026-10-02` 起，**唯一**的裁决窗口；
窗口没攒够 20 次独立下注时状态是 `pending` 并写明还差多少个交易日，不许拿历史那段顶替）、
`full`（全样本）。分布级评分 CRPS（`metrics.mean_crps`）与其对「零漂移」基准的技能分
（`metrics.crps_skill_vs_flat`）也在同一份 metrics 里：Brier 只评涨/跌，CRPS 评整张分布
与实现收益的匹配（正态闭式解 / 经验分布精确式，定义式数值积分在测试里逐点对照）。
守卫：`backend/tests/unit/quant/test_backtest_metrics.py`。

监测仪表盘（`monitor.py`）覆盖 22 行指标；其中 usdcny / cny_gold / tga / rrp /
cftc_oi 与第二轮接入的 gvz / gold_silver_ratio / copper_gold_ratio /
cftc_net_oi_ratio / gpr_daily、第四轮的 gld_close 与 2.0.2 的 digest_intensity
是监控专用序列，与因子同表（`factor_observations`）
存储但不参与信号合成 —— 顺序、数量与 `monitor.ROW_SPECS` 逐行对齐。
上海金溢价 = SGE Au99.99 收盘 − 国际金价折算（`sources/sge.py` 抓取，实测 2026-10-03 可达，
回看至 2016-12-19）；两条序列缺任何一条就如实显示「不可用 + 原因」，不拿单边冒充溢价。
守卫：`backend/tests/unit/quant/test_monitor.py`。

---

## 十二、消息板块（高权威消息精选）

页面上的「消息」板块拥有独立表与独立抓取节奏（与 `gold_news` 存储隔离）；2026-10-02 起，
其中的高权威条目同时作为分析输入：经 `services/analysis_input.py` 与 `gold_news` 按规范化
URL 去重合并（消息板块优先），进入看涨/看跌因子、机构观点、投资建议与市场总结的 prompt，
每条给「标题 + 清洗截断后的摘要」（实现见 `services/news_digest.py`、`services/analysis_input.py`）。

- **来源池**：默认 13 个实测可用来源，覆盖央行 / 通讯社 / 行业机构 / 专业财经四类：
  美联储与欧洲央行官方 RSS；路透社 / 美联社 / 世界黄金协会 / 金融时报 / 华尔街日报 /
  CNBC / MarketWatch / Kitco 走 Google News `site:` 限定（这些机构的官方 RSS 已下线，
  放失效地址等于编造能力）；彭博社 / MINING.COM / 英为财情直连。
  `NEWS_DIGEST_SOURCES` 可整体覆盖；格式 `名称|URL|tier|relevance`。
- **入库门槛**：必须有链接与发布时间 —— 缺失即跳过并计入抓取报告，绝不回填抓取时刻；
  `gold` 类来源必须命中金融语境的黄金词（排除体育 / 时尚等隐喻：`gold medal`、
  `gold dream`、`go for gold` 习语；名单按真实抓取到的误判样本维护），
  `monetary` 类额外接受 FOMC / 利率 / 通胀 / 央行等货币词。
- **确定性评分**（不调用 LLM）：`重要性 = 100×(0.40·权威 + 0.25·相关 + 0.20·覆盖 + 0.15·时效)`，
  `置信度 = 100×(0.45·权威 + 0.30·覆盖 + 0.25·相关)`；时效按 7 天尺度指数衰减
  （`exp(-age_hours/168)`）。同题报道按标题聚类（Jaccard ≥ 0.6 且共享 ≥ 2 词），
  覆盖数按不同来源计，代表条取簇内重要性最高者。
- **窗口**：先对最近 30 天全集评分，再输出 24 小时 / 7 天 / 30 天三个过滤视图，
  各取前 10 条 —— 同一事件在三个窗口里分数一致，**重叠是设计行为**。
- **空库是如实状态**：`has_data=false` + 原因（从未抓取 / 全部来源失败 /
  30 天内没有合格消息），页面显示「不可用」，不编造任何条目。
- **接口与定时**：`GET /api/gold/news/digest` 与 `POST /api/gold/news/digest/refresh`
  （抓取报告写入 cache_manager，key `news_digest_fetch_status`）；
  调度任务 `update_news_digest` 默认每小时第 25 分钟抓取。
- **中文译文（2026-10-03，`services/news_translation.py`）**：来源池全是英文 RSS，
  抓取后自动把标题与摘要译成「中文标题 + 2–3 句中文导语」，与英文原文**并存**存储
  （`title_zh` / `brief_zh` / `translated_at` / `translation_model`，老库补列走
  `scripts/migrate_news_digest_translation.py`）。
  - 一次 `translate_pending()` 只发**一次** chat 调用，取 `NEWS_TRANSLATE_BATCH`（默认 30）
    条**尚未翻译**的条目、按发布时间倒序（页面上先看到的先有中文）；已翻好的永不重复调用，
    `translation_model` 与当前模型不一致时算陈旧、重翻。调用经 `llm_provider`（红线 3），
    每日预算在 `llm_gate` 里扣。
  - **不许添加原文没有的事实**（红线 1）：prompt 要求只能压缩来源摘要里已有的信息，
    数字 / 机构名 / 目标价 / 日期 / 背景与因果原文没写就不写；代码侧再做一次确定性校验
    （`id` 必须落在本批输入集合内、中文标题必须非空），不合格的条目整条丢弃、不写库。
  - **降级逐条可解释**：`NEWS_TRANSLATE_ENABLED=false` / LLM 未配置 / 当日预算用尽 /
    调用失败 / 输出解析不了 —— 各给一句原因，响应里的 `translation.reason` 与每条 item 的
    `translated` 让页面显示「英文标题 + 中文翻译暂不可用（原因）」，绝不摆编出来的中文。
  - **GET 是读路径**：`translation_status()` 只数「还有多少条没有中文」，一次模型调用都不发。
  - 中文**不**参与评分、聚类与排序，也**不**进入任何分析 prompt（换语言会改变模型行为，
    那是另一件事）—— 分析输入仍是原始英文标题与摘要。
  - 守卫：`tests/unit/test_news_translation.py`（批量 / 幂等 / 校验 / 降级 / 预算）、
    `tests/unit/test_prompt_discipline.py`（翻译提示词必须被扫描到）、
    `tests/integration/test_news_digest_api.py`（GET 暴露中文字段与原因、GET 不调用模型）。

---

## 十三、明确不存在的能力

以下内容在早期文档中出现过，但代码里没有：

Redis、消息总线、WebSocket 推送、K8s / Istio、WAF、CSRF Token、
认证/鉴权中间件、日志追踪中间件、RAG（向量库 / embedding / 检索）、
ReAct 推理循环、多 Agent 协作、TF-IDF / NER、
新闻情感分析（2.0.2 起 `/news` 响应字段与 `/news/sentiment/summary` 端点已移除，
`gold_news.sentiment` 列留存历史数据，过滤参数继续可用、大小写不敏感）。

`app/agents/` 包（`BaseAgent` / `MarketAnalyzerAgent` / `NewsAnalyzerAgent`）
从未被任何地方实例化，已删除。


---

## 十四、全自动运行（2.0.2）

硬目标：**配置 `backend/.env` 是唯一的人工输入**。填好之后，建库建表、迁移、历史回填、
抓取、分析、备份与体检都由系统自己完成；人工脚本（`init_db.py` / `migrate_*.py` /
`backfill_quant.py` / 体检 / 备份）全部降级为**可选的运维入口**（见 README「全自动运行」）。

### 启动引导（`app/bootstrap.py`，挂在 FastAPI lifespan）

1. 迁移注册表（`schema_migrations`）应用建表 / 加列类迁移；SQLite 在会改动既有表的
   迁移前把库文件备份到 `backend/backups/`，备份失败即中止该条迁移（`run_migrations`）。
   MySQL 只做加列 / 建表 / 改列型，不删除数据。
2. 数据阶段按 `STEPS` 固定顺序执行：覆盖度检测 → 本地研究长库对齐
   （`services/store_alignment.py`：长库→服务库 insert-only，服务库→长库覆盖，
   对齐前冲突数如实上报）→ 金价 / 美元指数历史 → RSS 新闻与高权威消息 →
   量化因子历史（`QUANT_BACKFILL_YEARS`，可断点续跑）→ 因子修订流水 →
   回填后再次对齐长库（`align_stores_final`：把本轮回填的新行同步回长库，一次启动即收敛）→
   五个首轮 AI 分析。
3. 每个阶段只有两种状态：真跑了，或给出**为什么跳过**的明确理由；单阶段失败记录在
   `/health` 的 `bootstrap.phases[].note`，不阻塞后续阶段，下一轮启动重试。整条链路
   幂等：重复启动不会重复回填、不会重复计费。
4. `/health` 的 `bootstrap` 暴露 `status` / `step.index` / `step.total` / `gaps`，
   前端初始化期间显示「初始化中（第 N 步 / 共 M 步）」而不是「不可用」。

### 配置热更新（`app/config_watch.py`）

- 每 10 秒比对 `.env` 键值快照；`LLM_*` 出现 / 变化 / 删除即：
  `config.reload_settings` 只应用变化键（被删除的字符串 / 密钥键置空，防止
  `os.environ` 里的旧值复活）→ `llm_provider.reset_clients` 丢弃共享 httpx 客户端 →
  `llm_gate.reset_fingerprints` 清空输入指纹（旧模型的缓存结果不是新模型的答案；
  当日调用计数保留）→ 后台线程立刻触发一轮 `force=True` 分析。
- 非 `LLM_*` 变化（如 `DATABASE_URL`）不热应用，`config_watch.note` 明确提示需重启生效。
- `CONFIG_WATCH=false`，或 `SCHEDULER_ENABLED=false`（测试 / 外部调度模式）时不启动
  监听线程，`/health` 如实显示 `disabled` 与原因。

### 调度自愈与每日运维（`app/scheduler.py`、`app/services/maintenance.py`）

- 所有任务带 `coalesce=True`、`misfire_grace_time=3600`、`max_instances=1`：错过窗口
  只补跑一次，绝不并发两份。
- 启动约 20 秒后执行一轮「补差」（行情 / 美元 / 新闻 / 消息），不等 cron。
- 每日 04:00（`SCHEDULER_TIMEZONE`）：SQLite 备份（保留最近 7 份）→ `check_data_sanity`。
  **先备份、后修复**：备份没有真正完成（`AUTO_BACKUP=false`、内存库、MySQL 不代跑
  mysqldump）时体检只读运行；「自动修复」仅限未来日期清理这一类安全项。

### 部署路径

- 裸机：`uvicorn app.main:app`（README 快速开始）。
- Docker：`backend/docker-entrypoint.sh` 只做「等库就绪 → 起 uvicorn」。
- MySQL：自动迁移同样生效；自动备份如实标注为不支持（未代跑 mysqldump）。
