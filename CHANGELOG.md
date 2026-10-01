# 更新日志

本文件记录每个版本改了什么，**一行一条**。版本号与 git tag 一一对应：
`vX.Y.Z` 对应下面的 `## [X.Y.Z] - YYYY-MM-DD`。

版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)，格式参考
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

> 🌐 [中文](./CHANGELOG.md) | [English](./CHANGELOG_EN.md)

---

## [Unreleased]

### 新增

- 通用 LLM 接入：任何 OpenAI 兼容端点都行，配置面是 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`（三项齐备才算已配置），`LLM_PROVIDER` 仅作界面展示标签
- 新增 `LLM_MAX_TOKENS`（默认 `8192`）、`LLM_SEARCH_ENABLED`（默认 `false`）、`LLM_SEARCH_MODEL` / `LLM_SEARCH_BASE_URL` / `LLM_SEARCH_API_KEY` 与 `LLM_SEARCH_MAX_KEYWORD`

### 变更（破坏性）

- **LLM 配置改名：`MIMO_*` → `LLM_*`，不留兼容回退。** 升级时必须把 `backend/.env` 与部署环境里的 `MIMO_API_KEY` / `MIMO_BASE_URL` / `MIMO_MODEL` / `MIMO_SEARCH_MODEL` / `MIMO_SEARCH_MAX_KEYWORD` / `MIMO_TRUST_ENV` 换成 `LLM_*` 对应项

### 修复

- **投资策略长期显示「暂不可用」**：5 个分析服务硬编码 `max_tokens=4096`，三档策略的完整 JSON 被截断；改为取 `LLM_MAX_TOKENS`（默认 8192），解析失败时日志记录 `finish_reason` 与 token 用量
- 端点返回 `finish_reason=content_filter` 时自动重试一次；新闻提示词默认上限收到 10 条
- 冒烟脚本更名 `backend/scripts/smoke_llm.py`（原 `smoke_mimo.py`），联网搜索只在 `LLM_SEARCH_ENABLED=true` 时探测

### 文档

- README 修复复现缺口：Node 下限改为 ≥22.22.2（或 24.15+/26+）、补 Google Chrome 前置、删除并不存在的 `.\start_all.ps1`、补冷启动预期
- 报头 / 走势 / 多空 / 机构 / 策略 / 总结截图全部重截；机构观点如实保留「暂无最新预测」空态，文档写明精确报错文案

## [2.0.0] - 2026-10-01

2.0 的主线是**可核实**：预测收敛到一份可回测的分布，机构观点不再因为「当天没有新研报」
就抹掉真实数据，文档中英双版且接口文档由代码生成。

### 新增

- 量化预测引擎：14 个因子覆盖四类影响因素（货币政策与利率 / 避险与信用 / 供需结构 / 市场与技术面），数据源全部免费且免密钥
- 因子按源节流增量同步（6h～24h）并落库，`factor_observations` 对 `(factor_key, obs_date)` 建唯一约束，重复抓取幂等
- 五个预测尺度各有独立权重：短尺度由资金流与技术面主导，中尺度由政策预期与美元主导，长尺度由央行购金与需求结构主导
- 单一校准分布（模型版本 `quant-v4`）：方向 = sign(μ)、上行概率 = Φ(μ/σ)、目标价 = 基准价×(1+μ)、80% 区间 = μ±1.2816σ、三情景 = N(μ, σ²) 的分位数
- 区间宽度按走查预测误差的**经验分位**校准（正态分位在长尺度系统性偏窄）；已实现误差不足 60 组时退回扩展标准差
- 公允价四层分解：宏观锚 ＋ 需求溢价 ＋ 风险溢价 ＋ 情绪残差，偏离度 = 市场价 / 公允价 − 1
- 三情景各自带**触发条件**与**失效条件**（由该尺度最重因子与 200 日均线生成，可逐条核对）
- 走查式回测：命中率与「永远看多 / 动量 / 抛硬币」三个基准并排，另报 80% 名义区间的实际覆盖率、2022-01-01 前后分段、逐因子命中率与 IC
- 监测仪表盘：16 行水位表，每行给频率、来源、当前值、信号（看涨 / 看跌 / 中性 / 信息）与数据截至日
- 前端新增量化预测区块：五尺度 tab、公允价值分解、监测仪表盘、回测命中率、四类因子表
- 新增接口 `GET /api/gold/quant/factors|predictions|accuracy|monitor` 与 `POST /api/gold/quant/refresh`
- 新增迁移脚本 `backend/scripts/migrate_quant.py`（幂等，只加不删，带回滚）
- 新增迁移脚本 `backend/scripts/migrate_institution_views.py`（默认 dry-run，`--apply` 执行，`--drop-columns` 回滚，**不删除任何行**）

### 变更

- 机构观点改为「每家机构**最近一次可核实**的预测」：扫描窗口 `INSTITUTION_NEWS_LOOKBACK_DAYS`（默认 30 天），不再要求新闻在过去 24 小时内发布
- 机构观点表新增「预测日期」与「来源」两列，预测日期超过 30 天标注「已滞后 N 天」
- 机构名称规范化到四家规范行（高盛 / 瑞银 / 摩根士丹利 / 花旗），写入、读取、提示词与测试全部由同一份机构注册表派生
- 机构观点读取不再设「2 小时内才读库」门槛，直接按规范行组装；窗口内没有新预测时由服务端给出确定性说明
- 前端表现层重构为浅色研究简报：设计令牌化、数字表格化、红涨绿跌且方向同时给符号与文字，六节一律左对齐、无渐变无阴影
- 文档全面双版：README、用户文档、API 文档都有英文镜像；`docs/API.md` 与 `docs/en/api.md` 改由 `backend/scripts/gen_api_doc.py` 从路由表生成

### 修复

- **不再用空目标价覆盖已有真实预测** —— 2026-10-01 06:01 被「暂无」覆盖掉的四条机构目标价（5400 / 5000 / 6300 / 6000）已从旧别名行恢复到规范行
- 四条 `target_price` 全为 null 的占位缓存不再遮蔽数据库里的真实数据（旧判据只检查「列表非空」）
- 分析服务不再返回编造的兜底因子 / 策略：数据源或联网搜索不可用时如实返回「不可用 + 原因」
- 前端删除了各区块内置的写死兜底数据，并由测试钉住「失败时不得出现内置文案」
- 设置对象自身也做密钥掩码，避免密钥经日志或错误信息外泄

### 文档

- 重写 `README.md` 并新增 `README_EN.md`，含 2.0 发布横幅与专章《量化策略》
- 新增 `docs/en/`：`product-direction.md`、`secrets-and-privacy.md`、`frontend-design.md`、`architecture.md`、`api.md`
- 新增 `CONTRIBUTING_EN.md` 与本文件、`CHANGELOG_EN.md`

---

## [1.0.0] - 2026-02-03

首个公开版本。

### 新增

- 金价与美元指数采集（腾讯财经实时金价、新浪财经 ICE 美元指数），历史数据回填支持新浪 / 东方财富 / Yahoo 三源
- MySQL 8 持久化（`gold_prices` / `dollar_index` / `news` / `institution_views` / `predictions`）
- 四个 LLM 分析服务：看涨因子、看跌因子、机构观点、投资建议，外加市场总结
- React 单页看板：行情 / 多空对照 / 机构观点 / 投资策略 / 总结
- 内存 + JSON 文件两级缓存，支持多进程与重启后共享
- APScheduler 定时刷新，Docker Compose 一键部署

[2.0.0]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.0
[1.0.0]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v1.0.0
