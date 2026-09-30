# GoldMind API

> 🤖 **本文件由 `backend/scripts/gen_api_doc.py` 从 FastAPI 路由表生成，请勿手工编辑。**
> 改接口后运行 `cd backend && python scripts/gen_api_doc.py` 重新生成；
> `backend/tests/integration/test_api_doc.py` 会校验两者一致。

运行中的服务还提供交互式文档：`http://localhost:8000/docs`（Swagger UI）
与 `http://localhost:8000/openapi.json`（OpenAPI 规范）。

---

## 通用约定

- **前缀**：所有业务接口都在 `/api/gold` 下（不是 `/api/analysis` 或 `/api/news`）
- **鉴权**：无。若要公开部署，请在反向代理层加访问控制
- **限流**：按客户端 IP 的滑动窗口。普通接口默认 60 次/分钟；
  路径以 `/refresh` 结尾的接口按「重操作」限流，默认仅 6 次/分钟
  （AI 分析刷新会真实调用 LLM，量化刷新会出网抓取全部数据源）。
  `/health` 不限流。超限返回 `429`，响应体含 `retry_after`（秒）
- **CORS**：仅允许 `CORS_ALLOW_ORIGINS` 中列出的来源
- **错误格式**：FastAPI 默认的 `{"detail": ...}`；限流为 `{"error", "retry_after"}`

---

## 接口一览

### gold

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/gold/bearish-factors-ai` | 获取AI分析的看空因子 - 优化版（快速响应） |
| `POST` | `/api/gold/bearish-factors-ai/refresh` | 手动刷新看空因子分析（**会调用 LLM**，限流更严） |
| `GET` | `/api/gold/bullish-factors-ai` | 获取AI分析的看涨因子 - 优化版（快速响应） |
| `POST` | `/api/gold/bullish-factors-ai/refresh` | 手动刷新看涨因子分析（**会调用 LLM**，限流更严） |
| `GET` | `/api/gold/dollar-realtime` | 获取实时美元指数（数据源：新浪财经 ICE 美元指数 DINIW；带 30 秒缓存）。 |
| `GET` | `/api/gold/factors` | 获取已入库的市场因子，可按类型过滤。 |
| `GET` | `/api/gold/factors/bearish` | 获取看跌因子（直接读数据库，不做 AI 分析）。 |
| `GET` | `/api/gold/factors/bullish` | 获取看涨因子（直接读数据库，不做 AI 分析）。 |
| `GET` | `/api/gold/institution-predictions-ai` | 获取AI分析的机构预测 |
| `POST` | `/api/gold/institution-predictions-ai/refresh` | 手动刷新机构预测分析（**会调用 LLM**，限流更严） |
| `GET` | `/api/gold/institutions` | 获取已入库的机构观点。 |
| `GET` | `/api/gold/investment-advice-ai` | 获取AI生成的投资建议 |
| `POST` | `/api/gold/investment-advice-ai/refresh` | 手动刷新投资建议分析（**会调用 LLM**，限流更严） |
| `GET` | `/api/gold/latest` | 获取数据库里最新一条金价。 |
| `GET` | `/api/gold/market-summary-ai` | 获取AI生成的黄金市场综合分析 |
| `POST` | `/api/gold/market-summary-ai/refresh` | 手动刷新黄金市场综合分析（**会调用 LLM**，限流更严） |
| `GET` | `/api/gold/news` | 获取新闻列表，可按来源与情感过滤（无分页，只取前 limit 条）。 |
| `GET` | `/api/gold/news/sentiment/summary` | 新闻情感分布统计。注：入库时 sentiment 一律为 NEUTRAL，本项目没有做情感分析，这里恒为全中性，保留字段只为接口形状稳定。 |
| `GET` | `/api/gold/news/{news_id}` | 获取单条新闻详情。 |
| `GET` | `/api/gold/predictions` | 价格预测列表。表里现在有真实数据：量化引擎（services/quant）每次刷新写入。 |
| `GET` | `/api/gold/predictions/latest` | 最新一条已落库的价格预测。 |
| `GET` | `/api/gold/prices/correlation` | 获取黄金与美元指数相关性数据 |
| `GET` | `/api/gold/prices/daily` | 获取日线价格数据 |
| `GET` | `/api/gold/quant/accuracy` | 走查式回测的命中率：与「永远看多 / 动量 / 抛硬币」并排对照。 |
| `GET` | `/api/gold/quant/factors` | 四类影响因素的当前快照：值、方向、贡献、来源与数据截至时间。 |
| `GET` | `/api/gold/quant/predictions` | 量化预测：方向、上行概率、目标价与逐因子贡献。 |
| `POST` | `/api/gold/quant/refresh` | 立即抓取因子、重算预测并追加一次回测（耗时数十秒，已按付费档限流）。（**重操作**，限流更严） |
| `GET` | `/api/gold/stats` | 获取 2025 年至今的金价统计（当前价、涨跌幅、波动区间等）。 |

### 其他

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/` | 服务信息与文档入口。 |
| `GET` | `/health` | 增强健康检查 - 检查所有关键依赖服务 |

---

## 响应字段以代码为准

各接口的响应模型定义在 `backend/app/schemas/`，字段名请以那里为准。
举例：`GET /api/gold/stats` 返回的是 `ytd_return` 与 `volatility`，
而不是早期文档里写的 `ytd_change` 与 `volatility_range`。

前端对应的类型定义在 `app/src/services/api.ts`，两侧必须保持一致。
