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
├── app/                   前端（浅色研究简报；视觉与文案规则见 docs/20-前端设计规范.md）
│   ├── src/sections/      六节：行情 / 多空对照 / 机构观点 / 投资策略 / 量化预测 / 总结
│   ├── src/layout/        报头（字标、锚点导航、数据来源）与页脚
│   ├── src/components/    节内原语（Section / StateBlock / 表格 / 报价……）
│   ├── src/styles/        设计令牌与基础排版
│   ├── src/services/api.ts  唯一的 HTTP 出口
│   ├── src/contexts/      行情数据的 Provider 与轮询
│   ├── src/components/ui/  仅保留 tabs.tsx
│   └── e2e/               Playwright 端到端测试
└── backend/
    ├── app/
    │   ├── main.py        应用入口、限流、CORS
    │   ├── config.py      全部配置项（pydantic-settings）
    │   ├── database.py    引擎与会话（MySQL / SQLite 双支持）
    │   ├── models/        6 张表的 ORM 定义
    │   ├── routers/       4 个路由模块
    │   ├── services/      业务逻辑（见下）
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
| `market_factors` | 多空因子（`type` 区分） |
| `institution_views` | 机构观点 |
| `predictions` | 量化引擎（`services/quant/service.py`）每次刷新写入：方向、周期、基准价、目标价、得分、期望收益、不确定度与模型版本 |
| `factor_observations` | 量化因子观测，`(factor_key, obs_date)` 唯一；只存成功观测，失败在同步报告里说明 |
| `model_evaluations` | 走查式回测结果（命中率 / 基准对照 / Brier / 逐因子指标），每次评估追加一行 |

> `update_logs` 已删除：没有任何写入方、读取方或接口，产品方向里也没把它列为目标，
> 属于纯死表。同理，`schema.sql` 与模型的一致性由
> `tests/unit/test_schema_matches_models.py` 守住 —— 这两份 schema 曾经对枚举列的
> 取值约定不一致，而 MySQL 的 ENUM 比较不区分大小写，导致「写得进去、读不出来」。

引擎同时支持 MySQL 与 SQLite：SQLite 需要 `check_same_thread=False`，
内存库还需 `StaticPool`，否则每个连接看到的是各自独立的空库。

> 测试默认跑内存 SQLite，但生产用 MySQL。两者在枚举存储、JSON 列与字符串比较
> 大小写上都有差异，所以 `conftest.py` 留了 `GOLDMIND_TEST_DATABASE_URL` 开关，
> 可以拿同一套用例去跑 MySQL（指向独立的测试库，用例会清空所有表）。

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
| 更新 AI 分析 | 偶数整点 | 依次跑 4 个分析服务 |
| 同步量化因子 | `15 */2 * * *` | 各源按自身节奏跳过未到期的抓取（`QUANT_ENABLED=false` 可整体关闭） |
| 重算量化预测 | `45 */2 * * *` | 重算 1 / 5 / 20 / 60 / 250 个交易日预测；回测按 24 小时节流 |

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

## 十一、量化预测引擎

`app/services/quant/`：把「影响国际金价的四类因素」（货币政策与利率 / 避险与信用 /
供需结构 / 市场与技术面）变成可回测的信号。因子清单、权重、方向先验与新鲜度上限
只在 `app/services/quant/definitions.py` 定义一处，接口按它输出 —— 文档不另抄一份。

| 环节 | 位置 | 要点 |
|---|---|---|
| 数据源 | `sources/*.py` | 全部免费、无需密钥；HTTP 客户端可注入，测试永不真出网 |
| 派生 | `derive.py` | 原始序列 → 因子值，单位与口径只在这一层固定 |
| 落库 | `storage.py` | `factor_observations`，唯一约束 `(factor_key, obs_date)`，幂等 |
| 同步 | `sync.py` | 按源节流（6h ~ 24h）、增量抓取、逐源降级并写入同步报告 |
| 信号 | `engine.py` | 滚动 z → 方向对齐 → 按尺度取权重（`definitions.horizon_weights`）合成 → 上行概率与期望收益 |
| 公允价 | `decompose.py` | 走查式扩展窗口 OLS（`log 金价 ~ 实际利率 + log 美元指数 + log 央行储备 + VIX`）把金价拆成 宏观锚＋需求溢价＋风险溢价＋情绪残差；偏离度 = 市场价 / 公允价 − 1 |
| 情景 | `scenarios.py` | 预测分布 N(μ, σ²) 的分位数 → Base [q25, q75]（50%）/ Bull 上 25% / Bear 下 25%；触发与失效条件由该尺度最重因子＋200 日均线生成 |
| 回测 | `backtest.py` | 走查式命中率 + 三个基准 + 80% 区间覆盖率 + 2022-01-01 前后分段 + 逐因子命中率与 IC |
| 出口 | `service.py` | 调度任务与 `POST /api/gold/quant/refresh` 共用同一条链路 |

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
分段成绩；某段样本不足时只给样本数与原因，不凑数字。
守卫：`backend/tests/unit/quant/test_backtest_metrics.py`。

---

## 十二、明确不存在的能力

以下内容在早期文档中出现过，但代码里没有：

Redis、消息总线、WebSocket 推送、K8s / Istio、WAF、CSRF Token、
认证/鉴权中间件、日志追踪中间件、RAG（向量库 / embedding / 检索）、
ReAct 推理循环、多 Agent 协作、TF-IDF / NER、
新闻情感分析（`sentiment` 字段恒为 `NEUTRAL`，只为接口形状稳定）。

`app/agents/` 包（`BaseAgent` / `MarketAnalyzerAgent` / `NewsAnalyzerAgent`）
从未被任何地方实例化，已删除。
