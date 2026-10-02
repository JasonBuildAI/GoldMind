# 更新日志

本文件记录每个版本改了什么，**一行一条**。版本号与 git tag 一一对应：
`vX.Y.Z` 对应下面的 `## [X.Y.Z] - YYYY-MM-DD`。

版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)，格式参考
[Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

> 🌐 [中文](./CHANGELOG.md) | [English](./CHANGELOG_EN.md)

---

## [Unreleased]

### 新增

- 数据体检入口 `scripts/check_data_sanity.py`：未来日期 / NaN 与 ±inf / 宽松数值域 / 跨库一致性一起报告；首跑点出长库 1 行未来日期（etf_shares 2026-10-05，已备份后清理）与 seasonality 两库 778 行分歧
- 消息板块的 13 个高权威源接入四类 LLM 分析：多空因子 / 机构观点 / 投资策略 / 市场总结共用一份「分析输入包」，新闻从「仅标题」升级为「标题 + 摘要（截断、去 HTML）」，来源、时间与链接一并进 prompt
- LLM 输出的确定性结构校验（`services/factor_validation.py`）：id 与标题去重、空项过滤、最多 5 条、正文数字 best-effort 引用核对；不合格时降级为空结构而不是原样透传
- 预测落库改为**追加式每日快照**：`(模型版本, 尺度, 截止日)` 一行，同天重算就地更新、跨天保留，可回看「当时说过什么」
- 回测新增 **CRPS**（分布级连续评分）及对「零漂移」基准的技能分，与 Brier 技能分并排展示在接口与研究页
- 研究页显著标注数据窗口（起止、交易日数、年数）：所有数字由当前库这个窗口现算，与 README / 历史报告引用的快照样本数不一致时以研究页为准
- 备份入口 `scripts/backup_db.py`：SQLite 用 backup API 全量复制并逐表校验行数；MySQL 只打印 `mysqldump` 指引，不代跑
- 研究台新增 M 族候选：多因子 walk-forward Ridge 直接建模（只吃已实现样本对，标准化在同一窗口内估计），与「先合成再一元回归」对照；候选定义仍只在 `scripts/quant_lab.py` 一处，**不进线上 service**
- LLM 端点合规守卫：`tp-` key + token-plan 端点组合在构造时警告一次（不含密钥内容）并给出切换指引，`/health` 透传 `token_plan_backend` 字段

### 变更

- 四个 LLM 分析服务改为消费同一份「分析输入包」：同窗口、同价格上下文、同技能声明，消除各服务各拉数据的口径漂移
- 量化页把未校准的「因子偏向」与同步报告的「未到期」噪音从主表折进详情：偏向收进折叠说明，逐源状态收进折叠的「数据源状态」区，主版面只留结论与可行动信息
- 看板轮询从 10 秒放宽到 30 秒，标签页隐藏时暂停、恢复可见立即补一次（空闲请求量约 30 次/分 → 约 8 次/分）

### 修复

- 投资建议的统计窗口随日历滚动（去掉写死的 `datetime(2025,1,1)`）；「波动区间」正名为「高低振幅」并写明定义，prompt 同步
- `etf_shares` 拒绝写入晚于今天的观测日（存储层守卫 + 源层修复），页面上不再出现未来日期
- 机构观点的 news_scan 总结改为由结构化行**确定性拼装**，LLM 总结不再与结构化数据互相矛盾
- 市场总结在机构数据缺失时不再输出机构判断（确定性清洗 + prompt 加固）
- 投资建议在无因子 / 无机构 / 无新闻时不调 LLM：只给行情统计与「数据不足」说明，前端如实标注 `insufficient_data`
- 测试库护栏：`GOLDMIND_TEST_DATABASE_URL` 指向的库名必须含 `test`，否则测试在导入期拒跑（2026-10-02 事故：误连开发库，`drop_all` 删光 9 张业务表）
- 缺库/缺表时接口返回 **503 + `python init_db.py` 修复指引**（原先裸 500），启动时做 schema 自检并在缺表时打 ERROR；其余 SQL 错误仍是 500
- 外部行情源（Yahoo 限流/不可用）时，量化引擎改用本地已同步的 `gold_prices` / `dollar_index` 兜底基准价与美元因子，来源如实标注；不再整片「缺少黄金价格序列」
- 前端对 **429 / 5xx / 网络错误**做指数退避重试（429 尊重 `Retry-After`，最多 3 次尝试）；同一 URL 的在飞 GET 合并为一个请求；`POST` 与 `?refresh=true` 永不重试

---

## [2.0.1] - 2026-10-02

### 新增

- 因子闸门与筛选工具 `backend/scripts/screen_factors.py`：去均值协方差 + Newey–West HAC + Bonferroni + |t| ≥ 3、跨尺度同号、前向窗口确认；26 年面板 255 格无一过线，17 个候选在修好引擎后彼此不可区分 —— 这条阴性结果是本轮把预算指向新信息源的依据
- 监测仪表盘扩到 **21 行**：新增 GVZ / 金银比 / 铜金比 / CFTC 净多头占未平仓比 / GPR 五条信息行，一律不给多空方向；库里 0 行时显示「不可用 + 原因」而不是从表上消失
- 因子观测改为「当前值 + 追加式修订流水」双表，支持 `--as-of` 按时点重建面板；老库升级自动回填 10 年流水
- 评测新口径：按 stride=h 抽取的独立下注数（250 日留出期 506 个重叠样本实际只有 2 次下注）、逐因子 HAC t 与 iid 对照、按已实现波动率分档的覆盖率审计、「反向显著」只登记不采纳的出口
- 第三道前向窗口闸门落地为代码：窗口起点写死 2026-10-02，判不了时报 pending 并列出还差多少个交易日
- 通用 LLM 接入：任何 OpenAI 兼容端点都行，配置面是 `LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL`（三项齐备才算已配置），`LLM_PROVIDER` 仅作界面展示标签
- 新增 `LLM_MAX_TOKENS`（默认 `8192`）、`LLM_SEARCH_ENABLED`（默认 `false`）、`LLM_SEARCH_MODEL` / `LLM_SEARCH_BASE_URL` / `LLM_SEARCH_API_KEY` 与 `LLM_SEARCH_MAX_KEYWORD`
- 量化研究台与预注册：候选清单、选择规则与通过线的唯一实现 `backend/app/services/quant/preregistered.py`，全档评估工具 `backend/scripts/quant_lab.py`，接口 `GET /api/gold/quant/research`，独立「研究」页 `app/research.html`
- 量化统计工具箱 `backend/app/services/quant/stats.py`：Newey–West HAC 标准误、圆周分块自助区间、HAC t / Diebold–Mariano、Brier 技能分与可靠性分桶（重叠样本不再按独立样本处理）
- 20 年因子历史回填（新增 36,150 行 / 修订 26,445 行，见 `docs/specs/2026-10-02-回填报告.md`），为留出期评估补齐数据

### 变更

- 模型版本 `quant-v5`：方向、上行概率、80% 区间与三情景统一到同一张校准分布 F̂（区间宽度取 F̂ 的经验分位，不再被 uncertainty 二次放大）；方向判定退回校准后 μ 的符号（实测优于分布中位数）
- 四层公允价分解不再外推：目标价超出 6 个 σ 或 12 个 log 溢价时单列 `unsupported_by` 并拒绝给数
- 陈旧因子在合成阶段即变 NaN，不再向前填充成假水位；样本不足的尺度如实标「不可判定」而非「未通过」，每条落库预测自带该尺度实测技能状态
- 监测仪表盘逐行判新鲜度：超龄行只给数值与观测日，不再给多空标签
- 预注册候选 C2（每注校准 + 窗口）以 60 日 0.7679 未跨 0.78 通过线被淘汰，阈值不动；控制候选 C0 与 B0 逐值相同
- **默认数据库改为 SQLite 单文件**（`backend/goldmind.db`，零安装、零配置）：`init_db.py` 在 SQLite 下用模型 `create_all` 建表，`seed_data.py` 去掉 pymysql 直连；MySQL 降级为可选路径（未随本轮闸门实测）
- 量化评估改为**预注册**口径：候选清单与通过线先写死，再看留出期（2023-10-02 起）；修好引擎口径后重裁，17 个候选 × 5 个尺度彼此不可区分，26 年面板 255 格无一过闸门，研究页如实标注「无统计优势」

### 变更（破坏性）

- **LLM 配置改名：`MIMO_*` → `LLM_*`，不留兼容回退。** 升级时必须把 `backend/.env` 与部署环境里的 `MIMO_API_KEY` / `MIMO_BASE_URL` / `MIMO_MODEL` / `MIMO_SEARCH_MODEL` / `MIMO_SEARCH_MAX_KEYWORD` / `MIMO_TRUST_ENV` 换成 `LLM_*` 对应项

### 修复

- **ACI 区间覆盖错位**：α 更新曾拿「当前行的区间」判「h 天前发出的那一注」，修后开发期 20 日覆盖率 76.7%→79.3%、60 日 72.6%→73.6%
- 拒收任何观测日期晚于「今天」的记录；前端监测表不再把 <0.01 的比值四舍五入成 0.00
- **投资策略长期显示「暂不可用」**：5 个分析服务硬编码 `max_tokens=4096`，三档策略的完整 JSON 被截断；改为取 `LLM_MAX_TOKENS`（默认 8192），解析失败时日志记录 `finish_reason` 与 token 用量
- 端点返回 `finish_reason=content_filter` 时自动重试一次；新闻提示词默认上限收到 10 条
- 冒烟脚本更名 `backend/scripts/smoke_llm.py`（原 `smoke_mimo.py`），联网搜索只在 `LLM_SEARCH_ENABLED=true` 时探测

### 文档

- `README.md` / `README_EN.md` 全量重写：十节量化策略（含 21 行监测表、预注册裁决与已知限制）、逐项实测的快速开始与命令、14 张 2026-10-02 从真实栈截取的截图（脚本拒绝写空图）
- 新增漂移守卫：架构文档声明、README 监测表 vs `monitor.ROW_SPECS`、README 命令 vs 各脚本真实 `--help`（均做过变异验证）
- README 修复复现缺口：Node 下限改为 ≥22.22.2（或 24.15+/26+）、补 Google Chrome 前置、删除并不存在的 `.\start_all.ps1`、补冷启动预期
- 报头 / 走势 / 多空 / 机构 / 策略 / 总结截图全部重截；机构观点如实保留「暂无最新预测」空态，文档写明精确报错文案
- README 中英双版同步到 SQLite 零配置快速开始；量化第六节换成留出期实测覆盖率与方向命中率，新增「研究台与预注册」一节，已知限制改为留出期口径
- `docs/ARCHITECTURE.md`（含英文镜像）改为默认 SQLite 的部署与配置口径，第十一节补统计、预注册与研究台；`docs/00-产品方向.md`（含英文镜像）的存储口径改为 SQLite 默认

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

[2.0.1]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.1
[2.0.0]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v2.0.0
[1.0.0]: https://github.com/JasonBuildAI/GoldMind/releases/tag/v1.0.0
